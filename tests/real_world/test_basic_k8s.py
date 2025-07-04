#!/usr/bin/env python3
"""Basic Kubernetes connectivity tests for real environments"""

import pytest
import time
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pod.connections.kubernetes import KubernetesConnection
from pod.os_abstraction.kubernetes import KubernetesHandler
from pod.os_abstraction.base import NetworkConfig
from pod.exceptions import ConnectionError, AuthenticationError


class TestBasicKubernetes:
    """Test basic Kubernetes operations in real cluster"""
    
    @classmethod
    def setup_class(cls):
        """Setup test class - verify cluster connectivity"""
        cls.test_namespace = "pod-test"
        cls.cleanup_pods = []
        
        # Try to connect
        try:
            conn = KubernetesConnection()
            conn.connect()
            conn.disconnect()
        except Exception as e:
            pytest.skip(f"Cannot connect to Kubernetes cluster: {e}")
    
    @classmethod
    def teardown_class(cls):
        """Cleanup test resources"""
        try:
            conn = KubernetesConnection(namespace=cls.test_namespace)
            conn.connect()
            handler = KubernetesHandler(conn)
            
            # Delete test pods
            for pod_name in cls.cleanup_pods:
                try:
                    handler.delete_pod(pod_name)
                except:
                    pass
            
            # Delete test namespace
            try:
                conn.v1.delete_namespace(name=cls.test_namespace)
            except:
                pass
            
            conn.disconnect()
        except:
            pass
    
    def test_cluster_connection(self):
        """Test connection to Kubernetes cluster"""
        conn = KubernetesConnection()
        conn.connect()
        
        # Verify connection
        assert conn.is_connected()
        
        # Check cluster info
        info = conn.get_cluster_info()
        assert 'version' in info
        assert 'nodes' in info
        assert len(info['nodes']) > 0
        
        print(f"✓ Connected to Kubernetes {info['version']}")
        print(f"  Nodes: {', '.join(info['nodes'])}")
        
        conn.disconnect()
    
    def test_namespace_operations(self):
        """Test namespace creation and listing"""
        conn = KubernetesConnection()
        conn.connect()
        
        # Create test namespace
        namespace_manifest = {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": self.test_namespace,
                "labels": {
                    "test": "pod-library"
                }
            }
        }
        
        try:
            conn.v1.create_namespace(body=namespace_manifest)
            print(f"✓ Created namespace: {self.test_namespace}")
        except Exception as e:
            if "already exists" not in str(e):
                raise
        
        # List namespaces
        namespaces = conn.list_namespaces()
        assert self.test_namespace in namespaces
        assert 'default' in namespaces
        assert 'kube-system' in namespaces
        
        print(f"✓ Found {len(namespaces)} namespaces")
        
        conn.disconnect()
    
    def test_pod_lifecycle(self):
        """Test pod creation, listing, and deletion"""
        conn = KubernetesConnection(namespace=self.test_namespace)
        conn.connect()
        handler = KubernetesHandler(conn)
        
        pod_name = "test-nginx-pod"
        self.cleanup_pods.append(pod_name)
        
        # Create a simple pod
        config = NetworkConfig(
            interface="eth0",
            ip_address="",  # Let Kubernetes assign IP
            netmask="255.255.255.0"
        )
        
        print(f"\nCreating pod: {pod_name}")
        result = handler.create_pod_with_vlan(
            pod_name=pod_name,
            image="nginx:alpine",
            vlan_id=0,  # No VLAN for basic test
            network_config=config
        )
        
        assert result.success, f"Pod creation failed: {result.stderr}"
        print(f"✓ Pod created successfully")
        
        # Wait for pod to be ready
        print("  Waiting for pod to be ready...")
        max_wait = 60
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            pods = conn.list_pods(namespace=self.test_namespace)
            pod = next((p for p in pods if p['name'] == pod_name), None)
            
            if pod and pod['status'] == 'Running':
                print(f"✓ Pod is running (IP: {pod.get('ip', 'N/A')})")
                break
            
            time.sleep(2)
        else:
            pytest.fail(f"Pod did not become ready within {max_wait} seconds")
        
        # Execute command in pod
        print("\nTesting command execution...")
        stdout, stderr, exit_code = conn.execute_command(
            "nginx -v",
            pod_name=pod_name,
            namespace=self.test_namespace
        )
        
        assert exit_code == 0 or "nginx version" in stderr
        print(f"✓ Command executed: {stderr.strip()}")
        
        # Delete pod
        print("\nDeleting pod...")
        delete_result = handler.delete_pod(pod_name)
        assert delete_result.success
        print(f"✓ Pod deleted successfully")
        
        conn.disconnect()
    
    def test_cni_detection(self):
        """Test CNI plugin detection"""
        conn = KubernetesConnection()
        conn.connect()
        handler = KubernetesHandler(conn)
        
        # Get OS info with CNI details
        os_info = handler.get_os_info()
        
        print("\nCNI Plugin Detection:")
        print(f"  Detected plugins: {', '.join(os_info['cni_plugins'])}")
        
        # Check network capabilities
        capabilities = os_info['network_capabilities']
        print("\nNetwork Capabilities:")
        print(f"  Network Policies: {'✓' if capabilities['network_policies'] else '✗'}")
        print(f"  Service Mesh: {'✓' if capabilities['service_mesh'] else '✗'}")
        print(f"  CNI Chaining: {'✓' if capabilities['cni_chaining'] else '✗'}")
        print(f"  SR-IOV: {'✓' if capabilities['sr_iov'] else '✗'}")
        
        if capabilities['ingress_controllers']:
            print(f"  Ingress Controllers: {', '.join(capabilities['ingress_controllers'])}")
        
        # At least one CNI plugin should be detected
        assert len(os_info['cni_plugins']) > 0
        
        conn.disconnect()
    
    def test_multiple_pods(self):
        """Test creating and managing multiple pods"""
        conn = KubernetesConnection(namespace=self.test_namespace)
        conn.connect()
        handler = KubernetesHandler(conn)
        
        pod_count = 3
        created_pods = []
        
        print(f"\nCreating {pod_count} pods...")
        
        for i in range(pod_count):
            pod_name = f"test-multi-pod-{i}"
            self.cleanup_pods.append(pod_name)
            
            config = NetworkConfig(
                interface="eth0",
                ip_address="",
                netmask="255.255.255.0"
            )
            
            result = handler.create_pod_with_vlan(
                pod_name=pod_name,
                image="busybox",
                vlan_id=0,
                network_config=config
            )
            
            if result.success:
                created_pods.append(pod_name)
                print(f"  ✓ Created {pod_name}")
            else:
                print(f"  ✗ Failed to create {pod_name}: {result.stderr}")
        
        # Wait for pods to be ready
        print("\nWaiting for pods to be ready...")
        time.sleep(10)
        
        # List all pods
        pods = conn.list_pods(namespace=self.test_namespace)
        running_pods = [p for p in pods if p['status'] == 'Running']
        
        print(f"\n✓ {len(running_pods)} pods running in namespace {self.test_namespace}")
        
        # Cleanup is handled by teardown_class
        conn.disconnect()
        
        assert len(created_pods) == pod_count, f"Expected {pod_count} pods, created {len(created_pods)}"
    
    def test_pod_with_resources(self):
        """Test pod creation with resource limits"""
        conn = KubernetesConnection(namespace=self.test_namespace)
        conn.connect()
        
        pod_name = "test-resource-pod"
        self.cleanup_pods.append(pod_name)
        
        # Create pod with custom resources
        pod_spec = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": pod_name,
                "namespace": self.test_namespace,
                "labels": {
                    "app": "test-resources"
                }
            },
            "spec": {
                "containers": [{
                    "name": "main",
                    "image": "nginx:alpine",
                    "resources": {
                        "requests": {
                            "memory": "64Mi",
                            "cpu": "100m"
                        },
                        "limits": {
                            "memory": "128Mi",
                            "cpu": "200m"
                        }
                    }
                }]
            }
        }
        
        try:
            conn.v1.create_namespaced_pod(
                namespace=self.test_namespace,
                body=pod_spec
            )
            print(f"✓ Created pod with resource limits")
            
            # Verify pod was created
            pods = conn.list_pods(namespace=self.test_namespace)
            pod = next((p for p in pods if p['name'] == pod_name), None)
            assert pod is not None
            
        except Exception as e:
            pytest.fail(f"Failed to create pod with resources: {e}")
        
        conn.disconnect()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])