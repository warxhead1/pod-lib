"""
Unit tests for base classes
"""

import pytest
from unittest.mock import Mock, patch
from pod.os_abstraction.base import CommandResult, NetworkInterface, NetworkConfig, BaseOSHandler
from pod.connections.base import BaseConnection
from pod.exceptions import TimeoutError as PODTimeoutError


class TestCommandResult:
    """Test cases for CommandResult"""

    def test_init(self):
        """Test CommandResult initialization"""
        result = CommandResult(
            stdout="output",
            stderr="error",
            exit_code=0,
            success=True,
            command="test command",
            duration=0.5,
            data={"key": "value"}
        )
        
        assert result.stdout == "output"
        assert result.stderr == "error"
        assert result.exit_code == 0
        assert result.success is True
        assert result.command == "test command"
        assert result.duration == 0.5
        assert result.data == {"key": "value"}

    def test_init_minimal(self):
        """Test CommandResult initialization with minimal parameters"""
        result = CommandResult(
            stdout="output",
            stderr="",
            exit_code=0,
            success=True,
            command="test",
            duration=0.1
        )
        
        assert result.data is None

    def test_bool_success(self):
        """Test boolean conversion for successful result"""
        result = CommandResult("", "", 0, True, "test", 0.1)
        assert bool(result) is True

    def test_bool_failure(self):
        """Test boolean conversion for failed result"""
        result = CommandResult("", "error", 1, False, "test", 0.1)
        assert bool(result) is False


class TestNetworkInterface:
    """Test cases for NetworkInterface"""

    def test_init(self):
        """Test NetworkInterface initialization"""
        interface = NetworkInterface(
            name="eth0",
            mac_address="00:50:56:12:34:56",
            ip_addresses=["192.168.1.100", "10.0.0.100"],
            netmask="255.255.255.0",
            gateway="192.168.1.1",
            vlan_id=100,
            mtu=1500,
            state="up",
            type="ethernet"
        )
        
        assert interface.name == "eth0"
        assert interface.mac_address == "00:50:56:12:34:56"
        assert interface.ip_addresses == ["192.168.1.100", "10.0.0.100"]
        assert interface.netmask == "255.255.255.0"
        assert interface.gateway == "192.168.1.1"
        assert interface.vlan_id == 100
        assert interface.mtu == 1500
        assert interface.state == "up"
        assert interface.type == "ethernet"

    def test_init_minimal(self):
        """Test NetworkInterface initialization with minimal parameters"""
        interface = NetworkInterface(
            name="lo",
            mac_address="00:00:00:00:00:00",
            ip_addresses=["127.0.0.1"],
            netmask=None,
            gateway=None,
            vlan_id=None,
            mtu=65536,
            state="up",
            type="loopback"
        )
        
        assert interface.netmask is None
        assert interface.gateway is None
        assert interface.vlan_id is None


class TestNetworkConfig:
    """Test cases for NetworkConfig"""

    def test_init_full(self):
        """Test NetworkConfig initialization with all parameters"""
        config = NetworkConfig(
            interface="eth1",
            ip_address="192.168.100.10",
            netmask="255.255.255.0",
            gateway="192.168.100.1",
            dns_servers=["8.8.8.8", "8.8.4.4"],
            vlan_id=100,
            mtu=1500,
            dhcp=False
        )
        
        assert config.interface == "eth1"
        assert config.ip_address == "192.168.100.10"
        assert config.netmask == "255.255.255.0"
        assert config.gateway == "192.168.100.1"
        assert config.dns_servers == ["8.8.8.8", "8.8.4.4"]
        assert config.vlan_id == 100
        assert config.mtu == 1500
        assert config.dhcp is False

    def test_init_minimal(self):
        """Test NetworkConfig initialization with minimal parameters"""
        config = NetworkConfig(interface="eth0")
        
        assert config.interface == "eth0"
        assert config.ip_address is None
        assert config.netmask is None
        assert config.gateway is None
        assert config.dns_servers is None
        assert config.vlan_id is None
        assert config.mtu is None
        assert config.dhcp is False

    def test_init_dhcp(self):
        """Test NetworkConfig initialization for DHCP"""
        config = NetworkConfig(
            interface="eth0",
            dhcp=True
        )
        
        assert config.interface == "eth0"
        assert config.dhcp is True


class MockOSHandler(BaseOSHandler):
    """Mock implementation of BaseOSHandler for testing"""
    
    def execute_command(self, command: str, timeout: int = 30, as_admin: bool = False):
        return CommandResult("mock output", "", 0, True, command, 0.1)
    
    def get_network_interfaces(self):
        return []
    
    def configure_network(self, config):
        return CommandResult("", "", 0, True, "configure_network", 0.1)
    
    def restart_network_service(self):
        return CommandResult("", "", 0, True, "restart_network", 0.1)
    
    def get_os_info(self):
        return {"type": "mock", "distribution": "test"}
    
    def install_package(self, package_name: str):
        return CommandResult("", "", 0, True, f"install {package_name}", 0.1)
    
    def start_service(self, service_name: str):
        return CommandResult("", "", 0, True, f"start {service_name}", 0.1)
    
    def stop_service(self, service_name: str):
        return CommandResult("", "", 0, True, f"stop {service_name}", 0.1)
    
    def get_service_status(self, service_name: str):
        return CommandResult("active", "", 0, True, f"status {service_name}", 0.1)
    
    def create_user(self, username: str, password=None, groups=None):
        return CommandResult("", "", 0, True, f"create_user {username}", 0.1)
    
    def set_hostname(self, hostname: str):
        return CommandResult("", "", 0, True, f"set_hostname {hostname}", 0.1)
    
    def get_processes(self):
        return []
    
    def kill_process(self, process_id: int, signal: int = 15):
        return CommandResult("", "", 0, True, f"kill {process_id}", 0.1)
    
    def get_disk_usage(self):
        return []
    
    def get_memory_info(self):
        return {}
    
    def get_cpu_info(self):
        return {}
    
    def upload_file(self, local_path: str, remote_path: str):
        return True
    
    def download_file(self, remote_path: str, local_path: str):
        return True
    
    def file_exists(self, path: str):
        return True
    
    def create_directory(self, path: str, recursive: bool = True):
        return CommandResult("", "", 0, True, f"mkdir {path}", 0.1)
    
    def remove_file(self, path: str):
        return CommandResult("", "", 0, True, f"rm {path}", 0.1)
    
    def list_directory(self, path: str):
        return []


