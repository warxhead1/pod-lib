# Kubernetes Integration Real-World Testing Guide

## Overview

This guide provides comprehensive testing strategies for validating the POD library's Kubernetes integration in real environments. It covers local development testing, staging environments, and production validation.

## Test Environment Setup

### 1. Local Development Testing

#### Option A: Minikube (Simplest)
```bash
# Install Minikube
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube

# Start cluster with CNI plugin support
minikube start --cni=calico --nodes=3 --cpus=4 --memory=8192

# Enable required addons
minikube addons enable metrics-server
minikube addons enable ingress
```

#### Option B: Kind (Kubernetes in Docker)
```bash
# Install Kind
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind

# Create multi-node cluster with custom config
cat <<EOF > kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
- role: worker
- role: worker
networking:
  disableDefaultCNI: true  # We'll install our own CNI
EOF

kind create cluster --config kind-config.yaml

# Install Calico CNI
kubectl apply -f https://docs.projectcalico.org/manifests/calico.yaml
```

#### Option C: K3s (Lightweight Production-Grade)
```bash
# Install K3s with specific CNI
curl -sfL https://get.k3s.io | sh -s - --flannel-backend=none --disable-network-policy

# Install Cilium CNI for advanced networking
CILIUM_CLI_VERSION=$(curl -s https://raw.githubusercontent.com/cilium/cilium-cli/master/stable.txt)
curl -L --fail --remote-name-all https://github.com/cilium/cilium-cli/releases/download/${CILIUM_CLI_VERSION}/cilium-linux-amd64.tar.gz
sudo tar xzvfC cilium-linux-amd64.tar.gz /usr/local/bin
cilium install
```

### 2. Staging Environment Testing

#### Multi-CNI Cluster Setup
```bash
# Deploy Multus for multiple network interfaces
kubectl apply -f https://raw.githubusercontent.com/k8snetworkplumbingwg/multus-cni/master/deployments/multus-daemonset.yml

# Install additional CNI plugins
kubectl apply -f https://raw.githubusercontent.com/k8snetworkplumbingwg/multus-cni/master/examples/multus-cni.yaml
```

### 3. Cloud Provider Testing

#### GKE (Google Kubernetes Engine)
```bash
# Create cluster with network policy support
gcloud container clusters create pod-test-cluster \
    --enable-network-policy \
    --enable-ip-alias \
    --num-nodes=3 \
    --zone=us-central1-a

# Get credentials
gcloud container clusters get-credentials pod-test-cluster --zone=us-central1-a
```

#### EKS (Amazon Elastic Kubernetes Service)
```bash
# Create cluster with VPC CNI
eksctl create cluster \
  --name pod-test-cluster \
  --version 1.28 \
  --region us-west-2 \
  --nodegroup-name standard-workers \
  --node-type t3.medium \
  --nodes 3

# Install Calico for network policies
kubectl apply -f https://docs.projectcalico.org/manifests/calico-vxlan.yaml
```

## Test Scenarios

### 1. Basic Connectivity Tests

Create test script: `tests/real_world/test_basic_k8s.py`

```python
#!/usr/bin/env python3
"""Basic Kubernetes connectivity tests"""

import pytest
from pod.connections.kubernetes import KubernetesConnection
from pod.os_abstraction.kubernetes import KubernetesHandler

class TestBasicKubernetes:
    """Test basic Kubernetes operations"""
    
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
        
        conn.disconnect()
    
    def test_namespace_operations(self):
        """Test namespace creation and listing"""
        conn = KubernetesConnection()
        conn.connect()
        
        # List namespaces
        namespaces = conn.list_namespaces()
        assert 'default' in namespaces
        assert 'kube-system' in namespaces
        
        conn.disconnect()
    
    def test_pod_lifecycle(self):
        """Test pod creation and deletion"""
        conn = KubernetesConnection(namespace="default")
        conn.connect()
        handler = KubernetesHandler(conn)
        
        # Create a simple pod
        from pod.os_abstraction.base import NetworkConfig
        
        config = NetworkConfig(
            interface="eth0",
            ip_address="10.244.0.100",
            netmask="255.255.255.0"
        )
        
        result = handler.create_pod_with_vlan(
            pod_name="test-pod",
            image="nginx:alpine",
            vlan_id=0,  # No VLAN for basic test
            network_config=config
        )
        
        assert result.success
        
        # Verify pod exists
        pods = conn.list_pods()
        pod_names = [p['name'] for p in pods]
        assert "test-pod" in pod_names
        
        # Delete pod
        delete_result = handler.delete_pod("test-pod")
        assert delete_result.success
        
        conn.disconnect()
```

