#!/usr/bin/env python3
"""Validate Kubernetes test environment before running tests"""

import subprocess
import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pod.connections.kubernetes import KubernetesConnection
from pod.os_abstraction.kubernetes import KubernetesHandler


def check_kubectl():
    """Check if kubectl is available and configured"""
    try:
        result = subprocess.run(['kubectl', 'version', '--client', '--output=json'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            version_info = json.loads(result.stdout)
            client_version = version_info.get('clientVersion', {})
            return True, f"{client_version.get('major', '?')}.{client_version.get('minor', '?')}"
        return False, None
    except (FileNotFoundError, json.JSONDecodeError):
        return False, None


def check_cluster_access():
    """Check if we can access the cluster"""
    try:
        result = subprocess.run(['kubectl', 'get', 'nodes', '-o', 'json'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            nodes_info = json.loads(result.stdout)
            node_count = len(nodes_info.get('items', []))
            return True, node_count
        return False, 0
    except:
        return False, 0


def check_permissions():
    """Check if we have required permissions"""
    required_resources = [
        ('pods', 'create'),
        ('pods', 'delete'),
        ('pods', 'get'),
        ('pods/exec', 'create'),
        ('pods/log', 'get'),
        ('services', 'create'),
        ('deployments.apps', 'create'),
        ('networkpolicies.networking.k8s.io', 'create'),
        ('namespaces', 'create'),
        ('namespaces', 'delete')
    ]
    
    missing_permissions = []
    
    for resource, verb in required_resources:
        result = subprocess.run(
            ['kubectl', 'auth', 'can-i', verb, resource],
            capture_output=True
        )
        if result.returncode != 0:
            missing_permissions.append(f"{verb} {resource}")
    
    return len(missing_permissions) == 0, missing_permissions


def check_python_connection():
    """Check if POD library can connect to cluster"""
    try:
        conn = KubernetesConnection()
        conn.connect()
        
        # Get cluster info
        info = conn.get_cluster_info()
        
        # Get CNI plugins
        handler = KubernetesHandler(conn)
        os_info = handler.get_os_info()
        
        conn.disconnect()
        
        return True, {
            'version': info.get('version', 'unknown'),
            'nodes': len(info.get('nodes', [])),
            'cni_plugins': os_info['cni_plugins'],
            'capabilities': os_info['network_capabilities']
        }
    except Exception as e:
        return False, str(e)


def check_cni_plugins():
    """Check for specific CNI plugins"""
    cni_checks = {
        'calico': ['kubectl', 'get', 'pods', '-n', 'kube-system', '-l', 'k8s-app=calico-node'],
        'cilium': ['kubectl', 'get', 'pods', '-n', 'kube-system', '-l', 'k8s-app=cilium'],
        'flannel': ['kubectl', 'get', 'pods', '-n', 'kube-system', '-l', 'app=flannel'],
        'multus': ['kubectl', 'get', 'pods', '-n', 'kube-system', '-l', 'app=multus']
    }
    
    detected_cni = []
    
    for cni_name, check_cmd in cni_checks.items():
        try:
            result = subprocess.run(check_cmd, capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                detected_cni.append(cni_name)
        except:
            pass
    
    return detected_cni


def check_storage_classes():
    """Check available storage classes"""
    try:
        result = subprocess.run(
            ['kubectl', 'get', 'storageclass', '-o', 'json'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            sc_info = json.loads(result.stdout)
            storage_classes = [
                {
                    'name': sc['metadata']['name'],
                    'provisioner': sc.get('provisioner', 'unknown'),
                    'default': sc['metadata'].get('annotations', {}).get(
                        'storageclass.kubernetes.io/is-default-class', 'false'
                    ) == 'true'
                }
                for sc in sc_info.get('items', [])
            ]
            return True, storage_classes
        return False, []
    except:
        return False, []


def main():
    """Run all validation checks"""
    print("POD Library - Kubernetes Environment Validation")
    print("=" * 50)
    
    # Track overall status
    all_passed = True
    warnings = []
    
    # 1. Check kubectl
    print("\n1. Checking kubectl...")
    kubectl_ok, kubectl_version = check_kubectl()
    if kubectl_ok:
        print(f"   ✓ kubectl available (version {kubectl_version})")
    else:
        print("   ✗ kubectl not found or not configured")
        all_passed = False
    
    # 2. Check cluster access
    print("\n2. Checking cluster access...")
    cluster_ok, node_count = check_cluster_access()
    if cluster_ok:
        print(f"   ✓ Cluster accessible ({node_count} nodes)")
    else:
        print("   ✗ Cannot access cluster")
        all_passed = False
    
    # 3. Check permissions
    print("\n3. Checking permissions...")
    perms_ok, missing_perms = check_permissions()
    if perms_ok:
        print("   ✓ All required permissions granted")
    else:
        print("   ✗ Missing permissions:")
        for perm in missing_perms:
            print(f"     - {perm}")
        all_passed = False
    
    # 4. Check Python connection
    print("\n4. Checking POD library connection...")
    python_ok, python_info = check_python_connection()
    if python_ok:
        print(f"   ✓ POD library connected successfully")
        print(f"     - Cluster version: {python_info['version']}")
        print(f"     - Nodes: {python_info['nodes']}")
        print(f"     - CNI plugins: {', '.join(python_info['cni_plugins'])}")
        
        # Check capabilities
        caps = python_info['capabilities']
        if not caps['network_policies']:
            warnings.append("NetworkPolicies not supported - VLAN tests may be limited")
        if not caps['cni_chaining']:
            warnings.append("CNI chaining not available - Multus tests will be skipped")
    else:
        print(f"   ✗ POD library connection failed: {python_info}")
        all_passed = False
    
    # 5. Check CNI plugins
    print("\n5. Checking CNI plugins...")
    detected_cni = check_cni_plugins()
    if detected_cni:
        print(f"   ✓ Detected CNI plugins: {', '.join(detected_cni)}")
        if 'multus' not in detected_cni:
            warnings.append("Multus not detected - Advanced VLAN tests will be skipped")
    else:
        print("   ⚠ No specific CNI plugins detected")
        warnings.append("Using default CNI - Advanced networking tests may be limited")
    
    # 6. Check storage classes
    print("\n6. Checking storage classes...")
    storage_ok, storage_classes = check_storage_classes()
    if storage_ok and storage_classes:
        print("   ✓ Storage classes available:")
        for sc in storage_classes:
            default_marker = " (default)" if sc['default'] else ""
            print(f"     - {sc['name']} [{sc['provisioner']}]{default_marker}")
    else:
        print("   ⚠ No storage classes found")
        warnings.append("No storage classes - StatefulSet tests may fail")
    
    # Summary
    print("\n" + "=" * 50)
    
    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"  ⚠ {warning}")
    
    if all_passed:
        print("\n✅ Environment validation PASSED!")
        print("\nYou can now run the Kubernetes tests:")
        print("  pytest tests/real_world/test_basic_k8s.py -v")
        return 0
    else:
        print("\n❌ Environment validation FAILED!")
        print("\nPlease fix the issues above before running tests.")
        return 1


if __name__ == "__main__":
    sys.exit(main())