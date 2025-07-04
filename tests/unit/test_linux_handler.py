"""
Unit tests for Linux OS Handler
"""

import pytest
import json
from unittest.mock import Mock, patch
from pod.os_abstraction.linux import LinuxHandler
from pod.os_abstraction.base import NetworkConfig, CommandResult, NetworkInterface
from pod.connections.ssh import SSHConnection


class TestLinuxHandler:
    """Test cases for LinuxHandler"""

    def test_init(self, mock_ssh_connection):
        """Test Linux handler initialization"""
        handler = LinuxHandler(mock_ssh_connection)
        assert handler.connection == mock_ssh_connection
        assert handler._os_info is None

    def test_execute_command_success(self, linux_handler_with_mock_connection):
        """Test successful command execution"""
        handler = linux_handler_with_mock_connection
        handler.connection.execute_command.return_value = ("output", "", 0)
        
        with patch('time.time', side_effect=[0, 0.1]):
            result = handler.execute_command("ls -la")
        
        assert isinstance(result, CommandResult)
        assert result.stdout == "output"
        assert result.stderr == ""
        assert result.exit_code == 0
        assert result.success is True
        assert result.command == "ls -la"
        assert result.duration == 0.1

    def test_execute_command_with_sudo(self, linux_handler_with_mock_connection):
        """Test command execution with sudo"""
        handler = linux_handler_with_mock_connection
        handler.connection.execute_sudo_command.return_value = ("output", "", 0)
        
        with patch('time.time', side_effect=[0, 0.1]):
            result = handler.execute_command("systemctl restart nginx", as_admin=True)
        
        handler.connection.execute_sudo_command.assert_called_once()
        assert result.success is True

    def test_execute_command_with_error(self, linux_handler_with_mock_connection):
        """Test command execution with error"""
        handler = linux_handler_with_mock_connection
        handler.connection.execute_command.return_value = ("", "error", 1)
        
        with patch('time.time', side_effect=[0, 0.1]):
            result = handler.execute_command("invalid_command")
        
        assert result.success is False
        assert result.exit_code == 1
        assert result.stderr == "error"

    def test_get_network_interfaces_json_success(self, linux_handler_with_mock_connection, mock_ip_addr_json):
        """Test getting network interfaces with JSON output"""
        handler = linux_handler_with_mock_connection
        
        # Mock successful JSON command
        success_result = CommandResult("", "", 0, True, "ip -j addr show", 0.1)
        success_result.stdout = mock_ip_addr_json
        
        with patch.object(handler, 'execute_command', return_value=success_result):
            with patch.object(handler, '_get_default_gateway', return_value="192.168.1.1"):
                interfaces = handler.get_network_interfaces()
        
        assert len(interfaces) == 2
        assert interfaces[0].name == "lo"
        assert interfaces[0].ip_addresses == ["127.0.0.1"]
        assert interfaces[1].name == "eth0"
        assert interfaces[1].ip_addresses == ["192.168.1.100"]
        assert interfaces[1].mac_address == "00:50:56:12:34:56"

    def test_get_network_interfaces_json_fallback(self, linux_handler_with_mock_connection):
        """Test getting network interfaces with JSON fallback to text"""
        handler = linux_handler_with_mock_connection
        
        # Mock failed JSON command, successful text command
        failed_result = CommandResult("", "error", 1, False, "ip -j addr show", 0.1)
        text_output = "1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN\n    inet 127.0.0.1/8 scope host lo"
        success_result = CommandResult("", "", 0, True, "ip addr show", 0.1)
        success_result.stdout = text_output
        
        with patch.object(handler, 'execute_command', side_effect=[failed_result, success_result]):
            with patch.object(handler, '_parse_ip_addr_text', return_value=[]) as mock_parse:
                interfaces = handler.get_network_interfaces()
        
        mock_parse.assert_called_once_with(text_output)

    def test_get_network_interfaces_json_parse_error(self, linux_handler_with_mock_connection):
        """Test getting network interfaces with JSON parse error"""
        handler = linux_handler_with_mock_connection
        
        # Mock successful command but invalid JSON
        success_result = CommandResult("", "", 0, True, "ip -j addr show", 0.1)
        success_result.stdout = "invalid json"
        
        with patch.object(handler, 'execute_command', return_value=success_result):
            with patch.object(handler, '_parse_ip_addr_text', return_value=[]) as mock_parse:
                interfaces = handler.get_network_interfaces()
        
        mock_parse.assert_called_once_with("invalid json")

    def test_configure_network_networkmanager(self, linux_handler_with_mock_connection, sample_network_config):
        """Test network configuration with NetworkManager"""
        handler = linux_handler_with_mock_connection
        
        # Mock detection and NetworkManager configuration
        nm_active = CommandResult("active", "", 0, True, "systemctl is-active NetworkManager", 0.1)
        systemd_inactive = CommandResult("inactive", "", 1, False, "systemctl is-active systemd-networkd", 0.1)
        delete_result = CommandResult("", "", 0, True, "nmcli con delete", 0.1)
        config_success = CommandResult("", "", 0, True, "nmcli con add", 0.1)
        activate_success = CommandResult("", "", 0, True, "nmcli con up", 0.1)
        
        with patch.object(handler, 'execute_command', side_effect=[nm_active, systemd_inactive, delete_result, config_success, activate_success]):
            with patch.object(handler, '_netmask_to_prefix', return_value=24):
                result = handler.configure_network(sample_network_config)
        
        assert result.success is True

    def test_configure_network_systemd(self, linux_handler_with_mock_connection, sample_network_config):
        """Test network configuration with systemd-networkd"""
        handler = linux_handler_with_mock_connection
        
        # Mock systemd-networkd detection
        nm_inactive = CommandResult("inactive", "", 1, False, "systemctl is-active NetworkManager", 0.1)
        systemd_active = CommandResult("active", "", 0, True, "systemctl is-active systemd-networkd", 0.1)
        
        with patch.object(handler, 'execute_command', side_effect=[nm_inactive, systemd_active]):
            with patch.object(handler, '_configure_network_systemd', return_value=CommandResult("", "", 0, True, "configure", 0.1)) as mock_systemd:
                result = handler.configure_network(sample_network_config)
        
        mock_systemd.assert_called_once_with(sample_network_config)
        assert result.success is True

    def test_configure_network_legacy(self, linux_handler_with_mock_connection, sample_network_config):
        """Test network configuration with legacy ip commands"""
        handler = linux_handler_with_mock_connection
        
        # Mock no network managers active
        nm_inactive = CommandResult("inactive", "", 1, False, "systemctl is-active NetworkManager", 0.1)
        systemd_inactive = CommandResult("inactive", "", 1, False, "systemctl is-active systemd-networkd", 0.1)
        
        with patch.object(handler, 'execute_command', side_effect=[nm_inactive, systemd_inactive]):
            with patch.object(handler, '_configure_network_ip', return_value=CommandResult("", "", 0, True, "configure", 0.1)) as mock_ip:
                result = handler.configure_network(sample_network_config)
        
        mock_ip.assert_called_once_with(sample_network_config)
        assert result.success is True

    def test_restart_network_service_success(self, linux_handler_with_mock_connection):
        """Test successful network service restart"""
        handler = linux_handler_with_mock_connection
        success_result = CommandResult("", "", 0, True, "systemctl restart NetworkManager", 0.1)
        
        with patch.object(handler, 'execute_command', return_value=success_result):
            result = handler.restart_network_service()
        
        assert result.success is True

    def test_restart_network_service_fallback(self, linux_handler_with_mock_connection):
        """Test network service restart with fallback"""
        handler = linux_handler_with_mock_connection
        
        # Mock failures for first few services, success for last
        failed_result = CommandResult("", "error", 1, False, "systemctl restart", 0.1)
        success_result = CommandResult("", "", 0, True, "ifdown -a && ifup -a", 0.1)
        
        with patch.object(handler, 'execute_command', side_effect=[failed_result, failed_result, failed_result, failed_result, success_result]):
            result = handler.restart_network_service()
        
        assert result.success is True

    def test_get_os_info_cached(self, linux_handler_with_mock_connection):
        """Test getting cached OS info"""
        handler = linux_handler_with_mock_connection
        cached_info = {'type': 'linux', 'distribution': 'Rocky Linux'}
        handler._os_info = cached_info
        
        result = handler.get_os_info()
        assert result == cached_info

    def test_get_os_info_new(self, linux_handler_with_mock_connection, mock_os_release_content):
        """Test getting new OS info"""
        handler = linux_handler_with_mock_connection
        
        os_release_result = CommandResult("", "", 0, True, "cat /etc/os-release", 0.1)
        os_release_result.stdout = mock_os_release_content
        
        kernel_result = CommandResult("5.14.0-70.el9.x86_64", "", 0, True, "uname -r", 0.1)
        arch_result = CommandResult("x86_64", "", 0, True, "uname -m", 0.1)
        hostname_result = CommandResult("test-vm", "", 0, True, "hostname", 0.1)
        
        with patch.object(handler, 'execute_command', side_effect=[os_release_result, kernel_result, arch_result, hostname_result]):
            result = handler.get_os_info()
        
        assert result['type'] == 'linux'
        assert result['distribution'] == 'Rocky Linux'
        assert result['version'] == '9.0 (Blue Onyx)'
        assert result['kernel'] == '5.14.0-70.el9.x86_64'
        assert result['architecture'] == 'x86_64'
        assert result['hostname'] == 'test-vm'
        assert handler._os_info == result

    def test_install_package_dnf(self, linux_handler_with_mock_connection):
        """Test package installation with dnf"""
        handler = linux_handler_with_mock_connection
        
        dnf_found = CommandResult("/usr/bin/dnf", "", 0, True, "which dnf", 0.1)
        install_success = CommandResult("", "", 0, True, "dnf install -y tcpdump", 0.1)
        
        with patch.object(handler, 'execute_command', side_effect=[dnf_found, install_success]):
            result = handler.install_package("tcpdump")
        
        assert result.success is True

    def test_install_package_apt(self, linux_handler_with_mock_connection):
        """Test package installation with apt"""
        handler = linux_handler_with_mock_connection
        
        dnf_not_found = CommandResult("", "not found", 1, False, "which dnf", 0.1)
        yum_not_found = CommandResult("", "not found", 1, False, "which yum", 0.1)
        apt_found = CommandResult("/usr/bin/apt-get", "", 0, True, "which apt-get", 0.1)
        install_success = CommandResult("", "", 0, True, "apt-get install -y tcpdump", 0.1)
        
        with patch.object(handler, 'execute_command', side_effect=[dnf_not_found, yum_not_found, apt_found, install_success]):
            result = handler.install_package("tcpdump")
        
        assert result.success is True

    def test_install_package_no_manager(self, linux_handler_with_mock_connection):
        """Test package installation with no package manager"""
        handler = linux_handler_with_mock_connection
        
        not_found = CommandResult("", "not found", 1, False, "which", 0.1)
        
        with patch.object(handler, 'execute_command', return_value=not_found):
            result = handler.install_package("tcpdump")
        
        assert result.success is False
        assert "No supported package manager found" in result.stderr

    def test_start_service(self, linux_handler_with_mock_connection):
        """Test starting a service"""
        handler = linux_handler_with_mock_connection
        success_result = CommandResult("", "", 0, True, "systemctl start nginx", 0.1)
        
        with patch.object(handler, 'execute_command', return_value=success_result):
            result = handler.start_service("nginx")
        
        assert result.success is True

    def test_stop_service(self, linux_handler_with_mock_connection):
        """Test stopping a service"""
        handler = linux_handler_with_mock_connection
        success_result = CommandResult("", "", 0, True, "systemctl stop nginx", 0.1)
        
        with patch.object(handler, 'execute_command', return_value=success_result):
            result = handler.stop_service("nginx")
        
        assert result.success is True

    def test_get_service_status(self, linux_handler_with_mock_connection):
        """Test getting service status"""
        handler = linux_handler_with_mock_connection
        success_result = CommandResult("active (running)", "", 0, True, "systemctl status nginx", 0.1)
        
        with patch.object(handler, 'execute_command', return_value=success_result):
            result = handler.get_service_status("nginx")
        
        assert result.success is True
        assert "active (running)" in result.stdout

    def test_create_user_without_password(self, linux_handler_with_mock_connection):
        """Test creating user without password"""
        handler = linux_handler_with_mock_connection
        success_result = CommandResult("", "", 0, True, "useradd testuser", 0.1)
        
        with patch.object(handler, 'execute_command', return_value=success_result):
            result = handler.create_user("testuser")
        
        assert result.success is True

    def test_create_user_with_password(self, linux_handler_with_mock_connection):
        """Test creating user with password"""
        handler = linux_handler_with_mock_connection
        user_success = CommandResult("", "", 0, True, "useradd testuser", 0.1)
        pass_success = CommandResult("", "", 0, True, "echo 'testuser:password' | chpasswd", 0.1)
        
        with patch.object(handler, 'execute_command', side_effect=[user_success, pass_success]):
            result = handler.create_user("testuser", password="password")
        
        assert result.success is True

    def test_create_user_with_groups(self, linux_handler_with_mock_connection):
        """Test creating user with groups"""
        handler = linux_handler_with_mock_connection
        success_result = CommandResult("", "", 0, True, "useradd testuser -G wheel,docker", 0.1)
        
        with patch.object(handler, 'execute_command', return_value=success_result):
            result = handler.create_user("testuser", groups=["wheel", "docker"])
        
        assert result.success is True

    def test_set_hostname(self, linux_handler_with_mock_connection):
        """Test setting hostname"""
        handler = linux_handler_with_mock_connection
        success_result = CommandResult("", "", 0, True, "hostnamectl set-hostname test-host", 0.1)
        
        with patch.object(handler, 'execute_command', return_value=success_result):
            result = handler.set_hostname("test-host")
        
        assert result.success is True

    def test_get_processes(self, linux_handler_with_mock_connection, mock_ps_aux_output):
        """Test getting processes"""
        handler = linux_handler_with_mock_connection
        success_result = CommandResult("", "", 0, True, "ps aux", 0.1)
        success_result.stdout = mock_ps_aux_output
        
        with patch.object(handler, 'execute_command', return_value=success_result):
            processes = handler.get_processes()
        
        assert len(processes) == 5  # 4 system processes + 1 user process
        assert processes[0]['user'] == 'root'
        assert processes[0]['pid'] == 1
        assert processes[-1]['user'] == 'testuser'
        assert processes[-1]['pid'] == 1234

    def test_kill_process(self, linux_handler_with_mock_connection):
        """Test killing a process"""
        handler = linux_handler_with_mock_connection
        success_result = CommandResult("", "", 0, True, "kill -15 1234", 0.1)
        
        with patch.object(handler, 'execute_command', return_value=success_result):
            result = handler.kill_process(1234)
        
        assert result.success is True

    def test_kill_process_custom_signal(self, linux_handler_with_mock_connection):
        """Test killing a process with custom signal"""
        handler = linux_handler_with_mock_connection
        success_result = CommandResult("", "", 0, True, "kill -9 1234", 0.1)
        
        with patch.object(handler, 'execute_command', return_value=success_result):
            result = handler.kill_process(1234, signal=9)
        
        assert result.success is True

    def test_get_disk_usage(self, linux_handler_with_mock_connection, mock_df_output):
        """Test getting disk usage"""
        handler = linux_handler_with_mock_connection
        success_result = CommandResult("", "", 0, True, "df -h", 0.1)
        success_result.stdout = mock_df_output
        
        with patch.object(handler, 'execute_command', return_value=success_result):
            disks = handler.get_disk_usage()
        
        assert len(disks) == 7
        assert disks[0]['filesystem'] == '/dev/sda1'
        assert disks[0]['size'] == '20G'
        assert disks[0]['use_percent'] == '28'
        assert disks[0]['mount_point'] == '/'

    def test_get_memory_info(self, linux_handler_with_mock_connection, mock_free_output):
        """Test getting memory info"""
        handler = linux_handler_with_mock_connection
        success_result = CommandResult("", "", 0, True, "free -b", 0.1)
        success_result.stdout = mock_free_output
        
        with patch.object(handler, 'execute_command', return_value=success_result):
            info = handler.get_memory_info()
        
        assert info['total'] == 4147159040
        assert info['used'] == 524288000
        assert info['free'] == 3000000000
        assert info['available'] == 3500000000
        assert info['swap_total'] == 2147483648
        assert info['swap_used'] == 0
        assert info['swap_free'] == 2147483648

    def test_get_cpu_info(self, linux_handler_with_mock_connection, mock_lscpu_output):
        """Test getting CPU info"""
        handler = linux_handler_with_mock_connection
        success_result = CommandResult("", "", 0, True, "lscpu", 0.1)
        success_result.stdout = mock_lscpu_output
        
        with patch.object(handler, 'execute_command', return_value=success_result):
            info = handler.get_cpu_info()
        
        assert info['count'] == 4
        assert info['model'] == 'Intel(R) Core(TM) i7-8565U CPU @ 1.80GHz'
        assert info['speed_mhz'] == 1800.0
        assert info['architecture'] == 'x86_64'

    def test_upload_file(self, linux_handler_with_mock_connection):
        """Test file upload"""
        handler = linux_handler_with_mock_connection
        handler.connection.upload_file.return_value = True
        
        result = handler.upload_file("/local/file.txt", "/remote/file.txt")
        
        assert result is True
        handler.connection.upload_file.assert_called_once_with("/local/file.txt", "/remote/file.txt")

    def test_download_file(self, linux_handler_with_mock_connection):
        """Test file download"""
        handler = linux_handler_with_mock_connection
        handler.connection.download_file.return_value = True
        
        result = handler.download_file("/remote/file.txt", "/local/file.txt")
        
        assert result is True
        handler.connection.download_file.assert_called_once_with("/remote/file.txt", "/local/file.txt")

    def test_file_exists_true(self, linux_handler_with_mock_connection):
        """Test file exists check - file exists"""
        handler = linux_handler_with_mock_connection
        success_result = CommandResult("", "", 0, True, "test -e '/path/file.txt'", 0.1)
        
        with patch.object(handler, 'execute_command', return_value=success_result):
            result = handler.file_exists("/path/file.txt")
        
        assert result is True

    def test_file_exists_false(self, linux_handler_with_mock_connection):
        """Test file exists check - file doesn't exist"""
        handler = linux_handler_with_mock_connection
        failed_result = CommandResult("", "", 1, False, "test -e '/path/file.txt'", 0.1)
        
        with patch.object(handler, 'execute_command', return_value=failed_result):
            result = handler.file_exists("/path/file.txt")
        
        assert result is False

    def test_create_directory(self, linux_handler_with_mock_connection):
        """Test directory creation"""
        handler = linux_handler_with_mock_connection
        success_result = CommandResult("", "", 0, True, "mkdir -p '/path/dir'", 0.1)
        
        with patch.object(handler, 'execute_command', return_value=success_result):
            result = handler.create_directory("/path/dir")
        
        assert result.success is True

    def test_create_directory_non_recursive(self, linux_handler_with_mock_connection):
        """Test non-recursive directory creation"""
        handler = linux_handler_with_mock_connection
        success_result = CommandResult("", "", 0, True, "mkdir  '/path/dir'", 0.1)
        
        with patch.object(handler, 'execute_command', return_value=success_result):
            result = handler.create_directory("/path/dir", recursive=False)
        
        assert result.success is True

    def test_remove_file(self, linux_handler_with_mock_connection):
        """Test file removal"""
        handler = linux_handler_with_mock_connection
        success_result = CommandResult("", "", 0, True, "rm -f '/path/file.txt'", 0.1)
        
        with patch.object(handler, 'execute_command', return_value=success_result):
            result = handler.remove_file("/path/file.txt")
        
        assert result.success is True

    def test_list_directory(self, linux_handler_with_mock_connection):
        """Test directory listing"""
        handler = linux_handler_with_mock_connection
        ls_output = """total 12
drwxr-xr-x 2 root root 4096 Oct 1 10:30 .
drwxr-xr-x 3 root root 4096 Oct 1 10:29 ..
-rw-r--r-- 1 root root   12 Oct 1 10:30 test.txt"""
        
        success_result = CommandResult("", "", 0, True, "ls -la '/path'", 0.1)
        success_result.stdout = ls_output
        
        with patch.object(handler, 'execute_command', return_value=success_result):
            files = handler.list_directory("/path")
        
        assert len(files) == 3
        assert files[0]['name'] == '.'
        assert files[0]['permissions'] == 'drwxr-xr-x'
        assert files[2]['name'] == 'test.txt'
        assert files[2]['size'] == 12

    def test_reboot(self, linux_handler_with_mock_connection):
        """Test system reboot"""
        handler = linux_handler_with_mock_connection
        success_result = CommandResult("", "", 0, True, "shutdown -r now", 0.1)
        
        with patch.object(handler, 'execute_command', return_value=success_result):
            with patch.object(handler.connection, 'wait_for_reboot') as mock_wait:
                result = handler.reboot()
                
                assert result.success is True
                mock_wait.assert_called_once()

    def test_reboot_no_wait(self, linux_handler_with_mock_connection):
        """Test system reboot without waiting"""
        handler = linux_handler_with_mock_connection
        success_result = CommandResult("", "", 0, True, "shutdown -r now", 0.1)
        
        with patch.object(handler, 'execute_command', return_value=success_result):
            result = handler.reboot(wait_for_reboot=False)
        
        assert result.success is True

    def test_shutdown(self, linux_handler_with_mock_connection):
        """Test system shutdown"""
        handler = linux_handler_with_mock_connection
        success_result = CommandResult("", "", 0, True, "shutdown -h now", 0.1)
        
        with patch.object(handler, 'execute_command', return_value=success_result):
            result = handler.shutdown()
        
        assert result.success is True

    # Helper method tests
    def test_prefix_to_netmask(self, linux_handler_with_mock_connection):
        """Test converting CIDR prefix to netmask"""
        handler = linux_handler_with_mock_connection
        
        assert handler._prefix_to_netmask(24) == "255.255.255.0"
        assert handler._prefix_to_netmask(16) == "255.255.0.0"
        assert handler._prefix_to_netmask(8) == "255.0.0.0"
        assert handler._prefix_to_netmask(30) == "255.255.255.252"

    def test_netmask_to_prefix(self, linux_handler_with_mock_connection):
        """Test converting netmask to CIDR prefix"""
        handler = linux_handler_with_mock_connection
        
        assert handler._netmask_to_prefix("255.255.255.0") == 24
        assert handler._netmask_to_prefix("255.255.0.0") == 16
        assert handler._netmask_to_prefix("255.0.0.0") == 8
        assert handler._netmask_to_prefix("255.255.255.252") == 30

    def test_get_default_gateway(self, linux_handler_with_mock_connection):
        """Test getting default gateway"""
        handler = linux_handler_with_mock_connection
        route_output = "default via 192.168.1.1 dev eth0 proto dhcp metric 100"
        success_result = CommandResult("", "", 0, True, "ip route show default dev eth0", 0.1)
        success_result.stdout = route_output
        
        with patch.object(handler, 'execute_command', return_value=success_result):
            gateway = handler._get_default_gateway("eth0")
        
        assert gateway == "192.168.1.1"

    def test_get_default_gateway_not_found(self, linux_handler_with_mock_connection):
        """Test getting default gateway when not found"""
        handler = linux_handler_with_mock_connection
        failed_result = CommandResult("", "", 1, False, "ip route show default dev eth0", 0.1)
        
        with patch.object(handler, 'execute_command', return_value=failed_result):
            gateway = handler._get_default_gateway("eth0")
        
        assert gateway is None

    def test_get_interface_type(self, linux_handler_with_mock_connection):
        """Test determining interface type"""
        handler = linux_handler_with_mock_connection
        
        assert handler._get_interface_type("eth0") == "ethernet"
        assert handler._get_interface_type("enp0s3") == "ethernet"
        assert handler._get_interface_type("wlan0") == "wifi"
        assert handler._get_interface_type("wlp2s0") == "wifi"
        assert handler._get_interface_type("lo") == "loopback"
        assert handler._get_interface_type("docker0") == "virtual"
        assert handler._get_interface_type("br-123456") == "virtual"
        assert handler._get_interface_type("unknown") == "unknown"