"""
Windows OS handler implementation
"""

import re
import json
import time
import base64
from typing import Dict, Any, Optional, List
from .base import BaseOSHandler, CommandResult, NetworkInterface, NetworkConfig
from ..connections.winrm import WinRMConnection


class WindowsHandler(BaseOSHandler):
    """Handler for Windows operating systems"""
    
    def execute_command(self, command: str, timeout: int = 30, 
                       as_admin: bool = False) -> CommandResult:
        """Execute command on Windows"""
        start_time = time.time()
        
        if isinstance(self.connection, WinRMConnection):
            stdout, stderr, exit_code = self.connection.execute_command(command, timeout=timeout)
        else:
            raise ValueError("Windows handler requires WinRM connection")
            
        duration = time.time() - start_time
        
        return CommandResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            success=exit_code == 0,
            command=command,
            duration=duration
        )
    
    def execute_powershell(self, script: str, timeout: int = 30,
                          as_admin: bool = False) -> CommandResult:
        """Execute PowerShell script"""
        start_time = time.time()
        
        if isinstance(self.connection, WinRMConnection):
            stdout, stderr, exit_code = self.connection.execute_powershell(script, timeout=timeout)
        else:
            raise ValueError("Windows handler requires WinRM connection")
            
        duration = time.time() - start_time
        
        return CommandResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            success=exit_code == 0,
            command=f"PowerShell: {script[:50]}...",
            duration=duration
        )
    
    def get_network_interfaces(self) -> List[NetworkInterface]:
        """Get all network interfaces using PowerShell"""
        interfaces = []
        
        # PowerShell script to get network adapter information
        script = """
        Get-NetAdapter | ForEach-Object {
            $adapter = $_
            $config = Get-NetIPConfiguration -InterfaceIndex $adapter.ifIndex
            $addresses = Get-NetIPAddress -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue
            
            @{
                Name = $adapter.Name
                InterfaceAlias = $adapter.InterfaceAlias
                MacAddress = $adapter.MacAddress
                Status = $adapter.Status
                LinkSpeed = $adapter.LinkSpeed
                InterfaceIndex = $adapter.ifIndex
                IPAddresses = @($addresses | ForEach-Object { $_.IPAddress })
                PrefixLength = @($addresses | ForEach-Object { $_.PrefixLength })[0]
                Gateway = $config.IPv4DefaultGateway.NextHop
                DNSServers = @($config.DNSServer | Where-Object { $_.AddressFamily -eq 2 } | ForEach-Object { $_.ServerAddresses })
                VlanID = (Get-NetAdapterAdvancedProperty -Name $adapter.Name -DisplayName "VLAN ID" -ErrorAction SilentlyContinue).DisplayValue
            }
        } | ConvertTo-Json -Depth 5
        """
        
        result = self.execute_powershell(script)
        if not result.success:
            # Fallback to basic ipconfig
            return self._parse_ipconfig()
            
        try:
            adapter_data = json.loads(result.stdout)
            if not isinstance(adapter_data, list):
                adapter_data = [adapter_data]
                
            for adapter in adapter_data:
                # Convert prefix length to netmask
                prefix_len = adapter.get('PrefixLength', 24)
                netmask = self._prefix_to_netmask(prefix_len) if prefix_len else None
                
                # Parse VLAN ID
                vlan_id = None
                vlan_str = adapter.get('VlanID', '')
                if vlan_str and vlan_str.isdigit():
                    vlan_id = int(vlan_str)
                    
                interfaces.append(NetworkInterface(
                    name=adapter.get('Name', ''),
                    mac_address=adapter.get('MacAddress', '').replace('-', ':').lower(),
                    ip_addresses=adapter.get('IPAddresses', []),
                    netmask=netmask,
                    gateway=adapter.get('Gateway'),
                    vlan_id=vlan_id,
                    mtu=1500,  # Windows default
                    state='up' if adapter.get('Status') == 'Up' else 'down',
                    type='ethernet'
                ))
                
        except json.JSONDecodeError:
            return self._parse_ipconfig()
            
        return interfaces
    
    def configure_network(self, config: NetworkConfig) -> CommandResult:
        """Configure network interface using PowerShell"""
        # Build PowerShell script for network configuration
        script_parts = []
        
        # Find the interface
        script_parts.append(f'$adapter = Get-NetAdapter -Name "{config.interface}" -ErrorAction Stop')
        
        if config.dhcp:
            # Enable DHCP
            script_parts.append('Remove-NetIPAddress -InterfaceAlias $adapter.InterfaceAlias -Confirm:$false -ErrorAction SilentlyContinue')
            script_parts.append('Set-NetIPInterface -InterfaceAlias $adapter.InterfaceAlias -Dhcp Enabled')
        else:
            # Static IP configuration
            # Remove existing IP addresses
            script_parts.append('Remove-NetIPAddress -InterfaceAlias $adapter.InterfaceAlias -Confirm:$false -ErrorAction SilentlyContinue')
            script_parts.append('Remove-NetRoute -InterfaceAlias $adapter.InterfaceAlias -Confirm:$false -ErrorAction SilentlyContinue')
            
            # Add new IP address
            prefix_len = self._netmask_to_prefix(config.netmask) if config.netmask else 24
            script_parts.append(f'New-NetIPAddress -InterfaceAlias $adapter.InterfaceAlias -IPAddress "{config.ip_address}" -PrefixLength {prefix_len} -Confirm:$false')
            
            # Add gateway if specified
            if config.gateway:
                script_parts.append(f'New-NetRoute -InterfaceAlias $adapter.InterfaceAlias -DestinationPrefix "0.0.0.0/0" -NextHop "{config.gateway}" -Confirm:$false')
                
            # Set DNS servers if specified
            if config.dns_servers:
                dns_list = ','.join(f'"{dns}"' for dns in config.dns_servers)
                script_parts.append(f'Set-DnsClientServerAddress -InterfaceAlias $adapter.InterfaceAlias -ServerAddresses {dns_list}')
                
        # Configure VLAN if specified
        if config.vlan_id is not None:
            script_parts.append(f'Set-NetAdapterAdvancedProperty -Name $adapter.Name -DisplayName "VLAN ID" -DisplayValue {config.vlan_id}')
            
        # Configure MTU if specified
        if config.mtu:
            script_parts.append(f'Set-NetAdapterAdvancedProperty -Name $adapter.Name -DisplayName "Jumbo Packet" -DisplayValue {config.mtu}')
            
        # Execute the script
        script = '\n'.join(script_parts)
        return self.execute_powershell(script)
    
    def restart_network_service(self) -> CommandResult:
        """Restart network service"""
        # Windows doesn't have a single network service, so we restart the adapter
        script = """
        Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | ForEach-Object {
            Disable-NetAdapter -Name $_.Name -Confirm:$false
            Start-Sleep -Seconds 2
            Enable-NetAdapter -Name $_.Name -Confirm:$false
        }
        """
        return self.execute_powershell(script)
    
    def get_os_info(self) -> Dict[str, Any]:
        """Get OS information"""
        if self._os_info:
            return self._os_info
            
        info = {
            'type': 'windows',
            'distribution': 'Windows',
            'version': 'unknown',
            'kernel': 'unknown',
            'architecture': 'unknown',
            'hostname': 'unknown',
            'edition': 'unknown',
            'build': 'unknown'
        }
        
        # Get Windows version info
        script = """
        $os = Get-WmiObject -Class Win32_OperatingSystem
        $cs = Get-WmiObject -Class Win32_ComputerSystem
        @{
            Caption = $os.Caption
            Version = $os.Version
            BuildNumber = $os.BuildNumber
            Architecture = $os.OSArchitecture
            Hostname = $cs.Name
            ServicePack = $os.ServicePackMajorVersion
        } | ConvertTo-Json
        """
        
        result = self.execute_powershell(script)
        if result.success:
            try:
                data = json.loads(result.stdout)
                info['distribution'] = data.get('Caption', 'Windows')
                info['version'] = data.get('Version', 'unknown')
                info['build'] = data.get('BuildNumber', 'unknown')
                arch = data.get('Architecture', 'unknown')
                info['architecture'] = arch
                info['hostname'] = data.get('Hostname', 'unknown')
            except json.JSONDecodeError:
                pass
                
        self._os_info = info
        return info
    
    def install_package(self, package_name: str) -> CommandResult:
        """Install a package using Chocolatey or Windows Package Manager"""
        # First try Windows Package Manager (winget)
        result = self.execute_command("winget --version")
        if result.success:
            return self.execute_command(f"winget install -e --id {package_name} --accept-source-agreements --accept-package-agreements")
            
        # Try Chocolatey
        result = self.execute_command("choco --version")
        if result.success:
            return self.execute_command(f"choco install {package_name} -y")
            
        # Try to install Chocolatey
        install_choco = """
        Set-ExecutionPolicy Bypass -Scope Process -Force
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
        iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))
        """
        result = self.execute_powershell(install_choco)
        
        if result.success:
            # Try again with Chocolatey
            return self.execute_command(f"choco install {package_name} -y")
            
        return CommandResult(
            stdout="",
            stderr="No package manager available. Install winget or Chocolatey.",
            exit_code=1,
            success=False,
            command=f"install {package_name}",
            duration=0
        )
    
    def start_service(self, service_name: str) -> CommandResult:
        """Start a Windows service"""
        return self.execute_powershell(f"Start-Service -Name '{service_name}'")
    
    def stop_service(self, service_name: str) -> CommandResult:
        """Stop a Windows service"""
        return self.execute_powershell(f"Stop-Service -Name '{service_name}' -Force")
    
    def get_service_status(self, service_name: str) -> CommandResult:
        """Get service status"""
        script = f"""
        $service = Get-Service -Name '{service_name}' -ErrorAction SilentlyContinue
        if ($service) {{
            @{{
                Name = $service.Name
                DisplayName = $service.DisplayName
                Status = $service.Status.ToString()
                StartType = $service.StartType.ToString()
            }} | ConvertTo-Json
        }} else {{
            Write-Error "Service '{service_name}' not found"
        }}
        """
        return self.execute_powershell(script)
    
    def create_user(self, username: str, password: Optional[str] = None,
                   groups: Optional[List[str]] = None) -> CommandResult:
        """Create a user account"""
        script_parts = []
        
        # Create user
        if password:
            script_parts.append(f'$password = ConvertTo-SecureString "{password}" -AsPlainText -Force')
            script_parts.append(f'New-LocalUser -Name "{username}" -Password $password -PasswordNeverExpires')
        else:
            script_parts.append(f'New-LocalUser -Name "{username}" -NoPassword')
            
        # Add to groups
        if groups:
            for group in groups:
                script_parts.append(f'Add-LocalGroupMember -Group "{group}" -Member "{username}" -ErrorAction SilentlyContinue')
                
        script = '\n'.join(script_parts)
        return self.execute_powershell(script)
    
    def set_hostname(self, hostname: str) -> CommandResult:
        """Set system hostname"""
        return self.execute_powershell(f"Rename-Computer -NewName '{hostname}' -Force")
    
    def get_processes(self) -> List[Dict[str, Any]]:
        """Get running processes"""
        processes = []
        
        script = """
        Get-Process | Select-Object Id, ProcessName, CPU, WorkingSet, Handles, StartTime | 
        ConvertTo-Json -Depth 2
        """
        
        result = self.execute_powershell(script)
        if result.success:
            try:
                proc_data = json.loads(result.stdout)
                if not isinstance(proc_data, list):
                    proc_data = [proc_data]
                    
                for proc in proc_data:
                    processes.append({
                        'pid': proc.get('Id', 0),
                        'name': proc.get('ProcessName', ''),
                        'cpu': proc.get('CPU', 0),
                        'memory': proc.get('WorkingSet', 0),
                        'handles': proc.get('Handles', 0),
                        'start_time': proc.get('StartTime', '')
                    })
            except json.JSONDecodeError:
                pass
                
        return processes
    
    def kill_process(self, process_id: int, signal: int = 15) -> CommandResult:
        """Kill a process"""
        # Windows doesn't use signals like Unix, so we just force kill
        return self.execute_powershell(f"Stop-Process -Id {process_id} -Force")
    
    def get_disk_usage(self) -> List[Dict[str, Any]]:
        """Get disk usage information"""
        disks = []
        
        script = """
        Get-PSDrive -PSProvider FileSystem | Where-Object {$_.Used -ne $null} | ForEach-Object {
            @{
                Name = $_.Name
                Root = $_.Root
                Used = $_.Used
                Free = $_.Free
                Total = $_.Used + $_.Free
                UsedPercent = [math]::Round(($_.Used / ($_.Used + $_.Free)) * 100, 2)
            }
        } | ConvertTo-Json -Depth 2
        """
        
        result = self.execute_powershell(script)
        if result.success:
            try:
                disk_data = json.loads(result.stdout)
                if not isinstance(disk_data, list):
                    disk_data = [disk_data]
                    
                for disk in disk_data:
                    disks.append({
                        'filesystem': f"{disk.get('Name', '')}:",
                        'size': self._format_bytes(disk.get('Total', 0)),
                        'used': self._format_bytes(disk.get('Used', 0)),
                        'available': self._format_bytes(disk.get('Free', 0)),
                        'use_percent': str(disk.get('UsedPercent', 0)),
                        'mount_point': disk.get('Root', '')
                    })
            except json.JSONDecodeError:
                pass
                
        return disks
    
    def get_memory_info(self) -> Dict[str, Any]:
        """Get memory information"""
        info = {}
        
        script = """
        $os = Get-WmiObject -Class Win32_OperatingSystem
        $cs = Get-WmiObject -Class Win32_ComputerSystem
        @{
            TotalPhysicalMemory = $cs.TotalPhysicalMemory
            FreePhysicalMemory = $os.FreePhysicalMemory * 1024
            TotalVirtualMemory = $os.TotalVirtualMemorySize * 1024
            FreeVirtualMemory = $os.FreeVirtualMemory * 1024
        } | ConvertTo-Json
        """
        
        result = self.execute_powershell(script)
        if result.success:
            try:
                data = json.loads(result.stdout)
                total = data.get('TotalPhysicalMemory', 0)
                free = data.get('FreePhysicalMemory', 0)
                info['total'] = total
                info['free'] = free
                info['used'] = total - free
                info['available'] = free
                info['swap_total'] = data.get('TotalVirtualMemory', 0)
                info['swap_free'] = data.get('FreeVirtualMemory', 0)
                info['swap_used'] = info['swap_total'] - info['swap_free']
            except json.JSONDecodeError:
                pass
                
        return info
    
    def get_cpu_info(self) -> Dict[str, Any]:
        """Get CPU information"""
        info = {
            'count': 0,
            'model': 'unknown',
            'speed_mhz': 0,
            'architecture': 'unknown'
        }
        
        script = """
        $cpu = Get-WmiObject -Class Win32_Processor
        @{
            NumberOfCores = $cpu.NumberOfCores
            NumberOfLogicalProcessors = $cpu.NumberOfLogicalProcessors
            Name = $cpu.Name
            MaxClockSpeed = $cpu.MaxClockSpeed
            Architecture = switch($cpu.Architecture) {
                0 {'x86'}
                1 {'MIPS'}
                2 {'Alpha'}
                3 {'PowerPC'}
                5 {'ARM'}
                6 {'ia64'}
                9 {'x64'}
                default {'Unknown'}
            }
        } | ConvertTo-Json
        """
        
        result = self.execute_powershell(script)
        if result.success:
            try:
                data = json.loads(result.stdout)
                info['count'] = data.get('NumberOfLogicalProcessors', 0)
                info['model'] = data.get('Name', 'unknown')
                info['speed_mhz'] = data.get('MaxClockSpeed', 0)
                info['architecture'] = data.get('Architecture', 'unknown')
            except json.JSONDecodeError:
                pass
                
        return info
    
    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Upload file to remote system"""
        return self.connection.upload_file(local_path, remote_path)
    
    def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download file from remote system"""
        return self.connection.download_file(remote_path, local_path)
    
    def file_exists(self, path: str) -> bool:
        """Check if file exists"""
        result = self.execute_powershell(f"Test-Path -Path '{path}'")
        return result.success and result.stdout.strip().lower() == 'true'
    
    def create_directory(self, path: str, recursive: bool = True) -> CommandResult:
        """Create directory"""
        force = "-Force" if recursive else ""
        return self.execute_powershell(f"New-Item -ItemType Directory -Path '{path}' {force}")
    
    def remove_file(self, path: str) -> CommandResult:
        """Remove file"""
        return self.execute_powershell(f"Remove-Item -Path '{path}' -Force")
    
    def list_directory(self, path: str) -> List[Dict[str, Any]]:
        """List directory contents"""
        files = []
        
        script = f"""
        Get-ChildItem -Path '{path}' | ForEach-Object {{
            @{{
                Name = $_.Name
                FullName = $_.FullName
                Length = if ($_.PSIsContainer) {{ 0 }} else {{ $_.Length }}
                CreationTime = $_.CreationTime.ToString('yyyy-MM-dd HH:mm:ss')
                LastWriteTime = $_.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss')
                IsDirectory = $_.PSIsContainer
                Attributes = $_.Attributes.ToString()
            }}
        }} | ConvertTo-Json -Depth 2
        """
        
        result = self.execute_powershell(script)
        if result.success:
            try:
                file_data = json.loads(result.stdout)
                if not isinstance(file_data, list):
                    file_data = [file_data]
                    
                for item in file_data:
                    files.append({
                        'name': item.get('Name', ''),
                        'path': item.get('FullName', ''),
                        'size': item.get('Length', 0),
                        'created': item.get('CreationTime', ''),
                        'modified': item.get('LastWriteTime', ''),
                        'is_directory': item.get('IsDirectory', False),
                        'attributes': item.get('Attributes', '')
                    })
            except json.JSONDecodeError:
                pass
                
        return files
    
    def reboot(self, wait_for_reboot: bool = True) -> CommandResult:
        """Reboot the system"""
        result = self.execute_command("shutdown /r /t 0")
        
        if wait_for_reboot and result.success:
            # Connection handler should manage reconnection
            self.connection.wait_for_reboot()
            
        return result
    
    def shutdown(self) -> CommandResult:
        """Shutdown the system"""
        return self.execute_command("shutdown /s /t 0")
    
    # Helper methods
    def _parse_ipconfig(self) -> List[NetworkInterface]:
        """Parse ipconfig output as fallback"""
        interfaces = []
        result = self.execute_command("ipconfig /all")
        
        if result.success:
            current_iface = None
            
            for line in result.stdout.split('\n'):
                line = line.strip()
                
                # Adapter header
                if 'adapter' in line.lower() and ':' in line:
                    if current_iface:
                        interfaces.append(current_iface)
                    
                    name = line.split(':')[0].replace('Ethernet adapter', '').strip()
                    current_iface = NetworkInterface(
                        name=name,
                        mac_address='',
                        ip_addresses=[],
                        netmask=None,
                        gateway=None,
                        vlan_id=None,
                        mtu=1500,
                        state='up',
                        type='ethernet'
                    )
                    
                elif current_iface:
                    # Physical Address
                    if 'physical address' in line.lower():
                        mac = line.split(':')[-1].strip().replace('-', ':').lower()
                        current_iface.mac_address = mac
                        
                    # IPv4 Address
                    elif 'ipv4 address' in line.lower():
                        ip = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                        if ip:
                            current_iface.ip_addresses.append(ip.group(1))
                            
                    # Subnet Mask
                    elif 'subnet mask' in line.lower():
                        mask = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                        if mask:
                            current_iface.netmask = mask.group(1)
                            
                    # Default Gateway
                    elif 'default gateway' in line.lower():
                        gw = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                        if gw:
                            current_iface.gateway = gw.group(1)
                            
            if current_iface:
                interfaces.append(current_iface)
                
        return interfaces
    
    def _prefix_to_netmask(self, prefix: int) -> str:
        """Convert CIDR prefix to netmask"""
        mask = (0xffffffff << (32 - prefix)) & 0xffffffff
        return '.'.join([str((mask >> (8 * i)) & 0xff) for i in range(3, -1, -1)])
    
    def _netmask_to_prefix(self, netmask: str) -> int:
        """Convert netmask to CIDR prefix"""
        return sum(bin(int(x)).count('1') for x in netmask.split('.'))
    
    def _format_bytes(self, bytes_val: int) -> str:
        """Format bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.1f}{unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.1f}PB"