class TestBaseOSHandler:
    """Test cases for BaseOSHandler"""

    def test_init(self):
        """Test BaseOSHandler initialization"""
        mock_connection = Mock()
        handler = MockOSHandler(mock_connection)
        
        assert handler.connection == mock_connection
        assert handler._os_info is None

    def test_reboot_default(self):
        """Test reboot with default wait"""
        mock_connection = Mock()
        handler = MockOSHandler(mock_connection)
        
        result = handler.reboot()
        
        assert result.success is True
        mock_connection.wait_for_reboot.assert_called_once()

    def test_reboot_no_wait(self):
        """Test reboot without waiting"""
        mock_connection = Mock()
        handler = MockOSHandler(mock_connection)
        
        result = handler.reboot(wait_for_reboot=False)
        
        assert result.success is True
        mock_connection.wait_for_reboot.assert_not_called()

    def test_shutdown(self):
        """Test system shutdown"""
        mock_connection = Mock()
        handler = MockOSHandler(mock_connection)
        
        result = handler.shutdown()
        
        assert result.success is True
        assert result.command == "shutdown -h now"


class MockConnection(BaseConnection):
    """Mock implementation of BaseConnection for testing"""
    
    @property
    def default_port(self):
        return 22
    
    def connect(self):
        self._connected = True
    
    def disconnect(self):
        self._connected = False
    
    def execute_command(self, command: str, timeout=None):
        return ("output", "", 0)
    
    def upload_file(self, local_path: str, remote_path: str):
        return True
    
    def download_file(self, remote_path: str, local_path: str):
        return True
    
    def is_connected(self):
        return self._connected


class TestBaseConnection:
    """Test cases for BaseConnection"""

    def test_init(self):
        """Test BaseConnection initialization"""
        connection = MockConnection(
            host="192.168.1.100",
            username="user",
            password="password",
            port=2222,
            timeout=60
        )
        
        assert connection.host == "192.168.1.100"
        assert connection.username == "user"
        assert connection.password == "password"
        assert connection.port == 2222
        assert connection.timeout == 60
        assert connection._connected is False

    def test_init_default_port(self):
        """Test BaseConnection initialization with default port"""
        connection = MockConnection(
            host="192.168.1.100",
            username="user",
            password="password"
        )
        
        assert connection.port == 22  # default_port

    def test_init_with_key(self):
        """Test BaseConnection initialization with key file"""
        connection = MockConnection(
            host="192.168.1.100",
            username="user",
            key_filename="/path/to/key.pem"
        )
        
        assert connection.key_filename == "/path/to/key.pem"
        assert connection.password is None

    @pytest.mark.parametrize("wait_time,timeout", [
        (30, 300),
        (10, 120),
        (60, 600)
    ])
    def test_wait_for_reboot_params(self, wait_time, timeout):
        """Test wait_for_reboot with different parameters"""
        connection = MockConnection("host", "user", "pass")
        connection._connected = True
        
        with patch('time.sleep') as mock_sleep:
            with patch('time.time', side_effect=[0, wait_time + 5, wait_time + 10]):
                connection.wait_for_reboot(wait_time=wait_time, timeout=timeout)
        
        # Should sleep for wait_time initially
        mock_sleep.assert_called()

    def test_context_manager(self):
        """Test context manager functionality"""
        connection = MockConnection("host", "user", "pass")
        
        with connection as conn:
            assert conn is connection
            assert connection._connected is True
        
        assert connection._connected is False

    def test_context_manager_with_exception(self):
        """Test context manager with exception"""
        connection = MockConnection("host", "user", "pass")
        
        try:
            with connection:
                assert connection._connected is True
                raise ValueError("Test exception")
        except ValueError:
            pass
        
        assert connection._connected is False

    @patch('time.sleep')
    @patch('time.time')
    def test_wait_for_reboot_timeout_error(self, mock_time, mock_sleep):
        """Test wait_for_reboot timeout"""
        # Mock time to always exceed timeout
        mock_time.side_effect = [0] + [400] * 10  # Always exceed 300s timeout
        
        connection = MockConnection("host", "user", "pass")
        connection._connected = True
        
        # Mock failed reconnection attempts
        original_connect = connection.connect
        connection.connect = Mock(side_effect=Exception("Connection failed"))
        
        with pytest.raises(PODTimeoutError):
            connection.wait_for_reboot(wait_time=1, timeout=300)

    @patch('time.sleep')
    @patch('time.time')
    def test_wait_for_reboot_success(self, mock_time, mock_sleep):
        """Test successful wait_for_reboot"""
        # Mock time progression
        mock_time.side_effect = [0, 35, 40]  # Initial, after wait, after reconnect
        
        connection = MockConnection("host", "user", "pass")
        connection._connected = True
        
        connection.wait_for_reboot(wait_time=30, timeout=300)
        
        # Should have been disconnected and reconnected
        assert connection._connected is True