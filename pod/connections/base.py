"""
Base connection interface
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple, Any
import time
from ..exceptions import TimeoutError


class BaseConnection(ABC):
    """Abstract base class for all connection types"""
    
    def __init__(self, host: str, username: str, password: Optional[str] = None,
                 key_filename: Optional[str] = None, port: Optional[int] = None,
                 timeout: int = 30):
        self.host = host
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.port = port or self.default_port
        self.timeout = timeout
        self._connected = False
        
    @property
    @abstractmethod
    def default_port(self) -> int:
        """Default port for this connection type"""
        pass
    
    @abstractmethod
    def connect(self) -> None:
        """Establish connection"""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Close connection"""
        pass
    
    @abstractmethod
    def execute_command(self, command: str, timeout: Optional[int] = None) -> Tuple[str, str, int]:
        """Execute command and return (stdout, stderr, exit_code)"""
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
    def is_connected(self) -> bool:
        """Check if connection is active"""
        pass
    
    def wait_for_reboot(self, wait_time: int = 30, timeout: int = 300) -> None:
        """Wait for system to reboot and reconnect"""
        # Wait for system to go down
        time.sleep(wait_time)
        
        # Disconnect current connection
        self.disconnect()
        
        # Wait for system to come back up
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                self.connect()
                if self.is_connected():
                    return
            except Exception as e:
                # Connection check failed, will retry after delay
                import logging
                logging.debug(f"Connection check failed during reboot wait: {e}")
            time.sleep(5)
            
        raise TimeoutError(f"System did not come back up within {timeout} seconds")
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()