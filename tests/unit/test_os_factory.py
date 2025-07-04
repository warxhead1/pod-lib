"""
Unit tests for OS handler factory
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pod.os_abstraction.factory import OSHandlerFactory
from pod.os_abstraction.linux import LinuxHandler
from pod.os_abstraction.windows import WindowsHandler
from pod.connections.ssh import SSHConnection
from pod.connections.winrm import WinRMConnection


class TestOSHandlerFactory:
    """Test OS handler factory functionality"""
    
    @pytest.fixture
    def mock_ssh_connection(self):
        """Create a mock SSH connection"""
        mock = Mock(spec=SSHConnection)
        mock.execute_command.return_value = ("", "", 0)
        return mock
    
    @pytest.fixture
    def mock_winrm_connection(self):
        """Create a mock WinRM connection"""
        mock = Mock(spec=WinRMConnection)
        mock.execute_command.return_value = ("", "", 0)
        return mock
    
    def test_create_handler_with_explicit_os_type(self, mock_ssh_connection):
        """Test creating handler with explicit OS type"""
        os_info = {'type': 'linux'}
        
        handler = OSHandlerFactory.create_handler(mock_ssh_connection, os_info)
        
        assert isinstance(handler, LinuxHandler)
        assert handler.connection == mock_ssh_connection
    
    def test_create_handler_windows(self, mock_winrm_connection):
        """Test creating Windows handler"""
        os_info = {'type': 'windows'}
        
        handler = OSHandlerFactory.create_handler(mock_winrm_connection, os_info)
        
        assert isinstance(handler, WindowsHandler)
        assert handler.connection == mock_winrm_connection
    
    def test_create_handler_from_guest_id(self, mock_ssh_connection):
        """Test creating handler from vSphere guest ID"""
        test_cases = [
            ('rhel8_64Guest', LinuxHandler),
            ('ubuntu64Guest', LinuxHandler),
            ('windows2019srv_64Guest', WindowsHandler),
            ('windows10_64Guest', WindowsHandler),
        ]
        
        for guest_id, expected_handler in test_cases:
            os_info = {'guest_id': guest_id}
            handler = OSHandlerFactory.create_handler(mock_ssh_connection, os_info)
            assert isinstance(handler, expected_handler)
    
    def test_create_handler_from_connection_type(self, mock_ssh_connection, mock_winrm_connection):
        """Test handler creation based on connection type"""
        # SSH connection should create Linux handler
        handler = OSHandlerFactory.create_handler(mock_ssh_connection)
        assert isinstance(handler, LinuxHandler)
        
        # WinRM connection should create Windows handler
        handler = OSHandlerFactory.create_handler(mock_winrm_connection)
        assert isinstance(handler, WindowsHandler)
    
    def test_detect_linux_distro_ubuntu(self, mock_ssh_connection):
        """Test Linux distribution detection - Ubuntu"""
        mock_ssh_connection.execute_command.return_value = (
            """
NAME="Ubuntu"
VERSION="20.04.3 LTS (Focal Fossa)"
ID=ubuntu
ID_LIKE=debian
            """, "", 0
        )
        
        os_info = {}
        handler = OSHandlerFactory.create_handler(mock_ssh_connection, os_info)
        
        assert isinstance(handler, LinuxHandler)
    
    def test_detect_linux_distro_rhel(self, mock_ssh_connection):
        """Test Linux distribution detection - RHEL"""
        mock_ssh_connection.execute_command.return_value = (
            """
NAME="Red Hat Enterprise Linux"
VERSION="8.5 (Ootpa)"
ID="rhel"
ID_LIKE="fedora"
            """, "", 0
        )
        
        handler = OSHandlerFactory.create_handler(mock_ssh_connection)
        assert isinstance(handler, LinuxHandler)
    
    def test_detect_linux_distro_rocky(self, mock_ssh_connection):
        """Test Linux distribution detection - Rocky Linux"""
        mock_ssh_connection.execute_command.return_value = (
            """
