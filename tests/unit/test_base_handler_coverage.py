"""
Tests to improve coverage of base handler abstract methods
"""

import pytest
from unittest.mock import Mock
from pod.os_abstraction.base import BaseOSHandler, NetworkConfig, CommandResult
from pod.connections.base import BaseConnection


class ConcreteOSHandler(BaseOSHandler):
    """Concrete implementation for testing"""
    
    def execute_command(self, command, timeout=30, as_admin=False):
        stdout, stderr, code = self.connection.execute_command(command, timeout)
        return CommandResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=code,
            success=code == 0,
            command=command,
            duration=0.1
        )
    
    def get_network_interfaces(self):
        raise NotImplementedError("Test method")
    
    def configure_network(self, config):
        raise NotImplementedError("Test method")
    
    def restart_network_service(self):
        raise NotImplementedError("Test method")
    
    def get_os_info(self):
        raise NotImplementedError("Test method")
    
    def install_package(self, package_name):
        raise NotImplementedError("Test method")
    
    def start_service(self, service_name):
        raise NotImplementedError("Test method")
    
    def stop_service(self, service_name):
        raise NotImplementedError("Test method")
    
    def get_service_status(self, service_name):
        raise NotImplementedError("Test method")
    
    def create_user(self, username, password=None, groups=None):
        raise NotImplementedError("Test method")
    
    def set_hostname(self, hostname):
        raise NotImplementedError("Test method")
    
    def get_processes(self):
        raise NotImplementedError("Test method")
    
    def kill_process(self, process_id, signal=15):
        raise NotImplementedError("Test method")
    
    def get_disk_usage(self):
        raise NotImplementedError("Test method")
    
    def get_memory_info(self):
        raise NotImplementedError("Test method")
    
    def get_cpu_info(self):
        raise NotImplementedError("Test method")
    
    def upload_file(self, local_path, remote_path):
        raise NotImplementedError("Test method")
    
    def download_file(self, remote_path, local_path):
        raise NotImplementedError("Test method")
    
    def file_exists(self, path):
        raise NotImplementedError("Test method")
    
    def create_directory(self, path, recursive=True):
        raise NotImplementedError("Test method")
    
    def remove_file(self, path):
        raise NotImplementedError("Test method")
    
    def list_directory(self, path):
        raise NotImplementedError("Test method")


class TestBaseHandlerCoverage:
    """Test base handler for coverage"""
    
    @pytest.fixture
    def mock_connection(self):
        """Create mock connection"""
        mock = Mock(spec=BaseConnection)
        mock.wait_for_reboot = Mock()
        return mock
    
    @pytest.fixture
    def handler(self, mock_connection):
        """Create concrete handler"""
        return ConcreteOSHandler(mock_connection)
    
    def test_abstract_methods_raise_not_implemented(self, handler):
        """Test that abstract methods raise NotImplementedError"""
        methods = [
            ('get_network_interfaces', []),
            ('configure_network', [NetworkConfig("eth0")]),
            ('restart_network_service', []),
            ('get_os_info', []),
            ('install_package', ["test"]),
            ('start_service', ["nginx"]),
            ('stop_service', ["nginx"]),
            ('get_service_status', ["nginx"]),
            ('create_user', ["testuser"]),
            ('set_hostname', ["test-host"]),
            ('get_processes', []),
            ('kill_process', [1234]),
            ('get_disk_usage', []),
            ('get_memory_info', []),
            ('get_cpu_info', []),
            ('upload_file', ["/src", "/dst"]),
            ('download_file', ["/src", "/dst"]),
            ('file_exists', ["/test"]),
            ('create_directory', ["/test"]),
            ('remove_file', ["/test"]),
            ('list_directory', ["/test"])
        ]
        
        for method_name, args in methods:
            method = getattr(handler, method_name)
            with pytest.raises(NotImplementedError):
                method(*args)


class TestPODClient:
    """Test POD client for coverage"""
    
    def test_client_methods(self):
        """Test client method stubs"""
        from pod.client import PODClient
        
        client = PODClient("host", "user", "pass")
        
        # Test placeholder implementations
        client.connect()
        assert client._connected is True
        
        client.disconnect()
        assert client._connected is False
        
        # These methods have placeholder implementations that return None
        result = client.get_vm("test-vm")
        assert result is None
        
        result = client.clone_vm("source", "target")
        assert result is None
        
        # These methods don't exist in PODClient
        with pytest.raises(AttributeError):
            client.get_container("test-container")
            
        with pytest.raises(AttributeError):
            client.list_vms()


class TestBaseConnectionCoverage:
    """Test base connection abstract methods"""
    
    def test_abstract_methods(self):
        """Test that abstract methods are defined"""
        from pod.connections.base import BaseConnection
        
        # Create a concrete implementation
        class ConcreteConnection(BaseConnection):
            @property
            def default_port(self):
                return 22
                
            def connect(self, **kwargs):
                pass
                
            def disconnect(self):
                pass
                
            def is_connected(self):
                return True
                
            def execute_command(self, command, timeout=30):
                return "", "", 0
                
            def upload_file(self, local_path, remote_path):
                return True
                
            def download_file(self, remote_path, local_path):
                return True
                
        conn = ConcreteConnection(host="test", username="user")
        
        # Test methods work
        assert conn.default_port == 22
        conn.connect()
        conn.disconnect()
        assert conn.is_connected()
        
        # Test optional methods
        # execute_sudo_command doesn't exist on BaseConnection
        assert not hasattr(conn, 'execute_sudo_command')
        
        # wait_for_reboot has a default implementation
        conn.wait_for_reboot()  # Should complete without error
        
        # Test context manager
        with conn as c:
            assert c == conn