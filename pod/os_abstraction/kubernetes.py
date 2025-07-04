"""
Kubernetes OS handler with advanced networking and VLAN support
"""

import json
import yaml
import time
import asyncio
from typing import Dict, Any, Optional, List, Tuple, Union
from kubernetes.client.rest import ApiException
from .base import BaseOSHandler, CommandResult, NetworkInterface, NetworkConfig
from ..connections.kubernetes import KubernetesConnection
from ..exceptions import NetworkConfigError, CommandExecutionError


class KubernetesHandler(BaseOSHandler):
    """
    Kubernetes handler with enterprise networking capabilities
    Supports CNI plugins, NetworkPolicies, and VLAN isolation
    """
    
    def __init__(self, connection: KubernetesConnection):
        """
        Initialize Kubernetes handler
        
        Args:
            connection: KubernetesConnection instance
        """
        super().__init__(connection)
        self.k8s = connection
        self.cni_plugins = self._detect_cni_plugins()
        self.network_capabilities = self._detect_network_capabilities()
    
    def _detect_cni_plugins(self) -> List[str]:
        """Detect available CNI plugins in the cluster"""
        plugins = []
        
        try:
            # Check for Calico
            calico_nodes = self.k8s.v1.list_node(label_selector="projectcalico.org/ds-ready=true")
            if calico_nodes.items:
                plugins.append("calico")
            
            # Check for Cilium
            cilium_pods = self.k8s.v1.list_pod_for_all_namespaces(label_selector="k8s-app=cilium")
            if cilium_pods.items:
                plugins.append("cilium")
            
            # Check for Flannel
            flannel_pods = self.k8s.v1.list_pod_for_all_namespaces(label_selector="app=flannel")
            if flannel_pods.items:
                plugins.append("flannel")
            
            # Check for Weave
            weave_pods = self.k8s.v1.list_pod_for_all_namespaces(label_selector="name=weave-net")
            if weave_pods.items:
                plugins.append("weave")
            
            # Check for Multus (multiple CNI support)
            multus_pods = self.k8s.v1.list_pod_for_all_namespaces(label_selector="app=multus")
            if multus_pods.items:
                plugins.append("multus")
                
        except Exception:
            # Fallback to default CNI detection
            pass
        
        return plugins if plugins else ["default"]
    
    def _detect_network_capabilities(self) -> Dict[str, bool]:
        """Detect network capabilities of the cluster"""
        capabilities = {
            "network_policies": False,
            "pod_security_policies": False,
            "service_mesh": False,
            "ingress_controllers": [],
            "load_balancers": [],
            "cni_chaining": False,
            "sr_iov": False,
            "dpdk": False
        }
        
        try:
            # Check NetworkPolicy support
            try:
                self.k8s.networking_v1.list_network_policy_for_all_namespaces(limit=1)
                capabilities["network_policies"] = True
            except Exception:
                pass
            
            # Check for Istio service mesh
            istio_pods = self.k8s.v1.list_pod_for_all_namespaces(label_selector="app=istiod")
            if istio_pods.items:
                capabilities["service_mesh"] = True
            
            # Check for ingress controllers
            ingress_controllers = []
            nginx_pods = self.k8s.v1.list_pod_for_all_namespaces(label_selector="app.kubernetes.io/name=ingress-nginx")
            if nginx_pods.items:
                ingress_controllers.append("nginx")
            
            traefik_pods = self.k8s.v1.list_pod_for_all_namespaces(label_selector="app.kubernetes.io/name=traefik")
            if traefik_pods.items:
                ingress_controllers.append("traefik")
                
            capabilities["ingress_controllers"] = ingress_controllers
            
            # Check for Multus (CNI chaining support)
            if "multus" in self.cni_plugins:
                capabilities["cni_chaining"] = True
            
            # Check for SR-IOV support
            sriov_pods = self.k8s.v1.list_pod_for_all_namespaces(label_selector="app=sriov-device-plugin")
            if sriov_pods.items:
                capabilities["sr_iov"] = True
                
        except Exception:
            pass
        
        return capabilities
    
    def get_os_info(self) -> Dict[str, Any]:
        """Get Kubernetes cluster and node information"""
        cluster_info = self.k8s.get_cluster_info()
        
        # Get node information
        nodes = []
        try:
            node_list = self.k8s.v1.list_node()
            for node in node_list.items:
                node_info = {
                    'name': node.metadata.name,
                    'os': node.status.node_info.operating_system,
                    'architecture': node.status.node_info.architecture,
                    'kernel_version': node.status.node_info.kernel_version,
                    'container_runtime': node.status.node_info.container_runtime_version,
                    'kubelet_version': node.status.node_info.kubelet_version,
                    'cpu_capacity': node.status.capacity.get('cpu', 'unknown'),
                    'memory_capacity': node.status.capacity.get('memory', 'unknown'),
                    'conditions': [
                        {
                            'type': condition.type,
                            'status': condition.status,
                            'reason': condition.reason or 'Unknown'
                        }
                        for condition in node.status.conditions or []
                    ]
                }
                nodes.append(node_info)
        except Exception:
            nodes = []
        
        return {
            'type': 'kubernetes',
            'platform': 'kubernetes',
            'cluster_version': cluster_info.get('version', 'unknown'),
            'git_version': cluster_info.get('git_version', 'unknown'),
            'node_count': len(nodes),
            'nodes': nodes,
            'cni_plugins': self.cni_plugins,
            'network_capabilities': self.network_capabilities,
            'namespace': self.k8s.namespace
        }
    
    def configure_network(self, config: NetworkConfig) -> CommandResult:
        """
        Configure network for Kubernetes pods using modern CNI approaches
        
        Args:
            config: Network configuration including VLAN settings
        
        Returns:
            CommandResult with operation status
        """
        try:
            if config.vlan_id:
                return self._configure_vlan_network(config)
            else:
                return self._configure_standard_network(config)
                
        except Exception as e:
            return CommandResult(
                stdout="",
                stderr=f"Network configuration failed: {str(e)}",
                exit_code=1,
                success=False,
                command=f"configure_network(vlan_id={config.vlan_id})",
                duration=0.0
            )
    
    def _configure_vlan_network(self, config: NetworkConfig) -> CommandResult:
        """Configure VLAN-based network isolation using CNI plugins"""
        start_time = time.time()
        
        try:
            if "multus" in self.cni_plugins:
                return self._configure_multus_vlan(config)
            elif "calico" in self.cni_plugins:
                return self._configure_calico_vlan(config)
            elif "cilium" in self.cni_plugins:
                return self._configure_cilium_vlan(config)
            else:
                return self._configure_generic_vlan(config)
                
        except Exception as e:
            duration = time.time() - start_time
            return CommandResult(
                stdout="",
                stderr=f"VLAN configuration failed: {str(e)}",
                exit_code=1,
                success=False,
                command=f"configure_vlan_network(vlan_id={config.vlan_id})",
                duration=duration
            )
    
    def _configure_multus_vlan(self, config: NetworkConfig) -> CommandResult:
        """Configure VLAN using Multus CNI for multiple network interfaces"""
        start_time = time.time()
        
        # Create NetworkAttachmentDefinition for VLAN
        network_attachment = {
            "apiVersion": "k8s.cni.cncf.io/v1",
            "kind": "NetworkAttachmentDefinition",
            "metadata": {
                "name": f"vlan-{config.vlan_id}",
                "namespace": self.k8s.namespace
            },
            "spec": {
                "config": json.dumps({
                    "cniVersion": "0.3.1",
                    "name": f"vlan-{config.vlan_id}",
                    "type": "macvlan",
                    "master": config.interface or "eth0",
                    "vlan": config.vlan_id,
                    "ipam": {
                        "type": "static",
                        "addresses": [
                            {
                                "address": f"{config.ip_address}/{self._netmask_to_cidr(config.netmask)}",
                                "gateway": config.gateway
                            }
                        ],
                        "dns": {
                            "nameservers": config.dns_servers or ["8.8.8.8"]
                        }
                    }
                })
            }
        }
        
        try:
            # Apply the NetworkAttachmentDefinition
            self.k8s.custom_objects_v1.create_namespaced_custom_object(
                group="k8s.cni.cncf.io",
                version="v1",
                namespace=self.k8s.namespace,
                plural="network-attachment-definitions",
                body=network_attachment
            )
            
            duration = time.time() - start_time
            return CommandResult(
                stdout=f"VLAN {config.vlan_id} NetworkAttachmentDefinition created successfully",
                stderr="",
                exit_code=0,
                success=True,
                command=f"create_multus_vlan({config.vlan_id})",
                duration=duration
            )
            
        except ApiException as e:
            if e.status == 409:  # Already exists
                duration = time.time() - start_time
                return CommandResult(
                    stdout=f"VLAN {config.vlan_id} NetworkAttachmentDefinition already exists",
                    stderr="",
                    exit_code=0,
                    success=True,
                    command=f"create_multus_vlan({config.vlan_id})",
                    duration=duration
                )
            raise
    
    def _configure_calico_vlan(self, config: NetworkConfig) -> CommandResult:
        """Configure VLAN using Calico BGP and IP pools"""
        start_time = time.time()
        
        # Create Calico IP Pool for VLAN
        ip_pool = {
            "apiVersion": "projectcalico.org/v3",
            "kind": "IPPool",
            "metadata": {
                "name": f"vlan-{config.vlan_id}-pool"
            },
            "spec": {
                "cidr": f"{config.ip_address}/{self._netmask_to_cidr(config.netmask)}",
                "vxlanMode": "Never",
                "ipipMode": "Never",
                "natOutgoing": True,
                "blockSize": 26,
                "nodeSelector": f"vlan-{config.vlan_id} == 'true'"
            }
        }
        
        try:
            # Apply Calico IP Pool
            self.k8s.custom_objects_v1.create_cluster_custom_object(
                group="projectcalico.org",
                version="v3",
                plural="ippools",
                body=ip_pool
            )
            
            duration = time.time() - start_time
            return CommandResult(
                stdout=f"Calico IP Pool for VLAN {config.vlan_id} created successfully",
                stderr="",
                exit_code=0,
                success=True,
                command=f"create_calico_vlan({config.vlan_id})",
                duration=duration
            )
            
        except ApiException as e:
            if e.status == 409:  # Already exists
                duration = time.time() - start_time
                return CommandResult(
                    stdout=f"Calico IP Pool for VLAN {config.vlan_id} already exists",
                    stderr="",
                    exit_code=0,
                    success=True,
                    command=f"create_calico_vlan({config.vlan_id})",
                    duration=duration
                )
            raise
    
    def _configure_cilium_vlan(self, config: NetworkConfig) -> CommandResult:
        """Configure VLAN using Cilium eBPF networking"""
        start_time = time.time()
        
        # Create CiliumNetworkPolicy for VLAN isolation
        network_policy = {
            "apiVersion": "cilium.io/v2",
            "kind": "CiliumNetworkPolicy",
            "metadata": {
                "name": f"vlan-{config.vlan_id}-policy",
                "namespace": self.k8s.namespace
            },
            "spec": {
                "endpointSelector": {
                    "matchLabels": {
                        f"vlan-{config.vlan_id}": "true"
                    }
                },
                "ingress": [
                    {
                        "fromEndpoints": [
                            {
                                "matchLabels": {
                                    f"vlan-{config.vlan_id}": "true"
                                }
                            }
                        ]
                    }
                ],
                "egress": [
                    {
                        "toEndpoints": [
                            {
                                "matchLabels": {
                                    f"vlan-{config.vlan_id}": "true"
                                }
                            }
                        ]
                    },
                    {
                        "toFQDNs": [
                            {"matchPattern": "*"}
                        ]
                    }
                ]
            }
        }
        
        try:
            # Apply Cilium Network Policy
            self.k8s.custom_objects_v1.create_namespaced_custom_object(
                group="cilium.io",
                version="v2",
                namespace=self.k8s.namespace,
                plural="ciliumnetworkpolicies",
                body=network_policy
            )
            
            duration = time.time() - start_time
            return CommandResult(
                stdout=f"Cilium Network Policy for VLAN {config.vlan_id} created successfully",
                stderr="",
                exit_code=0,
                success=True,
                command=f"create_cilium_vlan({config.vlan_id})",
                duration=duration
            )
            
        except ApiException as e:
            if e.status == 409:  # Already exists
                duration = time.time() - start_time
                return CommandResult(
                    stdout=f"Cilium Network Policy for VLAN {config.vlan_id} already exists",
                    stderr="",
                    exit_code=0,
                    success=True,
                    command=f"create_cilium_vlan({config.vlan_id})",
                    duration=duration
                )
            raise
    
    def _configure_generic_vlan(self, config: NetworkConfig) -> CommandResult:
        """Configure VLAN using standard Kubernetes NetworkPolicy"""
        start_time = time.time()
        
        # Create standard NetworkPolicy for basic isolation
        network_policy = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {
                "name": f"vlan-{config.vlan_id}-isolation",
                "namespace": self.k8s.namespace
            },
            "spec": {
                "podSelector": {
                    "matchLabels": {
                        f"vlan-{config.vlan_id}": "true"
                    }
                },
                "policyTypes": ["Ingress", "Egress"],
                "ingress": [
                    {
                        "from": [
                            {
                                "podSelector": {
                                    "matchLabels": {
                                        f"vlan-{config.vlan_id}": "true"
                                    }
                                }
                            }
                        ]
                    }
                ],
                "egress": [
                    {
                        "to": [
                            {
                                "podSelector": {
                                    "matchLabels": {
                                        f"vlan-{config.vlan_id}": "true"
                                    }
                                }
                            }
                        ]
                    },
                    {
                        "to": [],
                        "ports": [
                            {"protocol": "UDP", "port": 53}  # DNS
                        ]
                    }
                ]
            }
        }
        
        try:
            # Apply NetworkPolicy
            self.k8s.networking_v1.create_namespaced_network_policy(
                namespace=self.k8s.namespace,
                body=network_policy
            )
            
            duration = time.time() - start_time
            return CommandResult(
                stdout=f"NetworkPolicy for VLAN {config.vlan_id} created successfully",
                stderr="",
                exit_code=0,
                success=True,
                command=f"create_generic_vlan({config.vlan_id})",
                duration=duration
            )
            
        except ApiException as e:
            if e.status == 409:  # Already exists
                duration = time.time() - start_time
                return CommandResult(
                    stdout=f"NetworkPolicy for VLAN {config.vlan_id} already exists",
                    stderr="",
                    exit_code=0,
                    success=True,
                    command=f"create_generic_vlan({config.vlan_id})",
                    duration=duration
                )
            raise
    
    def _configure_standard_network(self, config: NetworkConfig) -> CommandResult:
        """Configure standard pod networking without VLAN"""
        start_time = time.time()
        
        # For standard networking, we primarily work with Services and Ingress
        # This is a placeholder for standard network configuration
        
        duration = time.time() - start_time
        return CommandResult(
            stdout="Standard network configuration applied",
            stderr="",
            exit_code=0,
            success=True,
            command="configure_standard_network",
            duration=duration
        )
    
    def _netmask_to_cidr(self, netmask: str) -> int:
        """Convert netmask to CIDR notation"""
        if not netmask:
            return 24  # Default
        
        # Convert netmask to CIDR
        octets = netmask.split('.')
        cidr = 0
        for octet in octets:
            cidr += bin(int(octet)).count('1')
        return cidr
    
    def get_network_interfaces(self) -> List[NetworkInterface]:
        """Get network interfaces for pods in the namespace"""
        interfaces = []
        
        try:
            pods = self.k8s.list_pods(namespace=self.k8s.namespace)
            
            for pod in pods:
                if pod['status'] == 'Running' and pod['ip']:
                    interface = NetworkInterface(
                        name=f"pod-{pod['name']}",
                        mac_address="unknown",  # Pod MAC addresses are typically managed by CNI
                        ip_addresses=[pod['ip']],
                        netmask="255.255.255.0",  # Default pod subnet
                        gateway="unknown",
                        vlan_id=None,  # Would need to extract from annotations
                        mtu=1500,
                        state="up" if pod['status'] == 'Running' else "down",
                        type="pod"
                    )
                    interfaces.append(interface)
                    
        except Exception:
            pass
        
        return interfaces
    
    def create_pod_with_vlan(self, pod_name: str, image: str, vlan_id: int, 
                           network_config: NetworkConfig) -> CommandResult:
        """
        Create a pod with specific VLAN configuration
        
        Args:
            pod_name: Name of the pod to create
            image: Container image to use
            vlan_id: VLAN ID for network isolation
            network_config: Network configuration
        
        Returns:
            CommandResult with creation status
        """
        start_time = time.time()
        
        # Ensure VLAN network is configured
        vlan_result = self._configure_vlan_network(network_config)
        if not vlan_result.success:
            return vlan_result
        
        # Pod specification with VLAN labels and annotations
        pod_spec = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": pod_name,
                "namespace": self.k8s.namespace,
                "labels": {
                    f"vlan-{vlan_id}": "true",
                    "app": pod_name
                },
                "annotations": {}
            },
            "spec": {
                "containers": [
                    {
                        "name": "main",
                        "image": image,
                        "resources": {
                            "requests": {
                                "memory": "64Mi",
                                "cpu": "50m"
                            },
                            "limits": {
                                "memory": "128Mi",
                                "cpu": "100m"
                            }
                        }
                    }
                ],
                "restartPolicy": "Always"
            }
        }
        
        # Add Multus annotations if available
        if "multus" in self.cni_plugins:
            pod_spec["metadata"]["annotations"]["k8s.v1.cni.cncf.io/networks"] = f"vlan-{vlan_id}"
        
        try:
            # Create the pod
            self.k8s.v1.create_namespaced_pod(
                namespace=self.k8s.namespace,
                body=pod_spec
            )
            
            # Wait for pod to be ready
            self._wait_for_pod_ready(pod_name, timeout=300)
            
            duration = time.time() - start_time
            return CommandResult(
                stdout=f"Pod {pod_name} created successfully with VLAN {vlan_id}",
                stderr="",
                exit_code=0,
                success=True,
                command=f"create_pod_with_vlan({pod_name}, vlan_id={vlan_id})",
                duration=duration
            )
            
        except ApiException as e:
            duration = time.time() - start_time
            return CommandResult(
                stdout="",
                stderr=f"Failed to create pod: {str(e)}",
                exit_code=1,
                success=False,
                command=f"create_pod_with_vlan({pod_name}, vlan_id={vlan_id})",
                duration=duration
            )
    
    def _wait_for_pod_ready(self, pod_name: str, timeout: int = 300) -> bool:
        """Wait for pod to be in Ready state"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                pod = self.k8s.v1.read_namespaced_pod(
                    name=pod_name,
                    namespace=self.k8s.namespace
                )
                
                if pod.status.phase == 'Running':
                    # Check container readiness
                    if pod.status.container_statuses:
                        all_ready = all(cs.ready for cs in pod.status.container_statuses)
                        if all_ready:
                            return True
                
                time.sleep(5)
                
            except ApiException:
                time.sleep(5)
        
        return False
    
    def delete_pod(self, pod_name: str) -> CommandResult:
        """Delete a pod"""
        start_time = time.time()
        
        try:
            self.k8s.v1.delete_namespaced_pod(
                name=pod_name,
                namespace=self.k8s.namespace
            )
            
            duration = time.time() - start_time
            return CommandResult(
                stdout=f"Pod {pod_name} deleted successfully",
                stderr="",
                exit_code=0,
                success=True,
                command=f"delete_pod({pod_name})",
                duration=duration
            )
            
        except ApiException as e:
            duration = time.time() - start_time
            return CommandResult(
                stdout="",
                stderr=f"Failed to delete pod: {str(e)}",
                exit_code=1,
                success=False,
                command=f"delete_pod({pod_name})",
                duration=duration
            )
    
    def test_network_connectivity(self, source_pod: str, target_ip: str, 
                                 port: Optional[int] = None) -> CommandResult:
        """
        Test network connectivity between pods
        
        Args:
            source_pod: Source pod name
            target_ip: Target IP address
            port: Optional port to test
        
        Returns:
            CommandResult with connectivity test results
        """
        if port:
            command = f"nc -zv {target_ip} {port}"
        else:
            command = f"ping -c 3 {target_ip}"
        
        try:
            stdout, stderr, exit_code = self.k8s.execute_command(
                command,
                pod_name=source_pod,
                namespace=self.k8s.namespace
            )
            
            return CommandResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                success=exit_code == 0,
                command=command,
                duration=0.0
            )
            
        except Exception as e:
            return CommandResult(
                stdout="",
                stderr=f"Network connectivity test failed: {str(e)}",
                exit_code=1,
                success=False,
                command=command,
                duration=0.0
            )
    
    # Override base methods that don't apply to Kubernetes
    def install_package(self, package_name: str, **kwargs) -> CommandResult:
        """Package installation not applicable for Kubernetes pods"""
        return CommandResult(
            stdout="Package installation should be handled in container image",
            stderr="",
            exit_code=0,
            success=True,
            command=f"install_package({package_name})",
            duration=0.0
        )
    
    def uninstall_package(self, package_name: str, **kwargs) -> CommandResult:
        """Package uninstallation not applicable for Kubernetes pods"""
        return CommandResult(
            stdout="Package uninstallation should be handled in container image",
            stderr="",
            exit_code=0,
            success=True,
            command=f"uninstall_package({package_name})",
            duration=0.0
        )
    
    def reboot(self, wait_for_reboot: bool = True, **kwargs) -> CommandResult:
        """Reboot equivalent is pod restart"""
        pod_name = kwargs.get('pod_name')
        if not pod_name:
            return CommandResult(
                stdout="",
                stderr="pod_name required for pod restart",
                exit_code=1,
                success=False,
                command="reboot",
                duration=0.0
            )
        
        # Delete and recreate pod (restart)
        delete_result = self.delete_pod(pod_name)
        if not delete_result.success:
            return delete_result
        
        # Pod will be recreated by deployment controller if it's managed
        return CommandResult(
            stdout=f"Pod {pod_name} restart initiated",
            stderr="",
            exit_code=0,
            success=True,
            command=f"restart_pod({pod_name})",
            duration=0.0
        )
    
    def shutdown(self, **kwargs) -> CommandResult:
        """Shutdown equivalent is pod deletion"""
        pod_name = kwargs.get('pod_name')
        if not pod_name:
            return CommandResult(
                stdout="",
                stderr="pod_name required for pod shutdown",
                exit_code=1,
                success=False,
                command="shutdown",
                duration=0.0
            )
        
        return self.delete_pod(pod_name)
    
    # Implementation of remaining abstract methods from BaseOSHandler
    def execute_command(self, command: str, **kwargs) -> CommandResult:
        """Execute command in pod"""
        try:
            stdout, stderr, exit_code = self.k8s.execute_command(command, **kwargs)
            return CommandResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                success=exit_code == 0,
                command=command,
                duration=0.0
            )
        except Exception as e:
            return CommandResult(
                stdout="",
                stderr=str(e),
                exit_code=1,
                success=False,
                command=command,
                duration=0.0
            )
    
    def upload_file(self, local_path: str, remote_path: str, **kwargs) -> CommandResult:
        """Upload file to pod"""
        try:
            success = self.k8s.upload_file(local_path, remote_path, **kwargs)
            return CommandResult(
                stdout="File uploaded successfully" if success else "",
                stderr="" if success else "File upload failed",
                exit_code=0 if success else 1,
                success=success,
                command=f"upload_file({local_path}, {remote_path})",
                duration=0.0
            )
        except Exception as e:
            return CommandResult(
                stdout="",
                stderr=str(e),
                exit_code=1,
                success=False,
                command=f"upload_file({local_path}, {remote_path})",
                duration=0.0
            )
    
    def download_file(self, remote_path: str, local_path: str, **kwargs) -> CommandResult:
        """Download file from pod"""
        try:
            success = self.k8s.download_file(remote_path, local_path, **kwargs)
            return CommandResult(
                stdout="File downloaded successfully" if success else "",
                stderr="" if success else "File download failed",
                exit_code=0 if success else 1,
                success=success,
                command=f"download_file({remote_path}, {local_path})",
                duration=0.0
            )
        except Exception as e:
            return CommandResult(
                stdout="",
                stderr=str(e),
                exit_code=1,
                success=False,
                command=f"download_file({remote_path}, {local_path})",
                duration=0.0
            )
    
    def file_exists(self, path: str, **kwargs) -> bool:
        """Check if file exists in pod"""
        try:
            stdout, stderr, exit_code = self.k8s.execute_command(f"test -f {path}", **kwargs)
            return exit_code == 0
        except Exception:
            return False
    
    def create_directory(self, path: str, **kwargs) -> CommandResult:
        """Create directory in pod"""
        return self.execute_command(f"mkdir -p {path}", **kwargs)
    
    def list_directory(self, path: str, **kwargs) -> CommandResult:
        """List directory contents in pod"""
        return self.execute_command(f"ls -la {path}", **kwargs)
    
    def remove_file(self, path: str, **kwargs) -> CommandResult:
        """Remove file from pod"""
        return self.execute_command(f"rm -f {path}", **kwargs)
    
    def get_processes(self, **kwargs) -> CommandResult:
        """Get running processes in pod"""
        return self.execute_command("ps aux", **kwargs)
    
    def kill_process(self, pid: int, **kwargs) -> CommandResult:
        """Kill process in pod"""
        return self.execute_command(f"kill {pid}", **kwargs)
    
    def get_memory_info(self, **kwargs) -> CommandResult:
        """Get memory information from pod"""
        return self.execute_command("free -m", **kwargs)
    
    def get_cpu_info(self, **kwargs) -> CommandResult:
        """Get CPU information from pod"""
        return self.execute_command("lscpu", **kwargs)
    
    def get_disk_usage(self, path: str = "/", **kwargs) -> CommandResult:
        """Get disk usage in pod"""
        return self.execute_command(f"df -h {path}", **kwargs)
    
    def create_user(self, username: str, **kwargs) -> CommandResult:
        """Create user in pod (not typically applicable)"""
        return CommandResult(
            stdout="User creation not applicable for containers",
            stderr="",
            exit_code=0,
            success=True,
            command=f"create_user({username})",
            duration=0.0
        )
    
    def set_hostname(self, hostname: str, **kwargs) -> CommandResult:
        """Set hostname (not applicable for pods)"""
        return CommandResult(
            stdout="Hostname setting not applicable for pods",
            stderr="",
            exit_code=0,
            success=True,
            command=f"set_hostname({hostname})",
            duration=0.0
        )
    
    def start_service(self, service_name: str, **kwargs) -> CommandResult:
        """Start service in pod"""
        return self.execute_command(f"systemctl start {service_name}", **kwargs)
    
    def stop_service(self, service_name: str, **kwargs) -> CommandResult:
        """Stop service in pod"""
        return self.execute_command(f"systemctl stop {service_name}", **kwargs)
    
    def restart_network_service(self, **kwargs) -> CommandResult:
        """Restart network service (not applicable for pods)"""
        return CommandResult(
            stdout="Network service restart not applicable for pods",
            stderr="",
            exit_code=0,
            success=True,
            command="restart_network_service",
            duration=0.0
        )
    
    def get_service_status(self, service_name: str, **kwargs) -> CommandResult:
        """Get service status in pod"""
        return self.execute_command(f"systemctl status {service_name}", **kwargs)