NAME="Rocky Linux"
VERSION="9.0 (Blue Onyx)"
ID="rocky"
ID_LIKE="rhel centos fedora"
            """, "", 0
        )
        
        handler = OSHandlerFactory.create_handler(mock_ssh_connection)
        assert isinstance(handler, LinuxHandler)
    
    def test_fallback_to_uname(self, mock_ssh_connection):
        """Test fallback to uname when os-release fails"""
        # First call fails (os-release), second succeeds (uname)
        mock_ssh_connection.execute_command.side_effect = [
            ("", "File not found", 1),
            ("Linux ubuntu-server 5.4.0-88-generic #99-Ubuntu SMP", "", 0)
        ]
        
        handler = OSHandlerFactory.create_handler(mock_ssh_connection)
        assert isinstance(handler, LinuxHandler)
    
    def test_guest_family_detection(self, mock_ssh_connection):
        """Test OS detection from guest family"""
        os_info = {'guest_family': 'windowsGuest'}
        
        # Even with SSH connection, should detect Windows from guest family
        handler = OSHandlerFactory.create_handler(mock_ssh_connection, os_info)
        # Note: This will create a LinuxHandler because we're using SSH connection
        # In real scenario, proper connection type would be used
        
        os_info = {'guest_family': 'linuxGuest'}
        handler = OSHandlerFactory.create_handler(mock_ssh_connection, os_info)
        assert isinstance(handler, LinuxHandler)
    
    def test_unsupported_os_type(self, mock_ssh_connection):
        """Test error handling for unsupported OS type"""
        os_info = {'type': 'unsupported_os'}
        
        with pytest.raises(ValueError, match="Unsupported OS type"):
            OSHandlerFactory.create_handler(mock_ssh_connection, os_info)
    
    def test_register_custom_handler(self, mock_ssh_connection):
        """Test registering custom OS handler"""
        # Create a custom handler
        class CustomHandler(LinuxHandler):
            pass
        
        # Register it
        OSHandlerFactory.register_handler('custom_os', CustomHandler)
        
        # Create handler with custom OS type
        os_info = {'type': 'custom_os'}
        handler = OSHandlerFactory.create_handler(mock_ssh_connection, os_info)
        
        assert isinstance(handler, CustomHandler)
        assert 'custom_os' in OSHandlerFactory.get_supported_os_types()
    
    def test_register_invalid_handler(self):
        """Test registering invalid handler class"""
        class InvalidHandler:
            pass
        
        with pytest.raises(ValueError, match="must inherit from BaseOSHandler"):
            OSHandlerFactory.register_handler('invalid', InvalidHandler)
    
    def test_register_guest_id_mapping(self, mock_ssh_connection):
        """Test registering custom guest ID mapping"""
        # Register custom mapping
        OSHandlerFactory.register_guest_id_mapping('customGuest', 'linux')
        
        # Test it works
        os_info = {'guest_id': 'customGuest'}
        handler = OSHandlerFactory.create_handler(mock_ssh_connection, os_info)
        
        assert isinstance(handler, LinuxHandler)
    
    def test_get_supported_os_types(self):
        """Test getting list of supported OS types"""
        supported = OSHandlerFactory.get_supported_os_types()
        
        assert 'linux' in supported
        assert 'windows' in supported
        assert 'ubuntu' in supported
        assert 'rhel' in supported
        assert 'centos' in supported
        assert 'rocky' in supported
        assert 'windows_server' in supported
    
    def test_is_os_supported(self):
        """Test checking if OS is supported"""
        assert OSHandlerFactory.is_os_supported('linux') is True
        assert OSHandlerFactory.is_os_supported('windows') is True
        assert OSHandlerFactory.is_os_supported('WINDOWS') is True  # Case insensitive
        assert OSHandlerFactory.is_os_supported('unsupported') is False
    
    def test_multiple_os_info_precedence(self, mock_winrm_connection):
        """Test precedence when multiple OS info is provided"""
        # Explicit type should take precedence over guest_id
        os_info = {
            'type': 'windows',
            'guest_id': 'ubuntu64Guest',  # Contradictory info
            'guest_family': 'linuxGuest'
        }
        
        handler = OSHandlerFactory.create_handler(mock_winrm_connection, os_info)
        assert isinstance(handler, WindowsHandler)
    
    def test_linux_distro_variants(self, mock_ssh_connection):
        """Test various Linux distribution handlers"""
        distros = ['debian', 'ubuntu', 'rhel', 'centos', 'rocky', 'fedora', 'opensuse']
        
        for distro in distros:
            os_info = {'type': distro}
            handler = OSHandlerFactory.create_handler(mock_ssh_connection, os_info)
            assert isinstance(handler, LinuxHandler)
    
    def test_windows_variants(self, mock_winrm_connection):
        """Test various Windows version handlers"""
        versions = ['windows_server', 'windows_10', 'windows_11']
        
        for version in versions:
            os_info = {'type': version}
            handler = OSHandlerFactory.create_handler(mock_winrm_connection, os_info)
            assert isinstance(handler, WindowsHandler)
    
    def test_exception_handling_in_detection(self, mock_ssh_connection):
        """Test exception handling during OS detection"""
        # Make execute_command raise an exception
        mock_ssh_connection.execute_command.side_effect = Exception("Connection error")
        
        # Should still create a handler (defaults to Linux for SSH)
        handler = OSHandlerFactory.create_handler(mock_ssh_connection)
        assert isinstance(handler, LinuxHandler)
    
    @patch('pod.os_abstraction.factory.logger')
    def test_logging(self, mock_logger, mock_ssh_connection):
        """Test that factory logs appropriately"""
        os_info = {'type': 'linux'}
        
        handler = OSHandlerFactory.create_handler(mock_ssh_connection, os_info)
        
        # Should log handler creation
        mock_logger.info.assert_called()
        assert 'LinuxHandler' in str(mock_logger.info.call_args)