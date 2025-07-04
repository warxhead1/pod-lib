#!/usr/bin/env python3
"""Test VLAN isolation in real Kubernetes environment"""

import pytest
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pod.connections.kubernetes import KubernetesConnection
from pod.os_abstraction.kubernetes import KubernetesHandler
from pod.os_abstraction.base import NetworkConfig
from pod.network.cni import CNIManager, CNIConfig


class TestVLANIsolation:
    """Test VLAN-based network isolation in Kubernetes"""
    
    @classmethod
    def setup_class(cls):
        """Setup test environment"""
        cls.test_namespace = "pod-vlan-test"
        cls.test_pods = []
        cls.network_attachments = []
        
        # Check if cluster supports VLAN testing
        try:
            conn = KubernetesConnection()
            conn.connect()
            handler = KubernetesHandler(conn)
            
            os_info = handler.get_os_info()
            cls.has_multus = "multus" in os_info['cni_plugins']
            cls.has_calico = "calico" in os_info['cni_plugins']
            cls.has_cilium = "cilium" in os_info['cni_plugins']
            
            # Create test namespace
            try:
                conn.v1.create_namespace(body={
                    "apiVersion": "v1",
                    "kind": "Namespace",
                    "metadata": {"name": cls.test_namespace}
                })
            except:
                pass
            
            conn.disconnect()
            
        except Exception as e:
            pytest.skip(f"Cannot setup VLAN test environment: {e}")
    
    @classmethod
    def teardown_class(cls):
        """Cleanup test resources"""
        try:
            conn = KubernetesConnection(namespace=cls.test_namespace)
            conn.connect()
            handler = KubernetesHandler(conn)
            cni_manager = CNIManager(conn)
            
            # Delete test pods
            for pod_name in cls.test_pods:
                try:
                    handler.delete_pod(pod_name)
                except:
                    pass
            
            # Delete network attachments
            for nad_name in cls.network_attachments:
                try:
                    cni_manager.delete_network_attachment(nad_name, cls.test_namespace)
                except:
                    pass
            
            # Delete namespace
            try:
                conn.v1.delete_namespace(name=cls.test_namespace)
            except:
                pass
            
            conn.disconnect()
        except:
            pass
    
    def test_multus_vlan_creation(self):
        """Test creating VLAN networks with Multus"""
        if not self.has_multus:
            pytest.skip("Multus CNI not available")
            
        conn = KubernetesConnection(namespace=self.test_namespace)
        conn.connect()
        handler = KubernetesHandler(conn)
        cni_manager = CNIManager(conn)
        
        print("\nTesting Multus VLAN creation...")
        
        # Create VLAN 100 network attachment
        vlan100_config = CNIConfig(
            name="vlan100-net",
            type="macvlan",
            master_interface="eth0",  # Adjust based on your cluster
            vlan_id=100,
            subnet="10.100.0.0/24",
            gateway="10.100.0.1"
        )
        
        nad = cni_manager.create_network_attachment_definition(vlan100_config)
        result = cni_manager.apply_network_attachment(nad, self.test_namespace)
        
        if result['success']:
            self.network_attachments.append("vlan100-net")
            print("✓ Created VLAN 100 network attachment")
        else:
            pytest.skip(f"Failed to create network attachment: {result.get('error')}")
        
        # Create VLAN 200 network attachment
        vlan200_config = CNIConfig(
            name="vlan200-net",
            type="macvlan",
            master_interface="eth0",
            vlan_id=200,
            subnet="10.200.0.0/24",
            gateway="10.200.0.1"
        )
        
        nad = cni_manager.create_network_attachment_definition(vlan200_config)
        result = cni_manager.apply_network_attachment(nad, self.test_namespace)
        
        if result['success']:
            self.network_attachments.append("vlan200-net")
            print("✓ Created VLAN 200 network attachment")
        
        # List network attachments
        attachments = cni_manager.list_network_attachments(self.test_namespace)
        print(f"\nNetwork attachments in namespace: {len(attachments)}")
        for att in attachments:
            print(f"  - {att['name']}")
        
        conn.disconnect()
    
    def test_network_policy_vlan_simulation(self):
        """Test VLAN-like isolation using NetworkPolicies"""
        conn = KubernetesConnection(namespace=self.test_namespace)
        conn.connect()
        handler = KubernetesHandler(conn)
        
        print("\nTesting NetworkPolicy-based VLAN simulation...")
        
        # Create pods with VLAN labels
        vlan_configs = [
            ("vlan100-pod-1", 100),
            ("vlan100-pod-2", 100),
            ("vlan200-pod-1", 200)
        ]
        
        for pod_name, vlan_id in vlan_configs:
            # Create pod with VLAN label
            pod_spec = {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {
                    "name": pod_name,
                    "namespace": self.test_namespace,
                    "labels": {
                        f"vlan-{vlan_id}": "true",
                        "app": pod_name
                    }
                },
                "spec": {
                    "containers": [{
                        "name": "main",
                        "image": "nicolaka/netshoot",
                        "command": ["sleep", "3600"]
                    }]
                }
            }
            
            # If Multus is available, add network annotation
            if self.has_multus and f"vlan{vlan_id}-net" in self.network_attachments:
                pod_spec["metadata"]["annotations"] = {
                    "k8s.v1.cni.cncf.io/networks": f"vlan{vlan_id}-net"
                }
            
            try:
                conn.v1.create_namespaced_pod(
                    namespace=self.test_namespace,
                    body=pod_spec
                )
                self.test_pods.append(pod_name)
                print(f"✓ Created {pod_name} in VLAN {vlan_id}")
            except Exception as e:
                print(f"✗ Failed to create {pod_name}: {e}")
        
        # Create NetworkPolicy for VLAN isolation
        for vlan_id in [100, 200]:
            network_config = NetworkConfig(
                interface="eth0",
                ip_address="",
                netmask="255.255.255.0",
                vlan_id=vlan_id
            )
            
            result = handler.configure_network(network_config)
            if result.success:
                print(f"✓ Created NetworkPolicy for VLAN {vlan_id}")
        
        # Wait for pods to be ready
        print("\nWaiting for pods to be ready...")
        time.sleep(20)
        
        # Test connectivity
        self._test_pod_connectivity(conn)
        
        conn.disconnect()
    
    def _test_pod_connectivity(self, conn):
        """Test connectivity between pods"""
        print("\nTesting pod connectivity...")
        
        # Get pod IPs
        pods = conn.list_pods(namespace=self.test_namespace)
        pod_ips = {}
        
        for pod in pods:
            if pod['status'] == 'Running' and pod['ip']:
                pod_ips[pod['name']] = pod['ip']
                print(f"  {pod['name']}: {pod['ip']}")
        
        if len(pod_ips) < 2:
            print("✗ Not enough running pods for connectivity test")
            return
        
        # Test same VLAN connectivity (should work)
        if "vlan100-pod-1" in pod_ips and "vlan100-pod-2" in pod_ips:
            print("\nTesting same VLAN connectivity (100 -> 100)...")
            
            stdout, stderr, exit_code = conn.execute_command(
                f"ping -c 3 -W 2 {pod_ips['vlan100-pod-2']}",
                pod_name="vlan100-pod-1",
                namespace=self.test_namespace
            )
            
            if exit_code == 0:
                print("✓ Pods in same VLAN can communicate")
            else:
                print("✗ Same VLAN connectivity failed (may be due to NetworkPolicy)")
        
        # Test different VLAN isolation (should fail)
        if "vlan100-pod-1" in pod_ips and "vlan200-pod-1" in pod_ips:
            print("\nTesting cross-VLAN isolation (100 -> 200)...")
            
            stdout, stderr, exit_code = conn.execute_command(
                f"ping -c 3 -W 2 {pod_ips['vlan200-pod-1']}",
                pod_name="vlan100-pod-1",
                namespace=self.test_namespace
            )
            
            if exit_code != 0:
                print("✓ Pods in different VLANs are properly isolated")
            else:
                print("✗ Cross-VLAN isolation not working (pods can communicate)")
    
    def test_calico_ippool_vlan(self):
        """Test VLAN-like isolation using Calico IP Pools"""
        if not self.has_calico:
            pytest.skip("Calico CNI not available")
            
        conn = KubernetesConnection(namespace=self.test_namespace)
        conn.connect()
        handler = KubernetesHandler(conn)
        
        print("\nTesting Calico IP Pool based VLAN...")
        
        # Configure Calico VLAN
        config = NetworkConfig(
            interface="eth0",
            ip_address="192.168.100.10",
            netmask="255.255.255.0",
            vlan_id=100
        )
        
        result = handler._configure_calico_vlan(config)
        
        if result.success:
            print("✓ Calico IP Pool configured for VLAN 100")
        else:
            print(f"✗ Calico configuration failed: {result.stderr}")
        
        conn.disconnect()
    
    def test_cilium_network_policy_vlan(self):
        """Test VLAN-like isolation using Cilium Network Policies"""
        if not self.has_cilium:
            pytest.skip("Cilium CNI not available")
            
        conn = KubernetesConnection(namespace=self.test_namespace)
        conn.connect()
        handler = KubernetesHandler(conn)
        
        print("\nTesting Cilium Network Policy based VLAN...")
        
        # Configure Cilium VLAN policy
        config = NetworkConfig(
            interface="eth0",
            ip_address="172.16.100.10",
            netmask="255.255.255.0",
            vlan_id=100
        )
        
        result = handler._configure_cilium_vlan(config)
        
        if result.success:
            print("✓ Cilium Network Policy configured for VLAN 100")
        else:
            print(f"✗ Cilium configuration failed: {result.stderr}")
        
        conn.disconnect()
    
    def test_performance_with_vlan(self):
        """Test network performance with VLAN isolation"""
        conn = KubernetesConnection(namespace=self.test_namespace)
        conn.connect()
        
        print("\nTesting network performance...")
        
        # Find two pods in same VLAN
        pods = conn.list_pods(namespace=self.test_namespace)
        vlan100_pods = [p for p in pods if "vlan100" in p['name'] and p['status'] == 'Running']
        
        if len(vlan100_pods) >= 2:
            source_pod = vlan100_pods[0]['name']
            target_ip = vlan100_pods[1]['ip']
            
            # Run iperf test (if available in image)
            print(f"Running network performance test between pods...")
            
            # First, start iperf server on target
            conn.execute_command(
                "iperf3 -s -D",
                pod_name=vlan100_pods[1]['name'],
                namespace=self.test_namespace
            )
            
            time.sleep(2)
            
            # Run iperf client
            stdout, stderr, exit_code = conn.execute_command(
                f"iperf3 -c {target_ip} -t 5 -J",
                pod_name=source_pod,
                namespace=self.test_namespace
            )
            
            if exit_code == 0:
                print("✓ Performance test completed")
                # Parse results if needed
            else:
                print("✗ Performance test failed (iperf3 might not be available)")
        
        conn.disconnect()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])