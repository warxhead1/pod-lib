"""
Unit tests for SSH Connection
"""

import pytest
import paramiko
from unittest.mock import Mock, patch, MagicMock
from pod.connections.ssh import SSHConnection
from pod.exceptions import ConnectionError, AuthenticationError
from pod.exceptions import TimeoutError as PODTimeoutError


class TestSSHConnection:
    """Test cases for SSHConnection"""

    def test_init(self):
        """Test SSH connection initialization"""
        connection = SSHConnection(
            host="192.168.1.100",
            username="root",
            password="password",
            port=22,
            timeout=30
        )
        
        assert connection.host == "192.168.1.100"
        assert connection.username == "root"
        assert connection.password == "password"
        assert connection.port == 22
        assert connection.timeout == 30
        assert connection.look_for_keys is True
        assert connection.allow_agent is True
        assert connection._client is None
        assert connection._sftp is None

    def test_init_default_port(self):
        """Test SSH connection with default port"""
        connection = SSHConnection(
            host="192.168.1.100",
            username="root",
            password="password"
        )
        
        assert connection.port == 22

    def test_init_with_key_file(self):
        """Test SSH connection with key file"""
        connection = SSHConnection(
            host="192.168.1.100",
            username="root",
            key_filename="/path/to/key.pem"
        )
        
        assert connection.key_filename == "/path/to/key.pem"
        assert connection.password is None

    def test_init_custom_options(self):
        """Test SSH connection with custom options"""
        connection = SSHConnection(
            host="192.168.1.100",
            username="root",
            password="password",
            look_for_keys=False,
            allow_agent=False
        )
        
        assert connection.look_for_keys is False
        assert connection.allow_agent is False

    @patch('paramiko.SSHClient')
    def test_connect_with_password(self, mock_ssh_client_class):
        """Test successful connection with password"""
        mock_client = Mock()
        mock_ssh_client_class.return_value = mock_client
        
        connection = SSHConnection(
            host="192.168.1.100",
            username="root",
            password="password"
        )
        
        connection.connect()
        
        assert connection._connected is True
        assert connection._client == mock_client
        mock_client.set_missing_host_key_policy.assert_called_once()
        mock_client.connect.assert_called_once()

    @patch('paramiko.SSHClient')
    def test_connect_with_key_file(self, mock_ssh_client_class):
        """Test successful connection with key file"""
        mock_client = Mock()
        mock_ssh_client_class.return_value = mock_client
        
        connection = SSHConnection(
            host="192.168.1.100",
            username="root",
            key_filename="/path/to/key.pem"
        )
        
        connection.connect()
        
        connect_call = mock_client.connect.call_args
        assert connect_call[1]['key_filename'] == "/path/to/key.pem"
        assert 'password' not in connect_call[1]

    @patch('paramiko.SSHClient')
    def test_connect_authentication_error(self, mock_ssh_client_class):
        """Test connection with authentication error"""
        mock_client = Mock()
        mock_client.connect.side_effect = paramiko.AuthenticationException("Auth failed")
        mock_ssh_client_class.return_value = mock_client
        
        connection = SSHConnection(
            host="192.168.1.100",
            username="root",
            password="wrong_password"
        )
        
        with pytest.raises(AuthenticationError):
            connection.connect()

    @patch('paramiko.SSHClient')
    def test_connect_ssh_error(self, mock_ssh_client_class):
        """Test connection with SSH error"""
        mock_client = Mock()
        mock_client.connect.side_effect = paramiko.SSHException("SSH error")
        mock_ssh_client_class.return_value = mock_client
        
        connection = SSHConnection(
            host="192.168.1.100",
            username="root",
            password="password"
        )
        
        with pytest.raises(ConnectionError):
            connection.connect()

    @patch('paramiko.SSHClient')
    def test_connect_general_error(self, mock_ssh_client_class):
        """Test connection with general error"""
        mock_client = Mock()
        mock_client.connect.side_effect = Exception("Connection failed")
        mock_ssh_client_class.return_value = mock_client
        
        connection = SSHConnection(
            host="192.168.1.100",
            username="root",
            password="password"
        )
        
        with pytest.raises(ConnectionError):
            connection.connect()

    def test_disconnect(self, mock_ssh_connection):
        """Test disconnection"""
        mock_sftp = Mock()
        mock_client = Mock()
        
        # Use real disconnect method
        connection = SSHConnection("host", "user", "pass")
        connection._sftp = mock_sftp
        connection._client = mock_client
        connection._connected = True
        
        connection.disconnect()
        
        mock_sftp.close.assert_called_once()
        mock_client.close.assert_called_once()
        assert connection._sftp is None
        assert connection._client is None
        assert connection._connected is False

    def test_execute_command_success(self):
        """Test successful command execution"""
        connection = SSHConnection("host", "user", "pass")
        connection._connected = True
        connection._client = Mock()
        
        # Mock command execution
        mock_stdin = Mock()
        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        
        mock_stdout.read.return_value = b"Command output"
        mock_stderr.read.return_value = b""
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 0
        
        connection._client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        
        stdout, stderr, exit_code = connection.execute_command("ls -la")
        
        assert stdout == "Command output"
        assert stderr == ""
        assert exit_code == 0

    def test_execute_command_with_error(self):
        """Test command execution with error"""
        connection = SSHConnection("host", "user", "pass")
        connection._connected = True
        connection._client = Mock()
        
        # Mock command execution with error
        mock_stdin = Mock()
        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        
        mock_stdout.read.return_value = b""
        mock_stderr.read.return_value = b"Command failed"
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 1
        
        connection._client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        
        stdout, stderr, exit_code = connection.execute_command("invalid_command")
        
        assert stdout == ""
        assert stderr == "Command failed"
        assert exit_code == 1

    def test_execute_command_not_connected(self):
        """Test command execution when not connected"""
        connection = SSHConnection("host", "user", "pass")
        connection._connected = False
        
        with pytest.raises(ConnectionError):
            connection.execute_command("ls")

    def test_execute_command_ssh_exception(self):
        """Test command execution with SSH exception"""
        connection = SSHConnection("host", "user", "pass")
        connection._connected = True
        connection._client = Mock()
        connection._client.exec_command.side_effect = paramiko.SSHException("Execution failed")
        
        with pytest.raises(ConnectionError):
            connection.execute_command("ls")

    def test_execute_sudo_command_with_password(self):
        """Test sudo command execution with password"""
        connection = SSHConnection("host", "user", "password")
        connection._connected = True
        connection._client = Mock()
        
        # Mock command execution
        mock_stdin = Mock()
        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        
        mock_stdout.read.return_value = b"Sudo output"
        mock_stderr.read.return_value = b"[sudo] password for user:\n"
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 0
        
        connection._client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        
        stdout, stderr, exit_code = connection.execute_sudo_command("systemctl restart nginx")
        
        assert stdout == "Sudo output"
        assert stderr == ""  # Password prompt should be filtered out
        assert exit_code == 0

    def test_execute_sudo_command_without_password(self):
        """Test sudo command execution without password"""
        connection = SSHConnection("host", "user")
        connection._connected = True
        connection._client = Mock()
        
        # Mock command execution
        mock_stdin = Mock()
        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_channel = Mock()
        
        mock_stdout.read.return_value = b"Sudo output"
        mock_stderr.read.return_value = b""
        mock_stdout.channel = mock_channel
        mock_channel.recv_exit_status.return_value = 0
        
        connection._client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        
        stdout, stderr, exit_code = connection.execute_sudo_command("systemctl restart nginx")
        
        assert stdout == "Sudo output"
        assert exit_code == 0
        # Should execute "sudo systemctl restart nginx" directly
        connection._client.exec_command.assert_called_with("sudo systemctl restart nginx", timeout=30, get_pty=True)

    def test_upload_file_success(self):
        """Test successful file upload"""
        connection = SSHConnection("host", "user", "pass")
        connection._connected = True
        connection._client = Mock()
        connection._sftp = None
        
        mock_sftp = Mock()
        connection._client.open_sftp.return_value = mock_sftp
        
        result = connection.upload_file("/local/file.txt", "/remote/file.txt")
        
        assert result is True
        mock_sftp.put.assert_called_once_with("/local/file.txt", "/remote/file.txt")
        assert connection._sftp == mock_sftp

    def test_upload_file_not_connected(self):
        """Test file upload when not connected"""
        connection = SSHConnection("host", "user", "pass")
        connection._connected = False
        
        with pytest.raises(ConnectionError):
            connection.upload_file("/local/file.txt", "/remote/file.txt")

    def test_upload_file_error(self):
        """Test file upload with error"""
        connection = SSHConnection("host", "user", "pass")
        connection._connected = True
        connection._client = Mock()
        
        mock_sftp = Mock()
        mock_sftp.put.side_effect = Exception("Upload failed")
        connection._client.open_sftp.return_value = mock_sftp
        
        with pytest.raises(ConnectionError):
            connection.upload_file("/local/file.txt", "/remote/file.txt")

    def test_download_file_success(self):
        """Test successful file download"""
        connection = SSHConnection("host", "user", "pass")
        connection._connected = True
        connection._client = Mock()
        connection._sftp = None
        
        mock_sftp = Mock()
        connection._client.open_sftp.return_value = mock_sftp
        
        result = connection.download_file("/remote/file.txt", "/local/file.txt")
        
        assert result is True
        mock_sftp.get.assert_called_once_with("/remote/file.txt", "/local/file.txt")

    def test_download_file_error(self):
        """Test file download with error"""
        connection = SSHConnection("host", "user", "pass")
        connection._connected = True
        connection._client = Mock()
        
        mock_sftp = Mock()
        mock_sftp.get.side_effect = Exception("Download failed")
        connection._client.open_sftp.return_value = mock_sftp
        
        with pytest.raises(ConnectionError):
            connection.download_file("/remote/file.txt", "/local/file.txt")

    def test_is_connected_true(self):
        """Test connection status when connected"""
        connection = SSHConnection("host", "user", "pass")
        connection._connected = True
        connection._client = Mock()
        
        mock_transport = Mock()
        mock_transport.is_active.return_value = True
        connection._client.get_transport.return_value = mock_transport
        
        assert connection.is_connected() is True

    def test_is_connected_false_not_connected(self):
        """Test connection status when not connected"""
        connection = SSHConnection("host", "user", "pass")
        connection._connected = False
        connection._client = None
        
        assert connection.is_connected() is False

    def test_is_connected_false_inactive_transport(self):
        """Test connection status with inactive transport"""
        connection = SSHConnection("host", "user", "pass")
        connection._connected = True
        connection._client = Mock()
        
        mock_transport = Mock()
        mock_transport.is_active.return_value = False
        connection._client.get_transport.return_value = mock_transport
        
        assert connection.is_connected() is False
        assert connection._connected is False

    def test_is_connected_no_transport(self):
        """Test connection status with no transport"""
        connection = SSHConnection("host", "user", "pass")
        connection._connected = True
        connection._client = Mock()
        connection._client.get_transport.return_value = None
        
        assert connection.is_connected() is False

    def test_create_sftp_client_new(self):
        """Test creating new SFTP client"""
        connection = SSHConnection("host", "user", "pass")
        connection._connected = True
        connection._client = Mock()
        connection._sftp = None
        
        mock_sftp = Mock()
        connection._client.open_sftp.return_value = mock_sftp
        
        result = connection.create_sftp_client()
        
        assert result == mock_sftp
        assert connection._sftp == mock_sftp

    def test_create_sftp_client_existing(self):
        """Test getting existing SFTP client"""
        connection = SSHConnection("host", "user", "pass")
        connection._connected = True
        connection._client = Mock()
        
        mock_sftp = Mock()
        connection._sftp = mock_sftp
        
        result = connection.create_sftp_client()
        
        assert result == mock_sftp
        connection._client.open_sftp.assert_not_called()

    def test_create_sftp_client_not_connected(self):
        """Test creating SFTP client when not connected"""
        connection = SSHConnection("host", "user", "pass")
        connection._connected = False
        
        with pytest.raises(ConnectionError):
            connection.create_sftp_client()

    def test_forward_port(self):
        """Test port forwarding setup"""
        connection = SSHConnection("host", "user", "pass")
        connection._connected = True
        connection._client = Mock()
        
        mock_transport = Mock()
        connection._client.get_transport.return_value = mock_transport
        
        connection.forward_port(8080, "remote-host", 80)
        
        mock_transport.request_port_forward.assert_called_once_with('', 8080)

    def test_forward_port_not_connected(self):
        """Test port forwarding when not connected"""
        connection = SSHConnection("host", "user", "pass")
        connection._connected = False
        
        with pytest.raises(ConnectionError):
            connection.forward_port(8080, "remote-host", 80)

    def test_context_manager_success(self):
        """Test context manager successful usage"""
        connection = SSHConnection("host", "user", "pass")
        
        with patch.object(connection, 'connect') as mock_connect:
            with patch.object(connection, 'disconnect') as mock_disconnect:
                with connection:
                    pass
                
                mock_connect.assert_called_once()
                mock_disconnect.assert_called_once()

    def test_context_manager_with_exception(self):
        """Test context manager with exception"""
        connection = SSHConnection("host", "user", "pass")
        
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
        
        connection = SSHConnection("host", "user", "pass")
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
        
        connection = SSHConnection("host", "user", "pass")
        connection._connected = True
        
        with patch.object(connection, 'disconnect'):
            with patch.object(connection, 'connect', side_effect=Exception("Connection failed")):
                with patch.object(connection, 'is_connected', return_value=False):
                    with pytest.raises(PODTimeoutError):
                        connection.wait_for_reboot(wait_time=1, timeout=300)