"""
Kubernetes infrastructure provider
"""

from typing import Dict, Any, List, Optional, Union, Tuple
from kubernetes.client.rest import ApiException
from ...connections.kubernetes import KubernetesConnection
from ...os_abstraction.kubernetes import KubernetesHandler
from ...network.cni import CNIManager, CNIConfig
from ...exceptions import ProviderError, ConnectionError


class KubernetesProvider:
    """
    Kubernetes infrastructure provider for hybrid cloud management
    Integrates with vSphere and container infrastructures
    """
    
    def __init__(self, 
                 kubeconfig_path: Optional[str] = None,
                 context: Optional[str] = None,
                 namespace: str = "default",
                 api_server: Optional[str] = None,
                 token: Optional[str] = None,
                 ca_cert_path: Optional[str] = None):
        """
        Initialize Kubernetes provider
        
        Args:
            kubeconfig_path: Path to kubeconfig file
            context: Kubernetes context to use
            namespace: Default namespace
            api_server: Direct API server URL
            token: Service account token
            ca_cert_path: CA certificate path
        """
        self.connection = KubernetesConnection(
            kubeconfig_path=kubeconfig_path,
            context=context,
            namespace=namespace,
            api_server=api_server,
            token=token,
            ca_cert_path=ca_cert_path
        )
        
        self.handler = None
        self.cni_manager = None
        self.cluster_info = {}
        self._connected = False
    
    def connect(self) -> bool:
        """Connect to Kubernetes cluster"""
        try:
            self.connection.connect()
            self.handler = KubernetesHandler(self.connection)
            self.cni_manager = CNIManager(self.connection)
            self.cluster_info = self.connection.get_cluster_info()
            self._connected = True
            return True
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Kubernetes cluster: {str(e)}")
    
    def disconnect(self) -> None:
        """Disconnect from Kubernetes cluster"""
        if self.connection:
            self.connection.disconnect()
        self.handler = None
        self.cni_manager = None
        self.cluster_info = {}
        self._connected = False
    
    def is_connected(self) -> bool:
        """Check if connected to cluster"""
        return self._connected and self.connection.is_connected()
    
    def get_cluster_info(self) -> Dict[str, Any]:
        """Get comprehensive cluster information"""
        if not self.is_connected():
            raise ProviderError("Not connected to Kubernetes cluster")
        
        base_info = self.handler.get_os_info()
        
        # Add provider-specific information
        provider_info = {
            "provider_type": "kubernetes",
            "cluster_name": self.cluster_info.get("cluster_name", "unknown"),
            "api_server": self.connection.host,
            "namespace": self.connection.namespace,
            "cni_plugins": self.cni_manager.detected_cnis,
            "network_capabilities": self.cni_manager.capabilities,
            "observability": self.cni_manager.get_network_observability_config()
        }
        
        base_info.update(provider_info)
        return base_info
    
    def create_namespace(self, name: str, labels: Optional[Dict[str, str]] = None) -> bool:
        """Create a new namespace"""
        if not self.is_connected():
            raise ProviderError("Not connected to Kubernetes cluster")
        
        namespace_spec = {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": name,
                "labels": labels or {}
            }
        }
        
        try:
            self.connection.v1.create_namespace(body=namespace_spec)
            return True
        except Exception:
            return False
    
    def delete_namespace(self, name: str) -> bool:
        """Delete a namespace"""
        if not self.is_connected():
            raise ProviderError("Not connected to Kubernetes cluster")
        
        try:
            self.connection.v1.delete_namespace(name=name)
            return True
        except Exception:
            return False
    
    def list_namespaces(self) -> List[str]:
        """List all namespaces"""
        if not self.is_connected():
            raise ProviderError("Not connected to Kubernetes cluster")
        
        return self.connection.list_namespaces()
    
    def deploy_workload(self, 
                       workload_type: str,
                       name: str,
                       image: str,
                       namespace: Optional[str] = None,
                       replicas: int = 1,
                       labels: Optional[Dict[str, str]] = None,
                       annotations: Optional[Dict[str, str]] = None,
                       network_config: Optional[CNIConfig] = None,
                       vlan_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Deploy workload with advanced networking
        
        Args:
            workload_type: Type of workload (deployment, pod, daemonset, statefulset)
            name: Workload name
            image: Container image
            namespace: Target namespace
            replicas: Number of replicas
            labels: Pod labels
            annotations: Pod annotations
            network_config: Advanced network configuration
            vlan_id: VLAN ID for isolation
        
        Returns:
            Deployment result information
        """
        if not self.is_connected():
            raise ProviderError("Not connected to Kubernetes cluster")
        
        namespace = namespace or self.connection.namespace
        labels = labels or {}
        annotations = annotations or {}
        
        # Add VLAN labels if specified
        if vlan_id:
            labels[f"vlan-{vlan_id}"] = "true"
        
        # Configure advanced networking if specified
        if network_config:
            self._setup_network_configuration(network_config, namespace)
            if network_config.name:
                annotations["k8s.v1.cni.cncf.io/networks"] = network_config.name
        
        if workload_type.lower() == "pod":
            return self._deploy_pod(name, image, namespace, labels, annotations)
        elif workload_type.lower() == "deployment":
            return self._deploy_deployment(name, image, namespace, replicas, labels, annotations)
        elif workload_type.lower() == "statefulset":
            return self._deploy_statefulset(name, image, namespace, replicas, labels, annotations)
        elif workload_type.lower() == "daemonset":
            return self._deploy_daemonset(name, image, namespace, labels, annotations)
        else:
            raise ProviderError(f"Unsupported workload type: {workload_type}")
    
    def _setup_network_configuration(self, config: CNIConfig, namespace: str) -> None:
        """Setup network configuration using CNI manager"""
        if self.cni_manager.detected_cnis["multus"]:
            # Create NetworkAttachmentDefinition
            net_attachment = self.cni_manager.create_network_attachment_definition(config)
            net_attachment["metadata"]["namespace"] = namespace
            self.cni_manager.apply_network_configuration(net_attachment)
        
        # Setup CNI-specific configurations
        if config.vlan_id:
            if self.cni_manager.detected_cnis["calico"]:
                ip_pool = self.cni_manager.create_calico_ip_pool(
                    name=f"vlan-{config.vlan_id}-pool",
                    cidr=config.subnet or "192.168.100.0/24",
                    vlan_id=config.vlan_id
                )
                self.cni_manager.apply_network_configuration(ip_pool)
    
    def _deploy_pod(self, name: str, image: str, namespace: str,
                   labels: Dict[str, str], annotations: Dict[str, str]) -> Dict[str, Any]:
        """Deploy a single pod"""
        pod_spec = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": name,
                "namespace": namespace,
                "labels": labels,
                "annotations": annotations
            },
            "spec": {
                "containers": [
                    {
                        "name": "main",
                        "image": image,
                        "resources": {
                            "requests": {"memory": "64Mi", "cpu": "50m"},
                            "limits": {"memory": "128Mi", "cpu": "100m"}
                        }
                    }
                ],
                "restartPolicy": "Always"
            }
        }
        
        try:
            result = self.connection.v1.create_namespaced_pod(
                namespace=namespace,
                body=pod_spec
            )
            return {
                "type": "pod",
                "name": name,
                "namespace": namespace,
                "status": "created",
                "uid": result.metadata.uid
            }
        except Exception as e:
            raise ProviderError(f"Failed to deploy pod: {str(e)}")
    
    def _deploy_deployment(self, name: str, image: str, namespace: str, replicas: int,
                          labels: Dict[str, str], annotations: Dict[str, str]) -> Dict[str, Any]:
        """Deploy a Deployment"""
        deployment_spec = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": name,
                "namespace": namespace,
                "labels": labels
            },
            "spec": {
                "replicas": replicas,
                "selector": {
                    "matchLabels": {"app": name}
                },
                "template": {
                    "metadata": {
                        "labels": {**labels, "app": name},
                        "annotations": annotations
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": "main",
                                "image": image,
                                "resources": {
                                    "requests": {"memory": "64Mi", "cpu": "50m"},
                                    "limits": {"memory": "128Mi", "cpu": "100m"}
                                }
                            }
                        ]
                    }
                }
            }
        }
        
        try:
            result = self.connection.apps_v1.create_namespaced_deployment(
                namespace=namespace,
                body=deployment_spec
            )
            return {
                "type": "deployment",
                "name": name,
                "namespace": namespace,
                "replicas": replicas,
                "status": "created",
                "uid": result.metadata.uid
            }
        except Exception as e:
            raise ProviderError(f"Failed to deploy deployment: {str(e)}")
    
    def _deploy_statefulset(self, name: str, image: str, namespace: str, replicas: int,
                           labels: Dict[str, str], annotations: Dict[str, str]) -> Dict[str, Any]:
        """Deploy a StatefulSet"""
        statefulset_spec = {
            "apiVersion": "apps/v1",
            "kind": "StatefulSet",
            "metadata": {
                "name": name,
                "namespace": namespace,
                "labels": labels
            },
            "spec": {
                "serviceName": name,
                "replicas": replicas,
                "selector": {
                    "matchLabels": {"app": name}
                },
                "template": {
                    "metadata": {
                        "labels": {**labels, "app": name},
                        "annotations": annotations
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": "main",
                                "image": image,
                                "resources": {
                                    "requests": {"memory": "64Mi", "cpu": "50m"},
                                    "limits": {"memory": "128Mi", "cpu": "100m"}
                                }
                            }
                        ]
                    }
                }
            }
        }
        
        try:
            result = self.connection.apps_v1.create_namespaced_stateful_set(
                namespace=namespace,
                body=statefulset_spec
            )
            return {
                "type": "statefulset",
                "name": name,
                "namespace": namespace,
                "replicas": replicas,
                "status": "created",
                "uid": result.metadata.uid
            }
        except Exception as e:
            raise ProviderError(f"Failed to deploy statefulset: {str(e)}")
    
    def _deploy_daemonset(self, name: str, image: str, namespace: str,
                         labels: Dict[str, str], annotations: Dict[str, str]) -> Dict[str, Any]:
        """Deploy a DaemonSet"""
        daemonset_spec = {
            "apiVersion": "apps/v1",
            "kind": "DaemonSet",
            "metadata": {
                "name": name,
                "namespace": namespace,
                "labels": labels
            },
            "spec": {
                "selector": {
                    "matchLabels": {"app": name}
                },
                "template": {
                    "metadata": {
                        "labels": {**labels, "app": name},
                        "annotations": annotations
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": "main",
                                "image": image,
                                "resources": {
                                    "requests": {"memory": "64Mi", "cpu": "50m"},
                                    "limits": {"memory": "128Mi", "cpu": "100m"}
                                }
                            }
                        ]
                    }
                }
            }
        }
        
        try:
            result = self.connection.apps_v1.create_namespaced_daemon_set(
                namespace=namespace,
                body=daemonset_spec
            )
            return {
                "type": "daemonset",
                "name": name,
                "namespace": namespace,
                "status": "created",
                "uid": result.metadata.uid
            }
        except Exception as e:
            raise ProviderError(f"Failed to deploy daemonset: {str(e)}")
    
    def delete_workload(self, workload_type: str, name: str, namespace: Optional[str] = None) -> bool:
        """Delete a workload"""
        if not self.is_connected():
            raise ProviderError("Not connected to Kubernetes cluster")
        
        namespace = namespace or self.connection.namespace
        
        try:
            if workload_type.lower() == "pod":
                self.connection.v1.delete_namespaced_pod(name=name, namespace=namespace)
            elif workload_type.lower() == "deployment":
                self.connection.apps_v1.delete_namespaced_deployment(name=name, namespace=namespace)
            elif workload_type.lower() == "statefulset":
                self.connection.apps_v1.delete_namespaced_stateful_set(name=name, namespace=namespace)
            elif workload_type.lower() == "daemonset":
                self.connection.apps_v1.delete_namespaced_daemon_set(name=name, namespace=namespace)
            else:
                return False
            
            return True
        except Exception:
            return False
    
    def list_workloads(self, namespace: Optional[str] = None, workload_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """List workloads in namespace"""
        if not self.is_connected():
            raise ProviderError("Not connected to Kubernetes cluster")
        
        namespace = namespace or self.connection.namespace
        workloads = []
        
        try:
            if not workload_type or workload_type.lower() == "pod":
                pods = self.connection.list_pods(namespace=namespace)
                for pod in pods:
                    workloads.append({
                        "type": "pod",
                        "name": pod["name"],
                        "namespace": pod["namespace"],
                        "status": pod["status"],
                        "node": pod["node"],
                        "ip": pod["ip"]
                    })
            
            if not workload_type or workload_type.lower() == "deployment":
                deployments = self.connection.apps_v1.list_namespaced_deployment(namespace=namespace)
                for deployment in deployments.items:
                    workloads.append({
                        "type": "deployment",
                        "name": deployment.metadata.name,
                        "namespace": deployment.metadata.namespace,
                        "replicas": deployment.spec.replicas,
                        "ready_replicas": deployment.status.ready_replicas or 0
                    })
            
        except ApiException as e:
            # Log workload listing failures but return partial results
            pass
        except Exception as e:
            # Log unexpected errors but return partial results
            pass
        
        return workloads
    
    def scale_workload(self, workload_type: str, name: str, replicas: int, namespace: Optional[str] = None) -> bool:
        """Scale a workload"""
        if not self.is_connected():
            raise ProviderError("Not connected to Kubernetes cluster")
        
        namespace = namespace or self.connection.namespace
        
        try:
            if workload_type.lower() == "deployment":
                # Update deployment replicas
                deployment = self.connection.apps_v1.read_namespaced_deployment(name=name, namespace=namespace)
                deployment.spec.replicas = replicas
                self.connection.apps_v1.patch_namespaced_deployment(
                    name=name,
                    namespace=namespace,
                    body=deployment
                )
                return True
            elif workload_type.lower() == "statefulset":
                # Update statefulset replicas
                statefulset = self.connection.apps_v1.read_namespaced_stateful_set(name=name, namespace=namespace)
                statefulset.spec.replicas = replicas
                self.connection.apps_v1.patch_namespaced_stateful_set(
                    name=name,
                    namespace=namespace,
                    body=statefulset
                )
                return True
            
        except Exception:
            return False
        
        return False
    
    def get_workload_logs(self, workload_type: str, name: str, namespace: Optional[str] = None, 
                         container: Optional[str] = None, lines: int = 100) -> str:
        """Get workload logs"""
        if not self.is_connected():
            raise ProviderError("Not connected to Kubernetes cluster")
        
        namespace = namespace or self.connection.namespace
        
        try:
            if workload_type.lower() == "pod":
                return self.connection.v1.read_namespaced_pod_log(
                    name=name,
                    namespace=namespace,
                    container=container,
                    tail_lines=lines
                )
            else:
                # For other workload types, get logs from first pod
                pods = self.connection.list_pods(namespace=namespace, label_selector=f"app={name}")
                if pods:
                    return self.connection.v1.read_namespaced_pod_log(
                        name=pods[0]["name"],
                        namespace=namespace,
                        container=container,
                        tail_lines=lines
                    )
                return ""
        except Exception:
            return ""
    
    def execute_in_workload(self, workload_type: str, name: str, command: str,
                           namespace: Optional[str] = None, container: Optional[str] = None) -> Tuple[str, str, int]:
        """Execute command in workload"""
        if not self.is_connected():
            raise ProviderError("Not connected to Kubernetes cluster")
        
        namespace = namespace or self.connection.namespace
        
        try:
            if workload_type.lower() == "pod":
                return self.connection.execute_command(
                    command,
                    pod_name=name,
                    container=container,
                    namespace=namespace
                )
            else:
                # For other workload types, execute in first pod
                pods = self.connection.list_pods(namespace=namespace, label_selector=f"app={name}")
                if pods:
                    return self.connection.execute_command(
                        command,
                        pod_name=pods[0]["name"],
                        container=container,
                        namespace=namespace
                    )
                return "", "No pods found", 1
        except Exception as e:
            return "", f"Execution failed: {str(e)}", 1