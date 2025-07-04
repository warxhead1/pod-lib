"""
Advanced Kubernetes workload management
"""

import time
import yaml
from typing import Dict, Any, List, Optional, Tuple
from kubernetes.client.rest import ApiException
from ...connections.kubernetes import KubernetesConnection
from ...network.cni import CNIManager, CNIConfig
from ...exceptions import ProviderError


class WorkloadManager:
    """Advanced workload management with enterprise features"""
    
    def __init__(self, connection: KubernetesConnection):
        self.k8s = connection
        self.cni_manager = CNIManager(connection)
    
    def create_advanced_deployment(self, 
                                 name: str,
                                 image: str,
                                 namespace: str = "default",
                                 replicas: int = 1,
                                 resources: Optional[Dict[str, Any]] = None,
                                 network_config: Optional[CNIConfig] = None,
                                 security_context: Optional[Dict[str, Any]] = None,
                                 affinity: Optional[Dict[str, Any]] = None,
                                 tolerations: Optional[List[Dict[str, Any]]] = None,
                                 volume_mounts: Optional[List[Dict[str, Any]]] = None,
                                 env_vars: Optional[Dict[str, str]] = None,
                                 labels: Optional[Dict[str, str]] = None,
                                 annotations: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Create advanced deployment with enterprise features
        
        Args:
            name: Deployment name
            image: Container image
            namespace: Target namespace
            replicas: Number of replicas
            resources: Resource requests and limits
            network_config: Advanced network configuration
            security_context: Security context configuration
            affinity: Pod affinity/anti-affinity rules
            tolerations: Pod tolerations
            volume_mounts: Volume mount configurations
            env_vars: Environment variables
            labels: Pod labels
            annotations: Pod annotations
        
        Returns:
            Deployment creation result
        """
        
        # Default resources
        if not resources:
            resources = {
                "requests": {"memory": "64Mi", "cpu": "50m"},
                "limits": {"memory": "128Mi", "cpu": "100m"}
            }
        
        # Default labels
        if not labels:
            labels = {"app": name}
        else:
            labels.update({"app": name})
        
        # Default annotations
        if not annotations:
            annotations = {}
        
        # Setup network configuration
        if network_config:
            self._setup_network_configuration(network_config, namespace)
            if network_config.name:
                annotations["k8s.v1.cni.cncf.io/networks"] = network_config.name
            if network_config.vlan_id:
                labels[f"vlan-{network_config.vlan_id}"] = "true"
        
        # Build container spec
        container_spec = {
            "name": "main",
            "image": image,
            "resources": resources
        }
        
        # Add environment variables
        if env_vars:
            container_spec["env"] = [
                {"name": k, "value": v} for k, v in env_vars.items()
            ]
        
        # Add volume mounts
        if volume_mounts:
            container_spec["volumeMounts"] = volume_mounts
        
        # Build pod spec
        pod_spec = {
            "containers": [container_spec],
            "restartPolicy": "Always"
        }
        
        # Add security context
        if security_context:
            pod_spec["securityContext"] = security_context
        
        # Add affinity
        if affinity:
            pod_spec["affinity"] = affinity
        
        # Add tolerations
        if tolerations:
            pod_spec["tolerations"] = tolerations
        
        # Build deployment
        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": name,
                "namespace": namespace,
                "labels": labels,
                "annotations": annotations
            },
            "spec": {
                "replicas": replicas,
                "selector": {
                    "matchLabels": {"app": name}
                },
                "template": {
                    "metadata": {
                        "labels": labels,
                        "annotations": annotations
                    },
                    "spec": pod_spec
                },
                "strategy": {
                    "type": "RollingUpdate",
                    "rollingUpdate": {
                        "maxUnavailable": 1,
                        "maxSurge": 1
                    }
                }
            }
        }
        
        try:
            result = self.k8s.apps_v1.create_namespaced_deployment(
                namespace=namespace,
                body=deployment
            )
            
            return {
                "name": name,
                "namespace": namespace,
                "uid": result.metadata.uid,
                "replicas": replicas,
                "status": "created",
                "labels": labels,
                "network_config": network_config.name if network_config else None
            }
            
        except ApiException as e:
            raise ProviderError(f"Failed to create deployment: {str(e)}")
    
    def _setup_network_configuration(self, config: CNIConfig, namespace: str) -> None:
        """Setup advanced network configuration"""
        if self.cni_manager.detected_cnis["multus"]:
            # Create NetworkAttachmentDefinition
            net_attachment = self.cni_manager.create_network_attachment_definition(config)
            net_attachment["metadata"]["namespace"] = namespace
            self.cni_manager.apply_network_configuration(net_attachment)
        
        # Setup VLAN isolation
        if config.vlan_id:
            if self.cni_manager.detected_cnis["calico"]:
                # Create Calico IP Pool
                ip_pool = self.cni_manager.create_calico_ip_pool(
                    name=f"vlan-{config.vlan_id}-pool",
                    cidr=config.subnet or f"192.168.{config.vlan_id}.0/24",
                    vlan_id=config.vlan_id
                )
                self.cni_manager.apply_network_configuration(ip_pool)
            
            elif self.cni_manager.detected_cnis["cilium"]:
                # Create Cilium Network Policy
                policy = self.cni_manager.create_cilium_network_policy(
                    name=f"vlan-{config.vlan_id}-isolation",
                    namespace=namespace,
                    endpoint_selector={f"vlan-{config.vlan_id}": "true"},
                    ingress_rules=[{
                        "fromEndpoints": [{
                            "matchLabels": {f"vlan-{config.vlan_id}": "true"}
                        }]
                    }],
                    egress_rules=[{
                        "toEndpoints": [{
                            "matchLabels": {f"vlan-{config.vlan_id}": "true"}
                        }]
                    }]
                )
                self.cni_manager.apply_network_configuration(policy)
    
    def create_statefulset_with_storage(self,
                                      name: str,
                                      image: str,
                                      namespace: str = "default",
                                      replicas: int = 1,
                                      storage_class: str = "default",
                                      storage_size: str = "1Gi",
                                      mount_path: str = "/data",
                                      resources: Optional[Dict[str, Any]] = None,
                                      network_config: Optional[CNIConfig] = None,
                                      labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Create StatefulSet with persistent storage"""
        
        if not labels:
            labels = {"app": name}
        else:
            labels.update({"app": name})
        
        if not resources:
            resources = {
                "requests": {"memory": "128Mi", "cpu": "100m"},
                "limits": {"memory": "256Mi", "cpu": "200m"}
            }
        
        annotations = {}
        if network_config:
            self._setup_network_configuration(network_config, namespace)
            if network_config.name:
                annotations["k8s.v1.cni.cncf.io/networks"] = network_config.name
            if network_config.vlan_id:
                labels[f"vlan-{network_config.vlan_id}"] = "true"
        
        statefulset = {
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
                        "labels": labels,
                        "annotations": annotations
                    },
                    "spec": {
                        "containers": [{
                            "name": "main",
                            "image": image,
                            "resources": resources,
                            "volumeMounts": [{
                                "name": "data",
                                "mountPath": mount_path
                            }]
                        }]
                    }
                },
                "volumeClaimTemplates": [{
                    "metadata": {
                        "name": "data"
                    },
                    "spec": {
                        "accessModes": ["ReadWriteOnce"],
                        "storageClassName": storage_class,
                        "resources": {
                            "requests": {
                                "storage": storage_size
                            }
                        }
                    }
                }]
            }
        }
        
        try:
            result = self.k8s.apps_v1.create_namespaced_stateful_set(
                namespace=namespace,
                body=statefulset
            )
            
            return {
                "name": name,
                "namespace": namespace,
                "uid": result.metadata.uid,
                "replicas": replicas,
                "storage_size": storage_size,
                "storage_class": storage_class,
                "status": "created"
            }
            
        except ApiException as e:
            raise ProviderError(f"Failed to create StatefulSet: {str(e)}")
    
    def create_job(self,
                   name: str,
                   image: str,
                   command: List[str],
                   namespace: str = "default",
                   backoff_limit: int = 3,
                   ttl_seconds_after_finished: int = 3600,
                   resources: Optional[Dict[str, Any]] = None,
                   env_vars: Optional[Dict[str, str]] = None,
                   labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Create a Kubernetes Job"""
        
        if not labels:
            labels = {"app": name, "type": "job"}
        else:
            labels.update({"app": name, "type": "job"})
        
        if not resources:
            resources = {
                "requests": {"memory": "64Mi", "cpu": "50m"},
                "limits": {"memory": "128Mi", "cpu": "100m"}
            }
        
        container_spec = {
            "name": "job",
            "image": image,
            "command": command,
            "resources": resources,
            "restartPolicy": "Never"
        }
        
        if env_vars:
            container_spec["env"] = [
                {"name": k, "value": v} for k, v in env_vars.items()
            ]
        
        job = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": name,
                "namespace": namespace,
                "labels": labels
            },
            "spec": {
                "template": {
                    "metadata": {
                        "labels": labels
                    },
                    "spec": {
                        "containers": [container_spec],
                        "restartPolicy": "Never"
                    }
                },
                "backoffLimit": backoff_limit,
                "ttlSecondsAfterFinished": ttl_seconds_after_finished
            }
        }
        
        try:
            result = self.k8s.batch_v1.create_namespaced_job(
                namespace=namespace,
                body=job
            )
            
            return {
                "name": name,
                "namespace": namespace,
                "uid": result.metadata.uid,
                "status": "created",
                "backoff_limit": backoff_limit
            }
            
        except ApiException as e:
            raise ProviderError(f"Failed to create Job: {str(e)}")
    
    def create_cronjob(self,
                       name: str,
                       image: str,
                       command: List[str],
                       schedule: str,
                       namespace: str = "default",
                       timezone: Optional[str] = None,
                       suspend: bool = False,
                       resources: Optional[Dict[str, Any]] = None,
                       env_vars: Optional[Dict[str, str]] = None,
                       labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Create a Kubernetes CronJob"""
        
        if not labels:
            labels = {"app": name, "type": "cronjob"}
        else:
            labels.update({"app": name, "type": "cronjob"})
        
        if not resources:
            resources = {
                "requests": {"memory": "64Mi", "cpu": "50m"},
                "limits": {"memory": "128Mi", "cpu": "100m"}
            }
        
        container_spec = {
            "name": "cronjob",
            "image": image,
            "command": command,
            "resources": resources
        }
        
        if env_vars:
            container_spec["env"] = [
                {"name": k, "value": v} for k, v in env_vars.items()
            ]
        
        cronjob_spec = {
            "schedule": schedule,
            "suspend": suspend,
            "jobTemplate": {
                "spec": {
                    "template": {
                        "metadata": {
                            "labels": labels
                        },
                        "spec": {
                            "containers": [container_spec],
                            "restartPolicy": "OnFailure"
                        }
                    }
                }
            }
        }
        
        if timezone:
            cronjob_spec["timeZone"] = timezone
        
        cronjob = {
            "apiVersion": "batch/v1",
            "kind": "CronJob",
            "metadata": {
                "name": name,
                "namespace": namespace,
                "labels": labels
            },
            "spec": cronjob_spec
        }
        
        try:
            result = self.k8s.batch_v1.create_namespaced_cron_job(
                namespace=namespace,
                body=cronjob
            )
            
            return {
                "name": name,
                "namespace": namespace,
                "uid": result.metadata.uid,
                "schedule": schedule,
                "suspended": suspend,
                "status": "created"
            }
            
        except ApiException as e:
            raise ProviderError(f"Failed to create CronJob: {str(e)}")
    
    def update_deployment_image(self, name: str, new_image: str, namespace: str = "default") -> bool:
        """Update deployment container image"""
        try:
            # Get current deployment
            deployment = self.k8s.apps_v1.read_namespaced_deployment(
                name=name,
                namespace=namespace
            )
            
            # Update image
            deployment.spec.template.spec.containers[0].image = new_image
            
            # Apply update
            self.k8s.apps_v1.patch_namespaced_deployment(
                name=name,
                namespace=namespace,
                body=deployment
            )
            
            return True
            
        except ApiException:
            return False
    
    def rollback_deployment(self, name: str, namespace: str = "default", revision: Optional[int] = None) -> bool:
        """Rollback deployment to previous or specific revision"""
        try:
            # Get deployment
            deployment = self.k8s.apps_v1.read_namespaced_deployment(
                name=name,
                namespace=namespace
            )
            
            # Trigger rollback by updating annotation
            if not deployment.spec.template.metadata.annotations:
                deployment.spec.template.metadata.annotations = {}
            
            deployment.spec.template.metadata.annotations["deployment.kubernetes.io/rollback"] = str(revision or "")
            
            # Apply rollback
            self.k8s.apps_v1.patch_namespaced_deployment(
                name=name,
                namespace=namespace,
                body=deployment
            )
            
            return True
            
        except ApiException:
            return False
    
    def get_deployment_status(self, name: str, namespace: str = "default") -> Dict[str, Any]:
        """Get detailed deployment status"""
        try:
            deployment = self.k8s.apps_v1.read_namespaced_deployment(
                name=name,
                namespace=namespace
            )
            
            status = {
                "name": name,
                "namespace": namespace,
                "replicas": {
                    "desired": deployment.spec.replicas,
                    "current": deployment.status.replicas or 0,
                    "ready": deployment.status.ready_replicas or 0,
                    "available": deployment.status.available_replicas or 0,
                    "unavailable": deployment.status.unavailable_replicas or 0
                },
                "conditions": [],
                "revision": deployment.metadata.annotations.get("deployment.kubernetes.io/revision", "unknown"),
                "strategy": deployment.spec.strategy.type if deployment.spec.strategy else "RollingUpdate"
            }
            
            # Parse conditions
            if deployment.status.conditions:
                for condition in deployment.status.conditions:
                    status["conditions"].append({
                        "type": condition.type,
                        "status": condition.status,
                        "reason": condition.reason or "Unknown",
                        "message": condition.message or ""
                    })
            
            return status
            
        except ApiException:
            return {"error": "Deployment not found"}
    
    def wait_for_deployment_ready(self, name: str, namespace: str = "default", timeout: int = 300) -> bool:
        """Wait for deployment to be ready"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                status = self.get_deployment_status(name, namespace)
                
                if "error" not in status:
                    replicas = status["replicas"]
                    if (replicas["desired"] == replicas["ready"] and 
                        replicas["ready"] > 0):
                        return True
                
                time.sleep(5)
                
            except Exception:
                time.sleep(5)
        
        return False
    
    def get_pod_logs_advanced(self, 
                             name: str,
                             namespace: str = "default",
                             container: Optional[str] = None,
                             lines: Optional[int] = 100,
                             since_seconds: Optional[int] = None,
                             follow: bool = False) -> str:
        """Get advanced pod logs with filtering options"""
        try:
            kwargs = {
                "name": name,
                "namespace": namespace,
                "follow": follow
            }
            
            if container:
                kwargs["container"] = container
            if lines:
                kwargs["tail_lines"] = lines
            if since_seconds:
                kwargs["since_seconds"] = since_seconds
            
            return self.k8s.v1.read_namespaced_pod_log(**kwargs)
            
        except ApiException:
            return ""
    
    def exec_in_pod_advanced(self,
                            name: str,
                            command: List[str],
                            namespace: str = "default",
                            container: Optional[str] = None,
                            stdin: bool = False,
                            tty: bool = False) -> Tuple[str, str, int]:
        """Execute command in pod with advanced options"""
        try:
            from kubernetes.stream import stream
            
            resp = stream(
                self.k8s.v1.connect_get_namespaced_pod_exec,
                name,
                namespace,
                command=command,
                container=container,
                stderr=True,
                stdin=stdin,
                stdout=True,
                tty=tty,
                _preload_content=False
            )
            
            stdout_lines = []
            stderr_lines = []
            
            while resp.is_open():
                resp.update(timeout=1)
                if resp.peek_stdout():
                    stdout_lines.append(resp.read_stdout())
                if resp.peek_stderr():
                    stderr_lines.append(resp.read_stderr())
            
            stdout = ''.join(stdout_lines)
            stderr = ''.join(stderr_lines)
            exit_code = 0 if not stderr else 1
            
            return stdout, stderr, exit_code
            
        except ApiException as e:
            return "", f"Execution failed: {str(e)}", 1
    
    def create_hpa(self,
                   name: str,
                   target_name: str,
                   target_kind: str = "Deployment",
                   namespace: str = "default",
                   min_replicas: int = 1,
                   max_replicas: int = 10,
                   cpu_percent: int = 80,
                   memory_percent: Optional[int] = None) -> Dict[str, Any]:
        """Create Horizontal Pod Autoscaler"""
        
        metrics = [{
            "type": "Resource",
            "resource": {
                "name": "cpu",
                "target": {
                    "type": "Utilization",
                    "averageUtilization": cpu_percent
                }
            }
        }]
        
        if memory_percent:
            metrics.append({
                "type": "Resource",
                "resource": {
                    "name": "memory",
                    "target": {
                        "type": "Utilization",
                        "averageUtilization": memory_percent
                    }
                }
            })
        
        hpa = {
            "apiVersion": "autoscaling/v2",
            "kind": "HorizontalPodAutoscaler",
            "metadata": {
                "name": name,
                "namespace": namespace
            },
            "spec": {
                "scaleTargetRef": {
                    "apiVersion": "apps/v1",
                    "kind": target_kind,
                    "name": target_name
                },
                "minReplicas": min_replicas,
                "maxReplicas": max_replicas,
                "metrics": metrics
            }
        }
        
        try:
            result = self.k8s.autoscaling_v2.create_namespaced_horizontal_pod_autoscaler(
                namespace=namespace,
                body=hpa
            )
            
            return {
                "name": name,
                "namespace": namespace,
                "target": f"{target_kind}/{target_name}",
                "min_replicas": min_replicas,
                "max_replicas": max_replicas,
                "status": "created"
            }
            
        except ApiException as e:
            raise ProviderError(f"Failed to create HPA: {str(e)}")