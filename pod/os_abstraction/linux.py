"""
Linux OS handler implementation
"""

import re
import json
import time
from typing import Dict, Any, Optional, List
from .base import BaseOSHandler, CommandResult, NetworkInterface, NetworkConfig
from ..connections.ssh import SSHConnection


class LinuxHandler(BaseOSHandler):
    """Handler for Linux operating systems"""
    
    def execute_command(self, command: str, timeout: int = 30, 
                       as_admin: bool = False) -> CommandResult:
        """Execute command on Linux"""
        start_time = time.time()
        
        if as_admin and not command.startswith('sudo'):
            command = f"sudo {command}"
            
        if isinstance(self.connection, SSHConnection) and as_admin:
            stdout, stderr, exit_code = self.connection.execute_sudo_command(command, timeout=timeout)
        else:
            stdout, stderr, exit_code = self.connection.execute_command(command, timeout=timeout)
            
        duration = time.time() - start_time
        
        return CommandResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            success=exit_code == 0,
            command=command,
            duration=duration
        )
    
    def get_network_interfaces(self) -> List[NetworkInterface]:
        """Get all network interfaces using ip command"""
        interfaces = []
        
        # Get interface details
        result = self.execute_command("ip -j addr show")
        if not result.success:
            # Fallback to non-JSON output
            result = self.execute_command("ip addr show")
            return self._parse_ip_addr_text(result.stdout)
            
        # Parse JSON output
        try:
            iface_data = json.loads(result.stdout)
            for iface in iface_data:
                ip_addresses = []
                netmask = None
                
                for addr_info in iface.get('addr_info', []):
                    if addr_info.get('family') == 'inet':
                        ip_addresses.append(addr_info.get('local'))
                        if not netmask:
                            netmask = self._prefix_to_netmask(addr_info.get('prefixlen', 24))
                            
                # Get MAC address
                mac_address = iface.get('address', '')
                
                # Get VLAN info if available
                vlan_id = None
                if '@' in iface.get('ifname', ''):
                    # VLAN interface like eth0.100@eth0
                    vlan_match = re.search(r'\.(\d+)@', iface['ifname'])
                    if vlan_match:
                        vlan_id = int(vlan_match.group(1))
                        
                interfaces.append(NetworkInterface(
                    name=iface.get('ifname'),
                    mac_address=mac_address,
                    ip_addresses=ip_addresses,
                    netmask=netmask,
                    gateway=self._get_default_gateway(iface.get('ifname')),
                    vlan_id=vlan_id,
                    mtu=iface.get('mtu', 1500),
                    state='up' if 'UP' in iface.get('flags', []) else 'down',
                    type=self._get_interface_type(iface.get('ifname'))
                ))
                
        except json.JSONDecodeError:
            # Fallback to text parsing
            return self._parse_ip_addr_text(result.stdout)
            
        return interfaces
    
    def configure_network(self, config: NetworkConfig) -> CommandResult:
        """Configure network interface"""
        # Detect network management system
        network_manager = self._detect_network_manager()
        
        if network_manager == 'networkmanager':
            return self._configure_network_nm(config)
        elif network_manager == 'systemd-networkd':
            return self._configure_network_systemd(config)
        else:
            # Fallback to ip commands
            return self._configure_network_ip(config)
    
    def restart_network_service(self) -> CommandResult:
        """Restart network service"""
        # Try different network services
        services = [
            'NetworkManager',
            'systemd-networkd', 
            'network',
            'networking'
        ]
        
        for service in services:
            result = self.execute_command(f"systemctl restart {service}", as_admin=True)
            if result.success:
                return result
                
        # Fallback to ifdown/ifup
        return self.execute_command("ifdown -a && ifup -a", as_admin=True)
    
    def get_os_info(self) -> Dict[str, Any]:
        """Get OS information"""
        if self._os_info:
            return self._os_info
            
        info = {
            'type': 'linux',
            'distribution': 'unknown',
            'version': 'unknown',
            'kernel': 'unknown',
            'architecture': 'unknown',
            'hostname': 'unknown'
        }
        
        # Get distribution info
        result = self.execute_command("cat /etc/os-release")
        if result.success:
            for line in result.stdout.split('\n'):
                if line.startswith('NAME='):
                    info['distribution'] = line.split('=')[1].strip('"')
                elif line.startswith('VERSION='):
                    info['version'] = line.split('=')[1].strip('"')
                    
        # Get kernel version
        result = self.execute_command("uname -r")
        if result.success:
            info['kernel'] = result.stdout.strip()
            
        # Get architecture
        result = self.execute_command("uname -m")
        if result.success:
            info['architecture'] = result.stdout.strip()
            
        # Get hostname
        result = self.execute_command("hostname")
        if result.success:
            info['hostname'] = result.stdout.strip()
            
        self._os_info = info
        return info
    
    def install_package(self, package_name: str) -> CommandResult:
        """Install a package using the appropriate package manager"""
        # Detect package manager
        pkg_managers = [
            ('dnf', 'dnf install -y'),      # Fedora, RHEL 8+, Rocky 9
            ('yum', 'yum install -y'),      # RHEL 7, CentOS
            ('apt-get', 'apt-get install -y'),  # Debian, Ubuntu
            ('zypper', 'zypper install -y'),    # openSUSE
            ('pacman', 'pacman -S --noconfirm') # Arch
        ]
        
        for manager, install_cmd in pkg_managers:
            result = self.execute_command(f"which {manager}")
            if result.success:
                return self.execute_command(f"{install_cmd} {package_name}", as_admin=True)
                
        return CommandResult(
            stdout="",
            stderr="No supported package manager found",
            exit_code=1,
            success=False,
            command=f"install {package_name}",
            duration=0
        )
    
    def start_service(self, service_name: str) -> CommandResult:
        """Start a system service"""
        return self.execute_command(f"systemctl start {service_name}", as_admin=True)
    
    def stop_service(self, service_name: str) -> CommandResult:
        """Stop a system service"""
        return self.execute_command(f"systemctl stop {service_name}", as_admin=True)
    
    def get_service_status(self, service_name: str) -> CommandResult:
        """Get service status"""
        return self.execute_command(f"systemctl status {service_name}")
    
    def create_user(self, username: str, password: Optional[str] = None,
                   groups: Optional[List[str]] = None) -> CommandResult:
        """Create a user account"""
        cmd = f"useradd {username}"
        
        if groups:
            cmd += f" -G {','.join(groups)}"
            
        result = self.execute_command(cmd, as_admin=True)
        
        if result.success and password:
            # Set password
            pass_result = self.execute_command(
                f"echo '{username}:{password}' | chpasswd",
                as_admin=True
            )
            return pass_result
            
        return result
    
    def set_hostname(self, hostname: str) -> CommandResult:
        """Set system hostname"""
        return self.execute_command(f"hostnamectl set-hostname {hostname}", as_admin=True)
    
    def get_processes(self) -> List[Dict[str, Any]]:
        """Get running processes"""
        processes = []
        
        result = self.execute_command("ps aux")
        if result.success:
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            for line in lines:
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    processes.append({
                        'user': parts[0],
                        'pid': int(parts[1]),
                        'cpu': float(parts[2]),
                        'memory': float(parts[3]),
                        'vsz': int(parts[4]),
                        'rss': int(parts[5]),
                        'tty': parts[6],
                        'stat': parts[7],
                        'start': parts[8],
                        'time': parts[9],
                        'command': parts[10]
                    })
                    
        return processes
    
    def kill_process(self, process_id: int, signal: int = 15) -> CommandResult:
        """Kill a process"""
        return self.execute_command(f"kill -{signal} {process_id}", as_admin=True)
    
    def get_disk_usage(self) -> List[Dict[str, Any]]:
        """Get disk usage information"""
        disks = []
        
        result = self.execute_command("df -h")
        if result.success:
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            for line in lines:
                parts = line.split()
                if len(parts) >= 6:
                    disks.append({
                        'filesystem': parts[0],
                        'size': parts[1],
                        'used': parts[2],
                        'available': parts[3],
                        'use_percent': parts[4].rstrip('%'),
                        'mount_point': parts[5]
                    })
                    
        return disks
    
    def get_memory_info(self) -> Dict[str, Any]:
        """Get memory information"""
        info = {}
        
        result = self.execute_command("free -b")
        if result.success:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if line.startswith('Mem:'):
                    parts = line.split()
                    info['total'] = int(parts[1])
                    info['used'] = int(parts[2])
                    info['free'] = int(parts[3])
                    info['available'] = int(parts[6]) if len(parts) > 6 else info['free']
                elif line.startswith('Swap:'):
                    parts = line.split()
                    info['swap_total'] = int(parts[1])
                    info['swap_used'] = int(parts[2])
                    info['swap_free'] = int(parts[3])
                    
        return info
    
    def get_cpu_info(self) -> Dict[str, Any]:
        """Get CPU information"""
        info = {
            'count': 0,
            'model': 'unknown',
            'speed_mhz': 0,
            'architecture': 'unknown'
        }
        
        result = self.execute_command("lscpu")
        if result.success:
            for line in result.stdout.split('\n'):
                if line.startswith('CPU(s):'):
                    info['count'] = int(line.split(':')[1].strip())
                elif line.startswith('Model name:'):
                    info['model'] = line.split(':')[1].strip()
                elif line.startswith('CPU MHz:'):
                    info['speed_mhz'] = float(line.split(':')[1].strip())
                elif line.startswith('Architecture:'):
                    info['architecture'] = line.split(':')[1].strip()
                    
        return info
    
    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Upload file to remote system"""
        return self.connection.upload_file(local_path, remote_path)
    
    def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download file from remote system"""
        return self.connection.download_file(remote_path, local_path)
    
    def file_exists(self, path: str) -> bool:
        """Check if file exists"""
        result = self.execute_command(f"test -e '{path}'")
        return result.success
    
    def create_directory(self, path: str, recursive: bool = True) -> CommandResult:
        """Create directory"""
        cmd = f"mkdir {'-p' if recursive else ''} '{path}'"
        return self.execute_command(cmd)
    
    def remove_file(self, path: str) -> CommandResult:
        """Remove file"""
        return self.execute_command(f"rm -f '{path}'")
    
    def list_directory(self, path: str) -> List[Dict[str, Any]]:
        """List directory contents"""
        files = []
        
        result = self.execute_command(f"ls -la '{path}'")
        if result.success:
            lines = result.stdout.strip().split('\n')[1:]  # Skip total line
            for line in lines:
                parts = line.split(None, 8)
                if len(parts) >= 9:
                    files.append({
                        'permissions': parts[0],
                        'links': int(parts[1]),
                        'owner': parts[2],
                        'group': parts[3],
                        'size': int(parts[4]),
                        'date': f"{parts[5]} {parts[6]} {parts[7]}",
                        'name': parts[8]
                    })
                    
        return files
    
    # Helper methods
    def _detect_network_manager(self) -> str:
        """Detect which network management system is in use"""
        # Check for NetworkManager
        result = self.execute_command("systemctl is-active NetworkManager")
        if result.success and result.stdout.strip() == 'active':
            return 'networkmanager'
            
        # Check for systemd-networkd
        result = self.execute_command("systemctl is-active systemd-networkd")
        if result.success and result.stdout.strip() == 'active':
            return 'systemd-networkd'
            
        return 'legacy'
    
    def _configure_network_nm(self, config: NetworkConfig) -> CommandResult:
        """Configure network using NetworkManager"""
        con_name = f"pod-{config.interface}"
        
        # Delete existing connection if exists
        self.execute_command(f"nmcli con delete '{con_name}'", as_admin=True)
        
        # Create new connection
        cmd = f"nmcli con add con-name '{con_name}' ifname {config.interface} type ethernet"
        
        if config.dhcp:
            cmd += " ipv4.method auto"
        else:
            cmd += f" ipv4.method manual ipv4.addresses {config.ip_address}/{self._netmask_to_prefix(config.netmask)}"
            if config.gateway:
                cmd += f" ipv4.gateway {config.gateway}"
            if config.dns_servers:
                cmd += f" ipv4.dns '{','.join(config.dns_servers)}'"
                
        result = self.execute_command(cmd, as_admin=True)
        
        if result.success:
            # Activate connection
            return self.execute_command(f"nmcli con up '{con_name}'", as_admin=True)
            
        return result
    
    def _configure_network_ip(self, config: NetworkConfig) -> CommandResult:
        """Configure network using ip commands"""
        # Bring interface down
        self.execute_command(f"ip link set {config.interface} down", as_admin=True)
        
        # Flush existing addresses
        self.execute_command(f"ip addr flush dev {config.interface}", as_admin=True)
        
        if not config.dhcp:
            # Add IP address
            prefix = self._netmask_to_prefix(config.netmask)
            result = self.execute_command(
                f"ip addr add {config.ip_address}/{prefix} dev {config.interface}",
                as_admin=True
            )
            
            if not result.success:
                return result
                
            # Add default route if gateway specified
            if config.gateway:
                self.execute_command(f"ip route add default via {config.gateway}", as_admin=True)
                
        # Configure MTU if specified
        if config.mtu:
            self.execute_command(f"ip link set {config.interface} mtu {config.mtu}", as_admin=True)
            
        # Bring interface up
        return self.execute_command(f"ip link set {config.interface} up", as_admin=True)
    
    def _prefix_to_netmask(self, prefix: int) -> str:
        """Convert CIDR prefix to netmask"""
        mask = (0xffffffff << (32 - prefix)) & 0xffffffff
        return '.'.join([str((mask >> (8 * i)) & 0xff) for i in range(3, -1, -1)])
    
    def _netmask_to_prefix(self, netmask: str) -> int:
        """Convert netmask to CIDR prefix"""
        return sum(bin(int(x)).count('1') for x in netmask.split('.'))
    
    def _get_default_gateway(self, interface: str) -> Optional[str]:
        """Get default gateway for interface"""
        result = self.execute_command(f"ip route show default dev {interface}")
        if result.success:
            match = re.search(r'default via (\S+)', result.stdout)
            if match:
                return match.group(1)
        return None
    
    def _get_interface_type(self, name: str) -> str:
        """Determine interface type from name"""
        if name.startswith('eth') or name.startswith('en'):
            return 'ethernet'
        elif name.startswith('wl'):
            return 'wifi'
        elif name.startswith('lo'):
            return 'loopback'
        elif name.startswith('docker') or name.startswith('br'):
            return 'virtual'
        else:
            return 'unknown'
    
    def _parse_ip_addr_text(self, output: str) -> List[NetworkInterface]:
        """Parse text output of ip addr command"""
        interfaces = []
        current_iface = None
        
        for line in output.split('\n'):
            # New interface
            match = re.match(r'^\d+: (\S+):', line)
            if match:
                if current_iface:
                    interfaces.append(current_iface)
                    
                iface_name = match.group(1).split('@')[0]  # Handle VLAN interfaces
                current_iface = NetworkInterface(
                    name=iface_name,
                    mac_address='',
                    ip_addresses=[],
                    netmask=None,
                    gateway=None,
                    vlan_id=None,
                    mtu=1500,
                    state='down',
                    type=self._get_interface_type(iface_name)
                )
                
                # Check state - check for explicit state first
                if 'state DOWN' in line:
                    current_iface.state = 'down'
                elif 'state UP' in line or 'UP' in line:
                    current_iface.state = 'up'
                    
                # Get MTU
                mtu_match = re.search(r'mtu (\d+)', line)
                if mtu_match:
                    current_iface.mtu = int(mtu_match.group(1))
                    
            # MAC address
            elif current_iface and 'link/ether' in line:
                mac_match = re.search(r'link/ether (\S+)', line)
                if mac_match:
                    current_iface.mac_address = mac_match.group(1)
                    
            # IP address
            elif current_iface and 'inet ' in line:
                ip_match = re.search(r'inet (\S+)/(\d+)', line)
                if ip_match:
                    current_iface.ip_addresses.append(ip_match.group(1))
                    if not current_iface.netmask:
                        current_iface.netmask = self._prefix_to_netmask(int(ip_match.group(2)))
                        
        if current_iface:
            interfaces.append(current_iface)
            
        return interfaces
    
    def _configure_network_systemd(self, config: NetworkConfig) -> CommandResult:
        """Configure network using systemd-networkd"""
        # Create network file
        network_file = f"/etc/systemd/network/10-{config.interface}.network"
        
        content = f"""[Match]
Name={config.interface}

[Network]
"""
        
        if config.dhcp:
            content += "DHCP=yes\n"
        else:
            prefix = self._netmask_to_prefix(config.netmask)
            content += f"Address={config.ip_address}/{prefix}\n"
            if config.gateway:
                content += f"Gateway={config.gateway}\n"
            if config.dns_servers:
                for dns in config.dns_servers:
                    content += f"DNS={dns}\n"
                    
        # Write file
        self.execute_command(f"echo '{content}' > {network_file}", as_admin=True)
        
        # Restart systemd-networkd
        return self.execute_command("systemctl restart systemd-networkd", as_admin=True)