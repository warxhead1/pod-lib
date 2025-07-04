"""
Unit tests for Kubernetes connection handler
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from pod.connections.kubernetes import KubernetesConnection
from pod.exceptions import ConnectionError, AuthenticationError


class TestKubernetesConnection:
    """Test Kubernetes connection functionality"""
    
    @pytest.fixture
    def k8s_connection(self):
        """Create a Kubernetes connection"""
        return KubernetesConnection(
            kubeconfig_path="/mock/kubeconfig",
            context="test-context",
            namespace="test-namespace"
        )
    
    def test_init_with_kubeconfig(self):
        """Test initialization with kubeconfig"""
        conn = KubernetesConnection(
            kubeconfig_path="/test/kubeconfig",
            context="test-context",
            namespace="production"
        )
        
        assert conn.kubeconfig_path == "/test/kubeconfig"
        assert conn.context == "test-context"
        assert conn.namespace == "production"
        assert conn.default_port == 6443
    
    def test_init_with_direct_api(self):
        """Test initialization with direct API server"""
        conn = KubernetesConnection(
            api_server="https://k8s-api.example.com:6443",
            token="test-token",
            ca_cert_path="/test/ca.crt"
        )
        
        assert conn.api_server == "https://k8s-api.example.com:6443"
        assert conn.token == "test-token"
        assert conn.ca_cert_path == "/test/ca.crt"
    
    @patch('pod.connections.kubernetes.config.load_kube_config')
    @patch('pod.connections.kubernetes.client.CoreV1Api')
    def test_connect_kubeconfig_success(self, mock_core_api, mock_load_config, k8s_connection):
        """Test successful connection with kubeconfig"""
        # Mock kubeconfig file exists
        with patch('pathlib.Path.exists', return_value=True):
            # Mock version API
            mock_version = Mock()
            mock_version.major = "1"
            mock_version.minor = "28"
            mock_version.git_version = "v1.28.0"
            
            mock_api_instance = Mock()
            mock_api_instance.get_code.return_value = mock_version
            mock_api_instance.list_node.return_value = Mock(items=[])
            mock_core_api.return_value = mock_api_instance
            
            k8s_connection.connect()
            
            assert k8s_connection._connected is True
            mock_load_config.assert_called_once()
    
    @patch('pod.connections.kubernetes.config.load_kube_config')
    def test_connect_kubeconfig_not_found(self, mock_load_config, k8s_connection):
        """Test connection failure when kubeconfig not found"""
        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(ConnectionError):
                k8s_connection.connect()
    
    @patch('pod.connections.kubernetes.client.Configuration.set_default')
    @patch('pod.connections.kubernetes.client.CoreV1Api')
    def test_connect_direct_api_success(self, mock_core_api, mock_set_default):
        """Test successful connection with direct API"""
        conn = KubernetesConnection(
            api_server="https://k8s-api.example.com:6443",
            token="test-token"
        )
        
        # Mock version API
        mock_version = Mock()
        mock_version.major = "1"
        mock_version.minor = "28"
        mock_version.git_version = "v1.28.0"
        
        mock_api_instance = Mock()
        mock_api_instance.get_code.return_value = mock_version
        mock_api_instance.list_node.return_value = Mock(items=[])
        mock_core_api.return_value = mock_api_instance
        
        conn.connect()
        
        assert conn._connected is True
        mock_set_default.assert_called_once()
    
    @patch('pod.connections.kubernetes.client.CoreV1Api')
    def test_connect_authentication_error(self, mock_core_api, k8s_connection):
        """Test authentication error during connection"""
        from kubernetes.client.rest import ApiException
        
        mock_api_instance = Mock()
        mock_api_instance.get_code.side_effect = ApiException(status=401)
        mock_core_api.return_value = mock_api_instance
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pod.connections.kubernetes.config.load_kube_config'):
                with pytest.raises(AuthenticationError):
                    k8s_connection.connect()
    
    def test_disconnect(self, k8s_connection):
        """Test disconnection"""
        k8s_connection.v1 = Mock()
        k8s_connection._connected = True
        
        k8s_connection.disconnect()
        
        assert k8s_connection.v1 is None
        assert k8s_connection._connected is False
    
    @patch('pod.connections.kubernetes.client.CoreV1Api')
    def test_is_connected_true(self, mock_core_api, k8s_connection):
        """Test is_connected returns True when connected"""
        mock_api_instance = Mock()
        mock_api_instance.list_namespace.return_value = Mock()
        k8s_connection.v1 = mock_api_instance
        k8s_connection._connected = True
        
        assert k8s_connection.is_connected() is True
    
    def test_is_connected_false(self, k8s_connection):
        """Test is_connected returns False when not connected"""
        k8s_connection._connected = False
        k8s_connection.v1 = None
        
        assert k8s_connection.is_connected() is False
    
    @patch('pod.connections.kubernetes.stream')
    def test_execute_command_success(self, mock_stream, k8s_connection):
        """Test successful command execution"""
        k8s_connection.v1 = Mock()
        
        # Mock stream response
        mock_resp = Mock()
        mock_resp.is_open.side_effect = [True, True, False]
        mock_resp.peek_stdout.side_effect = [True, False, False]
        mock_resp.peek_stderr.side_effect = [False, False, False]
        mock_resp.read_stdout.return_value = "command output"
        mock_stream.return_value = mock_resp
        
        stdout, stderr, exit_code = k8s_connection.execute_command(
            "ls -la",
            pod_name="test-pod"
        )
        
        assert stdout == "command output"
        assert stderr == ""
        assert exit_code == 0
    
    def test_execute_command_no_pod_name(self, k8s_connection):
        """Test command execution without pod name"""
        with pytest.raises(ValueError, match="pod_name is required"):
            k8s_connection.execute_command("ls -la")
    
    @patch('builtins.open', create=True)
    @patch('base64.b64encode')
    def test_upload_file_success(self, mock_b64encode, mock_open, k8s_connection):
        """Test successful file upload"""
        k8s_connection.execute_command = Mock(return_value=("", "", 0))
        
        mock_file_content = b"test file content"
        mock_open.return_value.__enter__.return_value.read.return_value = mock_file_content
        mock_b64encode.return_value.decode.return_value = "dGVzdCBmaWxlIGNvbnRlbnQ="
        
        result = k8s_connection.upload_file(
            "/local/file.txt",
            "/remote/file.txt",
            pod_name="test-pod"
        )
        
        assert result is True
        k8s_connection.execute_command.assert_called_once()
    
    def test_upload_file_failure(self, k8s_connection):
        """Test file upload failure"""
        k8s_connection.execute_command = Mock(return_value=("", "error", 1))
        
        with patch('builtins.open', create=True):
            with patch('base64.b64encode'):
                result = k8s_connection.upload_file(
                    "/local/file.txt",
                    "/remote/file.txt",
                    pod_name="test-pod"
                )
        
        assert result is False
    
    @patch('builtins.open', create=True)
    @patch('base64.b64decode')
    def test_download_file_success(self, mock_b64decode, mock_open, k8s_connection):
        """Test successful file download"""
        k8s_connection.execute_command = Mock(return_value=("dGVzdCBmaWxlIGNvbnRlbnQ=", "", 0))
        mock_b64decode.return_value = b"test file content"
        
        result = k8s_connection.download_file(
            "/remote/file.txt",
            "/local/file.txt",
            pod_name="test-pod"
        )
        
        assert result is True
        mock_open.assert_called_once()
    
    def test_download_file_failure(self, k8s_connection):
        """Test file download failure"""
        k8s_connection.execute_command = Mock(return_value=("", "error", 1))
        
        result = k8s_connection.download_file(
            "/remote/file.txt",
            "/local/file.txt",
            pod_name="test-pod"
        )
        
        assert result is False
    
    def test_get_cluster_info(self, k8s_connection):
        """Test getting cluster information"""
        k8s_connection._cluster_info = {
            "version": "1.28",
            "git_version": "v1.28.0",
            "node_count": 3
        }
        
        info = k8s_connection.get_cluster_info()
        
        assert info["version"] == "1.28"
        assert info["git_version"] == "v1.28.0"
        assert info["node_count"] == 3
    
    def test_list_namespaces_success(self, k8s_connection):
        """Test listing namespaces successfully"""
        mock_ns1 = Mock()
        mock_ns1.metadata.name = "default"
        mock_ns2 = Mock()
        mock_ns2.metadata.name = "kube-system"
        
        k8s_connection.v1 = Mock()
        k8s_connection.v1.list_namespace.return_value = Mock(items=[mock_ns1, mock_ns2])
        
        namespaces = k8s_connection.list_namespaces()
        
        assert namespaces == ["default", "kube-system"]
    
    def test_list_namespaces_failure(self, k8s_connection):
        """Test listing namespaces failure"""
        from kubernetes.client.rest import ApiException
        
        k8s_connection.v1 = Mock()
        k8s_connection.v1.list_namespace.side_effect = ApiException()
        
        namespaces = k8s_connection.list_namespaces()
        
        assert namespaces == []
    
    def test_list_pods_success(self, k8s_connection):
        """Test listing pods successfully"""
        mock_pod = Mock()
        mock_pod.metadata.name = "test-pod"
        mock_pod.metadata.namespace = "default"
        mock_pod.status.phase = "Running"
        mock_pod.spec.node_name = "node-1"
        mock_pod.status.pod_ip = "10.244.1.5"
        mock_pod.metadata.labels = {"app": "test"}
        mock_pod.metadata.annotations = {}
        mock_pod.spec.containers = [Mock(name="main", image="nginx:latest")]
        mock_pod.status.container_statuses = [Mock(name="main", ready=True)]
        
        k8s_connection.v1 = Mock()
        k8s_connection.v1.list_namespaced_pod.return_value = Mock(items=[mock_pod])
        
        pods = k8s_connection.list_pods()
        
        assert len(pods) == 1
        assert pods[0]["name"] == "test-pod"
        assert pods[0]["status"] == "Running"
        assert pods[0]["ip"] == "10.244.1.5"
    
    @patch('time.sleep')
    def test_wait_for_reboot_success(self, mock_sleep, k8s_connection):
        """Test successful wait for pod restart"""
        # Mock pod states: first not ready, then ready
        mock_pod_not_ready = Mock()
        mock_pod_not_ready.status.phase = "Pending"
        
        mock_pod_ready = Mock()
        mock_pod_ready.status.phase = "Running"
        mock_pod_ready.status.container_statuses = [Mock(ready=True)]
        
        k8s_connection.v1 = Mock()
        k8s_connection.v1.read_namespaced_pod.side_effect = [mock_pod_not_ready, mock_pod_ready]
        
        result = k8s_connection.wait_for_reboot(
            check_interval=1,
            max_wait_time=10,
            pod_name="test-pod"
        )
        
        assert result is True
    
    @patch('time.sleep')
    @patch('time.time')
    def test_wait_for_reboot_timeout(self, mock_time, mock_sleep, k8s_connection):
        """Test wait for pod restart timeout"""
        # Mock time progression
        mock_time.side_effect = [0, 5, 301]  # Start, check, timeout
        
        mock_pod = Mock()
        mock_pod.status.phase = "Pending"
        
        k8s_connection.v1 = Mock()
        k8s_connection.v1.read_namespaced_pod.return_value = mock_pod
        
        result = k8s_connection.wait_for_reboot(
            check_interval=30,
            max_wait_time=300,
            pod_name="test-pod"
        )
        
        assert result is False