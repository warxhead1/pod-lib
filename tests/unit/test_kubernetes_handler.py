"""
Unit tests for Kubernetes OS handler
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from pod.os_abstraction.kubernetes import KubernetesHandler
from pod.connections.kubernetes import KubernetesConnection
from pod.os_abstraction.base import NetworkConfig, CommandResult


class TestKubernetesHandler:
    """Test Kubernetes OS handler functionality"""
    
    @pytest.fixture
    def mock_k8s_connection(self):
        """Create a mock Kubernetes connection"""
        mock_conn = Mock(spec=KubernetesConnection)
        mock_conn.namespace = "test-namespace"
        mock_conn.v1 = Mock()
        mock_conn.networking_v1 = Mock()
        mock_conn.custom_objects_v1 = Mock()
        return mock_conn
    
    @pytest.fixture
    def k8s_handler(self, mock_k8s_connection):
        """Create Kubernetes handler with mock connection"""
        return KubernetesHandler(mock_k8s_connection)
    
    def test_init(self, mock_k8s_connection):
        """Test handler initialization"""
        handler = KubernetesHandler(mock_k8s_connection)
        assert handler.k8s == mock_k8s_connection
        assert isinstance(handler.cni_plugins, list)
        assert isinstance(handler.network_capabilities, dict)
    
    @patch('pod.os_abstraction.kubernetes.KubernetesHandler._detect_cni_plugins')
    def test_detect_cni_plugins_calico(self, mock_detect, mock_k8s_connection):
        """Test Calico CNI detection"""
        mock_nodes = Mock()
        mock_nodes.items = [Mock()]
        mock_k8s_connection.v1.list_node.return_value = mock_nodes
        
        mock_detect.return_value = ["calico"]
        handler = KubernetesHandler(mock_k8s_connection)
        
        assert "calico" in handler.cni_plugins
    
    @patch('pod.os_abstraction.kubernetes.KubernetesHandler._detect_cni_plugins')
    def test_detect_cni_plugins_cilium(self, mock_detect, mock_k8s_connection):
        """Test Cilium CNI detection"""
        mock_pods = Mock()
        mock_pods.items = [Mock()]
        mock_k8s_connection.v1.list_pod_for_all_namespaces.return_value = mock_pods
        
        mock_detect.return_value = ["cilium"]
        handler = KubernetesHandler(mock_k8s_connection)
        
        assert "cilium" in handler.cni_plugins
    
    def test_get_os_info(self, k8s_handler, mock_k8s_connection):
        """Test getting Kubernetes cluster information"""
        # Mock cluster info
        mock_k8s_connection.get_cluster_info.return_value = {
            "version": "1.28",
            "git_version": "v1.28.0"
        }
        
        # Mock node list
        mock_node = Mock()
        mock_node.metadata.name = "node-1"
        mock_node.status.node_info.operating_system = "linux"
        mock_node.status.node_info.architecture = "amd64"
        mock_node.status.node_info.kernel_version = "5.15.0"
        mock_node.status.node_info.container_runtime_version = "containerd://1.6.0"
        mock_node.status.node_info.kubelet_version = "v1.28.0"
        mock_node.status.capacity = {"cpu": "4", "memory": "8Gi"}
        mock_node.status.conditions = []
        
        mock_k8s_connection.v1.list_node.return_value = Mock(items=[mock_node])
        
        info = k8s_handler.get_os_info()
        
        assert info["type"] == "kubernetes"
        assert info["cluster_version"] == "1.28"
        assert len(info["nodes"]) == 1
        assert info["nodes"][0]["name"] == "node-1"
        assert info["nodes"][0]["os"] == "linux"
    
    def test_configure_network_with_vlan(self, k8s_handler):
        """Test network configuration with VLAN"""
        config = NetworkConfig(
            interface="eth0",
            ip_address="192.168.100.10",
            netmask="255.255.255.0",
            vlan_id=100
        )
        
        with patch.object(k8s_handler, '_configure_vlan_network') as mock_vlan:
            mock_vlan.return_value = CommandResult(
                stdout="VLAN configured",
                stderr="",
                exit_code=0,
                success=True,
                command="configure_vlan",
                duration=1.0
            )
            
            result = k8s_handler.configure_network(config)
            
            assert result.success is True
            assert "VLAN configured" in result.stdout
            mock_vlan.assert_called_once_with(config)
    
    def test_configure_network_without_vlan(self, k8s_handler):
        """Test network configuration without VLAN"""
        config = NetworkConfig(
            interface="eth0",
            ip_address="192.168.1.10",
            netmask="255.255.255.0"
        )
        
        with patch.object(k8s_handler, '_configure_standard_network') as mock_standard:
            mock_standard.return_value = CommandResult(
                stdout="Standard network configured",
                stderr="",
                exit_code=0,
                success=True,
                command="configure_standard",
                duration=0.5
            )
            
            result = k8s_handler.configure_network(config)
            
            assert result.success is True
            mock_standard.assert_called_once_with(config)
    
    def test_configure_multus_vlan(self, k8s_handler, mock_k8s_connection):
        """Test VLAN configuration with Multus CNI"""
        k8s_handler.cni_plugins = ["multus"]
        
        config = NetworkConfig(
            interface="eth0",
            ip_address="192.168.100.10",
            netmask="255.255.255.0",
            vlan_id=100
        )
        
        # Mock successful NetworkAttachmentDefinition creation
        mock_k8s_connection.custom_objects_v1.create_namespaced_custom_object.return_value = Mock()
        
        result = k8s_handler._configure_multus_vlan(config)
        
        assert result.success is True
        assert "VLAN 100 NetworkAttachmentDefinition created" in result.stdout
        mock_k8s_connection.custom_objects_v1.create_namespaced_custom_object.assert_called_once()
    
    def test_configure_calico_vlan(self, k8s_handler, mock_k8s_connection):
        """Test VLAN configuration with Calico CNI"""
        k8s_handler.cni_plugins = ["calico"]
        
        config = NetworkConfig(
            interface="eth0",
            ip_address="192.168.100.10",
            netmask="255.255.255.0",
            vlan_id=100
        )
        
        # Mock successful IP Pool creation
        mock_k8s_connection.custom_objects_v1.create_cluster_custom_object.return_value = Mock()
        
        result = k8s_handler._configure_calico_vlan(config)
        
        assert result.success is True
        assert "Calico IP Pool for VLAN 100 created" in result.stdout
        mock_k8s_connection.custom_objects_v1.create_cluster_custom_object.assert_called_once()
    
    def test_configure_cilium_vlan(self, k8s_handler, mock_k8s_connection):
        """Test VLAN configuration with Cilium CNI"""
        k8s_handler.cni_plugins = ["cilium"]
        
        config = NetworkConfig(
            interface="eth0",
            ip_address="192.168.100.10",
            netmask="255.255.255.0",
            vlan_id=100
        )
        
        # Mock successful CiliumNetworkPolicy creation
        mock_k8s_connection.custom_objects_v1.create_namespaced_custom_object.return_value = Mock()
        
        result = k8s_handler._configure_cilium_vlan(config)
        
        assert result.success is True
        assert "Cilium Network Policy for VLAN 100 created" in result.stdout
        mock_k8s_connection.custom_objects_v1.create_namespaced_custom_object.assert_called_once()
    
    def test_configure_generic_vlan(self, k8s_handler, mock_k8s_connection):
        """Test VLAN configuration with generic NetworkPolicy"""
        config = NetworkConfig(
            interface="eth0",
            ip_address="192.168.100.10", 
            netmask="255.255.255.0",
            vlan_id=100
        )
        
        # Mock successful NetworkPolicy creation
        mock_k8s_connection.networking_v1.create_namespaced_network_policy.return_value = Mock()
        
        result = k8s_handler._configure_generic_vlan(config)
        
        assert result.success is True
        assert "NetworkPolicy for VLAN 100 created" in result.stdout
        mock_k8s_connection.networking_v1.create_namespaced_network_policy.assert_called_once()
    
    def test_netmask_to_cidr(self, k8s_handler):
        """Test netmask to CIDR conversion"""
        assert k8s_handler._netmask_to_cidr("255.255.255.0") == 24
        assert k8s_handler._netmask_to_cidr("255.255.0.0") == 16
        assert k8s_handler._netmask_to_cidr("255.0.0.0") == 8
        assert k8s_handler._netmask_to_cidr(None) == 24  # Default
    
    def test_get_network_interfaces(self, k8s_handler, mock_k8s_connection):
        """Test getting network interfaces for pods"""
        # Mock pod list
        mock_k8s_connection.list_pods.return_value = [
            {
                "name": "test-pod-1",
                "namespace": "default",
                "status": "Running",
                "node": "node-1",
                "ip": "10.244.1.5"
            },
            {
                "name": "test-pod-2",
                "namespace": "default", 
                "status": "Pending",
                "node": "node-1",
                "ip": None
            }
        ]
        
        interfaces = k8s_handler.get_network_interfaces()
        
        assert len(interfaces) == 1  # Only running pod with IP
        assert interfaces[0].name == "pod-test-pod-1"
        assert interfaces[0].ip_addresses == ["10.244.1.5"]
        assert interfaces[0].type == "pod"
    
    def test_create_pod_with_vlan(self, k8s_handler, mock_k8s_connection):
        """Test creating pod with VLAN configuration"""
        network_config = NetworkConfig(
            interface="eth0",
            ip_address="192.168.100.10",
            netmask="255.255.255.0",
            vlan_id=100
        )
        
        # Mock successful pod creation
        mock_pod = Mock()
        mock_pod.metadata.name = "test-pod"
        mock_k8s_connection.v1.create_namespaced_pod.return_value = mock_pod
        
        # Mock VLAN configuration
        with patch.object(k8s_handler, '_configure_vlan_network') as mock_vlan:
            mock_vlan.return_value = CommandResult(
                stdout="VLAN configured",
                stderr="",
                exit_code=0,
                success=True,
                command="configure_vlan",
                duration=1.0
            )
            
            # Mock pod ready wait
            with patch.object(k8s_handler, '_wait_for_pod_ready', return_value=True):
                result = k8s_handler.create_pod_with_vlan(
                    "test-pod",
                    "nginx:alpine",
                    100,
                    network_config
                )
        
        assert result.success is True
        assert "test-pod created successfully with VLAN 100" in result.stdout
        mock_k8s_connection.v1.create_namespaced_pod.assert_called_once()
    
    @patch('time.sleep')
    @patch('time.time')
    def test_wait_for_pod_ready_success(self, mock_time, mock_sleep, k8s_handler, mock_k8s_connection):
        """Test waiting for pod to be ready successfully"""
        # Mock time progression
        mock_time.side_effect = [0, 5]  # Start time, end time
        
        # Mock pod ready
        mock_pod = Mock()
        mock_pod.status.phase = "Running"
        mock_pod.status.container_statuses = [Mock(ready=True)]
        mock_k8s_connection.v1.read_namespaced_pod.return_value = mock_pod
        
        result = k8s_handler._wait_for_pod_ready("test-pod", timeout=10)
        
        assert result is True
    
    @patch('time.sleep')
    @patch('time.time')
    def test_wait_for_pod_ready_timeout(self, mock_time, mock_sleep, k8s_handler, mock_k8s_connection):
        """Test waiting for pod ready timeout"""
        # Mock time progression
        mock_time.side_effect = [0, 301]  # Start time, timeout
        
        # Mock pod not ready
        mock_pod = Mock()
        mock_pod.status.phase = "Pending"
        mock_k8s_connection.v1.read_namespaced_pod.return_value = mock_pod
        
        result = k8s_handler._wait_for_pod_ready("test-pod", timeout=300)
        
        assert result is False
    
    def test_delete_pod(self, k8s_handler, mock_k8s_connection):
        """Test pod deletion"""
        mock_k8s_connection.v1.delete_namespaced_pod.return_value = Mock()
        
        result = k8s_handler.delete_pod("test-pod")
        
        assert result.success is True
        assert "test-pod deleted successfully" in result.stdout
        mock_k8s_connection.v1.delete_namespaced_pod.assert_called_once()
    
    def test_test_network_connectivity_success(self, k8s_handler, mock_k8s_connection):
        """Test successful network connectivity test"""
        mock_k8s_connection.execute_command.return_value = (
            "PING 192.168.1.10 (192.168.1.10) 56(84) bytes of data.\n"
            "64 bytes from 192.168.1.10: icmp_seq=1 time=1.23 ms\n"
            "--- 192.168.1.10 ping statistics ---\n",
            "",
            0
        )
        
        result = k8s_handler.test_network_connectivity("source-pod", "192.168.1.10")
        
        assert result.success is True
        assert "192.168.1.10" in result.stdout
    
    def test_test_network_connectivity_with_port(self, k8s_handler, mock_k8s_connection):
        """Test network connectivity test with port"""
        mock_k8s_connection.execute_command.return_value = (
            "Connection to 192.168.1.10 80 port [tcp/http] succeeded!",
            "",
            0
        )
        
        result = k8s_handler.test_network_connectivity("source-pod", "192.168.1.10", 80)
        
        assert result.success is True
        # Should use nc command for port testing
        call_args = mock_k8s_connection.execute_command.call_args[0]
        assert "nc -zv" in call_args[0]
    
    def test_test_network_connectivity_failure(self, k8s_handler, mock_k8s_connection):
        """Test failed network connectivity test"""
        mock_k8s_connection.execute_command.return_value = (
            "",
            "ping: connect: Network is unreachable",
            1
        )
        
        result = k8s_handler.test_network_connectivity("source-pod", "192.168.1.10")
        
        assert result.success is False
        assert result.exit_code == 1
    
    def test_install_package_not_applicable(self, k8s_handler):
        """Test package installation (not applicable for Kubernetes)"""
        result = k8s_handler.install_package("nginx")
        
        assert result.success is True
        assert "Package installation should be handled in container image" in result.stdout
    
    def test_uninstall_package_not_applicable(self, k8s_handler):
        """Test package uninstallation (not applicable for Kubernetes)"""
        result = k8s_handler.uninstall_package("nginx")
        
        assert result.success is True
        assert "Package uninstallation should be handled in container image" in result.stdout
    
    def test_reboot_pod_restart(self, k8s_handler):
        """Test pod restart (reboot equivalent)"""
        with patch.object(k8s_handler, 'delete_pod') as mock_delete:
            mock_delete.return_value = CommandResult(
                stdout="Pod deleted",
                stderr="",
                exit_code=0,
                success=True,
                command="delete_pod",
                duration=1.0
            )
            
            result = k8s_handler.reboot(wait_for_reboot=True, pod_name="test-pod")
            
            assert result.success is True
            mock_delete.assert_called_once_with("test-pod")
    
    def test_reboot_no_pod_name(self, k8s_handler):
        """Test reboot without pod name"""
        result = k8s_handler.reboot()
        
        assert result.success is False
        assert "pod_name required for pod restart" in result.stderr
    
    def test_shutdown_pod_deletion(self, k8s_handler):
        """Test pod shutdown (deletion)"""
        with patch.object(k8s_handler, 'delete_pod') as mock_delete:
            mock_delete.return_value = CommandResult(
                stdout="Pod deleted",
                stderr="",
                exit_code=0,
                success=True,
                command="delete_pod",
                duration=1.0
            )
            
            result = k8s_handler.shutdown(pod_name="test-pod")
            
            assert result.success is True
            mock_delete.assert_called_once_with("test-pod")
    
    def test_shutdown_no_pod_name(self, k8s_handler):
        """Test shutdown without pod name"""
        result = k8s_handler.shutdown()
        
        assert result.success is False
        assert "pod_name required for pod shutdown" in result.stderr