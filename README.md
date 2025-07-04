# POD - Platform-agnostic OS Deployment Library

POD is a Python library that provides a unified interface for managing and configuring multiple operating systems (Linux, Windows, Containers). It abstracts away OS-specific differences, allowing you to write code once and run it across different platforms.

## Features

### Multi-OS Support
- **Linux**: SSH-based management for RHEL, Ubuntu, Rocky Linux, and other distributions
- **Windows**: WinRM-based management with PowerShell and CMD support
- **Containers**: Docker/Podman container management with network namespace support
- **Automatic OS Detection**: Factory pattern automatically selects the right handler

### Connection Types
- **SSH**: Linux/Unix systems via paramiko
- **WinRM**: Windows systems via pywinrm
- **Docker/Podman**: Container management via subprocess

### Network Configuration
- **VLAN Support**: Configure VLANs on physical and virtual interfaces
- **Static/DHCP**: Support for both static IP and DHCP configuration
- **Multiple Network Managers**: Works with NetworkManager, systemd-networkd, and direct ip commands
- **Container VLANs**: Special support for VLAN isolation in containers

### System Operations
- **Package Management**: Unified interface for dnf/yum, apt, chocolatey/winget
- **Service Control**: Start, stop, restart, and query service status
- **Process Management**: List processes, check resource usage
- **File Operations**: Upload, download, and verify files across all platforms
- **User Management**: Create users and configure permissions

## Quick Start

### Installation

```bash
pip install -e .
```

### Basic Usage

```python
from pod.connections.ssh import SSHConnection
from pod.os_abstraction.factory import OSHandlerFactory
from pod.os_abstraction.base import NetworkConfig

# Connect to a Linux system
connection = SSHConnection(
    host="192.168.1.100",
    username="admin",
    password="password"
)
connection.connect()

# Automatically detect OS and create appropriate handler
handler = OSHandlerFactory.create_handler(connection)

# Execute commands (same API regardless of OS)
result = handler.execute_command("uname -a")
print(result.stdout)

# Configure network with VLAN
config = NetworkConfig(
    interface="eth1",
    ip_address="192.168.100.10",
    netmask="255.255.255.0",
    gateway="192.168.100.1",
    vlan_id=100
)
handler.configure_network(config)

# Install packages
handler.install_package("tcpdump")

# Disconnect
connection.disconnect()
```

### Windows Example

```python
from pod.connections.winrm import WinRMConnection
from pod.os_abstraction.factory import OSHandlerFactory

# Connect to Windows system
connection = WinRMConnection(
    host="192.168.1.101",
    username="Administrator",
    password="password"
)
connection.connect()

handler = OSHandlerFactory.create_handler(connection)

# Same interface works on Windows
result = handler.get_os_info()
handler.install_package("7zip")
```

### Container Example

```python
from pod.connections.container import DockerConnection
from pod.os_abstraction.container import ContainerHandler

# Connect to container
connection = DockerConnection("my-container")
connection.connect()

handler = ContainerHandler(connection)

# Configure container VLAN
config = NetworkConfig(
    interface="eth0",
    vlan_id=200,
    ip_address="192.168.200.10",
    netmask="255.255.255.0"
)
handler.configure_network(config)
```

## Supported Platforms

| OS Type | Connection | Package Manager | Network Config |
|---------|------------|----------------|----------------|
| Linux (RHEL/Rocky) | SSH | dnf/yum | NetworkManager/systemd |
| Linux (Ubuntu/Debian) | SSH | apt | NetworkManager/systemd |
| Windows | WinRM | winget/chocolatey | PowerShell |
| Containers | Docker/Podman | host package manager | ip commands |

## Examples

See the [examples](examples/) directory for more comprehensive usage examples:

- `basic_usage.py` - Simple connection and command execution
- `multi_os_example.py` - Cross-platform examples
- `docker/` - Container VLAN configuration examples

## Testing

Run the test suite:

```bash
python run_tests.py
```

Run with coverage:

```bash
python run_tests.py --coverage
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - System design and components
- [Examples](examples/) - Usage examples and tutorials

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests (run `python run_tests.py` to verify)
5. Submit a pull request

Tests must pass and coverage should remain above 90%.

## License

MIT License - see LICENSE file for details.