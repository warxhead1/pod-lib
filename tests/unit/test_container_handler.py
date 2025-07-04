"""
Unit tests for Container OS handler
"""

import pytest
import json
import subprocess
from unittest.mock import Mock, patch, MagicMock, call
from pod.os_abstraction.container import ContainerHandler, ContainerConnection
from pod.os_abstraction.base import NetworkConfig, CommandResult
from pod.connections.container import DockerConnection


class TestContainerConnection:
    """Test container connection functionality"""
    
    @pytest.fixture
    def container_connection(self):
        """Create a container connection"""
        return ContainerConnection("test-container", use_docker=True)
    
    @patch('subprocess.run')
    def test_connect_running_container(self, mock_run, container_connection):
        """Test connecting to a running container"""
        # Mock inspect command showing running container
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([{
                "State": {"Running": True, "Pid": 12345}
            }])
        )
        
        container_connection.connect()
        
        assert container_connection._connected is True
        mock_run.assert_called_once()
        assert "docker inspect test-container" in mock_run.call_args[0][0]
    
    @patch('subprocess.run')
    def test_connect_stopped_container(self, mock_run, container_connection):
        """Test connecting to a stopped container (should start it)"""
        # First call: inspect shows stopped
        # Second call: start container succeeds
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=json.dumps([{"State": {"Running": False}}])),
            MagicMock(returncode=0, stdout="")
        ]
        
        container_connection.connect()
        
        assert container_connection._connected is True
        assert mock_run.call_count == 2
        assert "docker start test-container" in mock_run.call_args_list[1][0][0]
    
    @patch('subprocess.run')
    def test_execute_command(self, mock_run, container_connection):
        """Test executing command in container"""
        container_connection._connected = True
        # Mock is_connected to return True since we're checking container status
        mock_run.side_effect = [
            # First call: is_connected check
            MagicMock(returncode=0, stdout="true", text=True),
            # Second call: actual command execution
            MagicMock(returncode=0, stdout="command output", stderr="", text=True)
        ]
        
        stdout, stderr, code = container_connection.execute_command("ls -la")
        
        assert stdout == "command output"
        assert stderr == ""
        assert code == 0
        assert "docker exec test-container /bin/bash -c 'ls -la'" in mock_run.call_args[0][0]
    
    @patch('subprocess.run')
    def test_upload_file(self, mock_run, container_connection):
        """Test file upload to container"""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = container_connection.upload_file("/local/file.txt", "/container/file.txt")
        
        assert result is True
        assert "docker cp" in mock_run.call_args[0][0]
        assert "test-container:" in mock_run.call_args[0][0]
    
    def test_podman_support(self):
        """Test using podman instead of docker"""
        conn = ContainerConnection("test-container", use_docker=False)
        assert conn.command_prefix == "podman"


