"""
Container OS handler implementation with VLAN support
"""

import re
import json
import time
import subprocess
from typing import Dict, Any, Optional, List, Tuple
from .base import BaseOSHandler, CommandResult, NetworkInterface, NetworkConfig
from .linux import LinuxHandler
from ..connections.base import BaseConnection


class ContainerConnection(BaseConnection):
    """Connection handler for Docker containers"""
    
    def __init__(self, container_id: str, use_docker: bool = True):
        """
        Initialize container connection
        
        Args:
            container_id: Container ID or name
            use_docker: Use docker command (True) or podman (False)
        """
        self.container_id = container_id
        self.command_prefix = "docker" if use_docker else "podman"
        self._connected = False
    
    @property
    def default_port(self) -> int:
        """Return default port (not applicable for containers)"""
        return 0
        
    def connect(self, **kwargs):
        """Connect to container (verify it exists and is running)"""
        try:
            # Check if container exists and is running
            cmd = f"{self.command_prefix} inspect {self.container_id}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                container_info = json.loads(result.stdout)
                if isinstance(container_info, list):
                    container_info = container_info[0]
                    
                state = container_info.get('State', {})
                if state.get('Running', False):
                    self._connected = True
                else:
                    # Try to start the container
                    cmd = f"{self.command_prefix} start {self.container_id}"
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    if result.returncode == 0:
                        self._connected = True
                    else:
                        raise ConnectionError(f"Failed to start container: {result.stderr}")
            else:
                raise ConnectionError(f"Container not found: {result.stderr}")
                
        except Exception as e:
            raise ConnectionError(f"Failed to connect to container: {str(e)}")
            
    def disconnect(self):
        """Disconnect from container"""
        self._connected = False
        
    def is_connected(self) -> bool:
        """Check if connected to container"""
        if not self._connected:
            return False
            
        # Verify container is still running
        cmd = f"{self.command_prefix} inspect {self.container_id} --format='{{{{.State.Running}}}}'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        return result.returncode == 0 and result.stdout.strip() == 'true'
        
    def execute_command(self, command: str, timeout: int = 30) -> Tuple[str, str, int]:
        """Execute command in container"""
        if not self.is_connected():
            raise ConnectionError("Not connected to container")
            
        # Build docker/podman exec command
        exec_cmd = f"{self.command_prefix} exec {self.container_id} /bin/bash -c '{command}'"
        
        try:
            result = subprocess.run(
                exec_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return result.stdout, result.stderr, result.returncode
            
        except subprocess.TimeoutExpired:
            return "", f"Command timed out after {timeout} seconds", 124
            
    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Upload file to container"""
        cmd = f"{self.command_prefix} cp '{local_path}' {self.container_id}:'{remote_path}'"
        result = subprocess.run(cmd, shell=True, capture_output=True)
        return result.returncode == 0
        
    def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download file from container"""
        cmd = f"{self.command_prefix} cp {self.container_id}:'{remote_path}' '{local_path}'"
        result = subprocess.run(cmd, shell=True, capture_output=True)
        return result.returncode == 0


class ContainerHandler(LinuxHandler):
    """
    Handler for containers with VLAN support
    Extends LinuxHandler since containers typically run Linux
    """
    
    def __init__(self, connection: ContainerConnection, host_bridge: Optional[str] = None):
        """
        Initialize container handler
        
        Args:
            connection: Container connection
            host_bridge: Optional host bridge name for VLAN configuration
        """
        super().__init__(connection)
        self.host_bridge = host_bridge or "br0"
        self._container_info = None
        
    def configure_network(self, config: NetworkConfig) -> CommandResult:
        """
        Configure network with VLAN support
        
        This method supports creating VLAN interfaces inside containers
        and connecting them to host bridges for network isolation
        """
        if config.vlan_id is not None:
            # Configure VLAN interface in container
            return self._configure_vlan_network(config)
        else:
            # Use standard Linux network configuration
            return super().configure_network(config)
            
    def _configure_vlan_network(self, config: NetworkConfig) -> CommandResult:
        """Configure VLAN network for container"""
        # First, ensure vlan module is loaded (containers are privileged)
        self.execute_command("modprobe 8021q")
        
        # Create VLAN interface
        vlan_iface = f"{config.interface}.{config.vlan_id}"
        
        # Remove existing VLAN interface if exists
        self.execute_command(f"ip link delete {vlan_iface}")
        
        # Create new VLAN interface
        result = self.execute_command(
            f"ip link add link {config.interface} name {vlan_iface} type vlan id {config.vlan_id}"
        )
        
        if not result.success:
            return result
            
        # Bring up the VLAN interface
        result = self.execute_command(f"ip link set {vlan_iface} up")
        
        if not result.success:
            return result
            
        # Configure IP on VLAN interface
        if not config.dhcp:
            prefix = self._netmask_to_prefix(config.netmask) if config.netmask else 24
            result = self.execute_command(
                f"ip addr add {config.ip_address}/{prefix} dev {vlan_iface}"
            )
            
            if not result.success:
                return result
                
            # Add default route if gateway specified
            if config.gateway:
                # Remove existing default routes
                self.execute_command("ip route del default")
                
                # Add new default route
                result = self.execute_command(
                    f"ip route add default via {config.gateway} dev {vlan_iface}"
                )
                
        # Configure DNS if specified
        if config.dns_servers:
            dns_config = "\n".join(f"nameserver {dns}" for dns in config.dns_servers)
            self.execute_command(f"echo '{dns_config}' > /etc/resolv.conf")
            
        return CommandResult(
            stdout=f"VLAN {config.vlan_id} configured on {config.interface}",
            stderr="",
            exit_code=0,
            success=True,
            command="configure_vlan_network",
            duration=0
        )
        
    def install_package(self, package_name: str) -> CommandResult:
        """Install a package using the appropriate package manager (privileged containers)"""
        # Detect package manager
        pkg_managers = [
            ('apt-get', 'apt-get update && apt-get install -y'),  # Debian, Ubuntu
            ('dnf', 'dnf install -y'),      # Fedora, RHEL 8+, Rocky 9
            ('yum', 'yum install -y'),      # RHEL 7, CentOS
            ('zypper', 'zypper install -y'),    # openSUSE
            ('pacman', 'pacman -S --noconfirm') # Arch
        ]
        
        for manager, install_cmd in pkg_managers:
            result = self.execute_command(f"which {manager}")
            if result.success:
                # No as_admin needed for privileged containers
                return self.execute_command(f"{install_cmd} {package_name}")
                
        return CommandResult(
            stdout="",
            stderr="No supported package manager found",
            exit_code=1,
            success=False,
            command=f"install {package_name}",
            duration=0
        )
        
    def create_vlan_bridge(self, bridge_name: str, vlan_id: int, 
                          physical_interface: str = "eth0") -> CommandResult:
        """
        Create a bridge for VLAN traffic in the container
        This allows multiple containers to share the same VLAN
        """
        # Install bridge utilities if not present
        self.install_package("bridge-utils")
        
        # Create bridge
        self.execute_command(f"brctl addbr {bridge_name}")
        
        # Create VLAN interface
        vlan_iface = f"{physical_interface}.{vlan_id}"
        result = self.execute_command(
            f"ip link add link {physical_interface} name {vlan_iface} type vlan id {vlan_id}"
        )
        
        if result.success:
            # Add VLAN interface to bridge
            self.execute_command(f"brctl addif {bridge_name} {vlan_iface}")
            
            # Bring up bridge and VLAN interface
            self.execute_command(f"ip link set {bridge_name} up")
            self.execute_command(f"ip link set {vlan_iface} up")
            
        return result
        
    def add_veth_pair(self, veth_name: str, peer_name: str, 
                     bridge_name: Optional[str] = None) -> CommandResult:
        """
        Create veth pair for container networking
        Useful for connecting containers to specific VLANs
        """
        # Create veth pair
        result = self.execute_command(
            f"ip link add {veth_name} type veth peer name {peer_name}",
            as_admin=True
        )
        
        if result.success and bridge_name:
            # Add veth to bridge
            self.execute_command(f"brctl addif {bridge_name} {veth_name}", as_admin=True)
            
            # Bring up interfaces
            self.execute_command(f"ip link set {veth_name} up", as_admin=True)
            self.execute_command(f"ip link set {peer_name} up", as_admin=True)
            
        return result
        
    def get_container_info(self) -> Dict[str, Any]:
        """Get container information"""
        if self._container_info:
            return self._container_info
            
        info = {
            'type': 'container',
            'container_id': '',
            'image': '',
            'created': '',
            'status': '',
            'networks': []
        }
        
        if isinstance(self.connection, ContainerConnection):
            # Get container info from host
            cmd = f"{self.connection.command_prefix} inspect {self.connection.container_id}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    if isinstance(data, list):
                        data = data[0]
                        
                    info['container_id'] = data.get('Id', '')[:12]
                    info['image'] = data.get('Config', {}).get('Image', '')
                    info['created'] = data.get('Created', '')
                    info['status'] = data.get('State', {}).get('Status', '')
                    
                    # Get network info
                    networks = data.get('NetworkSettings', {}).get('Networks', {})
                    for net_name, net_info in networks.items():
                        info['networks'].append({
                            'name': net_name,
                            'ip_address': net_info.get('IPAddress', ''),
                            'gateway': net_info.get('Gateway', ''),
                            'mac_address': net_info.get('MacAddress', '')
                        })
                        
                except json.JSONDecodeError:
                    pass
                    
        self._container_info = info
        return info
        
    def get_os_info(self) -> Dict[str, Any]:
        """Get OS information from container"""
        # Get base Linux OS info
        info = super().get_os_info()
        
        # Add container-specific info
        container_info = self.get_container_info()
        info['container'] = True
        info['container_id'] = container_info['container_id']
        info['container_image'] = container_info['image']
        
        return info
        
    def configure_container_networking(self, vlan_configs: List[Dict[str, Any]]) -> List[CommandResult]:
        """
        Configure multiple VLAN interfaces for the container
        
        Args:
            vlan_configs: List of VLAN configurations, each containing:
                - vlan_id: VLAN ID
                - ip_address: IP address for this VLAN
                - netmask: Network mask
                - interface: Base interface (default: eth0)
                
        Returns:
            List of command results for each VLAN configuration
        """
        results = []
        
        # Load 8021q module
        self.execute_command("modprobe 8021q", as_admin=True)
        
        for config in vlan_configs:
            vlan_id = config['vlan_id']
            ip_address = config['ip_address']
            netmask = config.get('netmask', '255.255.255.0')
            interface = config.get('interface', 'eth0')
            
            # Create network config
            net_config = NetworkConfig(
                interface=interface,
                ip_address=ip_address,
                netmask=netmask,
                vlan_id=vlan_id,
                dhcp=False
            )
            
            result = self.configure_network(net_config)
            results.append(result)
            
        return results
        
    def create_macvlan_interface(self, name: str, parent: str, 
                               vlan_id: Optional[int] = None) -> CommandResult:
        """
        Create MACVLAN interface for container
        This allows containers to appear as separate hosts on the network
        """
        if vlan_id:
            # Create VLAN interface first
            vlan_parent = f"{parent}.{vlan_id}"
            self.execute_command(
                f"ip link add link {parent} name {vlan_parent} type vlan id {vlan_id}",
                as_admin=True
            )
            self.execute_command(f"ip link set {vlan_parent} up", as_admin=True)
            parent = vlan_parent
            
        # Create MACVLAN interface
        result = self.execute_command(
            f"ip link add {name} link {parent} type macvlan mode bridge",
            as_admin=True
        )
        
        if result.success:
            self.execute_command(f"ip link set {name} up", as_admin=True)
            
        return result