### 2. CNI Plugin Tests

Create test script: `tests/real_world/test_cni_plugins.py`

```python
#!/usr/bin/env python3
"""Test CNI plugin detection and configuration"""

import pytest
from pod.connections.kubernetes import KubernetesConnection
from pod.os_abstraction.kubernetes import KubernetesHandler
from pod.network.cni import CNIManager, CNIConfig

class TestCNIPlugins:
    """Test CNI plugin functionality"""
    
    def test_cni_detection(self):
        """Test CNI plugin detection"""
        conn = KubernetesConnection()
        conn.connect()
        handler = KubernetesHandler(conn)
        
        # Get detected CNI plugins
        os_info = handler.get_os_info()
        cni_plugins = os_info['cni_plugins']
        
        print(f"Detected CNI plugins: {cni_plugins}")
        
        # At least one plugin should be detected
        assert len(cni_plugins) > 0
        
        # Check for specific plugins based on cluster setup
        if 'calico' in cni_plugins:
            assert os_info['network_capabilities']['network_policies']
        
        conn.disconnect()
    
    @pytest.mark.skipif("not multus_available()", reason="Multus not installed")
    def test_multus_network_attachment(self):
        """Test Multus NetworkAttachmentDefinition creation"""
        conn = KubernetesConnection()
        conn.connect()
        
        cni_manager = CNIManager(conn)
        
        # Create MACVLAN network attachment
        config = CNIConfig(
            name="test-macvlan",
            type="macvlan",
            master="eth0",
            vlan_id=100,
            ipam_type="static",
            subnet="10.10.100.0/24",
            gateway="10.10.100.1"
        )
        
        nad = cni_manager.create_network_attachment_definition(config)
        
        # Apply to cluster
        result = cni_manager.apply_network_attachment(nad, namespace="default")
        assert result['success']
        
        # Verify it exists
        attachments = cni_manager.list_network_attachments(namespace="default")
        assert "test-macvlan" in [a['name'] for a in attachments]
        
        # Cleanup
        cni_manager.delete_network_attachment("test-macvlan", namespace="default")
        
        conn.disconnect()
```

### 3. VLAN Isolation Tests

Create test script: `tests/real_world/test_vlan_isolation.py`

```python
#!/usr/bin/env python3
"""Test VLAN isolation across pods"""

import time
import pytest
from pod.connections.kubernetes import KubernetesConnection
from pod.os_abstraction.kubernetes import KubernetesHandler
from pod.os_abstraction.base import NetworkConfig

class TestVLANIsolation:
    """Test VLAN-based network isolation"""
    
    def setup_class(self):
        """Setup test pods with different VLANs"""
        self.conn = KubernetesConnection(namespace="default")
        self.conn.connect()
        self.handler = KubernetesHandler(self.conn)
        self.test_pods = []
    
    def teardown_class(self):
        """Cleanup test pods"""
        for pod_name in self.test_pods:
            try:
                self.handler.delete_pod(pod_name)
            except:
                pass
        self.conn.disconnect()
    
    def test_same_vlan_connectivity(self):
        """Test pods in same VLAN can communicate"""
        # Create two pods in VLAN 100
        for i in range(2):
            config = NetworkConfig(
                interface="eth0",
                ip_address=f"10.10.100.{10+i}",
                netmask="255.255.255.0",
                vlan_id=100
            )
            
            pod_name = f"vlan100-pod-{i}"
            result = self.handler.create_pod_with_vlan(
                pod_name=pod_name,
                image="nicolaka/netshoot",  # Network troubleshooting image
                vlan_id=100,
                network_config=config
            )
            
            if result.success:
                self.test_pods.append(pod_name)
        
        # Wait for pods to be ready
        time.sleep(30)
        
        # Test connectivity
        result = self.handler.test_network_connectivity(
            source_pod="vlan100-pod-0",
            target_ip="10.10.100.11"
        )
        
        assert result.success, "Pods in same VLAN should communicate"
    
    def test_different_vlan_isolation(self):
        """Test pods in different VLANs cannot communicate"""
        # Create pod in VLAN 200
        config = NetworkConfig(
            interface="eth0",
            ip_address="10.10.200.10",
            netmask="255.255.255.0",
            vlan_id=200
        )
        
        result = self.handler.create_pod_with_vlan(
            pod_name="vlan200-pod",
            image="nicolaka/netshoot",
            vlan_id=200,
            network_config=config
        )
        
        if result.success:
            self.test_pods.append("vlan200-pod")
        
        # Wait for pod to be ready
        time.sleep(30)
        
        # Test isolation (should fail)
        result = self.handler.test_network_connectivity(
            source_pod="vlan100-pod-0",
            target_ip="10.10.200.10"
        )
        
        assert not result.success, "Pods in different VLANs should not communicate"
```

