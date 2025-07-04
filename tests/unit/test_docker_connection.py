"""
Unit tests for Docker connection
"""

import pytest
import json
import subprocess
from unittest.mock import Mock, patch, MagicMock, call
from pod.connections.container import DockerConnection


class TestDockerConnection:
    """Test Docker connection functionality"""
    
    @pytest.fixture
    def docker_connection(self):
        """Create a Docker connection instance"""
        return DockerConnection("test-container", runtime="docker")
    
    @patch('subprocess.run')
    def test_connect_running_container(self, mock_run, docker_connection):
        """Test connecting to a running container"""
        # Mock container info - already running
        container_info = {
            "State": {"Running": True, "Pid": 12345},
            "Id": "abc123def456",
            "Config": {"Image": "ubuntu:latest"}
        }
        
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([container_info])
        )
        
        docker_connection.connect()
        
        assert docker_connection._connected is True
        assert docker_connection._container_info == container_info
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == ["docker", "inspect", "test-container"]
    
    @patch('subprocess.run')
    def test_connect_stopped_container(self, mock_run, docker_connection):
        """Test connecting to a stopped container (should start it)"""
        # First call: inspect shows stopped container
        container_info = {
            "State": {"Running": False, "Pid": 0},
            "Id": "abc123def456"
        }
        
        mock_run.side_effect = [
            # inspect call
            MagicMock(returncode=0, stdout=json.dumps([container_info])),
            # start call
            MagicMock(returncode=0, stdout="")
        ]
        
        docker_connection.connect()
        
        assert docker_connection._connected is True
        assert mock_run.call_count == 2
        
        # Check both calls
        calls = mock_run.call_args_list
        assert calls[0][0][0] == ["docker", "inspect", "test-container"]
        assert calls[1][0][0] == ["docker", "start", "test-container"]
    
    @patch('subprocess.run')
    def test_connect_container_not_found(self, mock_run, docker_connection):
        """Test connecting to non-existent container"""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout=""
        )
        
        with pytest.raises(ConnectionError, match="Container test-container not found"):
            docker_connection.connect()
        
        assert not docker_connection._connected
    
    @patch('subprocess.run')
    def test_connect_start_failure(self, mock_run, docker_connection):
        """Test when container fails to start"""
        container_info = {"State": {"Running": False}}
        
        mock_run.side_effect = [
            # inspect succeeds
            MagicMock(returncode=0, stdout=json.dumps([container_info])),
            # start fails
            MagicMock(returncode=1, stderr="Error starting container".encode())
        ]
        
        with pytest.raises(ConnectionError, match="Failed to start container"):
            docker_connection.connect()
    
    @patch('subprocess.run')
    def test_disconnect(self, mock_run, docker_connection):
        """Test disconnecting from container"""
        docker_connection._connected = True
        docker_connection._container_info = {"test": "data"}
        
        docker_connection.disconnect()
        
        assert not docker_connection._connected
        assert docker_connection._container_info is None
    
    @patch('subprocess.run')
    def test_is_connected_true(self, mock_run, docker_connection):
        """Test is_connected when connected"""
        docker_connection._connected = True
        
        # Mock container is still running
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([{"State": {"Running": True}}])
        )
        
        assert docker_connection.is_connected() is True
    
    @patch('subprocess.run')
    def test_is_connected_false(self, mock_run, docker_connection):
        """Test is_connected when not connected"""
        docker_connection._connected = False
        
        assert docker_connection.is_connected() is False
        mock_run.assert_not_called()
    
    @patch('subprocess.run')
    def test_is_connected_container_stopped(self, mock_run, docker_connection):
        """Test is_connected when container stopped"""
        docker_connection._connected = True
        
        # Container no longer running
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([{"State": {"Running": False}}])
        )
        
        assert docker_connection.is_connected() is False
    
    @patch('subprocess.run')
    def test_execute_command_success(self, mock_run, docker_connection):
        """Test successful command execution"""
        docker_connection._connected = True
        docker_connection._container_info = {"State": {"Running": True}}
        
        # Mock _get_container_info to avoid subprocess call
        with patch.object(docker_connection, '_get_container_info', return_value={"State": {"Running": True}}):
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="command output",
                stderr=""
            )
            
            stdout, stderr, code = docker_connection.execute_command("echo test")
        
        assert stdout == "command output"
        assert stderr == ""
        assert code == 0
        
        # Check command format
        cmd = mock_run.call_args[0][0]
        assert cmd == ["docker", "exec", "test-container", "/bin/bash", "-c", "echo test"]
    
    @patch('subprocess.run')
    def test_execute_command_failure(self, mock_run, docker_connection):
        """Test failed command execution"""
        docker_connection._connected = True
        docker_connection._container_info = {"State": {"Running": True}}
        
        with patch.object(docker_connection, '_get_container_info', return_value={"State": {"Running": True}}):
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="command not found"
            )
            
            stdout, stderr, code = docker_connection.execute_command("bad_command")
        
        assert stdout == ""
        assert stderr == "command not found"
        assert code == 1
    
    @patch('subprocess.run')
    def test_execute_command_timeout(self, mock_run, docker_connection):
        """Test command execution timeout"""
        docker_connection._connected = True
        docker_connection._container_info = {"State": {"Running": True}}
        
        with patch.object(docker_connection, '_get_container_info', return_value={"State": {"Running": True}}):
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=5)
            
            stdout, stderr, code = docker_connection.execute_command("sleep 10", timeout=5)
        
        assert stdout == ""
        assert "timed out after 5 seconds" in stderr
        assert code == 124
    
    @patch('subprocess.run')
    def test_execute_command_not_connected(self, mock_run, docker_connection):
        """Test command execution when not connected"""
        docker_connection._connected = False
        
        with pytest.raises(ConnectionError, match="Not connected to container"):
            docker_connection.execute_command("echo test")
    
    @patch('subprocess.run')
    def test_upload_file_success(self, mock_run, docker_connection):
        """Test successful file upload"""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = docker_connection.upload_file("/local/file.txt", "/container/file.txt")
        
        assert result is True
        cmd = mock_run.call_args[0][0]
        assert cmd == ["docker", "cp", "/local/file.txt", "test-container:/container/file.txt"]
    
    @patch('subprocess.run')
    def test_upload_file_failure(self, mock_run, docker_connection):
        """Test failed file upload"""
        mock_run.return_value = MagicMock(returncode=1)
        
        result = docker_connection.upload_file("/local/file.txt", "/container/file.txt")
        
        assert result is False
    
    @patch('subprocess.run')
    def test_download_file_success(self, mock_run, docker_connection):
        """Test successful file download"""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = docker_connection.download_file("/container/file.txt", "/local/file.txt")
        
        assert result is True
        cmd = mock_run.call_args[0][0]
        assert cmd == ["docker", "cp", "test-container:/container/file.txt", "/local/file.txt"]
    
    @patch('subprocess.run')
    def test_execute_sudo_command(self, mock_run, docker_connection):
        """Test sudo command execution (same as regular in containers)"""
        docker_connection._connected = True
        docker_connection._container_info = {"State": {"Running": True}}
        
        with patch.object(docker_connection, '_get_container_info', return_value={"State": {"Running": True}}):
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="root",
                stderr=""
            )
            
            stdout, stderr, code = docker_connection.execute_sudo_command("whoami")
        
        assert stdout == "root"
        assert code == 0
    
    @patch('subprocess.run')
    def test_create_network_namespace(self, mock_run, docker_connection):
        """Test creating network namespace"""
        docker_connection._connected = True
        docker_connection._container_info = {"State": {"Running": True}}
        
        with patch.object(docker_connection, '_get_container_info', return_value={"State": {"Running": True}}):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            
            result = docker_connection.create_network_namespace("test-ns")
        
        assert result is True
        # Check the command executed
        cmd = mock_run.call_args[0][0]
        assert cmd[-1] == "ip netns add test-ns"
    
    @patch('subprocess.run')
    def test_attach_to_network(self, mock_run, docker_connection):
        """Test attaching container to network"""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = docker_connection.attach_to_network(
            "test-network",
            ip_address="192.168.1.100",
            aliases=["web", "app"]
        )
        
        assert result is True
        cmd = mock_run.call_args[0][0]
        assert cmd[0:3] == ["docker", "network", "connect"]
        assert "--ip" in cmd
        assert "192.168.1.100" in cmd
        assert "--alias" in cmd
        assert "web" in cmd
        assert "app" in cmd
    
    @patch('subprocess.run')
    def test_detach_from_network(self, mock_run, docker_connection):
        """Test detaching container from network"""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = docker_connection.detach_from_network("test-network")
        
        assert result is True
        cmd = mock_run.call_args[0][0]
        assert cmd == ["docker", "network", "disconnect", "test-network", "test-container"]
    
    @patch('subprocess.run')
    def test_create_vlan_network(self, mock_run, docker_connection):
        """Test creating VLAN network"""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = docker_connection.create_vlan_network(
            "vlan100",
            "eth0",
            100,
            "192.168.100.0/24",
            "192.168.100.1"
        )
        
        assert result is True
        cmd = mock_run.call_args[0][0]
        assert "docker" in cmd[0]
        assert "network" in cmd
        assert "create" in cmd
        assert "-d" in cmd
        assert "macvlan" in cmd
        assert "--subnet" in cmd
        assert "192.168.100.0/24" in cmd
        assert "-o" in cmd
        assert "parent=eth0.100" in cmd
        assert "--gateway" in cmd
        assert "192.168.100.1" in cmd
    
    @patch('subprocess.run')
    def test_get_container_pid(self, mock_run, docker_connection):
        """Test getting container PID"""
        docker_connection._container_info = {"State": {"Pid": 12345}}
        
        with patch.object(docker_connection, '_get_container_info', return_value={"State": {"Pid": 12345}}):
            pid = docker_connection._get_container_pid()
        
        assert pid == 12345
    
    @patch('subprocess.run')
    def test_get_container_networks(self, mock_run, docker_connection):
        """Test getting container networks"""
        networks = {
            "bridge": {
                "IPAddress": "172.17.0.2",
                "Gateway": "172.17.0.1"
            },
            "custom": {
                "IPAddress": "192.168.1.10",
                "Gateway": "192.168.1.1"
            }
        }
        
        docker_connection._container_info = {
            "NetworkSettings": {"Networks": networks}
        }
        
        with patch.object(docker_connection, '_get_container_info', return_value={"NetworkSettings": {"Networks": networks}}):
            result = docker_connection.get_container_networks()
        
        assert result == networks
    
    @patch('subprocess.run')
    def test_execute_in_network_namespace(self, mock_run, docker_connection):
        """Test executing command in network namespace"""
        docker_connection._connected = True
        docker_connection._container_info = {"State": {"Running": True}}
        
        with patch.object(docker_connection, '_get_container_info', return_value={"State": {"Running": True}}):
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="eth0: <BROADCAST,MULTICAST,UP>",
                stderr=""
            )
            
            stdout, stderr, code = docker_connection.execute_in_network_namespace(
                "test-ns", "ip link show"
            )
        
        assert code == 0
        assert "eth0" in stdout
        assert "ip netns exec test-ns ip link show" in mock_run.call_args[0][0][5]
    
    def test_podman_support(self):
        """Test using podman runtime"""
        conn = DockerConnection("test-container", runtime="podman")
        
        assert conn.runtime == "podman"
        assert conn.container_id == "test-container"
        assert not conn._connected
    
    @patch('subprocess.run')
    def test_exception_handling(self, mock_run, docker_connection):
        """Test general exception handling"""
        mock_run.side_effect = Exception("Unexpected error")
        
        # Upload file
        result = docker_connection.upload_file("/src", "/dst")
        assert result is False
        
        # Execute command with exception
        docker_connection._connected = True
        docker_connection._container_info = {"State": {"Running": True}}
        with patch.object(docker_connection, '_get_container_info', return_value={"State": {"Running": True}}):
            stdout, stderr, code = docker_connection.execute_command("test")
        assert stdout == ""
        assert "Unexpected error" in stderr
        assert code == 1