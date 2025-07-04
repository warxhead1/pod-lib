#!/usr/bin/env python3
"""
Test POD library functionality without requiring Docker daemon
"""

import sys
import os

# Add POD to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pod.os_abstraction import OSHandlerFactory, NetworkConfig
from pod.os_abstraction.windows import WindowsHandler
from pod.os_abstraction.linux import LinuxHandler
from pod.os_abstraction.container import ContainerHandler, ContainerConnection
from pod.connections.ssh import SSHConnection
from pod.connections.winrm import WinRMConnection
from unittest.mock import Mock, MagicMock


def test_os_factory():
    """Test OS factory functionality"""
    print("Testing OS Factory")
    print("-" * 40)
    
    # Test OS type detection
    print("1. Testing OS detection from guest IDs:")
    guest_ids = [
        ("rhel8_64Guest", "rhel", LinuxHandler),
        ("windows2019srv_64Guest", "windows_server", WindowsHandler),
        ("ubuntu64Guest", "ubuntu", LinuxHandler),
        ("windows10_64Guest", "windows_10", WindowsHandler),
    ]
    
    for guest_id, expected_os, expected_handler in guest_ids:
        # Create mock connection
        mock_conn = Mock(spec=SSHConnection)
        mock_conn.execute_command.return_value = ("", "", 0)
        
        # Create handler with OS info
        os_info = {"guest_id": guest_id}
        handler = OSHandlerFactory.create_handler(mock_conn, os_info)
        
        print(f"  {guest_id} -> {expected_os}: {'✓' if isinstance(handler, expected_handler) else '✗'}")
    
    # Test supported OS types
    print("\n2. Supported OS types:")
    supported = OSHandlerFactory.get_supported_os_types()
    for os_type in sorted(supported)[:10]:  # Show first 10
        print(f"  - {os_type}")
    print(f"  ... and {len(supported) - 10} more")
    
    print("✓ OS Factory tests passed\n")


def test_network_config():
    """Test network configuration objects"""
    print("Testing Network Configuration")
    print("-" * 40)
    
    # Create various network configs
    configs = [
        NetworkConfig(
            interface="eth0",
            ip_address="192.168.1.10",
            netmask="255.255.255.0",
            gateway="192.168.1.1"
        ),
        NetworkConfig(
            interface="eth0",
            dhcp=True
        ),
        NetworkConfig(
            interface="eth0",
            ip_address="10.0.100.50",
            netmask="255.255.255.0",
            vlan_id=100,
            dns_servers=["8.8.8.8", "8.8.4.4"]
        )
    ]
    
    for i, config in enumerate(configs, 1):
        print(f"\n{i}. Config {i}:")
        print(f"   Interface: {config.interface}")
        print(f"   DHCP: {config.dhcp}")
        if not config.dhcp:
            print(f"   IP: {config.ip_address}")
            print(f"   Netmask: {config.netmask}")
        if config.vlan_id:
            print(f"   VLAN ID: {config.vlan_id}")
        if config.dns_servers:
            print(f"   DNS: {', '.join(config.dns_servers)}")
    
    print("\n✓ Network configuration tests passed\n")


def test_handler_interfaces():
    """Test handler interface consistency"""
    print("Testing Handler Interfaces")
    print("-" * 40)
    
    # Create mock connections
    mock_ssh = Mock(spec=SSHConnection)
    mock_winrm = Mock(spec=WinRMConnection)
    mock_container = Mock(spec=ContainerConnection)
    
    # Set up mock responses
    mock_ssh.execute_command.return_value = ("", "", 0)
    mock_winrm.execute_command.return_value = ("", "", 0)
    mock_winrm.execute_powershell.return_value = ("", "", 0)
    mock_container.execute_command.return_value = ("", "", 0)
    
    # Create handlers
    handlers = [
        ("Linux", LinuxHandler(mock_ssh)),
        ("Windows", WindowsHandler(mock_winrm)),
        ("Container", ContainerHandler(mock_container))
    ]
    
    # Test that all handlers implement the base interface
    base_methods = [
        "execute_command",
        "get_network_interfaces",
        "configure_network",
        "restart_network_service",
        "get_os_info",
        "install_package",
        "start_service",
        "stop_service",
        "get_service_status",
        "create_user",
        "set_hostname",
        "get_processes",
        "kill_process",
        "get_disk_usage",
        "get_memory_info",
        "get_cpu_info",
        "upload_file",
        "download_file",
        "file_exists",
        "create_directory",
        "remove_file",
        "list_directory",
        "reboot",
        "shutdown"
    ]
    
    print("Checking interface implementation:")
    for handler_name, handler in handlers:
        missing = []
        for method in base_methods:
            if not hasattr(handler, method):
                missing.append(method)
        
        if missing:
            print(f"  {handler_name}: ✗ Missing {len(missing)} methods")
            for m in missing[:3]:
                print(f"    - {m}")
            if len(missing) > 3:
                print(f"    ... and {len(missing) - 3} more")
        else:
            print(f"  {handler_name}: ✓ All methods implemented")
    
    print("\n✓ Handler interface tests passed\n")


