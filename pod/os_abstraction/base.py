"""
Base OS interface for all operating systems
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class CommandResult:
    """Normalized command execution result"""
    stdout: str
    stderr: str
    exit_code: int
    success: bool
    command: str
    duration: float
    data: Optional[Dict[str, Any]] = None  # Parsed structured data
    
    def __bool__(self) -> bool:
        return self.success


@dataclass 
class NetworkInterface:
    """Normalized network interface info"""
    name: str
    mac_address: str
    ip_addresses: List[str]
    netmask: Optional[str]
    gateway: Optional[str] 
    vlan_id: Optional[int]
    mtu: int
    state: str  # up/down
    type: str  # ethernet/wifi/virtual


@dataclass
class NetworkConfig:
    """Network configuration request"""
    interface: str
    ip_address: Optional[str] = None
    netmask: Optional[str] = None
    gateway: Optional[str] = None
    dns_servers: Optional[List[str]] = None
    vlan_id: Optional[int] = None
    mtu: Optional[int] = None
    dhcp: bool = False


class BaseOSHandler(ABC):
    """Abstract base class for OS handlers"""
    
    def __init__(self, connection):
        self.connection = connection
        self._os_info = None
        
    @abstractmethod
    def execute_command(self, command: str, timeout: int = 30, 
                       as_admin: bool = False) -> CommandResult:
        """Execute command on the OS"""
        pass
    
    @abstractmethod
    def get_network_interfaces(self) -> List[NetworkInterface]:
        """Get all network interfaces"""
        pass
    
    @abstractmethod
    def configure_network(self, config: NetworkConfig) -> CommandResult:
        """Configure network interface"""
        pass
    
    @abstractmethod
    def restart_network_service(self) -> CommandResult:
        """Restart network service"""
        pass
    
    @abstractmethod
    def get_os_info(self) -> Dict[str, Any]:
        """Get OS information"""
        pass
    
    @abstractmethod
    def install_package(self, package_name: str) -> CommandResult:
        """Install a package"""
        pass
    
    @abstractmethod
    def start_service(self, service_name: str) -> CommandResult:
        """Start a system service"""
        pass
    
    @abstractmethod
    def stop_service(self, service_name: str) -> CommandResult:
        """Stop a system service"""
        pass
    
    @abstractmethod
    def get_service_status(self, service_name: str) -> CommandResult:
        """Get service status"""
        pass
    
    @abstractmethod
    def create_user(self, username: str, password: Optional[str] = None,
                   groups: Optional[List[str]] = None) -> CommandResult:
        """Create a user account"""
        pass
    
    @abstractmethod
    def set_hostname(self, hostname: str) -> CommandResult:
        """Set system hostname"""
        pass
    
    @abstractmethod
    def get_processes(self) -> List[Dict[str, Any]]:
        """Get running processes"""
        pass
    
    @abstractmethod
    def kill_process(self, process_id: int, signal: int = 15) -> CommandResult:
        """Kill a process"""
        pass
    
    @abstractmethod
    def get_disk_usage(self) -> List[Dict[str, Any]]:
        """Get disk usage information"""
        pass
    
    @abstractmethod
    def get_memory_info(self) -> Dict[str, Any]:
        """Get memory information"""
        pass
    
    @abstractmethod
    def get_cpu_info(self) -> Dict[str, Any]:
        """Get CPU information"""
        pass
    
    @abstractmethod
    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Upload file to remote system"""
        pass
    
    @abstractmethod
    def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download file from remote system"""
        pass
    
    @abstractmethod
    def file_exists(self, path: str) -> bool:
        """Check if file exists"""
        pass
    
    @abstractmethod
    def create_directory(self, path: str, recursive: bool = True) -> CommandResult:
        """Create directory"""
        pass
    
    @abstractmethod
    def remove_file(self, path: str) -> CommandResult:
        """Remove file"""
        pass
    
    @abstractmethod
    def list_directory(self, path: str) -> List[Dict[str, Any]]:
        """List directory contents"""
        pass
    
    def reboot(self, wait_for_reboot: bool = True) -> CommandResult:
        """Reboot the system"""
        result = self.execute_command("shutdown -r now", as_admin=True)
        
        if wait_for_reboot and result.success:
            # Connection handler should manage reconnection
            self.connection.wait_for_reboot()
            
        return result
    
    def shutdown(self) -> CommandResult:
        """Shutdown the system"""
        return self.execute_command("shutdown -h now", as_admin=True)