### 4. Performance Tests

Create test script: `tests/real_world/test_performance.py`

```python
#!/usr/bin/env python3
"""Performance testing for Kubernetes operations"""

import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from pod.connections.kubernetes import KubernetesConnection
from pod.infrastructure.kubernetes.provider import KubernetesProvider

class TestPerformance:
    """Test performance of Kubernetes operations"""
    
    def test_pod_creation_performance(self):
        """Test pod creation speed and scaling"""
        provider = KubernetesProvider(namespace="default")
        provider.connect()
        
        pod_count = 10
        creation_times = []
        
        for i in range(pod_count):
            start_time = time.time()
            
            result = provider.deploy_workload(
                workload_type="pod",
                name=f"perf-test-pod-{i}",
                image="nginx:alpine",
                labels={"test": "performance"}
            )
            
            creation_time = time.time() - start_time
            creation_times.append(creation_time)
            
            assert result['success']
        
        # Calculate statistics
        avg_time = statistics.mean(creation_times)
        max_time = max(creation_times)
        min_time = min(creation_times)
        
        print(f"Pod creation performance:")
        print(f"  Average: {avg_time:.2f}s")
        print(f"  Min: {min_time:.2f}s")
        print(f"  Max: {max_time:.2f}s")
        
        # Cleanup
        for i in range(pod_count):
            provider.delete_workload("pod", f"perf-test-pod-{i}")
        
        provider.disconnect()
        
        # Assert reasonable performance
        assert avg_time < 5.0, "Average pod creation should be under 5 seconds"
    
    def test_concurrent_operations(self):
        """Test concurrent pod operations"""
        provider = KubernetesProvider(namespace="default")
        provider.connect()
        
        def create_pod(index):
            """Create a single pod"""
            start_time = time.time()
            result = provider.deploy_workload(
                workload_type="pod",
                name=f"concurrent-pod-{index}",
                image="nginx:alpine"
            )
            return index, time.time() - start_time, result['success']
        
        # Create pods concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_pod, i) for i in range(20)]
            
            results = []
            for future in as_completed(futures):
                results.append(future.result())
        
        # Verify all succeeded
        successful = sum(1 for _, _, success in results if success)
        assert successful == 20, f"Expected 20 successful pods, got {successful}"
        
        # Cleanup
        for i in range(20):
            provider.delete_workload("pod", f"concurrent-pod-{i}")
        
        provider.disconnect()
```

### 5. Cross-Platform Integration Tests

Create test script: `tests/real_world/test_cross_platform.py`

```python
#!/usr/bin/env python3
"""Test cross-platform integration between Kubernetes and Docker"""

import docker
import pytest
from pod.connections.kubernetes import KubernetesConnection
from pod.connections.container import DockerConnection
from pod.os_abstraction.kubernetes import KubernetesHandler
from pod.os_abstraction.container import ContainerHandler

class TestCrossPlatform:
    """Test integration between Kubernetes and Docker"""
    
    @pytest.mark.skipif("not docker_available()", reason="Docker not available")
    def test_docker_to_kubernetes_networking(self):
        """Test networking between Docker container and Kubernetes pod"""
        # This requires special network setup (e.g., shared bridge)
        # Implementation depends on specific infrastructure
        pass
    
    def test_workload_migration_simulation(self):
        """Simulate migrating workload from Docker to Kubernetes"""
        # Create Docker container
        docker_client = docker.from_env()
        
        container = docker_client.containers.run(
            "nginx:alpine",
            name="migration-source",
            detach=True,
            ports={'80/tcp': 8080}
        )
        
        # Get container configuration
        container_info = container.attrs
        
        # Create equivalent Kubernetes pod
        k8s_conn = KubernetesConnection()
        k8s_conn.connect()
        
        from pod.infrastructure.kubernetes.provider import KubernetesProvider
        provider = KubernetesProvider()
        provider.connection = k8s_conn
        
        # Deploy equivalent workload
        result = provider.deploy_workload(
            workload_type="deployment",
            name="migration-target",
            image=container_info['Config']['Image'],
            replicas=1,
            ports=[{
                'name': 'http',
                'containerPort': 80,
                'protocol': 'TCP'
            }]
        )
        
        assert result['success']
        
        # Cleanup
        container.remove(force=True)
        provider.delete_workload("deployment", "migration-target")
        k8s_conn.disconnect()
```

