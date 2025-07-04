#!/usr/bin/env python3
"""
Kubernetes Integration Quickstart Example

This example demonstrates basic Kubernetes operations with the POD library,
including pod creation, VLAN configuration, and cross-platform networking.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pod.connections.kubernetes import KubernetesConnection
from pod.os_abstraction.kubernetes import KubernetesHandler
from pod.infrastructure.kubernetes.provider import KubernetesProvider
from pod.os_abstraction.base import NetworkConfig
from pod.network.cni import CNIConfig


def main():
    """Main example demonstrating Kubernetes integration"""
    
    print("POD Library - Kubernetes Integration Example")
    print("=" * 50)
    
    # 1. Connect to Kubernetes cluster
    print("\n1. Connecting to Kubernetes cluster...")
    
    # Option A: Using kubeconfig
    k8s_conn = KubernetesConnection(
        namespace="default",
        timeout=30
    )
    
    # Option B: Direct API connection (uncomment to use)
    # k8s_conn = KubernetesConnection(
    #     api_server="https://kubernetes.example.com:6443",
    #     token="your-service-account-token",
    #     ca_cert_path="/path/to/ca.crt",
    #     namespace="default"
    # )
    
    try:
        k8s_conn.connect()
        print("✓ Connected successfully")
        
        # Get cluster info
        cluster_info = k8s_conn.get_cluster_info()
        print(f"  Cluster version: {cluster_info.get('version', 'unknown')}")
        print(f"  Nodes: {', '.join(cluster_info.get('nodes', []))}")
        
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print("\nNote: This example requires access to a Kubernetes cluster.")
        print("Please ensure your kubeconfig is properly configured.")
        return
    
    # 2. Create OS handler and check capabilities
    print("\n2. Checking cluster capabilities...")
    handler = KubernetesHandler(k8s_conn)
    
    os_info = handler.get_os_info()
    print(f"  CNI Plugins: {', '.join(os_info['cni_plugins'])}")
    print(f"  Network Policies: {'✓' if os_info['network_capabilities']['network_policies'] else '✗'}")
    print(f"  Service Mesh: {'✓' if os_info['network_capabilities']['service_mesh'] else '✗'}")
    
    # 3. Configure VLAN network (if Multus is available)
    if "multus" in os_info['cni_plugins']:
        print("\n3. Configuring VLAN network...")
        
        network_config = NetworkConfig(
            interface="eth0",
            ip_address="10.10.100.10",
            netmask="255.255.255.0",
            vlan_id=100,
            gateway="10.10.100.1"
        )
        
        result = handler.configure_network(network_config)
        if result.success:
            print(f"✓ VLAN {network_config.vlan_id} configured")
        else:
            print(f"✗ VLAN configuration failed: {result.stderr}")
    
    # 4. Create infrastructure provider
    print("\n4. Creating infrastructure provider...")
    provider = KubernetesProvider(
        namespace="default",
        kubeconfig_path=k8s_conn.kubeconfig_path
    )
    provider.connect()
    
    # 5. Deploy a workload with network configuration
    print("\n5. Deploying workload with network configuration...")
    
    # Create CNI config for advanced networking
    cni_config = CNIConfig(
        name="pod-network",
        type="macvlan",
        master="eth0",
        vlan_id=100,
        ipam_type="static",
        subnet="10.10.100.0/24",
        gateway="10.10.100.1"
    )
    
    deployment_result = provider.deploy_workload(
        workload_type="pod",
        name="example-pod",
        image="nginx:alpine",
        network_config=cni_config,
        vlan_id=100,
        labels={"app": "example", "vlan-100": "true"}
    )
    
    if deployment_result['success']:
        print(f"✓ Pod deployed: {deployment_result['name']}")
        print(f"  Namespace: {deployment_result['namespace']}")
        if 'ip' in deployment_result:
            print(f"  IP Address: {deployment_result['ip']}")
    else:
        print(f"✗ Deployment failed: {deployment_result.get('error', 'Unknown error')}")
    
    # 6. List pods in namespace
    print("\n6. Listing pods in namespace...")
    pods = k8s_conn.list_pods(namespace="default")
    
    for pod in pods[:5]:  # Show first 5 pods
        print(f"  - {pod['name']} ({pod['status']})")
        if pod['ip']:
            print(f"    IP: {pod['ip']}")
    
    # 7. Test network connectivity (if pod was created)
    if deployment_result['success'] and pods:
        print("\n7. Testing network connectivity...")
        
        # Find our pod
        our_pod = next((p for p in pods if p['name'] == "example-pod"), None)
        
        if our_pod and our_pod['status'] == 'Running':
            # Test connectivity to another pod
            other_pods = [p for p in pods if p['name'] != "example-pod" and p['ip']]
            
            if other_pods:
                target_pod = other_pods[0]
                result = handler.test_network_connectivity(
                    source_pod="example-pod",
                    target_ip=target_pod['ip']
                )
                
                if result.success:
                    print(f"✓ Connectivity test passed to {target_pod['name']}")
                else:
                    print(f"✗ Connectivity test failed: {result.stderr}")
    
    # 8. Cleanup (optional)
    print("\n8. Cleanup...")
    cleanup = input("Delete example pod? (y/n): ").lower()
    
    if cleanup == 'y':
        delete_result = provider.delete_workload(
            workload_type="pod",
            name="example-pod"
        )
        
        if delete_result['success']:
            print("✓ Pod deleted successfully")
        else:
            print(f"✗ Deletion failed: {delete_result.get('error', 'Unknown error')}")
    
    # Disconnect
    k8s_conn.disconnect()
    provider.disconnect()
    
    print("\n✓ Example completed successfully!")


if __name__ == "__main__":
    main()