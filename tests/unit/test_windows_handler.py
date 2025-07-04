"""
Unit tests for Windows OS handler
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from pod.os_abstraction.windows import WindowsHandler
from pod.os_abstraction.base import NetworkConfig, CommandResult
from pod.connections.winrm import WinRMConnection


class TestWindowsHandler:
    """Test Windows OS handler functionality"""
    
    @pytest.fixture
    def mock_winrm_connection(self):
        """Create a mock WinRM connection"""
        mock = Mock(spec=WinRMConnection)
        mock.execute_command.return_value = ("", "", 0)
        mock.execute_powershell.return_value = ("", "", 0)
        mock.upload_file.return_value = True
        mock.download_file.return_value = True
        return mock
    
    @pytest.fixture
    def windows_handler(self, mock_winrm_connection):
        """Create Windows handler with mock connection"""
        return WindowsHandler(mock_winrm_connection)
    
    def test_execute_command(self, windows_handler, mock_winrm_connection):
        """Test command execution"""
        mock_winrm_connection.execute_command.return_value = ("output", "error", 0)
        
        result = windows_handler.execute_command("dir", timeout=30)
        
        assert result.stdout == "output"
        assert result.stderr == "error"
        assert result.exit_code == 0
        assert result.success is True
        assert result.command == "dir"
        mock_winrm_connection.execute_command.assert_called_once_with("dir", timeout=30)
    
    def test_execute_powershell(self, windows_handler, mock_winrm_connection):
        """Test PowerShell execution"""
        mock_winrm_connection.execute_powershell.return_value = ("PS output", "", 0)
        
        result = windows_handler.execute_powershell("Get-Process", timeout=60)
        
        assert result.stdout == "PS output"
        assert result.exit_code == 0
        assert result.success is True
        assert "PowerShell:" in result.command
        mock_winrm_connection.execute_powershell.assert_called_once_with("Get-Process", timeout=60)
    
    def test_get_network_interfaces(self, windows_handler, mock_winrm_connection):
        """Test getting network interfaces"""
        mock_output = json.dumps([{
            "Name": "Ethernet",
            "InterfaceAlias": "Ethernet",
            "MacAddress": "00-11-22-33-44-55",
            "Status": "Up",
            "LinkSpeed": "1 Gbps",
            "InterfaceIndex": 1,
            "IPAddresses": ["192.168.1.100"],
            "PrefixLength": 24,
            "Gateway": "192.168.1.1",
            "DNSServers": ["8.8.8.8", "8.8.4.4"],
            "VlanID": "100"
        }])
        
        mock_winrm_connection.execute_powershell.return_value = (mock_output, "", 0)
        
        interfaces = windows_handler.get_network_interfaces()
        
        assert len(interfaces) == 1
        assert interfaces[0].name == "Ethernet"
        assert interfaces[0].mac_address == "00:11:22:33:44:55"
        assert interfaces[0].ip_addresses == ["192.168.1.100"]
        assert interfaces[0].gateway == "192.168.1.1"
        assert interfaces[0].vlan_id == 100
        assert interfaces[0].state == "up"
    
    def test_configure_network_static(self, windows_handler, mock_winrm_connection):
        """Test static network configuration"""
        config = NetworkConfig(
            interface="Ethernet",
            ip_address="192.168.1.100",
            netmask="255.255.255.0",
            gateway="192.168.1.1",
            dns_servers=["8.8.8.8", "8.8.4.4"],
            vlan_id=100
        )
        
        result = windows_handler.configure_network(config)
        
        # Should execute PowerShell script
        mock_winrm_connection.execute_powershell.assert_called_once()
        script = mock_winrm_connection.execute_powershell.call_args[0][0]
        
        # Verify script contains expected commands
        assert '$adapter = Get-NetAdapter -Name "Ethernet"' in script
        assert 'New-NetIPAddress' in script
        assert '192.168.1.100' in script
        assert 'Set-DnsClientServerAddress' in script
        assert 'VLAN ID' in script
    
    def test_configure_network_dhcp(self, windows_handler, mock_winrm_connection):
        """Test DHCP network configuration"""
        config = NetworkConfig(
            interface="Ethernet",
            dhcp=True
        )
        
        result = windows_handler.configure_network(config)
        
        script = mock_winrm_connection.execute_powershell.call_args[0][0]
        assert 'Set-NetIPInterface' in script
        assert '-Dhcp Enabled' in script
    
    def test_install_package_winget(self, windows_handler, mock_winrm_connection):
        """Test package installation with winget"""
        # First call checks winget availability
        mock_winrm_connection.execute_command.side_effect = [
            ("1.2.3", "", 0),  # winget exists
            ("Installing...", "", 0)  # installation succeeds
        ]
        
        result = windows_handler.install_package("7zip")
        
        assert result.success is True
        assert mock_winrm_connection.execute_command.call_count == 2
        assert "winget install" in mock_winrm_connection.execute_command.call_args_list[1][0][0]
    
    def test_install_package_chocolatey(self, windows_handler, mock_winrm_connection):
        """Test package installation with Chocolatey"""
        # First winget fails, then choco succeeds
        mock_winrm_connection.execute_command.side_effect = [
            ("", "not found", 1),  # winget not found
            ("0.10.15", "", 0),  # choco exists
            ("Installing...", "", 0)  # installation succeeds
        ]
        
        result = windows_handler.install_package("7zip")
        
        assert result.success is True
        assert "choco install" in mock_winrm_connection.execute_command.call_args_list[2][0][0]
    
    def test_service_management(self, windows_handler, mock_winrm_connection):
        """Test service start/stop/status"""
        # Test start service
        result = windows_handler.start_service("TestService")
        mock_winrm_connection.execute_powershell.assert_called_with("Start-Service -Name 'TestService'", timeout=30)
        
        # Test stop service
        result = windows_handler.stop_service("TestService")
        assert "Stop-Service" in mock_winrm_connection.execute_powershell.call_args[0][0]
        
        # Test service status
        mock_winrm_connection.execute_powershell.return_value = (
            json.dumps({
                "Name": "TestService",
                "DisplayName": "Test Service",
                "Status": "Running",
                "StartType": "Automatic"
            }), "", 0
        )
        
        result = windows_handler.get_service_status("TestService")
        assert result.success is True
    
    def test_create_user(self, windows_handler, mock_winrm_connection):
        """Test user creation"""
        result = windows_handler.create_user("testuser", "password123", ["Administrators", "Users"])
        
        script = mock_winrm_connection.execute_powershell.call_args[0][0]
        assert "New-LocalUser" in script
        assert "testuser" in script
        assert "Add-LocalGroupMember" in script
        assert "Administrators" in script
    
    def test_get_os_info(self, windows_handler, mock_winrm_connection):
        """Test getting OS information"""
        mock_output = json.dumps({
            "Caption": "Microsoft Windows Server 2019 Standard",
            "Version": "10.0.17763",
            "BuildNumber": "17763",
            "Architecture": "64-bit",
            "Hostname": "WIN-SERVER01"
        })
        
        mock_winrm_connection.execute_powershell.return_value = (mock_output, "", 0)
        
        info = windows_handler.get_os_info()
        
        assert info['type'] == 'windows'
        assert info['distribution'] == "Microsoft Windows Server 2019 Standard"
        assert info['version'] == "10.0.17763"
        assert info['build'] == "17763"
        assert info['hostname'] == "WIN-SERVER01"
    
    def test_get_processes(self, windows_handler, mock_winrm_connection):
        """Test getting process list"""
        mock_output = json.dumps([{
            "Id": 1234,
            "ProcessName": "notepad",
            "CPU": 0.5,
            "WorkingSet": 10485760,
            "Handles": 100,
            "StartTime": "2023-01-01T10:00:00"
        }])
        
        mock_winrm_connection.execute_powershell.return_value = (mock_output, "", 0)
        
        processes = windows_handler.get_processes()
        
        assert len(processes) == 1
        assert processes[0]['pid'] == 1234
        assert processes[0]['name'] == "notepad"
        assert processes[0]['memory'] == 10485760
    
    def test_get_disk_usage(self, windows_handler, mock_winrm_connection):
        """Test getting disk usage"""
        mock_output = json.dumps([{
            "Name": "C",
            "Root": "C:\\",
            "Used": 53687091200,
            "Free": 53687091200,
            "Total": 107374182400,
            "UsedPercent": 50.0
        }])
        
        mock_winrm_connection.execute_powershell.return_value = (mock_output, "", 0)
        
        disks = windows_handler.get_disk_usage()
        
        assert len(disks) == 1
        assert disks[0]['filesystem'] == "C:"
        assert disks[0]['mount_point'] == "C:\\"
        assert "50" in disks[0]['use_percent']
    
    def test_file_operations(self, windows_handler, mock_winrm_connection):
        """Test file operations"""
        # Test file exists
        mock_winrm_connection.execute_powershell.return_value = ("True", "", 0)
        assert windows_handler.file_exists("C:\\test.txt") is True
        
        # Test create directory
        result = windows_handler.create_directory("C:\\TestDir", recursive=True)
        assert "New-Item -ItemType Directory" in mock_winrm_connection.execute_powershell.call_args[0][0]
        
        # Test remove file
        result = windows_handler.remove_file("C:\\test.txt")
        assert "Remove-Item" in mock_winrm_connection.execute_powershell.call_args[0][0]
    
    def test_list_directory(self, windows_handler, mock_winrm_connection):
        """Test directory listing"""
        mock_output = json.dumps([{
            "Name": "test.txt",
            "FullName": "C:\\TestDir\\test.txt",
            "Length": 1024,
            "CreationTime": "2023-01-01 10:00:00",
            "LastWriteTime": "2023-01-02 10:00:00",
            "IsDirectory": False,
            "Attributes": "Archive"
        }])
        
        mock_winrm_connection.execute_powershell.return_value = (mock_output, "", 0)
        
        files = windows_handler.list_directory("C:\\TestDir")
        
        assert len(files) == 1
        assert files[0]['name'] == "test.txt"
        assert files[0]['size'] == 1024
        assert files[0]['is_directory'] is False
    
    def test_memory_info(self, windows_handler, mock_winrm_connection):
        """Test getting memory information"""
        mock_output = json.dumps({
            "TotalPhysicalMemory": 17179869184,
            "FreePhysicalMemory": 8589934592,
            "TotalVirtualMemory": 34359738368,
            "FreeVirtualMemory": 17179869184
        })
        
        mock_winrm_connection.execute_powershell.return_value = (mock_output, "", 0)
        
        memory = windows_handler.get_memory_info()
        
        assert memory['total'] == 17179869184
        assert memory['free'] == 8589934592
        assert memory['used'] == memory['total'] - memory['free']
        assert memory['swap_total'] == 34359738368
    
    def test_cpu_info(self, windows_handler, mock_winrm_connection):
        """Test getting CPU information"""
        mock_output = json.dumps({
            "NumberOfCores": 4,
            "NumberOfLogicalProcessors": 8,
            "Name": "Intel(R) Core(TM) i7-8700 CPU @ 3.20GHz",
            "MaxClockSpeed": 3200,
            "Architecture": "x64"
        })
        
        mock_winrm_connection.execute_powershell.return_value = (mock_output, "", 0)
        
        cpu = windows_handler.get_cpu_info()
        
        assert cpu['count'] == 8
        assert "Intel" in cpu['model']
        assert cpu['speed_mhz'] == 3200
        assert cpu['architecture'] == 'x64'
    
    def test_error_handling(self, windows_handler, mock_winrm_connection):
        """Test error handling"""
        # Test command failure
        mock_winrm_connection.execute_command.return_value = ("", "Access denied", 5)
        
        result = windows_handler.execute_command("restricted_command")
        
        assert result.success is False
        assert result.exit_code == 5
        assert result.stderr == "Access denied"
    
    def test_network_fallback(self, windows_handler, mock_winrm_connection):
        """Test network interface fallback to ipconfig"""
        # PowerShell fails, falls back to ipconfig
        mock_winrm_connection.execute_powershell.return_value = ("", "error", 1)
        mock_winrm_connection.execute_command.return_value = (
            """
Ethernet adapter Ethernet:

   Connection-specific DNS Suffix  . : example.com
   Physical Address. . . . . . . . . : 00-11-22-33-44-55
   DHCP Enabled. . . . . . . . . . . : No
   IPv4 Address. . . . . . . . . . . : 192.168.1.100
   Subnet Mask . . . . . . . . . . . : 255.255.255.0
   Default Gateway . . . . . . . . . : 192.168.1.1
            """, "", 0
        )
        
        interfaces = windows_handler.get_network_interfaces()
        
        assert len(interfaces) > 0
        assert interfaces[0].mac_address == "00:11:22:33:44:55"
        assert "192.168.1.100" in interfaces[0].ip_addresses