## Validation Procedures

### 1. Pre-Test Validation

Create validation script: `tests/real_world/validate_environment.py`

```python
#!/usr/bin/env python3
"""Validate test environment before running tests"""

import subprocess
import sys

def check_kubectl():
    """Check if kubectl is available and configured"""
    try:
        result = subprocess.run(['kubectl', 'version', '--client'], 
                              capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def check_cluster_access():
    """Check if we can access the cluster"""
    try:
        result = subprocess.run(['kubectl', 'get', 'nodes'], 
                              capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False

def check_permissions():
    """Check if we have required permissions"""
    required_resources = [
        'pods', 'services', 'deployments', 
        'networkpolicies', 'namespaces'
    ]
    
    for resource in required_resources:
        result = subprocess.run(
            ['kubectl', 'auth', 'can-i', 'create', resource],
            capture_output=True
        )
        if result.returncode != 0:
            print(f"✗ Missing permission to create {resource}")
            return False
    
    return True

def main():
    """Run all validation checks"""
    print("Validating Kubernetes test environment...")
    
    checks = [
        ("kubectl available", check_kubectl),
        ("Cluster access", check_cluster_access),
        ("Required permissions", check_permissions)
    ]
    
    all_passed = True
    for check_name, check_func in checks:
        if check_func():
            print(f"✓ {check_name}")
        else:
            print(f"✗ {check_name}")
            all_passed = False
    
    if not all_passed:
        print("\n❌ Environment validation failed!")
        sys.exit(1)
    else:
        print("\n✅ Environment ready for testing!")

if __name__ == "__main__":
    main()
```

### 2. Test Execution Script

Create main test runner: `tests/real_world/run_k8s_tests.sh`

```bash
#!/bin/bash

# Kubernetes Integration Test Runner

set -e

echo "POD Library - Kubernetes Integration Tests"
echo "=========================================="

# Validate environment
echo -e "\n1. Validating environment..."
python tests/real_world/validate_environment.py

# Run tests in order
echo -e "\n2. Running basic connectivity tests..."
pytest tests/real_world/test_basic_k8s.py -v

echo -e "\n3. Running CNI plugin tests..."
pytest tests/real_world/test_cni_plugins.py -v

echo -e "\n4. Running VLAN isolation tests..."
pytest tests/real_world/test_vlan_isolation.py -v

echo -e "\n5. Running performance tests..."
pytest tests/real_world/test_performance.py -v

echo -e "\n6. Running cross-platform tests..."
pytest tests/real_world/test_cross_platform.py -v

# Generate report
echo -e "\n7. Generating test report..."
pytest tests/real_world/ --html=test_report.html --self-contained-html

echo -e "\n✅ All tests completed! Report available at test_report.html"
```

### 3. Continuous Testing

Create GitHub Actions workflow: `.github/workflows/k8s_integration_tests.yml`

```yaml
name: Kubernetes Integration Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]
  schedule:
    - cron: '0 0 * * *'  # Daily tests

jobs:
  test-minikube:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    
    - name: Start Minikube
      uses: medyagh/setup-minikube@master
      with:
        cpus: 2
        memory: 4096
        cni: calico
    
    - name: Install dependencies
      run: |
        pip install -e .
        pip install pytest pytest-html
    
    - name: Run integration tests
      run: |
        chmod +x tests/real_world/run_k8s_tests.sh
        ./tests/real_world/run_k8s_tests.sh
    
    - name: Upload test results
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: test-results
        path: test_report.html

  test-kind:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Create Kind cluster
      uses: helm/kind-action@v1.5.0
      with:
        config: tests/real_world/kind-config.yaml
    
    - name: Install Cilium CNI
      run: |
        curl -L --remote-name-all https://github.com/cilium/cilium-cli/releases/latest/download/cilium-linux-amd64.tar.gz
        sudo tar xzvfC cilium-linux-amd64.tar.gz /usr/local/bin
        cilium install
    
    - name: Run integration tests
      run: |
        pip install -e .
        pytest tests/real_world/ -v
```

## Monitoring and Debugging

### 1. Test Monitoring Dashboard

Create monitoring script: `tests/real_world/monitor_tests.py`

