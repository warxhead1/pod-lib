"""
WinRM connection implementation for Windows systems
"""

import base64
import time
from typing import Optional, Tuple
from winrm import Session
from winrm.protocol import Protocol
from winrm.exceptions import WinRMError, WinRMTransportError
from .base import BaseConnection
from ..exceptions import ConnectionError, AuthenticationError, TimeoutError


class WinRMConnection(BaseConnection):
    """WinRM connection for Windows systems"""
    
    @property 
    def default_port(self) -> int:
        return 5985  # HTTP, 5986 for HTTPS
    
    def __init__(self, host: str, username: str, password: Optional[str] = None,
                 port: Optional[int] = None, timeout: int = 30,
                 transport: str = 'ntlm', use_ssl: bool = False,
                 verify_ssl: bool = True, ca_cert: Optional[str] = None):
        super().__init__(host, username, password, None, port, timeout)
        self.transport = transport  # ntlm, kerberos, credssp
        self.use_ssl = use_ssl
        self.verify_ssl = verify_ssl
        self.ca_cert = ca_cert
        self._session = None
        self._protocol = None
        
        # Adjust default port for HTTPS
        if use_ssl and not port:
            self.port = 5986
            
    def connect(self) -> None:
        """Establish WinRM connection"""
        try:
            endpoint = f"{'https' if self.use_ssl else 'http'}://{self.host}:{self.port}/wsman"
            
            # Create session
            self._session = Session(
                target=endpoint,
                auth=(self.username, self.password),
                transport=self.transport,
                server_cert_validation='validate' if self.verify_ssl else 'ignore',
                ca_trust_path=self.ca_cert,
                timeout=self.timeout
            )
            
            # Test connection
            self._protocol = Protocol(
                endpoint=endpoint,
                transport=self.transport,
                username=self.username,
                password=self.password,
                server_cert_validation='validate' if self.verify_ssl else 'ignore',
                ca_trust_path=self.ca_cert
            )
            
            # Open shell to test connection
            shell_id = self._protocol.open_shell()
            self._protocol.close_shell(shell_id)
            
            self._connected = True
            
        except Exception as e:
            # Check if it's a WinRM transport error
            if hasattr(e, 'code') and hasattr(e, 'message'):
                # Check error message or code
                error_msg = getattr(e, 'message', str(e))
                if 'unauthorized' in error_msg.lower() or getattr(e, 'code', 0) == 401:
                    raise AuthenticationError(f"WinRM authentication failed: {error_msg}")
                else:
                    raise ConnectionError(f"WinRM transport error: {error_msg}")
            else:
                raise ConnectionError(f"Failed to connect to {self.host}:{self.port} - {str(e)}")
    
    def disconnect(self) -> None:
        """Close WinRM connection"""
        self._session = None
        self._protocol = None
        self._connected = False
    
    def execute_command(self, command: str, timeout: Optional[int] = None) -> Tuple[str, str, int]:
        """Execute command over WinRM"""
        if not self.is_connected():
            raise ConnectionError("Not connected")
            
        timeout = timeout or self.timeout
        
        try:
            # Execute command
            result = self._session.run_cmd(command, timeout=timeout)
            
            stdout = result.std_out.decode('utf-8', errors='ignore')
            stderr = result.std_err.decode('utf-8', errors='ignore')
            exit_code = result.status_code
            
            return stdout, stderr, exit_code
            
        except WinRMError as e:
            raise ConnectionError(f"Command execution failed: {str(e)}")
        except Exception as e:
            raise ConnectionError(f"Unexpected error during command execution: {str(e)}")
    
    def execute_powershell(self, script: str, timeout: Optional[int] = None) -> Tuple[str, str, int]:
        """Execute PowerShell script"""
        if not self.is_connected():
            raise ConnectionError("Not connected")
            
        timeout = timeout or self.timeout
        
        try:
            # Execute PowerShell script
            result = self._session.run_ps(script, timeout=timeout)
            
            stdout = result.std_out.decode('utf-8', errors='ignore')
            stderr = result.std_err.decode('utf-8', errors='ignore')
            exit_code = result.status_code
            
            return stdout, stderr, exit_code
            
        except WinRMError as e:
            raise ConnectionError(f"PowerShell execution failed: {str(e)}")
        except Exception as e:
            raise ConnectionError(f"Unexpected error during PowerShell execution: {str(e)}")
    
    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Upload file via WinRM (using PowerShell)"""
        if not self.is_connected():
            raise ConnectionError("Not connected")
            
        try:
            # Read local file
            with open(local_path, 'rb') as f:
                content = f.read()
                
            # Encode content as base64
            encoded_content = base64.b64encode(content).decode('utf-8')
            
            # PowerShell script to write file
            script = f'''
            $content = [System.Convert]::FromBase64String("{encoded_content}")
            [System.IO.File]::WriteAllBytes("{remote_path}", $content)
            '''
            
            stdout, stderr, exit_code = self.execute_powershell(script)
            
            if exit_code != 0:
                raise ConnectionError(f"Failed to upload file: {stderr}")
                
            return True
            
        except Exception as e:
            raise ConnectionError(f"Failed to upload file: {str(e)}")
    
    def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download file via WinRM (using PowerShell)"""
        if not self.is_connected():
            raise ConnectionError("Not connected")
            
        try:
            # PowerShell script to read file as base64
            script = f'''
            $content = [System.IO.File]::ReadAllBytes("{remote_path}")
            [System.Convert]::ToBase64String($content)
            '''
            
            stdout, stderr, exit_code = self.execute_powershell(script)
            
            if exit_code != 0:
                raise ConnectionError(f"Failed to download file: {stderr}")
                
            # Decode content from base64
            content = base64.b64decode(stdout.strip())
            
            # Write to local file
            with open(local_path, 'wb') as f:
                f.write(content)
                
            return True
            
        except Exception as e:
            raise ConnectionError(f"Failed to download file: {str(e)}")
    
    def is_connected(self) -> bool:
        """Check if WinRM connection is active"""
        if not self._connected or not self._session:
            return False
            
        # Try a simple command to test connection
        try:
            result = self._session.run_cmd('echo test', timeout=5)
            return result.status_code == 0
        except:
            self._connected = False
            return False
    
    def execute_as_admin(self, command: str, timeout: Optional[int] = None) -> Tuple[str, str, int]:
        """Execute command as Administrator using RunAs"""
        # Create PowerShell script for elevated execution
        script = f'''
        $secpasswd = ConvertTo-SecureString '{self.password}' -AsPlainText -Force
        $cred = New-Object System.Management.Automation.PSCredential ('{self.username}', $secpasswd)
        $result = Start-Process -FilePath "cmd.exe" -ArgumentList "/c {command}" -Credential $cred -Wait -PassThru -NoNewWindow -RedirectStandardOutput "$env:TEMP\\stdout.txt" -RedirectStandardError "$env:TEMP\\stderr.txt"
        
        $stdout = Get-Content "$env:TEMP\\stdout.txt" -Raw
        $stderr = Get-Content "$env:TEMP\\stderr.txt" -Raw
        
        Remove-Item "$env:TEMP\\stdout.txt" -Force -ErrorAction SilentlyContinue
        Remove-Item "$env:TEMP\\stderr.txt" -Force -ErrorAction SilentlyContinue
        
        Write-Output $stdout
        Write-Error $stderr
        exit $result.ExitCode
        '''
        
        return self.execute_powershell(script, timeout)