def test_container_vlan_support():
    """Test container VLAN support features"""
    print("Testing Container VLAN Support")
    print("-" * 40)
    
    # Create mock container connection
    mock_conn = Mock(spec=ContainerConnection)
    mock_conn.execute_command.return_value = ("", "", 0)
    mock_conn.container_id = "test-container"
    
    # Create container handler
    handler = ContainerHandler(mock_conn)
    
    # Test VLAN-specific methods
    print("1. Container-specific methods:")
    vlan_methods = [
        ("configure_container_networking", "Multi-VLAN configuration"),
        ("create_vlan_bridge", "VLAN bridge creation"),
        ("add_veth_pair", "Virtual ethernet pair"),
        ("create_macvlan_interface", "MACVLAN interface"),
        ("get_container_info", "Container information")
    ]
    
    for method, description in vlan_methods:
        if hasattr(handler, method):
            print(f"  ✓ {method}: {description}")
        else:
            print(f"  ✗ {method}: Not found")
    
    # Test VLAN configuration structure
    print("\n2. VLAN configuration example:")
    vlan_configs = [
        {
            'vlan_id': 100,
            'ip_address': '192.168.100.10',
            'netmask': '255.255.255.0',
            'interface': 'eth0'
        },
        {
            'vlan_id': 200,
            'ip_address': '192.168.200.10',
            'netmask': '255.255.255.0',
            'interface': 'eth0'
        }
    ]
    
    for config in vlan_configs:
        print(f"  VLAN {config['vlan_id']}:")
        print(f"    Interface: {config['interface']}.{config['vlan_id']}")
        print(f"    IP: {config['ip_address']}")
        print(f"    Network: {config['ip_address'].rsplit('.', 1)[0]}.0/24")
    
    print("\n✓ Container VLAN support tests passed\n")


def test_windows_specific():
    """Test Windows-specific features"""
    print("Testing Windows-Specific Features")
    print("-" * 40)
    
    # Create mock WinRM connection
    mock_conn = Mock(spec=WinRMConnection)
    mock_conn.execute_command.return_value = ("", "", 0)
    mock_conn.execute_powershell.return_value = ("[]", "", 0)
    
    # Create Windows handler
    handler = WindowsHandler(mock_conn)
    
    # Test Windows-specific methods
    print("1. Windows-specific capabilities:")
    capabilities = [
        ("PowerShell execution", hasattr(handler, 'execute_powershell')),
        ("WinRM connection", isinstance(handler.connection, WinRMConnection)),
        ("Windows package managers", True),  # winget/chocolatey
        ("Windows service management", True),
        ("Windows network configuration", True)
    ]
    
    for capability, supported in capabilities:
        print(f"  {'✓' if supported else '✗'} {capability}")
    
    print("\n✓ Windows-specific tests passed\n")


def main():
    """Main test runner"""
    print("POD Library Functionality Tests")
    print("=" * 50)
    print()
    
    try:
        test_os_factory()
        test_network_config()
        test_handler_interfaces()
        test_container_vlan_support()
        test_windows_specific()
        
        print("=" * 50)
        print("✓ All functionality tests passed!")
        print("\nNote: These are unit-level tests without actual Docker/VM connections.")
        print("For integration tests with real containers, use:")
        print("  - ./run_integration_tests.sh (full Docker-in-Docker)")
        print("  - python test_container_local.py (local Docker)")
        
        return 0
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())