# Network Testing Framework

This directory contains specialized testing frameworks for evaluating container capacity and network performance using the POD library. These tools are designed for testing network devices and measuring system limits.

## Components

### 1. Container Capacity Test (`container_capacity_test.py`)

Tests the maximum number of containers that can be deployed on a machine and measures network throughput between them.

#### Features
- **Scalability Testing**: Deploy up to N containers across multiple VLANs
- **Performance Metrics**: Measure deployment speed and resource usage
- **Network Throughput**: Test bandwidth between containers on different VLANs
- **Automated Cleanup**: Clean container removal after testing

#### Usage
```bash
# Test with 50 containers across 5 VLANs
python container_capacity_test.py --max-containers 50 --vlan-count 5

# Quick test with detailed output
python container_capacity_test.py --max-containers 10 --vlan-count 2 --verbose

# Custom test duration and concurrency
python container_capacity_test.py \
  --max-containers 30 \
  --vlan-count 3 \
  --test-duration 20 \
  --max-concurrent 10 \
  --output my_test_results.json
```

#### Output Metrics
- Container deployment success rate
- Average deployment time per container
- Network configuration time
- Cross-VLAN vs same-VLAN throughput
- Resource utilization patterns

### 2. Network Device Test Framework (`network_device_test_framework.py`)

Creates controlled test environments for network device testing using isolated container endpoints.

#### Features
- **YAML Configuration**: Define test scenarios declaratively
- **Role-based Endpoints**: Client, server, and monitor containers
- **VLAN Isolation Testing**: Verify network segmentation
- **Custom Test Matrix**: Define specific test combinations
- **Automated Tool Installation**: Install network testing tools per endpoint

#### Usage

First, create a test configuration:
```bash
# Generate sample configuration
python network_device_test_framework.py --create-sample

# Edit the generated sample_network_test_config.yaml as needed
```

Then run tests:
```bash
# Run tests with configuration
python network_device_test_framework.py --config my_test_config.yaml

# Run with verbose output
python network_device_test_framework.py --config my_test_config.yaml --verbose
```

#### Configuration Example
```yaml
scenarios:
  - name: "vlan_isolation_test"
    description: "Test VLAN isolation between network segments"
    endpoints:
      - name: "vlan100-client"
        vlan_id: 100
        ip_address: "192.168.100.10"
        role: "client"
        tools: ["iproute", "iputils", "iperf3"]
      - name: "vlan200-server"
        vlan_id: 200
        ip_address: "192.168.200.20"
        role: "server"
        tools: ["iproute", "iputils", "iperf3", "netcat"]
    test_matrix:
      - source: "vlan100-client"
        target: "vlan200-server"
        type: "ping"
        expected: "should_fail"  # VLAN isolation should block this
```

## Use Cases

### Network Device Testing
Perfect for testing:
- **CMTS (Cable Modem Termination System)** configurations
- **Switch VLAN isolation** functionality  
- **Router ACL** effectiveness
- **Network segmentation** policies
- **Bandwidth shaping** and QoS

### Performance Benchmarking
Measure:
- **Container density limits** per host
- **Network throughput** across VLANs
- **Deployment scaling** characteristics
- **Resource consumption** patterns
- **Network latency** between segments

### Automated Testing
- **CI/CD integration** for network device firmware
- **Regression testing** for network configurations
- **Load testing** for network infrastructure
- **Compliance testing** for network policies

## Architecture

The testing framework leverages POD's container VLAN capabilities:

```
Host Machine
├── Docker Engine
├── VLAN 100 (192.168.100.0/24)
│   ├── Container 1 (Client)
│   └── Container 2 (Server)
├── VLAN 200 (192.168.200.0/24)
│   ├── Container 3 (Client)
│   └── Container 4 (Monitor)
└── VLAN 300 (192.168.300.0/24)
    └── Container 5 (Server)
```

Each container:
- Has isolated network namespace
- Configured on specific VLAN
- Contains network testing tools
- Can communicate within VLAN constraints

## Requirements

### System Requirements
- Docker or Podman runtime
- Linux host with VLAN support (802.1q module)
- Sufficient resources for target container count
- Network interfaces supporting VLAN tagging

### Python Dependencies
```bash
pip install -e ../../  # Install POD library
pip install pyyaml asyncio  # Additional dependencies
```

### Network Tools (Auto-installed in containers)
- `iproute2` - Network configuration
- `iputils` - Ping and basic tools  
- `iperf3` - Bandwidth testing
- `tcpdump` - Packet capture (optional)
- `netcat` - Network debugging (optional)

## Sample Results

### Container Capacity Test Results
```json
{
  "test_summary": {
    "total_containers_requested": 50,
    "successful_deployments": 47,
    "deployment_success_rate": 94.0
  },
  "performance_metrics": {
    "deployment_time": 125.3,
    "containers_per_second": 0.38,
    "average_startup_time": 2.1,
    "average_network_config_time": 0.8
  },
  "network_performance": {
    "cross_vlan_tests": 15,
    "same_vlan_tests": 10,
    "average_throughput_mbps": 850.2,
    "max_throughput_mbps": 940.1
  }
}
```

### Network Device Test Results
```json
{
  "scenarios": [
    {
      "scenario_name": "vlan_isolation_test",
      "connectivity_tests": [
        {
          "source": "vlan100-client",
          "target": "vlan200-server", 
          "ping_success": false,
          "comment": "VLAN isolation working correctly"
        }
      ],
      "bandwidth_tests": [
        {
          "client": "vlan100-client",
          "server": "vlan100-server",
          "throughput_mbps": 920.5,
          "success": true
        }
      ]
    }
  ]
}
```

## Best Practices

### Container Limits
- Start with small container counts (10-20) to establish baseline
- Monitor host resource usage (CPU, memory, network)
- Consider container overhead when planning large deployments

### Network Testing
- Use realistic test durations (10-30 seconds minimum)
- Test both same-VLAN and cross-VLAN scenarios
- Include negative tests (expected failures) to verify isolation

### Troubleshooting
- Check Docker daemon logs for container issues
- Verify VLAN module is loaded: `lsmod | grep 8021q`
- Ensure sufficient network bandwidth for testing
- Monitor host system resources during testing

## Integration with CI/CD

Example GitHub Actions workflow:
```yaml
name: Network Device Testing
on: [push, pull_request]

jobs:
  network-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install -e .
          pip install pyyaml
      - name: Run network tests
        run: |
          cd examples/network_testing
          python network_device_test_framework.py --config ci_test_config.yaml
      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: network-test-results
          path: network_test_results.json
```

This testing framework provides a robust foundation for validating network device functionality and measuring system performance limits using POD's container VLAN capabilities.