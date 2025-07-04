"""
Unit tests for WinRM Connection
"""

import pytest
import base64
from unittest.mock import Mock, patch, mock_open
from winrm.exceptions import WinRMError, WinRMTransportError
from pod.connections.winrm import WinRMConnection
from pod.exceptions import ConnectionError, AuthenticationError, TimeoutError as PODTimeoutError


class TestWinRMConnection:
    """Test cases for WinRMConnection"""

    def test_init_default(self):
        """Test WinRM connection initialization with defaults"""
        connection = WinRMConnection(
            host="192.168.1.101",
            username="Administrator",
            password="password"
        )
        
        assert connection.host == "192.168.1.101"
        assert connection.username == "Administrator"
        assert connection.password == "password"
        assert connection.port == 5985  # HTTP default
        assert connection.transport == "ntlm"
        assert connection.use_ssl is False
        assert connection.verify_ssl is True
        assert connection._session is None
        assert connection._protocol is None

    def test_init_with_ssl(self):
        """Test WinRM connection initialization with SSL"""
        connection = WinRMConnection(
            host="192.168.1.101",
            username="Administrator",
            password="password",
            use_ssl=True
        )
        
        assert connection.port == 5986  # HTTPS default
        assert connection.use_ssl is True

    def test_init_custom_port(self):
        """Test WinRM connection with custom port"""
        connection = WinRMConnection(
            host="192.168.1.101",
            username="Administrator",
            password="password",
            port=5555,
            use_ssl=True
        )
        
        assert connection.port == 5555

    def test_init_custom_transport(self):
        """Test WinRM connection with custom transport"""
        connection = WinRMConnection(
            host="192.168.1.101",
            username="Administrator",
            password="password",
            transport="kerberos"
        )
        
        assert connection.transport == "kerberos"

    def test_default_port_property(self):
        """Test default port property"""
        connection = WinRMConnection("host", "user", "pass")
        assert connection.default_port == 5985

    @patch('pod.connections.winrm.Session')
    @patch('pod.connections.winrm.Protocol')
    def test_connect_success(self, mock_protocol_class, mock_session_class):
        """Test successful connection"""
        # Set up the mocks first
        mock_session = Mock()
        mock_protocol = Mock()
        mock_session_class.return_value = mock_session
        mock_protocol_class.return_value = mock_protocol
        
        # Mock protocol shell operations
        mock_protocol.open_shell.return_value = "shell-id-123"
        mock_protocol.close_shell.return_value = None
        
        connection = WinRMConnection(
            host="192.168.1.101",
            username="Administrator",
            password="password"
        )
        
        connection.connect()
        
        assert connection._connected is True
        assert connection._session is not None
        assert connection._protocol is not None
        mock_protocol.open_shell.assert_called_once()
        mock_protocol.close_shell.assert_called_once_with("shell-id-123")

    @patch('pod.connections.winrm.Session')
    @patch('pod.connections.winrm.Protocol')
    def test_connect_transport_error_unauthorized(self, mock_protocol_class, mock_session_class):
        """Test connection with unauthorized transport error"""
        mock_session_class.return_value = Mock()
        mock_protocol = Mock()
        # Create a real WinRMTransportError instance
        class MockWinRMTransportError(Exception):
            def __init__(self):
                self.message = "unauthorized"
                self.code = 401
                super().__init__(self.message)
        
        mock_protocol.open_shell.side_effect = MockWinRMTransportError()
        mock_protocol_class.return_value = mock_protocol
        
        connection = WinRMConnection(
            host="192.168.1.101",
            username="Administrator",
            password="wrong_password"
        )
        
        with pytest.raises(AuthenticationError):
            connection.connect()

    @patch('pod.connections.winrm.Session')
    @patch('pod.connections.winrm.Protocol')
    def test_connect_transport_error_other(self, mock_protocol_class, mock_session_class):
        """Test connection with other transport error"""
        mock_session_class.return_value = Mock()
        mock_protocol = Mock()
        # Create a real exception instance
        class MockWinRMTransportError(Exception):
            def __init__(self):
                self.message = "timeout"
                self.code = 500
                super().__init__(self.message)
        
        mock_protocol.open_shell.side_effect = MockWinRMTransportError()
        mock_protocol_class.return_value = mock_protocol
        
        connection = WinRMConnection(
            host="192.168.1.101",
            username="Administrator",
            password="password"
        )
        
        with pytest.raises(ConnectionError):
            connection.connect()

    @patch('pod.connections.winrm.Session')
    def test_connect_general_error(self, mock_session_class):
        """Test connection with general error"""
        mock_session_class.side_effect = Exception("Connection failed")
        
        connection = WinRMConnection(
            host="192.168.1.101",
            username="Administrator",
            password="password"
        )
        
        with pytest.raises(ConnectionError):
            connection.connect()

    def test_disconnect(self):
        """Test disconnection"""
        connection = WinRMConnection("host", "user", "pass")
        connection._session = Mock()
        connection._protocol = Mock()
        connection._connected = True
        
        connection.disconnect()
        
        assert connection._session is None
        assert connection._protocol is None
        assert connection._connected is False

    def test_execute_command_success(self):
        """Test successful command execution"""
        connection = WinRMConnection("host", "user", "pass")
        connection._connected = True
        connection._session = Mock()
        
        # Mock result
        mock_result = Mock()
        mock_result.std_out = b"Command output"
        mock_result.std_err = b""
        mock_result.status_code = 0
        connection._session.run_cmd.return_value = mock_result
        
        # Mock is_connected to return True
        with patch.object(connection, 'is_connected', return_value=True):
            stdout, stderr, exit_code = connection.execute_command("dir")
        
        assert stdout == "Command output"
        assert stderr == ""
        assert exit_code == 0
        connection._session.run_cmd.assert_called_once_with("dir", timeout=30)

    def test_execute_command_with_error(self):
        """Test command execution with error"""
        connection = WinRMConnection("host", "user", "pass")
        connection._connected = True
        connection._session = Mock()
        
        # Mock result with error
        mock_result = Mock()
        mock_result.std_out = b""
        mock_result.std_err = b"Command failed"
        mock_result.status_code = 1
        connection._session.run_cmd.return_value = mock_result
        
        # Mock is_connected to return True
        with patch.object(connection, 'is_connected', return_value=True):
            stdout, stderr, exit_code = connection.execute_command("invalid_command")
        
        assert stdout == ""
        assert stderr == "Command failed"
        assert exit_code == 1

    def test_execute_command_not_connected(self):
        """Test command execution when not connected"""
        connection = WinRMConnection("host", "user", "pass")
        connection._connected = False
        
        with pytest.raises(ConnectionError):
            connection.execute_command("dir")

    def test_execute_command_winrm_error(self):
        """Test command execution with WinRM error"""
        connection = WinRMConnection("host", "user", "pass")
        connection._connected = True
        connection._session = Mock()
        connection._session.run_cmd.side_effect = WinRMError("Execution failed")
        
        with pytest.raises(ConnectionError):
            connection.execute_command("dir")

    def test_execute_command_general_error(self):
        """Test command execution with general error"""
        connection = WinRMConnection("host", "user", "pass")
        connection._connected = True
        connection._session = Mock()
        connection._session.run_cmd.side_effect = Exception("Unexpected error")
        
        with pytest.raises(ConnectionError):
            connection.execute_command("dir")

    def test_execute_powershell_success(self):
        """Test successful PowerShell execution"""
        connection = WinRMConnection("host", "user", "pass")
        connection._connected = True
        connection._session = Mock()
        
        # Mock result
        mock_result = Mock()
        mock_result.std_out = b"PowerShell output"
        mock_result.std_err = b""
        mock_result.status_code = 0
        connection._session.run_ps.return_value = mock_result
        
        # Mock is_connected to return True
        with patch.object(connection, 'is_connected', return_value=True):
            stdout, stderr, exit_code = connection.execute_powershell("Get-Service")
        
        assert stdout == "PowerShell output"
        assert stderr == ""
        assert exit_code == 0
        connection._session.run_ps.assert_called_once_with("Get-Service", timeout=30)

    def test_execute_powershell_not_connected(self):
        """Test PowerShell execution when not connected"""
        connection = WinRMConnection("host", "user", "pass")
        connection._connected = False
        
        with pytest.raises(ConnectionError):
            connection.execute_powershell("Get-Service")

    def test_execute_powershell_winrm_error(self):
        """Test PowerShell execution with WinRM error"""
        connection = WinRMConnection("host", "user", "pass")
        connection._connected = True
        connection._session = Mock()
        connection._session.run_ps.side_effect = WinRMError("PowerShell failed")
        
        with pytest.raises(ConnectionError):
            connection.execute_powershell("Get-Service")

    @patch('builtins.open', new_callable=mock_open, read_data=b'test file content')
    def test_upload_file_success(self, mock_file):
        """Test successful file upload"""
        connection = WinRMConnection("host", "user", "pass")
        connection._connected = True
        connection._session = Mock()
        
        # Mock successful PowerShell execution
        mock_result = Mock()
        mock_result.std_out = b""
        mock_result.std_err = b""
        mock_result.status_code = 0
        connection._session.run_ps.return_value = mock_result
        
        # Mock is_connected to return True
        with patch.object(connection, 'is_connected', return_value=True):
            result = connection.upload_file("/local/file.txt", "C:\\remote\\file.txt")
        
        assert result is True
        connection._session.run_ps.assert_called_once()
        
        # Verify the PowerShell script contains base64 encoded content
        call_args = connection._session.run_ps.call_args[0][0]
        assert "System.Convert" in call_args
        assert "FromBase64String" in call_args

    def test_upload_file_not_connected(self):
        """Test file upload when not connected"""
        connection = WinRMConnection("host", "user", "pass")
        connection._connected = False
        
        with pytest.raises(ConnectionError):
            connection.upload_file("/local/file.txt", "C:\\remote\\file.txt")

    @patch('builtins.open', new_callable=mock_open, read_data=b'test file content')
    def test_upload_file_powershell_error(self, mock_file):
        """Test file upload with PowerShell error"""
        connection = WinRMConnection("host", "user", "pass")
        connection._connected = True
        connection._session = Mock()
        
        # Mock PowerShell execution failure
        mock_result = Mock()
        mock_result.std_out = b""
        mock_result.std_err = b"Upload failed"
        mock_result.status_code = 1
        connection._session.run_ps.return_value = mock_result
        
        with pytest.raises(ConnectionError):
            connection.upload_file("/local/file.txt", "C:\\remote\\file.txt")

    @patch('builtins.open', new_callable=mock_open)
    def test_download_file_success(self, mock_file):
        """Test successful file download"""
        connection = WinRMConnection("host", "user", "pass")
        connection._connected = True
        connection._session = Mock()
        
        # Mock successful PowerShell execution with base64 content
        test_content = b"test file content"
        encoded_content = base64.b64encode(test_content).decode('utf-8')
        
        mock_result = Mock()
        mock_result.std_out = encoded_content.encode('utf-8')
        mock_result.std_err = b""
        mock_result.status_code = 0
        connection._session.run_ps.return_value = mock_result
        
        # Mock is_connected to return True
        with patch.object(connection, 'is_connected', return_value=True):
            result = connection.download_file("C:\\remote\\file.txt", "/local/file.txt")
        
        assert result is True
        connection._session.run_ps.assert_called_once()
        
        # Verify file was written
        mock_file.assert_called_with("/local/file.txt", "wb")
        mock_file().write.assert_called_once_with(test_content)

    def test_download_file_not_connected(self):
        """Test file download when not connected"""
        connection = WinRMConnection("host", "user", "pass")
        connection._connected = False
        
        with pytest.raises(ConnectionError):
            connection.download_file("C:\\remote\\file.txt", "/local/file.txt")

    def test_download_file_powershell_error(self):
        """Test file download with PowerShell error"""
        connection = WinRMConnection("host", "user", "pass")
        connection._connected = True
        connection._session = Mock()
        
        # Mock PowerShell execution failure
        mock_result = Mock()
        mock_result.std_out = b""
        mock_result.std_err = b"File not found"
        mock_result.status_code = 1
        connection._session.run_ps.return_value = mock_result
        
        with pytest.raises(ConnectionError):
            connection.download_file("C:\\remote\\file.txt", "/local/file.txt")

    def test_is_connected_true(self):
        """Test connection status when connected"""
        connection = WinRMConnection("host", "user", "pass")
        connection._connected = True
        connection._session = Mock()
        
        # Mock successful test command
        mock_result = Mock()
        mock_result.status_code = 0
        connection._session.run_cmd.return_value = mock_result
        
        assert connection.is_connected() is True

    def test_is_connected_false_not_connected(self):
        """Test connection status when not connected"""
        connection = WinRMConnection("host", "user", "pass")
        connection._connected = False
        connection._session = None
        
        assert connection.is_connected() is False

    def test_is_connected_false_test_command_fails(self):
        """Test connection status when test command fails"""
        connection = WinRMConnection("host", "user", "pass")
        connection._connected = True
        connection._session = Mock()
        connection._session.run_cmd.side_effect = Exception("Connection lost")
        
        assert connection.is_connected() is False
        assert connection._connected is False

    def test_is_connected_false_non_zero_exit(self):
        """Test connection status when test command returns non-zero"""
        connection = WinRMConnection("host", "user", "pass")
        connection._connected = True
        connection._session = Mock()
        
        # Mock test command failure
        mock_result = Mock()
        mock_result.status_code = 1
        connection._session.run_cmd.return_value = mock_result
        
        assert connection.is_connected() is False

    def test_execute_as_admin_success(self):
        """Test executing command as administrator"""
        connection = WinRMConnection("host", "Administrator", "password")
        connection._connected = True
        connection._session = Mock()
        
        # Mock successful PowerShell execution
        mock_result = Mock()
        mock_result.std_out = b"Admin command output"
        mock_result.std_err = b""
        mock_result.status_code = 0
        connection._session.run_ps.return_value = mock_result
        
        # Mock is_connected to return True
        with patch.object(connection, 'is_connected', return_value=True):
            stdout, stderr, exit_code = connection.execute_as_admin("dir")
        
        assert stdout == "Admin command output"
        assert stderr == ""
        assert exit_code == 0
        
        # Verify PowerShell script contains RunAs logic
        call_args = connection._session.run_ps.call_args[0][0]
        assert "Start-Process" in call_args
        assert "-Credential" in call_args

    def test_context_manager_success(self):
        """Test context manager successful usage"""
        connection = WinRMConnection("host", "user", "pass")
        
        with patch.object(connection, 'connect') as mock_connect:
            with patch.object(connection, 'disconnect') as mock_disconnect:
                with connection:
                    pass
                
                mock_connect.assert_called_once()
                mock_disconnect.assert_called_once()

    def test_context_manager_with_exception(self):
        """Test context manager with exception"""
        connection = WinRMConnection("host", "user", "pass")
        
        with patch.object(connection, 'connect') as mock_connect:
            with patch.object(connection, 'disconnect') as mock_disconnect:
                try:
                    with connection:
                        raise Exception("Test exception")
                except Exception:
                    pass
                
                mock_connect.assert_called_once()
                mock_disconnect.assert_called_once()

    @patch('time.sleep')
    @patch('time.time')
    def test_wait_for_reboot_success(self, mock_time, mock_sleep):
        """Test successful reboot wait"""
        # Mock time progression
        mock_time.side_effect = [0, 35, 40]  # Initial, after wait, after reconnect
        
        connection = WinRMConnection("host", "user", "pass")
        connection._connected = True
        
        with patch.object(connection, 'disconnect') as mock_disconnect:
            with patch.object(connection, 'connect') as mock_connect:
                with patch.object(connection, 'is_connected', return_value=True):
                    connection.wait_for_reboot(wait_time=30, timeout=300)
        
        mock_disconnect.assert_called_once()
        mock_connect.assert_called()

    @patch('time.sleep')
    @patch('time.time')
    def test_wait_for_reboot_timeout(self, mock_time, mock_sleep):
        """Test reboot wait timeout"""
        # Mock time progression to exceed timeout
        mock_time.side_effect = [0] + [310] * 10  # Exceed timeout immediately
        
        connection = WinRMConnection("host", "user", "pass")
        connection._connected = True
        
        with patch.object(connection, 'disconnect'):
            with patch.object(connection, 'connect', side_effect=Exception("Connection failed")):
                with patch.object(connection, 'is_connected', return_value=False):
                    with pytest.raises(PODTimeoutError):
                        connection.wait_for_reboot(wait_time=1, timeout=300)