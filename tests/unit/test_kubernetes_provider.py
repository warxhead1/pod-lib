"""
Unit tests for Kubernetes infrastructure provider
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pod.infrastructure.kubernetes.provider import KubernetesProvider
from pod.network.cni import CNIConfig
from pod.exceptions import ProviderError, ConnectionError


class TestKubernetesProvider:
    """Test Kubernetes infrastructure provider"""
    
    @pytest.fixture
    def k8s_provider(self):
        """Create Kubernetes provider"""
        return KubernetesProvider(
            kubeconfig_path="/test/kubeconfig",
            context="test-context",
            namespace="test-namespace"
        )
    
    def test_init(self):
        """Test provider initialization"""
        provider = KubernetesProvider(
            kubeconfig_path="/test/kubeconfig",
            context="test-context",
            namespace="production"
        )
        
        assert provider.connection.kubeconfig_path == "/test/kubeconfig"
        assert provider.connection.context == "test-context"
        assert provider.connection.namespace == "production"
        assert provider._connected is False
    
    def test_init_with_api_server(self):
        """Test initialization with API server"""
        provider = KubernetesProvider(
            api_server="https://k8s.example.com:6443",
            token="test-token"
        )
        
        assert provider.connection.api_server == "https://k8s.example.com:6443"
        assert provider.connection.token == "test-token"
    
    @patch('pod.infrastructure.kubernetes.provider.KubernetesHandler')
    @patch('pod.infrastructure.kubernetes.provider.CNIManager')
    def test_connect_success(self, mock_cni_manager, mock_handler, k8s_provider):
        """Test successful connection"""
        # Mock connection success
        k8s_provider.connection.connect = Mock()
        k8s_provider.connection.get_cluster_info = Mock(return_value={"version": "1.28"})
        
        result = k8s_provider.connect()
        
        assert result is True
        assert k8s_provider._connected is True
        assert k8s_provider.handler is not None
        assert k8s_provider.cni_manager is not None
    
    def test_connect_failure(self, k8s_provider):
        """Test connection failure"""
        k8s_provider.connection.connect = Mock(side_effect=Exception("Connection failed"))
        
        with pytest.raises(ConnectionError, match="Failed to connect to Kubernetes cluster"):
            k8s_provider.connect()
    
    def test_disconnect(self, k8s_provider):
        """Test disconnection"""
        k8s_provider.connection = Mock()
        k8s_provider.handler = Mock()
        k8s_provider.cni_manager = Mock()
        k8s_provider._connected = True
        
        k8s_provider.disconnect()
        
        assert k8s_provider._connected is False
        assert k8s_provider.handler is None
        assert k8s_provider.cni_manager is None
        k8s_provider.connection.disconnect.assert_called_once()
    
    def test_is_connected_true(self, k8s_provider):
        """Test is_connected returns True"""
        k8s_provider._connected = True
        k8s_provider.connection.is_connected = Mock(return_value=True)
        
        assert k8s_provider.is_connected() is True
    
    def test_is_connected_false(self, k8s_provider):
        """Test is_connected returns False"""
        k8s_provider._connected = False
        
        assert k8s_provider.is_connected() is False
    
    def test_get_cluster_info_not_connected(self, k8s_provider):
        """Test get_cluster_info when not connected"""
        k8s_provider._connected = False
        
        with pytest.raises(ProviderError, match="Not connected to Kubernetes cluster"):
            k8s_provider.get_cluster_info()
    
    def test_get_cluster_info_success(self, k8s_provider):
        """Test successful cluster info retrieval"""
        k8s_provider._connected = True
        k8s_provider.connection.is_connected = Mock(return_value=True)
        k8s_provider.handler = Mock()
        k8s_provider.handler.get_os_info.return_value = {
            "type": "kubernetes",
            "cluster_version": "1.28"
        }
        k8s_provider.cni_manager = Mock()
        k8s_provider.cni_manager.detected_cnis = {"calico": True}
        k8s_provider.cni_manager.capabilities = {"network_policies": True}
        k8s_provider.cni_manager.get_network_observability_config.return_value = {}
        k8s_provider.cluster_info = {"cluster_name": "test-cluster"}
        
        info = k8s_provider.get_cluster_info()
        
        assert info["provider_type"] == "kubernetes"
        assert info["cluster_version"] == "1.28"
        assert info["cni_plugins"] == {"calico": True}
    
    def test_create_namespace_success(self, k8s_provider):
        """Test successful namespace creation"""
        k8s_provider._connected = True
        k8s_provider.connection = Mock()
        k8s_provider.connection.is_connected.return_value = True
        k8s_provider.connection.v1.create_namespace.return_value = Mock()
        
        result = k8s_provider.create_namespace("test-ns", {"env": "test"})
        
        assert result is True
        k8s_provider.connection.v1.create_namespace.assert_called_once()
    
    def test_create_namespace_not_connected(self, k8s_provider):
        """Test namespace creation when not connected"""
        k8s_provider._connected = False
        
        with pytest.raises(ProviderError, match="Not connected to Kubernetes cluster"):
            k8s_provider.create_namespace("test-ns")
    
    def test_create_namespace_failure(self, k8s_provider):
        """Test namespace creation failure"""
        k8s_provider._connected = True
        k8s_provider.connection = Mock()
        k8s_provider.connection.is_connected.return_value = True
        k8s_provider.connection.v1.create_namespace.side_effect = Exception("Creation failed")
        
        result = k8s_provider.create_namespace("test-ns")
        
        assert result is False
    
    def test_delete_namespace_success(self, k8s_provider):
        """Test successful namespace deletion"""
        k8s_provider._connected = True
        k8s_provider.connection = Mock()
        k8s_provider.connection.is_connected.return_value = True
        k8s_provider.connection.v1.delete_namespace.return_value = Mock()
        
        result = k8s_provider.delete_namespace("test-ns")
        
        assert result is True
        k8s_provider.connection.v1.delete_namespace.assert_called_once_with(name="test-ns")
    
    def test_list_namespaces_success(self, k8s_provider):
        """Test successful namespace listing"""
        k8s_provider._connected = True
        k8s_provider.connection = Mock()
        k8s_provider.connection.is_connected.return_value = True
        k8s_provider.connection.list_namespaces.return_value = ["default", "kube-system"]
        
        namespaces = k8s_provider.list_namespaces()
        
        assert namespaces == ["default", "kube-system"]
    
    def test_deploy_workload_pod(self, k8s_provider):
        """Test pod deployment"""
        k8s_provider._connected = True
        k8s_provider.connection = Mock()
        k8s_provider.connection.is_connected.return_value = True
        k8s_provider.connection.namespace = "default"
        
        with patch.object(k8s_provider, '_deploy_pod') as mock_deploy:
            mock_deploy.return_value = {
                "type": "pod",
                "name": "test-pod",
                "status": "created"
            }
            
            result = k8s_provider.deploy_workload(
                workload_type="pod",
                name="test-pod",
                image="nginx:alpine"
            )
            
            assert result["type"] == "pod"
            assert result["name"] == "test-pod"
            mock_deploy.assert_called_once()
    
    def test_deploy_workload_deployment(self, k8s_provider):
        """Test deployment workload"""
        k8s_provider._connected = True
        k8s_provider.connection = Mock()
        k8s_provider.connection.is_connected.return_value = True
        k8s_provider.connection.namespace = "default"
        
        with patch.object(k8s_provider, '_deploy_deployment') as mock_deploy:
            mock_deploy.return_value = {
                "type": "deployment", 
                "name": "test-deploy",
                "replicas": 3
            }
            
            result = k8s_provider.deploy_workload(
                workload_type="deployment",
                name="test-deploy",
                image="nginx:alpine",
                replicas=3
            )
            
            assert result["type"] == "deployment"
            assert result["replicas"] == 3
            mock_deploy.assert_called_once()
    
    def test_deploy_workload_with_vlan(self, k8s_provider):
        """Test workload deployment with VLAN"""
        k8s_provider._connected = True
        k8s_provider.connection = Mock()
        k8s_provider.connection.is_connected.return_value = True
        k8s_provider.connection.namespace = "default"
        
        network_config = CNIConfig(
            name="test-vlan",
            type="macvlan",
            vlan_id=100
        )
        
        with patch.object(k8s_provider, '_setup_network_configuration') as mock_setup:
            with patch.object(k8s_provider, '_deploy_pod') as mock_deploy:
                mock_deploy.return_value = {"type": "pod", "name": "test-pod"}
                
                result = k8s_provider.deploy_workload(
                    workload_type="pod",
                    name="test-pod",
                    image="nginx:alpine",
                    network_config=network_config,
                    vlan_id=100
                )
                
                mock_setup.assert_called_once()
                mock_deploy.assert_called_once()
    
    def test_deploy_workload_unsupported_type(self, k8s_provider):
        """Test deployment with unsupported workload type"""
        k8s_provider._connected = True
        k8s_provider.connection = Mock()
        k8s_provider.connection.is_connected.return_value = True
        
        with pytest.raises(ProviderError, match="Unsupported workload type"):
            k8s_provider.deploy_workload(
                workload_type="unsupported",
                name="test",
                image="nginx:alpine"
            )
    
    def test_deploy_pod_success(self, k8s_provider):
        """Test successful pod deployment"""
        k8s_provider.connection = Mock()
        k8s_provider.connection.v1.create_namespaced_pod.return_value = Mock(
            metadata=Mock(uid="pod-uid-123")
        )
        
        result = k8s_provider._deploy_pod(
            "test-pod",
            "nginx:alpine", 
            "default",
            {"app": "test"},
            {}
        )
        
        assert result["type"] == "pod"
        assert result["name"] == "test-pod"
        assert result["uid"] == "pod-uid-123"
    
    def test_deploy_deployment_success(self, k8s_provider):
        """Test successful deployment creation"""
        k8s_provider.connection = Mock()
        k8s_provider.connection.apps_v1.create_namespaced_deployment.return_value = Mock(
            metadata=Mock(uid="deploy-uid-123")
        )
        
        result = k8s_provider._deploy_deployment(
            "test-deploy",
            "nginx:alpine",
            "default", 
            3,
            {"app": "test"},
            {}
        )
        
        assert result["type"] == "deployment"
        assert result["name"] == "test-deploy"
        assert result["replicas"] == 3
        assert result["uid"] == "deploy-uid-123"
    
    def test_delete_workload_pod(self, k8s_provider):
        """Test pod deletion"""
        k8s_provider._connected = True
        k8s_provider.connection = Mock()
        k8s_provider.connection.is_connected.return_value = True
        k8s_provider.connection.namespace = "default"
        k8s_provider.connection.v1.delete_namespaced_pod.return_value = Mock()
        
        result = k8s_provider.delete_workload("pod", "test-pod")
        
        assert result is True
        k8s_provider.connection.v1.delete_namespaced_pod.assert_called_once()
    
    def test_delete_workload_deployment(self, k8s_provider):
        """Test deployment deletion"""
        k8s_provider._connected = True
        k8s_provider.connection = Mock()
        k8s_provider.connection.is_connected.return_value = True
        k8s_provider.connection.namespace = "default"
        k8s_provider.connection.apps_v1.delete_namespaced_deployment.return_value = Mock()
        
        result = k8s_provider.delete_workload("deployment", "test-deploy")
        
        assert result is True
        k8s_provider.connection.apps_v1.delete_namespaced_deployment.assert_called_once()
    
    def test_list_workloads_success(self, k8s_provider):
        """Test successful workload listing"""
        k8s_provider._connected = True
        k8s_provider.connection = Mock()
        k8s_provider.connection.is_connected.return_value = True
        k8s_provider.connection.namespace = "default"
        k8s_provider.connection.list_pods.return_value = [
            {
                "name": "test-pod",
                "namespace": "default",
                "status": "Running",
                "node": "node-1",
                "ip": "10.244.1.5"
            }
        ]
        
        # Mock deployment list
        mock_deployment = Mock()
        mock_deployment.metadata.name = "test-deploy"
        mock_deployment.metadata.namespace = "default"
        mock_deployment.spec.replicas = 3
        mock_deployment.status.ready_replicas = 3
        
        k8s_provider.connection.apps_v1.list_namespaced_deployment.return_value = Mock(
            items=[mock_deployment]
        )
        
        workloads = k8s_provider.list_workloads()
        
        assert len(workloads) == 2  # 1 pod + 1 deployment
        assert workloads[0]["type"] == "pod"
        assert workloads[1]["type"] == "deployment"
    
    def test_scale_workload_deployment(self, k8s_provider):
        """Test deployment scaling"""
        k8s_provider._connected = True
        k8s_provider.connection = Mock()
        k8s_provider.connection.is_connected.return_value = True
        k8s_provider.connection.namespace = "default"
        
        # Mock deployment read and patch
        mock_deployment = Mock()
        mock_deployment.spec.replicas = 3
        k8s_provider.connection.apps_v1.read_namespaced_deployment.return_value = mock_deployment
        k8s_provider.connection.apps_v1.patch_namespaced_deployment.return_value = Mock()
        
        result = k8s_provider.scale_workload("deployment", "test-deploy", 5)
        
        assert result is True
        assert mock_deployment.spec.replicas == 5
        k8s_provider.connection.apps_v1.patch_namespaced_deployment.assert_called_once()
    
    def test_get_workload_logs_pod(self, k8s_provider):
        """Test getting pod logs"""
        k8s_provider._connected = True
        k8s_provider.connection = Mock()
        k8s_provider.connection.is_connected.return_value = True
        k8s_provider.connection.namespace = "default"
        k8s_provider.connection.v1.read_namespaced_pod_log.return_value = "Log output"
        
        logs = k8s_provider.get_workload_logs("pod", "test-pod")
        
        assert logs == "Log output"
        k8s_provider.connection.v1.read_namespaced_pod_log.assert_called_once()
    
    def test_get_workload_logs_deployment(self, k8s_provider):
        """Test getting deployment logs"""
        k8s_provider._connected = True
        k8s_provider.connection = Mock()
        k8s_provider.connection.is_connected.return_value = True
        k8s_provider.connection.namespace = "default"
        k8s_provider.connection.list_pods.return_value = [
            {"name": "test-deploy-abc123"}
        ]
        k8s_provider.connection.v1.read_namespaced_pod_log.return_value = "Deployment logs"
        
        logs = k8s_provider.get_workload_logs("deployment", "test-deploy")
        
        assert logs == "Deployment logs"
    
    def test_execute_in_workload_pod(self, k8s_provider):
        """Test command execution in pod"""
        k8s_provider._connected = True
        k8s_provider.connection = Mock()
        k8s_provider.connection.is_connected.return_value = True
        k8s_provider.connection.namespace = "default"
        k8s_provider.connection.execute_command.return_value = ("output", "", 0)
        
        stdout, stderr, exit_code = k8s_provider.execute_in_workload(
            "pod", "test-pod", "ls -la"
        )
        
        assert stdout == "output"
        assert stderr == ""
        assert exit_code == 0
    
    def test_execute_in_workload_deployment(self, k8s_provider):
        """Test command execution in deployment pod"""
        k8s_provider._connected = True
        k8s_provider.connection = Mock()
        k8s_provider.connection.is_connected.return_value = True
        k8s_provider.connection.namespace = "default"
        k8s_provider.connection.list_pods.return_value = [
            {"name": "test-deploy-abc123"}
        ]
        k8s_provider.connection.execute_command.return_value = ("deploy output", "", 0)
        
        stdout, stderr, exit_code = k8s_provider.execute_in_workload(
            "deployment", "test-deploy", "ps aux"
        )
        
        assert stdout == "deploy output"
        assert exit_code == 0