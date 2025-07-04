"""
Extended unit tests for Linux handler to improve coverage
"""

import pytest
import json
from unittest.mock import Mock, patch
from pod.os_abstraction.linux import LinuxHandler
from pod.os_abstraction.base import NetworkConfig
from pod.connections.ssh import SSHConnection


class TestLinuxHandlerExtended:
    """Extended tests for Linux handler coverage"""
    
    @pytest.fixture
    def mock_ssh_connection(self):
        """Create a mock SSH connection"""
        mock = Mock(spec=SSHConnection)
        mock.execute_command.return_value = ("", "", 0)
        mock.execute_sudo_command.return_value = ("", "", 0)
        mock.upload_file.return_value = True
        mock.download_file.return_value = True
        return mock
    
    @pytest.fixture
    def linux_handler(self, mock_ssh_connection):
        """Create Linux handler with mock connection"""
        return LinuxHandler(mock_ssh_connection)
    
    def test_get_network_interfaces_text_parsing(self, linux_handler, mock_ssh_connection):
        """Test parsing text output when JSON is not available"""
        # Reset the mock to use side_effect
        mock_ssh_connection.execute_command.return_value = None
        # First call fails (no JSON support), second returns text output
        text_output = """
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP
    link/ether 52:54:00:12:34:56 brd ff:ff:ff:ff:ff:ff
    inet 192.168.1.100/24 brd 192.168.1.255 scope global eth0
3: eth0.100@eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP
    link/ether 52:54:00:12:34:56 brd ff:ff:ff:ff:ff:ff
    inet 192.168.100.10/24 scope global eth0.100
4: docker0: <NO-CARRIER,BROADCAST,MULTICAST,UP> mtu 1500 qdisc noqueue state DOWN
    link/ether 02:42:ac:11:00:01 brd ff:ff:ff:ff:ff:ff
"""
        
        mock_ssh_connection.execute_command.side_effect = [
            ("", "error", 1),  # JSON command fails
            (text_output, "", 0)  # Text command succeeds
        ]
        
        interfaces = linux_handler.get_network_interfaces()
        
        assert len(interfaces) == 4
        
        # Check loopback
        lo = next(i for i in interfaces if i.name == "lo")
        assert lo.state == "up"
        assert "127.0.0.1" in lo.ip_addresses
        assert lo.type == "loopback"
        
        # Check eth0
        eth0 = next(i for i in interfaces if i.name == "eth0")
        assert eth0.mac_address == "52:54:00:12:34:56"
        assert "192.168.1.100" in eth0.ip_addresses
        assert eth0.netmask == "255.255.255.0"
        assert eth0.mtu == 1500
        assert eth0.state == "up"
        
        # Check VLAN interface
        vlan = next(i for i in interfaces if i.name == "eth0.100")
        assert "192.168.100.10" in vlan.ip_addresses
        
        # Check docker0
        docker = next(i for i in interfaces if i.name == "docker0")
        assert docker.state == "down"
        assert docker.type == "virtual"
    
    def test_configure_network_systemd(self, linux_handler, mock_ssh_connection):
        """Test network configuration with systemd-networkd"""
        # Mock systemd-networkd as active
        mock_ssh_connection.execute_command.side_effect = [
            ("inactive", "", 0),  # NetworkManager not active
            ("active", "", 0),    # systemd-networkd is active
        ]
        # After side_effect is exhausted, return default
        mock_ssh_connection.execute_command.return_value = ("", "", 0)
        mock_ssh_connection.execute_sudo_command.return_value = ("", "", 0)
        
        config = NetworkConfig(
            interface="eth0",
            ip_address="192.168.1.50",
            netmask="255.255.255.0",
            gateway="192.168.1.1",
            dns_servers=["8.8.8.8", "8.8.4.4"]
        )
        
        result = linux_handler.configure_network(config)
        
        assert result.success
        
        # Check that systemd network file was created
        # The execute_sudo_command should have been called for the network file creation
        sudo_calls = mock_ssh_connection.execute_sudo_command.call_args_list
        assert len(sudo_calls) > 0
        
        # Find the call that creates the network file
        network_file_created = False
        for call in sudo_calls:
            cmd = call[0][0]
            if "/etc/systemd/network" in cmd and "192.168.1.50/24" in cmd:
                network_file_created = True
                assert "Gateway=192.168.1.1" in cmd
                assert "DNS=8.8.8.8" in cmd
                break
        
        assert network_file_created, "Network file was not created"
    
    def test_execute_command_with_sudo_already_present(self, linux_handler, mock_ssh_connection):
        """Test that sudo is not duplicated if already in command"""
        mock_ssh_connection.execute_sudo_command.return_value = ("output", "", 0)
        
        result = linux_handler.execute_command("sudo apt update", as_admin=True)
        
        # Should not add sudo twice
        assert result.success
        mock_ssh_connection.execute_sudo_command.assert_called_with("sudo apt update", timeout=30)
    
    def test_json_decode_error_fallback(self, linux_handler, mock_ssh_connection):
        """Test JSON decode error handling"""
        # Return invalid JSON
        mock_ssh_connection.execute_command.return_value = ("{invalid json", "", 0)
        
        # Should fall back to text parsing
        interfaces = linux_handler.get_network_interfaces()
        
        # Will attempt to parse as text (empty in this case)
        assert interfaces == []
    
    def test_configure_network_dhcp_systemd(self, linux_handler, mock_ssh_connection):
        """Test DHCP configuration with systemd"""
        mock_ssh_connection.execute_command.side_effect = [
            ("inactive", "", 0),  # NetworkManager not active
            ("active", "", 0),    # systemd-networkd is active
        ]
        # Set defaults for remaining calls
        mock_ssh_connection.execute_command.return_value = ("", "", 0)
        mock_ssh_connection.execute_sudo_command.return_value = ("", "", 0)
        
        config = NetworkConfig(
            interface="eth0",
            dhcp=True
        )
        
        result = linux_handler.configure_network(config)
        assert result.success
        
        # Check DHCP was configured
        sudo_calls = mock_ssh_connection.execute_sudo_command.call_args_list
        assert len(sudo_calls) > 0
        
        # Find the call that creates the network file with DHCP
        dhcp_configured = False
        for call in sudo_calls:
            cmd = call[0][0]
            if "/etc/systemd/network" in cmd and "DHCP=yes" in cmd:
                dhcp_configured = True
                break
        
        assert dhcp_configured, "DHCP was not configured"
    
    def test_install_package_no_manager_found(self, linux_handler, mock_ssh_connection):
        """Test package installation when no package manager is found"""
        # All package managers fail
        mock_ssh_connection.execute_command.side_effect = [
            ("", "command not found", 1),  # dnf
            ("", "command not found", 1),  # yum
            ("", "command not found", 1),  # apt-get
            ("", "command not found", 1),  # zypper
            ("", "command not found", 1),  # pacman
        ]
        
        result = linux_handler.install_package("test-package")
        
        assert not result.success
        assert "No supported package manager found" in result.stderr
    
    def test_get_processes_malformed_output(self, linux_handler, mock_ssh_connection):
        """Test process listing with malformed output"""
        # Return output with incomplete lines
        mock_ssh_connection.execute_command.return_value = (
            "USER PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND\n"
            "root 1 0.0\n"  # Incomplete line
            "user 1234 0.1 0.5 12345 6789 pts/0 S 10:00 0:01 /usr/bin/test",
            "", 0
        )
        
        processes = linux_handler.get_processes()
        
        # Should only parse complete lines
        assert len(processes) == 1
        assert processes[0]['pid'] == 1234
    
    def test_get_disk_usage_malformed_output(self, linux_handler, mock_ssh_connection):
        """Test disk usage with malformed output"""
        mock_ssh_connection.execute_command.return_value = (
            "Filesystem Size Used Avail Use% Mounted\n"
            "/dev/sda1\n"  # Incomplete line
            "/dev/sda2 100G 50G 45G 53% /home",
            "", 0
        )
        
        disks = linux_handler.get_disk_usage()
        
        assert len(disks) == 1
        assert disks[0]['filesystem'] == "/dev/sda2"
    
    def test_list_directory_malformed_output(self, linux_handler, mock_ssh_connection):
        """Test directory listing with malformed output"""
        mock_ssh_connection.execute_command.return_value = (
            "total 16\n"
            "drwxr-xr-x 2\n"  # Incomplete line
            "-rw-r--r-- 1 user group 1024 Jan 1 10:00 file.txt",
            "", 0
        )
        
        files = linux_handler.list_directory("/test")
        
        assert len(files) == 1
        assert files[0]['name'] == "file.txt"
    
    def test_network_interface_edge_cases(self, linux_handler, mock_ssh_connection):
        """Test various network interface types"""
        text_output = """
1: wlan0: <BROADCAST,MULTICAST> mtu 1500 qdisc mq state DOWN
    link/ether aa:bb:cc:dd:ee:ff brd ff:ff:ff:ff:ff:ff
2: br0: <BROADCAST,MULTICAST,UP> mtu 1500 qdisc noqueue state UP
    link/ether 11:22:33:44:55:66 brd ff:ff:ff:ff:ff:ff
3: tun0: <POINTOPOINT,MULTICAST,NOARP,UP> mtu 1500 qdisc fq_codel state UNKNOWN
    link/none
"""
        
        mock_ssh_connection.execute_command.side_effect = [
            ("", "error", 1),  # JSON fails
            (text_output, "", 0)
        ]
        
        interfaces = linux_handler.get_network_interfaces()
        
        # Check interface types
        wlan = next(i for i in interfaces if i.name == "wlan0")
        assert wlan.type == "wifi"
        assert wlan.state == "down"
        
        bridge = next(i for i in interfaces if i.name == "br0")
        assert bridge.type == "virtual"
        
        tun = next(i for i in interfaces if i.name == "tun0")
        assert tun.type == "unknown"
    
    def test_memory_info_edge_cases(self, linux_handler, mock_ssh_connection):
        """Test memory info parsing edge cases"""
        # Output without available memory (older systems)
        mock_ssh_connection.execute_command.return_value = (
            "              total        used        free      shared  buff/cache   available\n"
            "Mem:     8589934592  4294967296  2147483648   134217728  2147483648\n"
            "Swap:    4294967296  1073741824  3221225472",
            "", 0
        )
        
        memory = linux_handler.get_memory_info()
        
        assert memory['total'] == 8589934592
        assert memory['used'] == 4294967296
        assert memory['free'] == 2147483648
        assert memory['available'] == memory['free']  # Falls back to free
        assert memory['swap_total'] == 4294967296