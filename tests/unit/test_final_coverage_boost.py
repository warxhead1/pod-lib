"""
Final coverage boost - testing remaining uncovered lines
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pod.connections.winrm import WinRMConnection
from pod.os_abstraction.windows import WindowsHandler
from pod.os_abstraction.base import NetworkConfig


class TestWinRMConnectionFinal:
    """Final WinRM connection tests"""
    
    @patch('pod.connections.winrm.Session')
    @patch('pod.connections.winrm.Protocol')
    def test_execute_powershell_error_handling(self, mock_protocol_class, mock_session_class):
        """Test PowerShell execution error handling"""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_protocol = Mock()
        mock_protocol.open_shell.return_value = "shell-123"
        mock_protocol_class.return_value = mock_protocol
        
        connection = WinRMConnection("192.168.1.100", username="admin", password="pass")
        connection.connect()
        
        # Test PowerShell execution with error
        mock_result = Mock()
        mock_result.std_out = b"Output"
        mock_result.std_err = b"Error"
        mock_result.status_code = 1
        mock_session.run_ps.return_value = mock_result
        
        # Mock is_connected to return True
        with patch.object(connection, 'is_connected', return_value=True):
            stdout, stderr, code = connection.execute_powershell("Get-Process")
        
        assert stdout == "Output"
        assert stderr == "Error"
        assert code == 1
    
    def test_upload_download_not_implemented(self):
        """Test upload/download are implemented"""
        connection = WinRMConnection("192.168.1.100", username="admin", password="pass")
        connection._connected = True
        connection._session = Mock()
        
        # Upload file - should call PowerShell
        mock_result = Mock()
        mock_result.std_out = b""
        mock_result.std_err = b""
        mock_result.status_code = 0
        connection._session.run_ps = Mock(return_value=mock_result)
        
        from unittest.mock import mock_open
        
        with patch.object(connection, 'is_connected', return_value=True):
            with patch('builtins.open', mock_open(read_data=b'test content')):
                result = connection.upload_file("/src", "/dst")
                assert result is True
            
            # Download file - should call PowerShell
            mock_result.std_out = b"dGVzdCBjb250ZW50"  # base64 encoded "test content"
            connection._session.run_ps = Mock(return_value=mock_result)
            
            with patch('builtins.open', mock_open()):
                result = connection.download_file("/src", "/dst")
                assert result is True


class TestWindowsHandlerFinal:
    """Final Windows handler tests"""
    
    @pytest.fixture
    def mock_winrm(self):
        mock = Mock(spec=WinRMConnection)
        mock.execute_command.return_value = ("", "", 0)
        mock.execute_powershell.return_value = ("", "", 0)
        return mock
    
    @pytest.fixture
    def handler(self, mock_winrm):
        return WindowsHandler(mock_winrm)
    
    def test_restart_network_service(self, handler, mock_winrm):
        """Test network service restart"""
        mock_winrm.execute_powershell.return_value = ("", "", 0)
        
        result = handler.restart_network_service()
        
        assert result.success
        # Check PowerShell script was called
        script = mock_winrm.execute_powershell.call_args[0][0]
        assert "Get-NetAdapter" in script
        assert "Disable-NetAdapter" in script
        assert "Enable-NetAdapter" in script
    
    def test_reboot_system(self, handler, mock_winrm):
        """Test system reboot"""
        mock_winrm.execute_command.return_value = ("", "", 0)
        mock_winrm.wait_for_reboot = Mock()
        
        result = handler.reboot(wait_for_reboot=True)
        
        assert result.success
        mock_winrm.execute_command.assert_called_with("shutdown /r /t 0", timeout=30)
        mock_winrm.wait_for_reboot.assert_called_once()
    
    def test_shutdown_system(self, handler, mock_winrm):
        """Test system shutdown"""
        mock_winrm.execute_command.return_value = ("", "", 0)
        
        result = handler.shutdown()
        
        assert result.success
        mock_winrm.execute_command.assert_called_with("shutdown /s /t 0", timeout=30)
    
    def test_install_package_install_chocolatey(self, handler, mock_winrm):
        """Test installing Chocolatey when not present"""
        # winget not found, choco not found, then install choco succeeds
        mock_winrm.execute_command.side_effect = [
            ("", "not found", 1),  # winget check
            ("", "not found", 1),  # choco check
            ("", "", 0),  # install package after choco install
        ]
        mock_winrm.execute_powershell.return_value = ("", "", 0)  # install choco
        
        result = handler.install_package("test-package")
        
        # Should have tried to install chocolatey
        ps_script = mock_winrm.execute_powershell.call_args[0][0]
        assert "chocolatey.org/install.ps1" in ps_script
        assert result.success


class TestOSAbstractionBaseFinal:
    """Test remaining base OS abstraction lines"""
    
    def test_command_result_bool(self):
        """Test CommandResult boolean conversion"""
        from pod.os_abstraction.base import CommandResult
        
        # Success case
        result = CommandResult(
            stdout="output",
            stderr="",
            exit_code=0,
            success=True,
            command="test",
            duration=0.1
        )
        assert bool(result) is True
        
        # Failure case
        result = CommandResult(
            stdout="",
            stderr="error",
            exit_code=1,
            success=False,
            command="test",
            duration=0.1
        )
        assert bool(result) is False