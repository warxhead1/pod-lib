# POD Container Integration Testing

This directory contains integration tests for the POD library's container support, including advanced VLAN networking capabilities.

## Overview

The integration tests use Docker-in-Docker (DinD) to create an isolated environment where we can:
- Create and manage containers
- Configure VLANs and network isolation
- Test container-to-container communication
- Validate the POD library's container abstraction layer

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Host Machine                           │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌─────────────────────┐     ┌──────────────────────┐   │
│  │   DinD Host          │     │   POD Controller     │   │
│  │  (Docker daemon)     │◄────┤  (Test runner)       │   │
│  │                      │     │                      │   │
│  │  ┌──────────────┐   │     └──────────────────────┘   │
│  │  │ Test         │   │                                 │
│  │  │ Container 1  │   │     ┌──────────────────────┐   │
│  │  │ VLAN 100     │   │     │  VLAN Bridge Setup   │   │
│  │  └──────────────┘   │     │  - br-vlan100        │   │
│  │                      │     │  - br-vlan200        │   │
│  │  ┌──────────────┐   │     │  - br-vlan300        │   │
│  │  │ Test         │   │     └──────────────────────┘   │
│  │  │ Container 2  │   │                                 │
│  │  │ VLAN 200     │   │                                 │
│  │  └──────────────┘   │                                 │
│  └─────────────────────┘                                 │
└───────────────────────────────────────────────────────────┘
```

## Test Environment Setup

### Prerequisites

1. Docker installed and running
2. Docker Compose installed
3. Sufficient permissions to run privileged containers

### Quick Start

```bash
# Run all integration tests
./run_integration_tests.sh

# Run with log output
./run_integration_tests.sh --logs

# Run local tests (without DinD)
python test_container_local.py
```

## Test Coverage

### 1. Basic Container Operations
- Container connection and command execution
- OS detection and information gathering
- Package installation across different distributions

### 2. VLAN Configuration
- Single VLAN interface creation
- Multiple VLANs on single container
- VLAN ID assignment and IP configuration

### 3. Network Isolation
- Container-to-container communication within same VLAN
- Isolation between different VLANs
- Bridge networking setup

### 4. Advanced Networking
- MACVLAN interface creation
- Veth pair configuration
- Network namespace operations

### 5. Multi-Container Scenarios
- Multiple containers on same VLAN
- Containers spanning multiple VLANs
- Network segregation testing

## Docker Compose Services

### dind-host
The Docker-in-Docker host that runs the Docker daemon where test containers are created.

### pod-controller
Runs the integration test suite and manages test execution.

### vlan-bridge-setup
Sets up network bridges for VLAN support (requires host network mode).

## Manual Testing

You can also manually test the container functionality:

```python
# Connect to a container
from pod.os_abstraction import ContainerHandler, ContainerConnection, NetworkConfig

# Create connection
conn = ContainerConnection("my-container", use_docker=True)
conn.connect()

# Create handler
handler = ContainerHandler(conn)

# Configure VLAN
config = NetworkConfig(
    interface="eth0",
    ip_address="192.168.100.10",
    netmask="255.255.255.0",
    vlan_id=100
)

result = handler.configure_network(config)
print(f"VLAN configured: {result.success}")

# Run commands
result = handler.execute_command("ip addr show")
print(result.stdout)
```

## Troubleshooting

### Docker-in-Docker Issues
- Ensure the DinD container has `--privileged` flag
- Check Docker daemon logs: `docker-compose logs dind-host`

### VLAN Configuration Failures
- VLANs require `CAP_NET_ADMIN` capability
- The host kernel must have 8021q module available
- Some environments (like Docker Desktop) may have limitations

### Network Isolation Not Working
- Verify bridge networks are created properly
- Check iptables rules aren't interfering
- Ensure containers are on different subnets

## Security Considerations

- The DinD setup requires privileged containers
- VLAN configuration needs NET_ADMIN capabilities
- Test in isolated environments only
- Don't expose DinD ports to public networks

## Extending Tests

To add new integration tests:

1. Add test method to `TestContainerIntegration` class
2. Follow the naming convention `test_<feature>`
3. Add to the `tests` list in `run_all_tests()`
4. Ensure proper cleanup in case of failures

## Known Limitations

1. VLAN support depends on host kernel capabilities
2. Some Docker environments (Docker Desktop) have networking limitations
3. MACVLAN may not work in all environments
4. Performance overhead due to nested containerization