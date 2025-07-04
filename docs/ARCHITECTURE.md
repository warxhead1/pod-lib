# POD Library Architecture

This document describes the architecture and design principles of the POD (Platform-agnostic OS Deployment) library.

## Overview

POD is built around a layered architecture that abstracts OS-specific operations behind a unified interface. The library follows the adapter pattern to provide consistent APIs across different operating systems and connection types.

## Core Principles

1. **Platform Abstraction**: Hide OS-specific differences behind common interfaces
2. **Connection Separation**: Separate connection management from OS operations
3. **Factory Pattern**: Automatic detection and instantiation of appropriate handlers
4. **Composition over Inheritance**: Favor object composition for flexibility
5. **Fail Fast**: Validate inputs early and provide clear error messages

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                        │
│  (User code using POD library)                             │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                 OS Abstraction Layer                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ LinuxHandler│  │WindowsHandler│  │ContainerHandler│      │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
│                   BaseOSHandler (Abstract Base)            │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                  Connection Layer                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │SSHConnection│  │WinRMConnection│ │DockerConnection│      │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
│                  BaseConnection (Abstract Base)            │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                   Transport Layer                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   paramiko  │  │   pywinrm   │  │  subprocess │        │
│  │   (SSH)     │  │   (WinRM)   │  │  (Docker)   │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Connection Layer

The connection layer handles low-level communication with target systems.

#### BaseConnection (Abstract)
- Defines common interface for all connection types
- Manages connection state and basic operations
- Provides context manager support

#### SSHConnection
- Uses paramiko for SSH connectivity
- Supports password and key-based authentication
- Handles connection pooling and reconnection

#### WinRMConnection
- Uses pywinrm for Windows Remote Management
- Supports multiple authentication methods (NTLM, Kerberos)
- Handles PowerShell and CMD execution

#### DockerConnection / ContainerConnection
- Uses subprocess to invoke docker/podman commands
- Manages container lifecycle
- Provides network namespace capabilities

### 2. OS Abstraction Layer

The OS abstraction layer provides a unified interface for system operations.

#### BaseOSHandler (Abstract)
- Defines common interface for all OS operations
- Standardizes method signatures and return types
- Provides default implementations where possible

#### LinuxHandler
- Implements Linux-specific operations
- Supports multiple package managers (dnf/yum, apt, zypper, pacman)
- Handles different network managers (NetworkManager, systemd-networkd)
- Provides VLAN configuration via 802.1q module

#### WindowsHandler
- Implements Windows-specific operations via PowerShell
- Supports multiple package managers (winget, chocolatey)
- Uses WMI for system information
- Handles Windows network configuration

#### ContainerHandler
- Extends LinuxHandler for container environments
- Adds container-specific network capabilities
- Supports VLAN configuration via MACVLAN interfaces
- Provides network namespace isolation

### 3. Factory Pattern

The OSHandlerFactory automatically detects the target OS and creates appropriate handlers.

```python
class OSHandlerFactory:
    @classmethod
    def create_handler(cls, connection, os_info=None):
        # Detect OS type
        # Return appropriate handler instance
```

Detection logic:
1. Check connection type (WinRM → Windows, Docker → Container)
2. Execute OS detection commands if needed
3. Map OS information to handler type
4. Instantiate and return handler

### 4. Data Models

#### NetworkConfig
Represents network configuration parameters:
- Interface name
- IP address and netmask
- Gateway and DNS servers
- VLAN ID
- DHCP vs static configuration

#### CommandResult
Standardizes command execution results:
- stdout, stderr, exit_code
- Success flag and duration
- Original command for debugging

## Network Architecture

### VLAN Support

The library provides comprehensive VLAN support across all platforms:

#### Linux VLAN Implementation
```
Physical Interface (eth0)
    └── VLAN Interface (eth0.100)
        └── IP Configuration (192.168.100.10/24)
```

Uses 802.1q kernel module:
```bash
modprobe 8021q
ip link add link eth0 name eth0.100 type vlan id 100
ip addr add 192.168.100.10/24 dev eth0.100
```

#### Container VLAN Implementation
```
Host Network Namespace
    └── MACVLAN Interface
        └── Container Network Namespace
            └── VLAN Interface
```

Uses MACVLAN for isolation:
```bash
docker network create -d macvlan \
  --subnet=192.168.100.0/24 \
  --gateway=192.168.100.1 \
  -o parent=eth0.100 vlan100
```

#### Windows VLAN Implementation
Uses PowerShell and native Windows networking:
```powershell
New-NetIPAddress -InterfaceAlias "Ethernet 2" -IPAddress "192.168.100.10" -PrefixLength 24
```

## Error Handling

### Exception Hierarchy
```
PODException (Base)
├── ConnectionError
├── AuthenticationError
├── TimeoutError
├── NetworkConfigError
└── CommandExecutionError
```

### Error Handling Strategy
1. **Connection Errors**: Retry with backoff, then fail
2. **Authentication Errors**: Fail immediately with clear message
3. **Command Errors**: Return error in CommandResult, don't raise
4. **Network Errors**: Validate configuration before applying

## Testing Architecture

### Test Structure
```
tests/
├── unit/           # Unit tests for individual components
├── integration/    # Integration tests with real systems
└── fixtures/       # Test data and mock objects
```

### Mock Strategy
- Mock external dependencies (paramiko, pywinrm, subprocess)
- Use real objects for internal components
- Provide configurable mock responses

### Coverage Goals
- Maintain >90% test coverage
- Cover all platform-specific code paths
- Test error conditions and edge cases

## Performance Considerations

### Connection Pooling
- Reuse SSH connections when possible
- Implement connection timeouts
- Handle connection cleanup properly

### Network Operations
- Validate configurations before applying
- Use atomic operations where possible
- Provide rollback capabilities for complex changes

### Memory Management
- Clean up temporary files
- Close file handles and sockets
- Avoid holding large objects in memory

## Security Considerations

### Credential Handling
- Never log passwords or keys
- Support secure credential storage
- Use secure defaults for connections

### Command Injection
- Validate and sanitize all inputs
- Use parameterized commands where possible
- Escape special characters properly

### Network Security
- Validate IP addresses and ranges
- Check for privilege escalation needs
- Audit network configuration changes

## Extension Points

### Adding New OS Support
1. Create new handler class inheriting from BaseOSHandler
2. Implement all abstract methods
3. Add OS detection logic to OSHandlerFactory
4. Add tests for new platform

### Adding New Connection Types
1. Create new connection class inheriting from BaseConnection
2. Implement all abstract methods
3. Update factory logic if needed
4. Add integration tests

### Adding New Features
1. Add method to BaseOSHandler interface
2. Implement in all concrete handlers
3. Add appropriate tests
4. Update documentation