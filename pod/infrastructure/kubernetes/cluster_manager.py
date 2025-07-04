"""
Kubernetes cluster management utilities
"""

from typing import Dict, Any, List, Optional
from kubernetes.client.rest import ApiException
from ...connections.kubernetes import KubernetesConnection
from ...exceptions import ProviderError


class ClusterManager:
    """Kubernetes cluster management and monitoring"""
    
    def __init__(self, connection: KubernetesConnection):
        self.k8s = connection
    
    def get_cluster_health(self) -> Dict[str, Any]:
        """Get comprehensive cluster health information"""
        health = {
            "status": "unknown",
            "nodes": {"ready": 0, "not_ready": 0, "total": 0},
            "system_pods": {"running": 0, "pending": 0, "failed": 0, "total": 0},
            "api_server": {"reachable": False, "version": "unknown"},
            "etcd": {"healthy": False},
            "dns": {"healthy": False},
            "network": {"cni_healthy": False},
            "storage": {"healthy": False},
            "warnings": [],
            "critical_issues": []
        }
        
        try:
            # Check API server
            version = self.k8s.v1.get_code()
            health["api_server"] = {
                "reachable": True,
                "version": f"{version.major}.{version.minor}",
                "git_version": version.git_version
            }
            
            # Check nodes
            nodes = self.k8s.v1.list_node()
            for node in nodes.items:
                health["nodes"]["total"] += 1
                
                ready = False
                for condition in node.status.conditions or []:
                    if condition.type == "Ready" and condition.status == "True":
                        ready = True
                        break
                
                if ready:
                    health["nodes"]["ready"] += 1
                else:
                    health["nodes"]["not_ready"] += 1
                    health["warnings"].append(f"Node {node.metadata.name} is not ready")
            
            # Check system pods
            system_namespaces = ["kube-system", "kube-public", "kube-node-lease"]
            for namespace in system_namespaces:
                try:
                    pods = self.k8s.v1.list_namespaced_pod(namespace=namespace)
                    for pod in pods.items:
                        health["system_pods"]["total"] += 1
                        
                        if pod.status.phase == "Running":
                            health["system_pods"]["running"] += 1
                        elif pod.status.phase == "Pending":
                            health["system_pods"]["pending"] += 1
                        elif pod.status.phase == "Failed":
                            health["system_pods"]["failed"] += 1
                            health["warnings"].append(f"System pod {pod.metadata.name} failed")
                except Exception:
                    pass
            
            # Check DNS
            try:
                dns_pods = self.k8s.v1.list_namespaced_pod(
                    namespace="kube-system",
                    label_selector="k8s-app=kube-dns"
                )
                if not dns_pods.items:
                    # Try CoreDNS
                    dns_pods = self.k8s.v1.list_namespaced_pod(
                        namespace="kube-system",
                        label_selector="k8s-app=coredns"
                    )
                
                if dns_pods.items:
                    dns_ready = all(
                        pod.status.phase == "Running" 
                        for pod in dns_pods.items
                    )
                    health["dns"]["healthy"] = dns_ready
                    if not dns_ready:
                        health["warnings"].append("DNS pods are not all running")
            except Exception:
                health["warnings"].append("Could not check DNS health")
            
            # Determine overall status
            critical_issues = len(health["critical_issues"])
            warnings = len(health["warnings"])
            
            if critical_issues > 0:
                health["status"] = "critical"
            elif warnings > 0:
                health["status"] = "warning"
            elif health["nodes"]["ready"] == health["nodes"]["total"] and health["nodes"]["total"] > 0:
                health["status"] = "healthy"
            else:
                health["status"] = "degraded"
                
        except Exception as e:
            health["status"] = "error"
            health["critical_issues"].append(f"Failed to check cluster health: {str(e)}")
        
        return health
    
    def get_resource_usage(self) -> Dict[str, Any]:
        """Get cluster resource usage metrics"""
        usage = {
            "nodes": [],
            "cluster_totals": {
                "cpu_capacity": "0",
                "memory_capacity": "0",
                "cpu_allocatable": "0",
                "memory_allocatable": "0",
                "pods_capacity": 0,
                "pods_allocatable": 0
            },
            "namespace_usage": {}
        }
        
        try:
            # Get node metrics
            nodes = self.k8s.v1.list_node()
            for node in nodes.items:
                node_info = {
                    "name": node.metadata.name,
                    "capacity": node.status.capacity or {},
                    "allocatable": node.status.allocatable or {},
                    "conditions": []
                }
                
                # Parse conditions
                for condition in node.status.conditions or []:
                    node_info["conditions"].append({
                        "type": condition.type,
                        "status": condition.status,
                        "reason": condition.reason or "Unknown"
                    })
                
                usage["nodes"].append(node_info)
                
                # Add to cluster totals (simplified - would need proper parsing for CPU/memory)
                if node.status.capacity:
                    if "pods" in node.status.capacity:
                        usage["cluster_totals"]["pods_capacity"] += int(node.status.capacity["pods"])
                
                if node.status.allocatable:
                    if "pods" in node.status.allocatable:
                        usage["cluster_totals"]["pods_allocatable"] += int(node.status.allocatable["pods"])
            
            # Get namespace usage
            namespaces = self.k8s.v1.list_namespace()
            for namespace in namespaces.items:
                ns_name = namespace.metadata.name
                try:
                    pods = self.k8s.v1.list_namespaced_pod(namespace=ns_name)
                    usage["namespace_usage"][ns_name] = {
                        "pod_count": len(pods.items),
                        "running_pods": len([p for p in pods.items if p.status.phase == "Running"]),
                        "pending_pods": len([p for p in pods.items if p.status.phase == "Pending"]),
                        "failed_pods": len([p for p in pods.items if p.status.phase == "Failed"])
                    }
                except Exception:
                    usage["namespace_usage"][ns_name] = {"pod_count": 0, "error": "Could not fetch pods"}
                    
        except Exception:
            pass
        
        return usage
    
    def get_networking_info(self) -> Dict[str, Any]:
        """Get cluster networking information"""
        networking = {
            "cni_plugin": "unknown",
            "service_cidr": "unknown",
            "pod_cidr": "unknown",
            "cluster_dns": "unknown",
            "ingress_controllers": [],
            "load_balancers": [],
            "network_policies": {"supported": False, "count": 0},
            "services": {"count": 0, "types": {}},
            "endpoints": {"count": 0}
        }
        
        try:
            # Detect CNI plugin (basic detection)
            cni_pods = self.k8s.v1.list_pod_for_all_namespaces(label_selector="k8s-app")
            for pod in cni_pods.items:
                labels = pod.metadata.labels or {}
                app = labels.get("k8s-app", "")
                
                if "calico" in app.lower():
                    networking["cni_plugin"] = "calico"
                elif "cilium" in app.lower():
                    networking["cni_plugin"] = "cilium"
                elif "flannel" in app.lower():
                    networking["cni_plugin"] = "flannel"
                elif "weave" in app.lower():
                    networking["cni_plugin"] = "weave"
            
            # Check NetworkPolicy support
            try:
                policies = self.k8s.networking_v1.list_network_policy_for_all_namespaces()
                networking["network_policies"] = {
                    "supported": True,
                    "count": len(policies.items)
                }
            except Exception:
                networking["network_policies"] = {"supported": False, "count": 0}
            
            # Get services information
            services = self.k8s.v1.list_service_for_all_namespaces()
            networking["services"]["count"] = len(services.items)
            
            service_types = {}
            for service in services.items:
                svc_type = service.spec.type
                service_types[svc_type] = service_types.get(svc_type, 0) + 1
            
            networking["services"]["types"] = service_types
            
            # Get endpoints
            endpoints = self.k8s.v1.list_endpoints_for_all_namespaces()
            networking["endpoints"]["count"] = len(endpoints.items)
            
        except Exception:
            pass
        
        return networking
    
    def get_storage_info(self) -> Dict[str, Any]:
        """Get cluster storage information"""
        storage = {
            "storage_classes": [],
            "persistent_volumes": {"count": 0, "by_status": {}},
            "persistent_volume_claims": {"count": 0, "by_status": {}},
            "volume_snapshots": {"supported": False, "count": 0}
        }
        
        try:
            # Get storage classes
            try:
                storage_classes = self.k8s.storage_v1.list_storage_class()
                for sc in storage_classes.items:
                    storage["storage_classes"].append({
                        "name": sc.metadata.name,
                        "provisioner": sc.provisioner,
                        "is_default": sc.metadata.annotations and 
                                    sc.metadata.annotations.get("storageclass.kubernetes.io/is-default-class") == "true"
                    })
            except Exception:
                pass
            
            # Get persistent volumes
            try:
                pvs = self.k8s.v1.list_persistent_volume()
                storage["persistent_volumes"]["count"] = len(pvs.items)
                
                pv_status = {}
                for pv in pvs.items:
                    status = pv.status.phase
                    pv_status[status] = pv_status.get(status, 0) + 1
                
                storage["persistent_volumes"]["by_status"] = pv_status
            except Exception:
                pass
            
            # Get persistent volume claims
            try:
                pvcs = self.k8s.v1.list_persistent_volume_claim_for_all_namespaces()
                storage["persistent_volume_claims"]["count"] = len(pvcs.items)
                
                pvc_status = {}
                for pvc in pvcs.items:
                    status = pvc.status.phase
                    pvc_status[status] = pvc_status.get(status, 0) + 1
                
                storage["persistent_volume_claims"]["by_status"] = pvc_status
            except Exception:
                pass
                
        except Exception:
            pass
        
        return storage
    
    def get_security_info(self) -> Dict[str, Any]:
        """Get cluster security information"""
        security = {
            "rbac": {"enabled": False, "roles": 0, "bindings": 0},
            "pod_security": {"policies": 0, "standards": []},
            "network_policies": {"count": 0},
            "secrets": {"count": 0},
            "service_accounts": {"count": 0},
            "admission_controllers": [],
            "security_contexts": {"pods_with_context": 0, "total_pods": 0}
        }
        
        try:
            # Check RBAC
            try:
                roles = self.k8s.rbac_authorization_v1.list_role_for_all_namespaces()
                cluster_roles = self.k8s.rbac_authorization_v1.list_cluster_role()
                role_bindings = self.k8s.rbac_authorization_v1.list_role_binding_for_all_namespaces()
                cluster_role_bindings = self.k8s.rbac_authorization_v1.list_cluster_role_binding()
                
                security["rbac"] = {
                    "enabled": True,
                    "roles": len(roles.items) + len(cluster_roles.items),
                    "bindings": len(role_bindings.items) + len(cluster_role_bindings.items)
                }
            except Exception:
                security["rbac"]["enabled"] = False
            
            # Check secrets
            try:
                secrets = self.k8s.v1.list_secret_for_all_namespaces()
                security["secrets"]["count"] = len(secrets.items)
            except Exception:
                pass
            
            # Check service accounts
            try:
                service_accounts = self.k8s.v1.list_service_account_for_all_namespaces()
                security["service_accounts"]["count"] = len(service_accounts.items)
            except Exception:
                pass
            
            # Check network policies
            try:
                network_policies = self.k8s.networking_v1.list_network_policy_for_all_namespaces()
                security["network_policies"]["count"] = len(network_policies.items)
            except Exception:
                pass
            
            # Check pod security contexts
            try:
                pods = self.k8s.v1.list_pod_for_all_namespaces()
                total_pods = len(pods.items)
                pods_with_context = 0
                
                for pod in pods.items:
                    if pod.spec.security_context:
                        pods_with_context += 1
                
                security["security_contexts"] = {
                    "pods_with_context": pods_with_context,
                    "total_pods": total_pods
                }
            except Exception:
                pass
                
        except Exception:
            pass
        
        return security
    
    def get_events(self, namespace: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get cluster events"""
        events = []
        
        try:
            if namespace:
                event_list = self.k8s.v1.list_namespaced_event(namespace=namespace, limit=limit)
            else:
                event_list = self.k8s.v1.list_event_for_all_namespaces(limit=limit)
            
            for event in event_list.items:
                events.append({
                    "type": event.type,
                    "reason": event.reason,
                    "message": event.message,
                    "object": f"{event.involved_object.kind}/{event.involved_object.name}",
                    "namespace": event.namespace,
                    "first_timestamp": event.first_timestamp.isoformat() if event.first_timestamp else None,
                    "last_timestamp": event.last_timestamp.isoformat() if event.last_timestamp else None,
                    "count": event.count
                })
                
        except Exception:
            pass
        
        # Sort by last timestamp
        events.sort(key=lambda x: x["last_timestamp"] or "", reverse=True)
        return events
    
    def cordon_node(self, node_name: str) -> bool:
        """Cordon a node (mark as unschedulable)"""
        try:
            node = self.k8s.v1.read_node(name=node_name)
            node.spec.unschedulable = True
            self.k8s.v1.patch_node(name=node_name, body=node)
            return True
        except Exception:
            return False
    
    def uncordon_node(self, node_name: str) -> bool:
        """Uncordon a node (mark as schedulable)"""
        try:
            node = self.k8s.v1.read_node(name=node_name)
            node.spec.unschedulable = False
            self.k8s.v1.patch_node(name=node_name, body=node)
            return True
        except Exception:
            return False
    
    def drain_node(self, node_name: str, delete_emptydir_data: bool = False, 
                   force: bool = False, grace_period: int = 300) -> bool:
        """Drain a node (evict all pods)"""
        # This is a simplified version - a full implementation would need
        # to handle DaemonSets, local storage, etc.
        try:
            pods = self.k8s.v1.list_pod_for_all_namespaces(field_selector=f"spec.nodeName={node_name}")
            
            for pod in pods.items:
                # Skip system pods unless forced
                if not force and pod.metadata.namespace in ["kube-system", "kube-public"]:
                    continue
                
                # Delete pod
                try:
                    self.k8s.v1.delete_namespaced_pod(
                        name=pod.metadata.name,
                        namespace=pod.metadata.namespace,
                        grace_period_seconds=grace_period
                    )
                except Exception:
                    continue
            
            return True
        except Exception:
            return False