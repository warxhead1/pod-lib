# Kubernetes Integration for POD Library

This directory contains examples and documentation for the POD library's Kubernetes integration, enabling hybrid infrastructure management across vSphere VMs, Docker containers, and Kubernetes pods.

## Features

### 🚀 **Modern Kubernetes Integration**
- **Official Python Kubernetes Client**: Latest kubernetes>=28.0.0 with async support
- **Advanced CNI Support**: Calico, Cilium, Multus, Flannel, Weave, Antrea
- **Enterprise Networking**: VLAN isolation, NetworkPolicies, service mesh integration
- **Scalable Architecture**: HPA, VPA, cluster autoscaling support

### 🌐 **Advanced Network Testing**
- **Cross-Platform VLAN Testing**: Test isolation between VMs, containers, and pods
- **Performance Benchmarking**: Latency, bandwidth, and throughput testing
- **Security Validation**: NetworkPolicy enforcement testing
- **Hybrid Connectivity**: End-to-end network validation

### 🔄 **Hybrid Workflows**
- **VM-to-Container Migration**: Automated workload modernization
- **Disaster Recovery**: Cross-platform failover scenarios
- **Cost Optimization**: Dynamic workload placement
- **Unified Management**: Single interface for multiple platforms

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Required packages:
- `kubernetes>=28.0.0` - Official Kubernetes Python client
- `kubernetes-asyncio>=28.0.0` - Async support
- `kopf>=1.37.0` - Kubernetes Operator framework
- `pykube-ng>=22.9.0` - Lightweight alternative client

### 2. Setup Kubernetes Access

```bash
# Option 1: Use existing kubeconfig
export KUBECONFIG=~/.kube/config

# Option 2: Use service account token
export K8S_API_SERVER=https://your-cluster.example.com:6443
export K8S_TOKEN=your-service-account-token

# Option 3: In-cluster configuration (when running in pod)
# No setup needed - will auto-detect
```

### 3. Run Hybrid Network Testing

```bash
python hybrid_network_test.py
```

This will:
- Connect to your Kubernetes cluster
- Create test pods with VLAN isolation
- Test cross-platform network connectivity
- Generate comprehensive reports

### 4. Run Integration Demo

```bash
python k8s_vsphere_integration.py
```

This demonstrates:
- VM to container migration workflows
- Disaster recovery scenarios
- Network testing across platforms
- Auto-scaling configurations

## Architecture

### Core Components

```
POD Kubernetes Integration
├── Connections
│   └── KubernetesConnection     # Modern K8s client with sync/async
├── OS Abstraction
│   └── KubernetesHandler        # Pod lifecycle management
├── Infrastructure
│   ├── KubernetesProvider       # High-level provider interface
│   ├── ClusterManager          # Cluster health and monitoring
│   └── WorkloadManager         # Advanced workload management
├── Network
│   └── CNIManager              # Advanced CNI integration
└── Examples
    ├── HybridNetworkTest       # Cross-platform testing
    └── K8sVSphereIntegration   # Hybrid workflows
```

### Network Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Hybrid Network Topology                  │
├─────────────────┬─────────────────┬─────────────────────────┤
│   vSphere VMs   │ Docker Containers│   Kubernetes Pods      │
│                 │                 │                         │
│  VLAN 100       │    VLAN 100     │     VLAN 100           │
│  192.168.100.x  │   192.168.100.x │    192.168.100.x       │
│                 │                 │                         │
│  VLAN 200       │    VLAN 200     │     VLAN 200           │
│  192.168.200.x  │   192.168.200.x │    192.168.200.x       │
└─────────────────┴─────────────────┴─────────────────────────┘
          │                 │                     │
          └─────────────────┼─────────────────────┘
                           │
                    Physical Network
                    (VLAN-aware switches)
```

## CNI Integration

### Supported CNI Plugins

| CNI Plugin | VLAN Support | NetworkPolicies | eBPF | Service Mesh |
|------------|--------------|-----------------|------|--------------|
| **Calico** | ✅ BGP VLAN | ✅ Advanced    | ❌   | Limited      |
| **Cilium** | ✅ eBPF     | ✅ L3-L7       | ✅   | ✅ Native    |
| **Multus** | ✅ Multi-CNI| ✅ Via primary | Depends | Depends   |
| **Flannel**| ❌ Overlay  | ❌ Basic       | ❌   | ❌          |
| **Weave**  | ✅ Limited  | ✅ Basic       | ❌   | Limited      |

### VLAN Configuration Examples

#### Multus + MACVLAN
```python
network_config = CNIConfig(
    name="vlan-100",
    type="macvlan",
    vlan_id=100,
    master_interface="eth0",
    subnet="192.168.100.0/24"
)
```

#### Calico IP Pools
```python
# Automatic IP pool creation for VLAN isolation
calico_pool = cni_manager.create_calico_ip_pool(
    name="vlan-100-pool",
    cidr="192.168.100.0/24",
    vlan_id=100
)
```

#### Cilium Network Policies
```python
# eBPF-based micro-segmentation
cilium_policy = cni_manager.create_cilium_network_policy(
    name="vlan-isolation",
    namespace="production",
    endpoint_selector={"vlan-100": "true"}
)
```

## Testing Framework

### Network Isolation Testing

The framework tests VLAN isolation across all platforms:

```python
# Test intra-VLAN connectivity (should work)
for vlan_id, nodes in vlan_groups.items():
    for source, target in itertools.combinations(nodes, 2):
        result = test_connectivity(source, target)
        assert result.success  # Same VLAN should connect

