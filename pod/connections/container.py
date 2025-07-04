"""
Container connection implementation with enhanced networking support
"""

import json
import subprocess  # nosec B404
import time
from typing import Optional, Dict, Any, List, Tuple
from .base import BaseConnection


class DockerConnection(BaseConnection):
    """
    Enhanced Docker container connection with VLAN and networking support
    """
    
    def __init__(self, container_id: str, runtime: str = "docker"):
        """
        Initialize Docker connection
        
        Args:
            container_id: Container ID or name
            runtime: Container runtime ('docker' or 'podman')
        """
        self.container_id = container_id
        self.runtime = runtime
        self._connected = False
        self._container_info = None
    
    @property
    def default_port(self) -> int:
        """Return default port (not applicable for containers)"""
        return 0
        
    def connect(self, **kwargs):
        """Connect to container and verify it's running"""
        try:
            # Get container info
            self._container_info = self._get_container_info()
            
            if not self._container_info:
                raise ConnectionError(f"Container {self.container_id} not found")
                
            # Check if running
            state = self._container_info.get('State', {})
            if not state.get('Running', False):
                # Try to start it
                self._start_container()
                
            self._connected = True
            
        except Exception as e:
            raise ConnectionError(f"Failed to connect to container: {str(e)}")
            
    def disconnect(self):
        """Disconnect from container"""
        self._connected = False
        self._container_info = None
        
    def is_connected(self) -> bool:
        """Check if connected to container"""
        if not self._connected:
            return False
            
        # Verify container is still running
        try:
            info = self._get_container_info()
            return info and info.get('State', {}).get('Running', False)
        except:
            return False
            
    def execute_command(self, command: str, timeout: int = 30) -> Tuple[str, str, int]:
        """Execute command in container"""
        if not self.is_connected():
            raise ConnectionError("Not connected to container")
            
        cmd = [self.runtime, "exec", self.container_id, "/bin/bash", "-c", command]
        
        try:
            result = subprocess.run(  # nosec B603
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return result.stdout, result.stderr, result.returncode
            
        except subprocess.TimeoutExpired:
            return "", f"Command timed out after {timeout} seconds", 124
        except Exception as e:
            return "", str(e), 1
            
    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Upload file to container"""
        cmd = [self.runtime, "cp", local_path, f"{self.container_id}:{remote_path}"]
        
        try:
            result = subprocess.run(cmd, capture_output=True)  # nosec B603
            return result.returncode == 0
        except:
            return False
            
    def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download file from container"""
        cmd = [self.runtime, "cp", f"{self.container_id}:{remote_path}", local_path]
        
        try:
            result = subprocess.run(cmd, capture_output=True)  # nosec B603
            return result.returncode == 0
        except:
            return False
            
    def execute_sudo_command(self, command: str, timeout: int = 30) -> Tuple[str, str, int]:
        """Execute command with sudo in container"""
        # In containers, we often run as root already
        return self.execute_command(command, timeout)
        
    def create_network_namespace(self, namespace: str) -> bool:
        """Create network namespace in container"""
        stdout, stderr, code = self.execute_command(f"ip netns add {namespace}")
        return code == 0
        
    def attach_to_network(self, network_name: str, 
                         ip_address: Optional[str] = None,
                         aliases: Optional[List[str]] = None) -> bool:
        """Attach container to a Docker network"""
        cmd = [self.runtime, "network", "connect"]
        
        if ip_address:
            cmd.extend(["--ip", ip_address])
            
        if aliases:
            for alias in aliases:
                cmd.extend(["--alias", alias])
                
        cmd.extend([network_name, self.container_id])
        
        try:
            result = subprocess.run(cmd, capture_output=True)  # nosec B603
            return result.returncode == 0
        except:
            return False
            
    def detach_from_network(self, network_name: str) -> bool:
        """Detach container from a Docker network"""
        cmd = [self.runtime, "network", "disconnect", network_name, self.container_id]
        
        try:
            result = subprocess.run(cmd, capture_output=True)  # nosec B603
            return result.returncode == 0
        except:
            return False
            
    def create_vlan_network(self, network_name: str, parent_interface: str,
                           vlan_id: int, subnet: str, gateway: Optional[str] = None) -> bool:
        """
        Create a Docker network with VLAN support
        
        Args:
            network_name: Name for the Docker network
            parent_interface: Parent interface on host (e.g., eth0)
            vlan_id: VLAN ID
            subnet: Subnet for the network (e.g., 192.168.100.0/24)
            gateway: Optional gateway IP
            
        Returns:
            True if successful
        """
        cmd = [
            self.runtime, "network", "create",
            "-d", "macvlan",
            "--subnet", subnet,
            "-o", f"parent={parent_interface}.{vlan_id}",
            network_name
        ]
        
        if gateway:
            cmd.extend(["--gateway", gateway])
            
        try:
            result = subprocess.run(cmd, capture_output=True)  # nosec B603
            return result.returncode == 0
        except:
            return False
            
    def add_veth_interface(self, veth_name: str, ip_address: str, 
                          netmask: str = "255.255.255.0") -> bool:
        """Add veth interface to container"""
        # Create veth pair on host
        host_veth = f"h-{veth_name}"
        container_veth = f"c-{veth_name}"
        
        # This would typically be done on the host system
        # Here we document the process
        commands = [
            f"ip link add {host_veth} type veth peer name {container_veth}",
            f"ip link set {container_veth} netns {self._get_container_pid()}",
            f"ip link set {host_veth} up"
        ]
        
        # Configure inside container
        prefix = sum(bin(int(x)).count('1') for x in netmask.split('.'))
        stdout, stderr, code = self.execute_command(
            f"ip addr add {ip_address}/{prefix} dev {container_veth} && "
            f"ip link set {container_veth} up"
        )
        
        return code == 0
        
    # Helper methods
    def _get_container_info(self) -> Optional[Dict[str, Any]]:
        """Get container information"""
        cmd = [self.runtime, "inspect", self.container_id]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)  # nosec B603
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return data[0] if isinstance(data, list) else data
        except Exception as e:
            # JSON parsing failed - container may not exist or be in invalid state
            import logging
            logging.debug(f"Could not parse container inspect data: {e}")
            
        return None
        
    def _start_container(self):
        """Start the container"""
        cmd = [self.runtime, "start", self.container_id]
        result = subprocess.run(cmd, capture_output=True)  # nosec B603
        
        if result.returncode != 0:
            raise ConnectionError(f"Failed to start container: {result.stderr.decode()}")
            
        # Wait for container to be ready
        time.sleep(2)
        
    def _get_container_pid(self) -> int:
        """Get container PID"""
        info = self._get_container_info()
        if info:
            return info.get('State', {}).get('Pid', 0)
        return 0
        
    def get_container_networks(self) -> Dict[str, Any]:
        """Get container network configuration"""
        info = self._get_container_info()
        if info:
            return info.get('NetworkSettings', {}).get('Networks', {})
        return {}
        
    def execute_in_network_namespace(self, namespace: str, command: str) -> Tuple[str, str, int]:
        """Execute command in specific network namespace"""
        ns_command = f"ip netns exec {namespace} {command}"
        return self.execute_command(ns_command)