#!/usr/bin/env python3
"""
Example demonstrating multi-OS support with automatic OS detection
"""

from pod import PODClient
from pod.os_abstraction import NetworkConfig, OSHandlerFactory
from pod.connections import SSHConnection, WinRMConnection, DockerConnection
from pod.os_abstraction import ContainerHandler


def example_auto_os_detection():
    """Example: Automatic OS detection and handler creation"""
    print("=== Automatic OS Detection Example ===\n")
    
    # Initialize POD client
    client = PODClient(
        vsphere_host="vcenter.example.com",
        vsphere_username="admin@vsphere.local",
        vsphere_password="password"
    )
    
    # Connect to vSphere
    client.connect()
    
    # Get VMs with different OS types
    vms = [
        ("linux-server", "root", "password"),
        ("windows-server", "Administrator", "password"),
        ("ubuntu-desktop", "user", "password")
    ]
    
    for vm_name, username, password in vms:
        print(f"\nProcessing VM: {vm_name}")
        
        # Get VM from vSphere
        vm = client.get_vm(vm_name)
        
        # Get OS info from vSphere
        os_info = {
            'guest_id': vm.guest_id,
            'guest_family': vm.guest_family
        }
        
        # Power on and get IP
        vm.power_on(wait_for_ip=True)
        ip_address = vm.get_ip_address()
        
        # Create appropriate connection based on OS
        if 'windows' in os_info.get('guest_family', '').lower():
            connection = WinRMConnection(ip_address)
        else:
            connection = SSHConnection(ip_address)
            
        connection.connect(username=username, password=password)
        
        # Create OS handler automatically
        handler = OSHandlerFactory.create_handler(connection, os_info)
        
        # Now use the handler - same API for all OS types!
        os_details = handler.get_os_info()
        print(f"  OS Type: {os_details['type']}")
        print(f"  Distribution: {os_details['distribution']}")
        print(f"  Version: {os_details['version']}")
        
        # Configure network - same API works for all OS types
        network_config = NetworkConfig(
            interface="eth0" if os_details['type'] == 'linux' else "Ethernet",
            ip_address="192.168.100.10",
            netmask="255.255.255.0",
            gateway="192.168.100.1",
            vlan_id=100
        )
        
        result = handler.configure_network(network_config)
        print(f"  Network configured: {result.success}")
        
        # Install a package - handler knows the right package manager
        result = handler.install_package("curl")
        print(f"  Package installed: {result.success}")


def example_container_with_vlans():
    """Example: Container with multiple VLAN support"""
    print("\n=== Container with VLAN Support Example ===\n")
    
    # Connect to a container
    container_conn = DockerConnection("test-container")
    container_conn.connect()
    
    # Create container handler
    handler = ContainerHandler(container_conn, host_bridge="br0")
    
    # Configure multiple VLANs for the container
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
        },
        {
            'vlan_id': 300,
            'ip_address': '192.168.300.10',
            'netmask': '255.255.255.0',
            'interface': 'eth0'
        }
    ]
    
    print("Configuring multiple VLANs on container...")
    results = handler.configure_container_networking(vlan_configs)
    
    for i, (config, result) in enumerate(zip(vlan_configs, results)):
        print(f"  VLAN {config['vlan_id']}: {'Success' if result.success else 'Failed'}")
        if result.success:
            print(f"    IP: {config['ip_address']}")
    
    # Create MACVLAN interface for container to appear as separate host
    print("\nCreating MACVLAN interface...")
    result = handler.create_macvlan_interface("macvlan0", "eth0", vlan_id=400)
    print(f"  MACVLAN created: {result.success}")
    
    # Show network interfaces
    interfaces = handler.get_network_interfaces()
    print("\nContainer network interfaces:")
    for iface in interfaces:
        if iface.ip_addresses:
            print(f"  {iface.name}: {', '.join(iface.ip_addresses)}")
            if iface.vlan_id:
                print(f"    VLAN: {iface.vlan_id}")


def example_windows_specific():
    """Example: Windows-specific operations"""
    print("\n=== Windows-Specific Operations Example ===\n")
    
    # Connect to Windows VM
    win_conn = WinRMConnection("192.168.1.100")
    win_conn.connect(username="Administrator", password="password")
    
    # Create Windows handler
    from pod.os_abstraction import WindowsHandler
    handler = WindowsHandler(win_conn)
    
    # Windows-specific: PowerShell execution
    print("Executing PowerShell commands...")
    result = handler.execute_powershell("""
        Get-Service | Where-Object {$_.Status -eq 'Running'} | 
        Select-Object -First 5 | Format-Table Name, DisplayName
    """)
    print(f"Running services:\n{result.stdout}")
    
    # Configure Windows network with VLAN
    print("\nConfiguring Windows network with VLAN...")
    config = NetworkConfig(
        interface="Ethernet",
        ip_address="192.168.100.50",
        netmask="255.255.255.0",
        gateway="192.168.100.1",
        dns_servers=["8.8.8.8", "8.8.4.4"],
        vlan_id=100
    )
    
    result = handler.configure_network(config)
    print(f"Network configured: {result.success}")
    
    # Install software using Windows package managers
    print("\nInstalling software...")
    result = handler.install_package("7zip")
    print(f"7zip installation: {result.success}")
    
    # Windows service management
    print("\nManaging Windows services...")
    result = handler.get_service_status("Spooler")
    if result.success:
        import json
        service_info = json.loads(result.stdout)
        print(f"Print Spooler status: {service_info['Status']}")


def example_multi_container_vlan_isolation():
    """Example: Multiple containers on different VLANs on same host"""
    print("\n=== Multi-Container VLAN Isolation Example ===\n")
    
    # This demonstrates how to run multiple containers on the same host
    # with each container on different VLANs for network isolation
    
    containers = [
        ("web-container-1", 100, "192.168.100.10"),
        ("web-container-2", 100, "192.168.100.11"),
        ("db-container", 200, "192.168.200.10"),
        ("app-container", 300, "192.168.300.10")
    ]
    
    for container_name, vlan_id, ip_address in containers:
        print(f"\nConfiguring {container_name}:")
        
        # Connect to container
        conn = DockerConnection(container_name)
        try:
            conn.connect()
        except:
            print(f"  Creating container {container_name}...")
            # In real scenario, create the container first
            continue
            
        handler = ContainerHandler(conn)
        
        # Configure VLAN
        config = NetworkConfig(
            interface="eth0",
            ip_address=ip_address,
            netmask="255.255.255.0",
            gateway=f"192.168.{vlan_id}.1",
            vlan_id=vlan_id
        )
        
        result = handler.configure_network(config)
        print(f"  VLAN {vlan_id} configured: {result.success}")
        print(f"  IP address: {ip_address}")
        
        # Test connectivity within VLAN
        if result.success:
            # Containers on same VLAN can communicate
            # Containers on different VLANs are isolated
            test_result = handler.execute_command(f"ping -c 1 192.168.{vlan_id}.1")
            print(f"  Gateway reachable: {test_result.success}")


if __name__ == "__main__":
    # Run examples
    print("POD Multi-OS Support Examples")
    print("=" * 50)
    
    # Uncomment the examples you want to run
    
    # example_auto_os_detection()
    # example_container_with_vlans()
    # example_windows_specific()
    # example_multi_container_vlan_isolation()
    
    print("\nNote: These are example demonstrations.")
    print("Ensure you have the appropriate infrastructure set up before running.")