# Test cross-VLAN isolation (should fail)
for vlan1, vlan2 in itertools.combinations(vlan_groups.keys(), 2):
    for source in vlan_groups[vlan1]:
        for target in vlan_groups[vlan2]:
            result = test_connectivity(source, target)
            assert not result.success  # Different VLANs should be isolated
```

### Performance Testing

Cross-platform performance comparison:

```python
performance_results = {
    "k8s_to_k8s_latency": "1.2ms",
    "k8s_to_vsphere_latency": "2.8ms",
    "vsphere_to_vsphere_latency": "2.1ms",
    "bandwidth_k8s": "1.2 Gbps",
    "bandwidth_vsphere": "1.0 Gbps"
}
```

## Example Workflows

### 1. VM to Container Migration

```python
# Step 1: Analyze existing VM
vm_analysis = {
    "os": "Rocky Linux 9",
    "applications": ["nginx", "nodejs", "postgresql"],
    "network_config": {"vlan": 100, "ip": "192.168.100.10"}
}

# Step 2: Create containerized version
k8s_provider.deploy_workload(
    workload_type="deployment",
    name="migrated-web",
    image="nginx:alpine",
    network_config=network_config,
    vlan_id=100
)
```

### 2. Disaster Recovery

```python
# Primary: vSphere VM
# Backup: Kubernetes deployment with same VLAN
backup_deployment = k8s_provider.deploy_workload(
    workload_type="deployment",
    name="dr-backup",
    replicas=3,
    vlan_id=100,
    labels={"purpose": "disaster-recovery"}
)
```

### 3. Auto-Scaling Setup

```python
# Horizontal Pod Autoscaler
hpa = workload_manager.create_hpa(
    name="web-app-hpa",
    target_name="web-app",
    min_replicas=2,
    max_replicas=10,
    cpu_percent=70
)
```

## Advanced Features

### 1. Service Mesh Integration

When Cilium is detected:
```python
# Automatic service mesh capabilities
if "cilium" in cni_plugins:
    capabilities.update({
        "service_mesh": True,
        "encryption": True,  # Transparent encryption
        "load_balancing": True,  # eBPF load balancing
        "observability": ["hubble", "cilium-metrics"]
    })
```

### 2. SR-IOV Support

For high-performance networking:
```python
sriov_config = CNIConfig(
    name="sriov-net",
    type="sriov",
    master_interface="0000:00:07.0",
    vlan_id=100
)
```

### 3. Network Observability

Built-in monitoring integration:
```python
observability_config = cni_manager.get_network_observability_config()
# Returns Prometheus endpoints, Hubble flows, etc.
```

## Troubleshooting

### Common Issues

1. **CNI Plugin Not Detected**
   ```bash
   kubectl get pods -n kube-system | grep -E "(calico|cilium|flannel)"
   ```

2. **VLAN Configuration Issues**
   ```bash
   kubectl get network-attachment-definitions
   kubectl describe networkpolicy vlan-100-isolation
   ```

3. **Pod Network Problems**
   ```bash
   kubectl exec -it test-pod -- ip addr show
   kubectl logs -n kube-system cilium-xxx
   ```

### Debug Mode

Enable detailed logging:
```python
import logging
logging.getLogger('pod.kubernetes').setLevel(logging.DEBUG)
```

## Best Practices

### 1. Security
- Always use NetworkPolicies for VLAN isolation
- Implement least-privilege RBAC
- Enable CNI encryption when available

### 2. Performance
- Use SR-IOV for high-throughput workloads
- Consider DPDK for packet processing
- Monitor cross-platform latency

### 3. Scalability
- Implement HPA for dynamic scaling
- Use cluster autoscaler for node scaling
- Monitor resource utilization

### 4. Monitoring
- Deploy Prometheus + Grafana
- Enable CNI-specific metrics
- Set up alerting for network issues

## Contributing

To add new CNI support:

1. Update `CNIManager._detect_cni_plugins()`
2. Add configuration methods in `CNIManager`
3. Update capability detection
4. Add unit tests
5. Update documentation

## Resources

- [Kubernetes Networking Concepts](https://kubernetes.io/docs/concepts/cluster-administration/networking/)
- [CNI Specification](https://github.com/containernetworking/cni)
- [Calico Documentation](https://docs.projectcalico.org/)
- [Cilium Documentation](https://docs.cilium.io/)
- [Multus Documentation](https://github.com/k8snetworkplumbingwg/multus-cni)