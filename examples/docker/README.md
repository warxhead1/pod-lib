# Docker Examples for POD Library

This directory contains Docker-related examples for testing and demonstrating the POD library's container support capabilities.

## Docker-in-Docker Test Environment

The `docker-compose.yml` and `Dockerfile.test` files set up a Docker-in-Docker (DinD) environment that allows you to test POD's container management features in an isolated environment.

### Features

- **Multi-VLAN Support**: Demonstrates how to configure containers on separate VLANs
- **Network Isolation**: Each container can be on its own network segment
- **Container Management**: Test POD's ability to manage containers within containers

### Usage

1. Start the test environment:
   ```bash
   docker-compose up -d
   ```

2. Connect to the DinD container:
   ```bash
   docker exec -it pod-dind-test /bin/bash
   ```

3. Inside the container, you can run POD tests:
   ```bash
   python -m pytest tests/integration/test_container_integration.py
   ```

### Network Configuration

The docker-compose file defines multiple networks with different VLAN configurations:

- **vlan100**: 192.168.100.0/24 (VLAN ID: 100)
- **vlan200**: 192.168.200.0/24 (VLAN ID: 200)
- **vlan300**: 192.168.300.0/24 (VLAN ID: 300)

This setup allows testing of the POD library's ability to manage containers across different network segments, simulating a multi-tenant or multi-service environment.

### Container VLAN Example

```python
from pod.connections.container import DockerConnection
from pod.os_abstraction.container import ContainerHandler
from pod.os_abstraction.base import NetworkConfig

# Connect to a container
conn = DockerConnection("my-container")
conn.connect()

# Create handler
handler = ContainerHandler(conn)

# Configure VLAN network
config = NetworkConfig(
    interface="eth0",
    vlan_id=100,
    ip_address="192.168.100.10",
    netmask="255.255.255.0",
    gateway="192.168.100.1"
)

result = handler.configure_network(config)
```

## Security Note

The Docker-in-Docker setup is intended for testing purposes only. Do not use this configuration in production environments without proper security considerations.