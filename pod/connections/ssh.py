"""
SSH connection implementation using Paramiko
"""

import os
import time
import paramiko
from typing import Optional, Tuple
from .base import BaseConnection
from ..exceptions import ConnectionError, AuthenticationError, TimeoutError


class SSHConnection(BaseConnection):
    """SSH connection for Linux and Unix-like systems"""
    
    @property
    def default_port(self) -> int:
        return 22
    
    def __init__(self, host: str, username: str, password: Optional[str] = None,
                 key_filename: Optional[str] = None, port: Optional[int] = None,
                 timeout: int = 30, look_for_keys: bool = True,
                 allow_agent: bool = True):
        super().__init__(host, username, password, key_filename, port, timeout)
        self.look_for_keys = look_for_keys
        self.allow_agent = allow_agent
        self._client = None
        self._sftp = None
        
    def connect(self) -> None:
        """Establish SSH connection"""
        try:
            self._client = paramiko.SSHClient()
            # Infrastructure tools need to connect to unknown hosts
            self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # nosec B507
            
            connect_kwargs = {
                'hostname': self.host,
                'port': self.port,
                'username': self.username,
                'timeout': self.timeout,
                'look_for_keys': self.look_for_keys,
                'allow_agent': self.allow_agent,
            }
            
            if self.key_filename:
                connect_kwargs['key_filename'] = self.key_filename
            elif self.password:
                connect_kwargs['password'] = self.password
                
            self._client.connect(**connect_kwargs)
            self._connected = True
            
        except paramiko.AuthenticationException as e:
            raise AuthenticationError(f"SSH authentication failed: {str(e)}")
        except paramiko.SSHException as e:
            raise ConnectionError(f"SSH connection failed: {str(e)}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to {self.host}:{self.port} - {str(e)}")
    
    def disconnect(self) -> None:
        """Close SSH connection"""
        if self._sftp:
            self._sftp.close()
            self._sftp = None
            
        if self._client:
            self._client.close()
            self._client = None
            
        self._connected = False
    
    def execute_command(self, command: str, timeout: Optional[int] = None) -> Tuple[str, str, int]:
        """Execute command over SSH"""
        if not self.is_connected():
            raise ConnectionError("Not connected")
            
        timeout = timeout or self.timeout
        
        try:
            # Execute command - paramiko input is controlled by POD library
            stdin, stdout, stderr = self._client.exec_command(  # nosec B601
                command, 
                timeout=timeout,
                get_pty=True  # Get pseudo-terminal for interactive commands
            )
            
            # Read output
            stdout_data = stdout.read().decode('utf-8', errors='ignore')
            stderr_data = stderr.read().decode('utf-8', errors='ignore')
            exit_code = stdout.channel.recv_exit_status()
            
            return stdout_data, stderr_data, exit_code
            
        except paramiko.SSHException as e:
            raise ConnectionError(f"Command execution failed: {str(e)}")
        except Exception as e:
            raise ConnectionError(f"Unexpected error during command execution: {str(e)}")
    
    def execute_sudo_command(self, command: str, sudo_password: Optional[str] = None,
                           timeout: Optional[int] = None) -> Tuple[str, str, int]:
        """Execute command with sudo"""
        sudo_password = sudo_password or self.password
        if not sudo_password:
            # Try without password first
            return self.execute_command(f"sudo {command}", timeout)
            
        # Use sudo with password
        sudo_cmd = f"echo '{sudo_password}' | sudo -S {command}"
        stdout, stderr, exit_code = self.execute_command(sudo_cmd, timeout)
        
        # Remove sudo password prompt from stderr if present
        stderr_lines = stderr.split('\n')
        cleaned_stderr = '\n'.join(
            line for line in stderr_lines 
            if not line.startswith('[sudo] password for')
        )
        
        return stdout, cleaned_stderr, exit_code
    
    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Upload file via SFTP"""
        if not self.is_connected():
            raise ConnectionError("Not connected")
            
        try:
            if not self._sftp:
                self._sftp = self._client.open_sftp()
                
            self._sftp.put(local_path, remote_path)
            return True
            
        except Exception as e:
            raise ConnectionError(f"Failed to upload file: {str(e)}")
    
    def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download file via SFTP"""
        if not self.is_connected():
            raise ConnectionError("Not connected")
            
        try:
            if not self._sftp:
                self._sftp = self._client.open_sftp()
                
            self._sftp.get(remote_path, local_path)
            return True
            
        except Exception as e:
            raise ConnectionError(f"Failed to download file: {str(e)}")
    
    def is_connected(self) -> bool:
        """Check if SSH connection is active"""
        if not self._connected or not self._client:
            return False
            
        # Check if transport is active
        transport = self._client.get_transport()
        if transport and transport.is_active():
            return True
            
        self._connected = False
        return False
    
    def create_sftp_client(self) -> paramiko.SFTPClient:
        """Get SFTP client for advanced file operations"""
        if not self.is_connected():
            raise ConnectionError("Not connected")
            
        if not self._sftp:
            self._sftp = self._client.open_sftp()
            
        return self._sftp
    
    def forward_port(self, local_port: int, remote_host: str, remote_port: int) -> None:
        """Set up SSH port forwarding"""
        if not self.is_connected():
            raise ConnectionError("Not connected")
            
        transport = self._client.get_transport()
        transport.request_port_forward('', local_port)
        
        # This is simplified - full implementation would handle the forwarding