class TestContainerHandler:
    """Test container OS handler functionality"""
    
    @pytest.fixture
    def mock_container_connection(self):
        """Create a mock container connection"""
        mock = Mock(spec=ContainerConnection)
        mock.execute_command.return_value = ("", "", 0)
        mock.upload_file.return_value = True
        mock.download_file.return_value = True
        mock.container_id = "test-container"
        mock.command_prefix = "docker"
        return mock
    
    @pytest.fixture
    def container_handler(self, mock_container_connection):
        """Create container handler with mock connection"""
        return ContainerHandler(mock_container_connection, host_bridge="br0")
    
    def test_configure_network_with_vlan(self, container_handler, mock_container_connection):
        """Test VLAN network configuration"""
        config = NetworkConfig(
            interface="eth0",
            ip_address="192.168.100.10",
            netmask="255.255.255.0",
            gateway="192.168.100.1",
            vlan_id=100
        )
        
        # Mock successful command execution
        mock_container_connection.execute_command.return_value = ("", "", 0)
        
        result = container_handler.configure_network(config)
        
        assert result.success is True
        
        # Check that VLAN commands were executed
        calls = mock_container_connection.execute_command.call_args_list
        commands = [call[0][0] for call in calls]
        
        # Should load 8021q module
        assert any("modprobe 8021q" in cmd for cmd in commands)
        
        # Should create VLAN interface
        assert any("ip link add link eth0 name eth0.100 type vlan id 100" in cmd for cmd in commands)
        
        # Should configure IP
        assert any("192.168.100.10" in cmd for cmd in commands)
    
    def test_configure_network_without_vlan(self, container_handler, mock_container_connection):
        """Test standard network configuration without VLAN"""
        config = NetworkConfig(
            interface="eth0",
            ip_address="192.168.1.10",
            netmask="255.255.255.0",
            dhcp=False
        )
        
        result = container_handler.configure_network(config)
        
        # Should use standard Linux network configuration
        calls = mock_container_connection.execute_command.call_args_list
        commands = [call[0][0] for call in calls]
        
        # Should NOT create VLAN interface
        assert not any("type vlan" in cmd for cmd in commands)
    
    def test_create_vlan_bridge(self, container_handler, mock_container_connection):
        """Test creating VLAN bridge"""
        result = container_handler.create_vlan_bridge("br100", 100, "eth0")
        
        calls = mock_container_connection.execute_command.call_args_list
        commands = [call[0][0] for call in calls]
        
        # Should create bridge
        assert any("brctl addbr br100" in cmd for cmd in commands)
        
        # Should create VLAN interface
        assert any("eth0.100 type vlan id 100" in cmd for cmd in commands)
        
        # Should add VLAN to bridge
        assert any("brctl addif br100 eth0.100" in cmd for cmd in commands)
    
    def test_add_veth_pair(self, container_handler, mock_container_connection):
        """Test creating veth pair"""
        result = container_handler.add_veth_pair("veth0", "veth1", "br0")
        
        calls = mock_container_connection.execute_command.call_args_list
        commands = [call[0][0] for call in calls]
        
        # Should create veth pair
        assert any("ip link add veth0 type veth peer name veth1" in cmd for cmd in commands)
        
        # Should add to bridge
        assert any("brctl addif br0 veth0" in cmd for cmd in commands)
    
    @patch('subprocess.run')
    def test_get_container_info(self, mock_run, container_handler, mock_container_connection):
        """Test getting container information"""
        mock_container_connection.container_id = "test-container"
        mock_container_connection.command_prefix = "docker"
        
        container_info = {
            "Id": "abc123def456789",
            "Config": {"Image": "rocky:9"},
            "Created": "2023-01-01T10:00:00Z",
            "State": {"Status": "running"},
            "NetworkSettings": {
                "Networks": {
                    "bridge": {
                        "IPAddress": "172.17.0.2",
                        "Gateway": "172.17.0.1",
                        "MacAddress": "02:42:ac:11:00:02"
                    }
                }
            }
        }
        
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([container_info])
        )
        
        info = container_handler.get_container_info()
        
        assert info['container_id'] == "abc123def456"
        assert info['image'] == "rocky:9"
        assert info['status'] == "running"
        assert len(info['networks']) == 1
        assert info['networks'][0]['ip_address'] == "172.17.0.2"
    
    def test_get_os_info(self, container_handler, mock_container_connection):
        """Test getting OS info includes container info"""
        # Mock Linux OS info
        mock_container_connection.execute_command.return_value = (
            'NAME="Rocky Linux"\nVERSION="9.0"', "", 0
        )
        
        with patch.object(container_handler, 'get_container_info') as mock_container_info:
            mock_container_info.return_value = {
                'container_id': 'abc123',
                'image': 'rocky:9'
            }
            
            info = container_handler.get_os_info()
            
            assert info['container'] is True
            assert info['container_id'] == 'abc123'
            assert info['container_image'] == 'rocky:9'
            assert info['type'] == 'linux'
    
    def test_configure_container_networking_multiple_vlans(self, container_handler, mock_container_connection):
        """Test configuring multiple VLANs"""
        vlan_configs = [
            {
                'vlan_id': 100,
                'ip_address': '192.168.100.10',
                'netmask': '255.255.255.0',
                'interface': 'eth0'
            },
            {
                'vlan_id': 200,
                'ip_address': '192.168.200.10',
                'netmask': '255.255.255.0',
                'interface': 'eth0'
            }
        ]
        
        results = container_handler.configure_container_networking(vlan_configs)
        
        assert len(results) == 2
        assert all(r.success for r in results)
        
        # Check both VLANs were configured
        calls = mock_container_connection.execute_command.call_args_list
        commands = [call[0][0] for call in calls]
        
        assert any("eth0.100" in cmd for cmd in commands)
        assert any("eth0.200" in cmd for cmd in commands)
        assert any("192.168.100.10" in cmd for cmd in commands)
        assert any("192.168.200.10" in cmd for cmd in commands)
    
    def test_create_macvlan_interface(self, container_handler, mock_container_connection):
        """Test creating MACVLAN interface"""
        result = container_handler.create_macvlan_interface("macvlan0", "eth0", vlan_id=100)
        
        calls = mock_container_connection.execute_command.call_args_list
        commands = [call[0][0] for call in calls]
        
        # Should create VLAN interface first
        assert any("eth0.100 type vlan id 100" in cmd for cmd in commands)
        
        # Should create MACVLAN interface
        assert any("ip link add macvlan0 link eth0.100 type macvlan mode bridge" in cmd for cmd in commands)
    
    def test_dns_configuration(self, container_handler, mock_container_connection):
        """Test DNS configuration in VLAN setup"""
        config = NetworkConfig(
            interface="eth0",
            ip_address="192.168.100.10",
            netmask="255.255.255.0",
            dns_servers=["8.8.8.8", "8.8.4.4"],
            vlan_id=100
        )
        
        result = container_handler.configure_network(config)
        
        calls = mock_container_connection.execute_command.call_args_list
        commands = [call[0][0] for call in calls]
        
        # Should configure DNS
        assert any("nameserver 8.8.8.8" in cmd for cmd in commands)
        assert any("nameserver 8.8.4.4" in cmd for cmd in commands)
    
    def test_inherited_linux_functionality(self, container_handler, mock_container_connection):
        """Test that container handler inherits Linux functionality"""
        # Test package installation (container handler overrides install_package)
        mock_container_connection.execute_command.side_effect = [
            ("", "", 0),  # which apt-get
            ("Package installed", "", 0)  # apt-get update && install
        ]
        
        result = container_handler.install_package("tcpdump")
        
        assert result.success is True
        # Container handler uses apt-get update && apt-get install -y (no as_admin needed)
        calls = mock_container_connection.execute_command.call_args_list
        assert any("apt-get" in str(call) for call in calls)
    
    def test_error_handling(self, container_handler, mock_container_connection):
        """Test error handling in VLAN configuration"""
        config = NetworkConfig(
            interface="eth0",
            ip_address="192.168.100.10",
            netmask="255.255.255.0",
            vlan_id=100
        )
        
        # Make VLAN creation fail
        mock_container_connection.execute_command.side_effect = [
            ("", "", 0),  # modprobe succeeds
            ("", "", 0),  # delete existing interface
            ("", "Error: Permission denied", 1),  # create VLAN fails
        ]
        
        result = container_handler.configure_network(config)
        
        assert result.success is False
        assert result.exit_code == 1