```python
#!/usr/bin/env python3
"""Monitor test execution and cluster state"""

import time
import subprocess
from datetime import datetime
from pod.connections.kubernetes import KubernetesConnection

def monitor_cluster_resources():
    """Monitor cluster resource usage during tests"""
    conn = KubernetesConnection()
    conn.connect()
    
    while True:
        # Get node metrics
        nodes = conn.v1.list_node()
        
        print(f"\n[{datetime.now()}] Cluster Status:")
        for node in nodes.items:
            # Get node resource usage
            metrics = conn.v1.read_node(name=node.metadata.name)
            
            print(f"  Node: {node.metadata.name}")
            print(f"    CPU: {metrics.status.capacity.get('cpu', 'N/A')}")
            print(f"    Memory: {metrics.status.capacity.get('memory', 'N/A')}")
        
        # Get pod count
        pods = conn.list_pods(namespace="default")
        print(f"  Active test pods: {len([p for p in pods if 'test' in p['name']])}")
        
        time.sleep(5)

if __name__ == "__main__":
    monitor_cluster_resources()
```

### 2. Debug Failed Tests

Create debug helper: `tests/real_world/debug_helper.py`

```python
#!/usr/bin/env python3
"""Debug helper for failed tests"""

import sys
from pod.connections.kubernetes import KubernetesConnection

def debug_pod(pod_name, namespace="default"):
    """Debug a specific pod"""
    conn = KubernetesConnection(namespace=namespace)
    conn.connect()
    
    # Get pod details
    pod = conn.v1.read_namespaced_pod(name=pod_name, namespace=namespace)
    
    print(f"Pod: {pod_name}")
    print(f"Status: {pod.status.phase}")
    print(f"Node: {pod.spec.node_name}")
    
    # Get events
    events = conn.v1.list_namespaced_event(
        namespace=namespace,
        field_selector=f"involvedObject.name={pod_name}"
    )
    
    print("\nEvents:")
    for event in events.items:
        print(f"  {event.type}: {event.message}")
    
    # Get logs
    try:
        logs = conn.v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            tail_lines=50
        )
        print(f"\nLogs:\n{logs}")
    except:
        print("\nNo logs available")
    
    # Describe pod
    print("\nPod Description:")
    subprocess.run(['kubectl', 'describe', 'pod', pod_name, '-n', namespace])

if __name__ == "__main__":
    if len(sys.argv) > 1:
        debug_pod(sys.argv[1])
    else:
        print("Usage: python debug_helper.py <pod-name>")
```

## Best Practices

1. **Test Isolation**
   - Use separate namespaces for each test suite
   - Clean up resources after each test
   - Use unique resource names with timestamps

2. **Network Testing**
   - Test with different CNI plugins
   - Verify VLAN isolation with packet captures
   - Test cross-node networking

3. **Performance Testing**
   - Establish baseline metrics
   - Test under load conditions
   - Monitor resource usage

4. **Security Testing**
   - Verify NetworkPolicy enforcement
   - Test pod security contexts
   - Validate RBAC permissions

5. **Continuous Integration**
   - Run tests on every commit
   - Test against multiple Kubernetes versions
   - Generate coverage reports

## Troubleshooting Common Issues

1. **CNI Plugin Issues**
   ```bash
   # Check CNI plugin status
   kubectl get pods -n kube-system | grep -E '(calico|cilium|flannel)'
   
   # View CNI configuration
   kubectl exec -n kube-system <cni-pod> -- cat /etc/cni/net.d/*
   ```

2. **VLAN Configuration Issues**
   ```bash
   # Check NetworkAttachmentDefinitions
   kubectl get network-attachment-definitions -A
   
   # Verify pod annotations
   kubectl get pod <pod-name> -o jsonpath='{.metadata.annotations}'
   ```

3. **Permission Issues**
   ```bash
   # Check current permissions
   kubectl auth can-i --list
   
   # Create service account with required permissions
   kubectl create serviceaccount pod-test-sa
   kubectl create clusterrolebinding pod-test-binding \
     --clusterrole=cluster-admin \
     --serviceaccount=default:pod-test-sa
   ```

## Conclusion

Real-world testing of the Kubernetes integration requires:
- Multiple test environments (local, staging, cloud)
- Comprehensive test scenarios covering all features
- Performance and stress testing
- Cross-platform validation
- Continuous monitoring and debugging capabilities

The provided test framework ensures the POD library's Kubernetes integration works reliably across different environments and configurations.