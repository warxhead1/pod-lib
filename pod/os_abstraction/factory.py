"""
OS handler factory for automatic OS detection and handler instantiation
"""

import logging
from typing import Optional, Dict, Any, Type
from .base import BaseOSHandler
from .linux import LinuxHandler
from .windows import WindowsHandler
from ..connections.base import BaseConnection
from ..connections.ssh import SSHConnection
from ..connections.winrm import WinRMConnection


logger = logging.getLogger(__name__)


class OSHandlerFactory:
    """Factory for creating OS-specific handlers"""
    
    # Mapping of OS types to handler classes
    _handlers: Dict[str, Type[BaseOSHandler]] = {
        'linux': LinuxHandler,
        'windows': WindowsHandler,
        'debian': LinuxHandler,
        'ubuntu': LinuxHandler,
        'rhel': LinuxHandler,
        'centos': LinuxHandler,
        'rocky': LinuxHandler,
        'fedora': LinuxHandler,
        'opensuse': LinuxHandler,
        'windows_server': WindowsHandler,
        'windows_10': WindowsHandler,
        'windows_11': WindowsHandler,
    }
    
    # Mapping of guest IDs to OS types (vSphere specific)
    _vsphere_guest_map = {
        # Linux variants
        'rhel8_64Guest': 'rhel',
        'rhel7_64Guest': 'rhel',
        'rhel6_64Guest': 'rhel',
        'centos8_64Guest': 'centos',
        'centos7_64Guest': 'centos',
        'centos6_64Guest': 'centos',
        'ubuntu64Guest': 'ubuntu',
        'debian10_64Guest': 'debian',
        'debian9_64Guest': 'debian',
        'debian8_64Guest': 'debian',
        'sles15_64Guest': 'opensuse',
        'sles12_64Guest': 'opensuse',
        'other3xLinux64Guest': 'linux',
        'otherLinux64Guest': 'linux',
        
        # Windows variants
        'windows9_64Guest': 'windows',
        'windows9Server64Guest': 'windows_server',
        'windows2019srv_64Guest': 'windows_server',
        'windows2016srv_64Guest': 'windows_server',
        'windows2012srv_64Guest': 'windows_server',
        'windows8Server64Guest': 'windows_server',
        'windows7Server64Guest': 'windows_server',
        'windows7_64Guest': 'windows',
        'windows8_64Guest': 'windows',
        'windows10_64Guest': 'windows_10',
        'windows11_64Guest': 'windows_11',
    }
    
    @classmethod
    def create_handler(cls, connection: BaseConnection, 
                      os_info: Optional[Dict[str, Any]] = None) -> BaseOSHandler:
        """
        Create appropriate OS handler based on connection type and OS info
        
        Args:
            connection: The connection object (SSH, WinRM, etc.)
            os_info: Optional OS information dict with keys like 'type', 'guest_id', etc.
            
        Returns:
            Appropriate OS handler instance
            
        Raises:
            ValueError: If OS type cannot be determined or is unsupported
        """
        os_type = cls._detect_os_type(connection, os_info)
        
        if os_type not in cls._handlers:
            raise ValueError(f"Unsupported OS type: {os_type}")
            
        handler_class = cls._handlers[os_type]
        logger.info(f"Creating {handler_class.__name__} for OS type: {os_type}")
        
        return handler_class(connection)
    
    @classmethod
    def _detect_os_type(cls, connection: BaseConnection, 
                       os_info: Optional[Dict[str, Any]] = None) -> str:
        """
        Detect OS type from connection and optional OS info
        
        Args:
            connection: The connection object
            os_info: Optional OS information
            
        Returns:
            Detected OS type string
        """
        # First, check if OS type is explicitly provided
        if os_info and 'type' in os_info:
            return os_info['type'].lower()
            
        # Check vSphere guest ID if available
        if os_info and 'guest_id' in os_info:
            guest_id = os_info['guest_id']
            if guest_id in cls._vsphere_guest_map:
                return cls._vsphere_guest_map[guest_id]
                
        # Infer from connection type
        if isinstance(connection, WinRMConnection):
            return 'windows'
        elif isinstance(connection, SSHConnection):
            # Try to detect Linux distribution
            return cls._detect_linux_distro(connection)
            
        # Check guest family if available (vSphere)
        if os_info and 'guest_family' in os_info:
            family = os_info['guest_family'].lower()
            if 'windows' in family:
                return 'windows'
            elif 'linux' in family:
                return 'linux'
                
        # Default based on connection type
        if isinstance(connection, WinRMConnection):
            return 'windows'
        else:
            return 'linux'
    
    @classmethod
    def _detect_linux_distro(cls, connection: SSHConnection) -> str:
        """
        Detect specific Linux distribution
        
        Args:
            connection: SSH connection to Linux system
            
        Returns:
            Linux distribution name
        """
        try:
            # Try to read os-release file
            stdout, stderr, exit_code = connection.execute_command("cat /etc/os-release")
            
            if exit_code == 0:
                os_release = stdout.lower()
                
                # Check for specific distributions
                if 'ubuntu' in os_release:
                    return 'ubuntu'
                elif 'debian' in os_release:
                    return 'debian'
                elif 'rhel' in os_release or 'red hat' in os_release:
                    return 'rhel'
                elif 'centos' in os_release:
                    return 'centos'
                elif 'rocky' in os_release:
                    return 'rocky'
                elif 'fedora' in os_release:
                    return 'fedora'
                elif 'opensuse' in os_release or 'suse' in os_release:
                    return 'opensuse'
                    
            # Try alternative detection methods
            stdout, stderr, exit_code = connection.execute_command("uname -a")
            if exit_code == 0:
                uname = stdout.lower()
                if 'ubuntu' in uname:
                    return 'ubuntu'
                elif 'debian' in uname:
                    return 'debian'
                    
        except Exception as e:
            logger.warning(f"Failed to detect Linux distribution: {e}")
            
        # Default to generic Linux
        return 'linux'
    
    @classmethod
    def register_handler(cls, os_type: str, handler_class: Type[BaseOSHandler]):
        """
        Register a custom OS handler
        
        Args:
            os_type: OS type string
            handler_class: Handler class that inherits from BaseOSHandler
        """
        if not issubclass(handler_class, BaseOSHandler):
            raise ValueError("Handler class must inherit from BaseOSHandler")
            
        cls._handlers[os_type.lower()] = handler_class
        logger.info(f"Registered {handler_class.__name__} for OS type: {os_type}")
    
    @classmethod
    def register_guest_id_mapping(cls, guest_id: str, os_type: str):
        """
        Register a vSphere guest ID to OS type mapping
        
        Args:
            guest_id: vSphere guest ID
            os_type: OS type string
        """
        cls._vsphere_guest_map[guest_id] = os_type.lower()
        logger.info(f"Registered guest ID mapping: {guest_id} -> {os_type}")
    
    @classmethod
    def get_supported_os_types(cls) -> list:
        """Get list of supported OS types"""
        return list(cls._handlers.keys())
    
    @classmethod
    def is_os_supported(cls, os_type: str) -> bool:
        """Check if an OS type is supported"""
        return os_type.lower() in cls._handlers