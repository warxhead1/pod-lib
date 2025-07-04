# POD Library Examples

This directory contains various examples demonstrating how to use the POD (Platform-agnostic OS Deployment) library.

## Examples Overview

### Basic Usage
- `basic_usage.py` - Simple example showing how to connect to VMs and execute commands
- `pod_demo.py` - Comprehensive demo of POD features including network configuration

### Multi-OS Support
- `multi_os_example.py` - Demonstrates the multi-OS capabilities (Linux, Windows, Containers)

### Container Management
- `test_container_local.py` - Local container testing examples
- `test_pod_functionality.py` - Full POD functionality testing suite

### Docker Examples
- `docker/` - Docker-in-Docker setup for testing container VLAN support
  - See [docker/README.md](docker/README.md) for detailed Docker examples

## Quick Start

### Basic VM Connection

```python
from pod.connections.ssh import SSHConnection
from pod.os_abstraction.linux import LinuxHandler

# Connect to a Linux VM
conn = SSHConnection(host="192.168.1.100", username="admin", password="password")
conn.connect()

# Create OS handler
handler = LinuxHandler(conn)

# Execute commands
result = handler.execute_command("uname -a")
print(result.stdout)

# Disconnect
conn.disconnect()
```

### Multi-OS with Factory

```python
from pod.connections.ssh import SSHConnection
from pod.connections.winrm import WinRMConnection
from pod.os_abstraction.factory import OSFactory

# Linux VM
linux_conn = SSHConnection("linux-host", "user", "pass")
linux_handler = OSFactory.create_handler(linux_conn)

# Windows VM
win_conn = WinRMConnection("windows-host", "Administrator", "pass")
win_handler = OSFactory.create_handler(win_conn)

# Commands work the same way regardless of OS
for handler in [linux_handler, win_handler]:
    result = handler.get_os_info()
    print(f"OS: {result}")
```

### Container with VLAN

```python
from pod.connections.container import DockerConnection
from pod.os_abstraction.container import ContainerHandler
from pod.os_abstraction.base import NetworkConfig

# Connect to container
conn = DockerConnection("my-container")
conn.connect()

handler = ContainerHandler(conn)

# Configure VLAN
config = NetworkConfig(
    interface="eth0",
    vlan_id=100,
    ip_address="192.168.100.10",
    netmask="255.255.255.0"
)

result = handler.configure_network(config)
```

## Running the Examples

1. Install POD library:
   ```bash
   pip install -e ..
   ```

2. Run any example:
   ```bash
   python basic_usage.py
   ```

## Note

Most examples require actual infrastructure (VMs, containers) to connect to. For testing without real infrastructure, see the Docker examples which provide an isolated test environment.