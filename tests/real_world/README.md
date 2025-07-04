# Kubernetes Integration Real-World Testing

This directory contains real-world tests for the POD library's Kubernetes integration. These tests are designed to run against actual Kubernetes clusters to validate functionality in realistic environments.

## Quick Start

### 1. Local Testing with Kind

```bash
# Setup a local test cluster
./setup_test_cluster.sh kind

# Run all tests
./run_k8s_tests.sh

# Cleanup when done
./setup_test_cluster.sh cleanup
```

### 2. Testing with Existing Cluster

```bash
# Ensure kubectl is configured
kubectl get nodes

# Validate environment
python validate_environment.py

# Run tests
./run_k8s_tests.sh
```

## Test Structure

### Core Test Files

- **`test_basic_k8s.py`** - Basic connectivity and operations
  - Cluster connection
  - Namespace operations
  - Pod lifecycle management
  - CNI plugin detection
  - Resource management

- **`test_vlan_isolation.py`** - VLAN and network isolation
  - Multus NetworkAttachmentDefinitions
  - NetworkPolicy-based isolation
  - Calico IP pools
  - Cilium policies
  - Cross-VLAN connectivity tests

- **`validate_environment.py`** - Pre-test validation
  - kubectl availability
  - Cluster access
  - Required permissions
  - CNI plugin detection
  - Storage class availability

### Helper Scripts

- **`setup_test_cluster.sh`** - Automated cluster setup
  - Supports Kind, Minikube, and K3s
  - Installs CNI plugins (Multus, Calico)
  - Creates test resources
  - Validates cluster readiness

- **`run_k8s_tests.sh`** - Test execution orchestrator
  - Environment validation
  - Sequential test execution
  - Coverage reporting
  - HTML report generation

## Supported Environments

### Local Development

1. **Kind (Kubernetes in Docker)**
   - Best for CI/CD pipelines
   - Multi-node support
   - Fast cluster creation
   - Resource efficient

2. **Minikube**
   - Good for local development
   - Supports various drivers
   - Built-in addons
   - Easy to use

3. **K3s**
   - Lightweight Kubernetes
   - Production-grade
   - Low resource usage
   - Good for edge testing

### Cloud Providers

1. **GKE (Google Kubernetes Engine)**
   ```bash
   gcloud container clusters create pod-test \
     --enable-network-policy \
     --num-nodes=3
   ```

2. **EKS (Amazon Elastic Kubernetes Service)**
   ```bash
   eksctl create cluster --name pod-test \
     --nodes 3 --managed
   ```

3. **AKS (Azure Kubernetes Service)**
   ```bash
   az aks create --name pod-test \
     --resource-group myResourceGroup \
     --node-count 3
   ```

## Test Scenarios

### Basic Functionality
- ✓ Cluster connectivity
- ✓ Authentication methods
- ✓ Namespace management
- ✓ Pod creation/deletion
- ✓ Command execution
- ✓ File upload/download

### Network Testing
- ✓ CNI plugin detection
- ✓ VLAN configuration
- ✓ Network isolation
- ✓ Cross-pod connectivity
- ✓ NetworkPolicy enforcement
- ✓ Multi-interface pods

### Advanced Features
- ✓ Multus CNI chaining
- ✓ Calico BGP routing
- ✓ Cilium eBPF policies
- ✓ SR-IOV support
- ✓ Performance testing
- ✓ Concurrent operations

## Running Tests

### Full Test Suite
```bash
./run_k8s_tests.sh
```

### Specific Test Module
```bash
pytest test_basic_k8s.py -v -s
```

### Single Test
```bash
pytest test_basic_k8s.py::TestBasicKubernetes::test_cluster_connection -v
```

### With Coverage
```bash
pytest . --cov=pod.connections.kubernetes --cov-report=html
```

## CI/CD Integration

### GitHub Actions
```yaml
- name: Setup Kind cluster
  run: ./tests/real_world/setup_test_cluster.sh kind

- name: Run Kubernetes tests
  run: ./tests/real_world/run_k8s_tests.sh
```

### GitLab CI
```yaml
test:kubernetes:
  image: python:3.10
  services:
    - docker:dind
  script:
    - ./tests/real_world/setup_test_cluster.sh kind
    - ./tests/real_world/run_k8s_tests.sh
```

### Jenkins
```groovy
stage('Kubernetes Tests') {
    steps {
        sh './tests/real_world/setup_test_cluster.sh kind'
        sh './tests/real_world/run_k8s_tests.sh'
    }
}
```

## Troubleshooting

### Common Issues

1. **Connection Failed**
   ```bash
   # Check kubectl configuration
   kubectl config view
   
   # Verify cluster access
   kubectl cluster-info
   ```

2. **Permission Denied**
   ```bash
   # Check permissions
   kubectl auth can-i --list
   
   # Create service account
   kubectl create serviceaccount pod-test
   kubectl create clusterrolebinding pod-test \
     --clusterrole=cluster-admin \
     --serviceaccount=default:pod-test
   ```

3. **CNI Not Working**
   ```bash
   # Check CNI pods
   kubectl get pods -n kube-system | grep -E 'calico|multus'
   
   # View CNI logs
   kubectl logs -n kube-system -l k8s-app=calico-node
   ```

### Debug Mode

```bash
# Run with debug output
PYTEST_VERBOSE=1 ./run_k8s_tests.sh

# Interactive debugging
pytest test_basic_k8s.py -v -s --pdb

# Save cluster state
kubectl get all -A > cluster-state.txt
```

## Performance Considerations

### Resource Requirements

- **Kind**: 4GB RAM, 2 CPUs minimum
- **Minikube**: 2GB RAM, 2 CPUs per node
- **Cloud**: t3.medium or equivalent

### Test Optimization

1. **Parallel Execution**
   ```bash
   pytest -n 4  # Run 4 tests in parallel
   ```

2. **Test Markers**
   ```python
   @pytest.mark.slow
   @pytest.mark.requires_multus
   ```

3. **Resource Cleanup**
   - Tests clean up after themselves
   - Namespace deletion on teardown
   - Automatic pod removal

## Contributing

When adding new tests:

1. Follow the existing test structure
2. Add appropriate skip conditions
3. Include cleanup in teardown
4. Document any special requirements
5. Update this README

## Security Notes

- Tests create temporary resources
- NetworkPolicies are tested for isolation
- No sensitive data in test configs
- Service accounts use minimal permissions
- All test resources are namespaced

## Future Enhancements

- [ ] Istio service mesh testing
- [ ] Multi-cluster federation
- [ ] Admission webhook validation
- [ ] CRD and operator testing
- [ ] Chaos engineering scenarios
- [ ] Load testing framework