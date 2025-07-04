"""
Kubernetes connection handler with modern client libraries
"""

import os
import yaml
import asyncio
from typing import Dict, Any, Optional, List, Union, Tuple
from pathlib import Path
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from kubernetes_asyncio import client as async_client, config as async_config
from .base import BaseConnection
from ..exceptions import ConnectionError, AuthenticationError


class KubernetesConnection(BaseConnection):
    """Modern Kubernetes connection handler with sync/async support"""
    
    def __init__(self, 
                 kubeconfig_path: Optional[str] = None,
                 context: Optional[str] = None,
                 namespace: str = "default",
                 api_server: Optional[str] = None,
                 token: Optional[str] = None,
                 ca_cert_path: Optional[str] = None,
                 verify_ssl: bool = True,
                 timeout: int = 300):
        """
        Initialize Kubernetes connection
        
        Args:
            kubeconfig_path: Path to kubeconfig file (defaults to ~/.kube/config)
            context: Kubernetes context to use
            namespace: Default namespace for operations
            api_server: Direct API server URL (alternative to kubeconfig)
            token: Service account token (for direct API access)
            ca_cert_path: CA certificate path (for direct API access)
            verify_ssl: Verify SSL certificates
            timeout: Connection timeout in seconds
        """
        super().__init__(
            host=api_server or "kubernetes-cluster", 
            username="kubernetes-user",  # Not used in K8s auth but required by base
            timeout=timeout
        )
        
        self.kubeconfig_path = kubeconfig_path or os.path.expanduser("~/.kube/config")
        self.context = context
        self.namespace = namespace
        self.api_server = api_server
        self.token = token
        self.ca_cert_path = ca_cert_path
        self.verify_ssl = verify_ssl
        
        # Client instances
        self.v1 = None  # Core API
        self.apps_v1 = None  # Apps API (Deployments, etc.)
        self.networking_v1 = None  # Networking API (NetworkPolicies)
        self.custom_objects_v1 = None  # Custom Resources
        
        # Async client instances
        self.async_v1 = None
        self.async_apps_v1 = None
        self.async_networking_v1 = None
        self.async_custom_objects_v1 = None
        
        self._connected = False
        self._cluster_info = {}
    
    @property
    def default_port(self) -> int:
        """Return default Kubernetes API port"""
        return 6443
    
    def connect(self, **kwargs) -> None:
        """Establish connection to Kubernetes cluster"""
        try:
            if self.api_server and self.token:
                # Direct API server connection
                self._connect_direct()
            else:
                # Kubeconfig-based connection
                self._connect_kubeconfig()
            
            # Initialize client instances
            self._initialize_clients()
            
            # Verify connection by getting cluster info
            self._verify_connection()
            
            self._connected = True
            
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Kubernetes cluster: {str(e)}")
    
    def _connect_direct(self) -> None:
        """Connect using direct API server credentials"""
        configuration = client.Configuration()
        configuration.host = self.api_server
        configuration.api_key = {"authorization": f"Bearer {self.token}"}
        configuration.verify_ssl = self.verify_ssl
        
        if self.ca_cert_path:
            configuration.ssl_ca_cert = self.ca_cert_path
        
        client.Configuration.set_default(configuration)
    
    def _connect_kubeconfig(self) -> None:
        """Connect using kubeconfig file"""
        if not Path(self.kubeconfig_path).exists():
            raise ConnectionError(f"Kubeconfig file not found: {self.kubeconfig_path}")
        
        try:
            config.load_kube_config(
                config_file=self.kubeconfig_path,
                context=self.context
            )
        except Exception as e:
            # Try in-cluster config as fallback
            try:
                config.load_incluster_config()
            except Exception:
                raise ConnectionError(f"Failed to load kubeconfig: {str(e)}")
    
    def _initialize_clients(self) -> None:
        """Initialize all Kubernetes API clients"""
        self.v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
        self.networking_v1 = client.NetworkingV1Api()
        self.custom_objects_v1 = client.CustomObjectsApi()
    
    async def _initialize_async_clients(self) -> None:
        """Initialize async Kubernetes API clients"""
        if self.api_server and self.token:
            await self._connect_async_direct()
        else:
            await self._connect_async_kubeconfig()
        
        self.async_v1 = async_client.CoreV1Api()
        self.async_apps_v1 = async_client.AppsV1Api()
        self.async_networking_v1 = async_client.NetworkingV1Api()
        self.async_custom_objects_v1 = async_client.CustomObjectsApi()
    
    async def _connect_async_direct(self) -> None:
        """Connect async client using direct API server credentials"""
        configuration = async_client.Configuration()
        configuration.host = self.api_server
        configuration.api_key = {"authorization": f"Bearer {self.token}"}
        configuration.verify_ssl = self.verify_ssl
        
        if self.ca_cert_path:
            configuration.ssl_ca_cert = self.ca_cert_path
        
        async_client.Configuration.set_default(configuration)
    
    async def _connect_async_kubeconfig(self) -> None:
        """Connect async client using kubeconfig file"""
        try:
            await async_config.load_kube_config(
                config_file=self.kubeconfig_path,
                context=self.context
            )
        except Exception as e:
            try:
                await async_config.load_incluster_config()
            except Exception:
                raise ConnectionError(f"Failed to load async kubeconfig: {str(e)}")
    
    def _verify_connection(self) -> None:
        """Verify connection by fetching cluster information"""
        try:
            # Get cluster version
            version_info = self.v1.get_code()
            
            # Get node information
            nodes = self.v1.list_node()
            
            self._cluster_info = {
                'version': f"{version_info.major}.{version_info.minor}",
                'git_version': version_info.git_version,
                'platform': version_info.platform,
                'node_count': len(nodes.items),
                'nodes': [node.metadata.name for node in nodes.items]
            }
            
        except ApiException as e:
            if e.status == 401:
                raise AuthenticationError("Kubernetes authentication failed")
            raise ConnectionError(f"Failed to verify Kubernetes connection: {str(e)}")
    
    def disconnect(self) -> None:
        """Disconnect from Kubernetes cluster"""
        self.v1 = None
        self.apps_v1 = None
        self.networking_v1 = None
        self.custom_objects_v1 = None
        
        self.async_v1 = None
        self.async_apps_v1 = None
        self.async_networking_v1 = None
        self.async_custom_objects_v1 = None
        
        self._connected = False
        self._cluster_info = {}
    
    def is_connected(self) -> bool:
        """Check if connection is active"""
        if not self._connected or not self.v1:
            return False
        
        try:
            # Quick health check
            self.v1.list_namespace(limit=1)
            return True
        except Exception:
            return False
    
    def execute_command(self, command: str, **kwargs) -> Tuple[str, str, int]:
        """
        Execute command in a pod (requires pod name and optional container)
        
        Args:
            command: Command to execute
            pod_name: Name of the pod (from kwargs)
            container: Container name (optional, from kwargs)
            namespace: Namespace (optional, from kwargs)
        
        Returns:
            Tuple of (stdout, stderr, exit_code)
        """
        pod_name = kwargs.get('pod_name')
        container = kwargs.get('container')
        namespace = kwargs.get('namespace', self.namespace)
        
        if not pod_name:
            raise ValueError("pod_name is required for Kubernetes command execution")
        
        try:
            from kubernetes.stream import stream
            
            exec_command = ['/bin/sh', '-c', command]
            
            resp = stream(
                self.v1.connect_get_namespaced_pod_exec,
                pod_name,
                namespace,
                command=exec_command,
                container=container,
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
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
            
            # Kubernetes doesn't provide exit code directly
            # We'll return 0 for successful execution, 1 for errors
            exit_code = 1 if stderr else 0
            
            return stdout, stderr, exit_code
            
        except ApiException as e:
            return "", f"Kubernetes API error: {str(e)}", 1
        except Exception as e:
            return "", f"Command execution error: {str(e)}", 1
    
    async def execute_command_async(self, command: str, **kwargs) -> Tuple[str, str, int]:
        """Async version of execute_command"""
        if not self.async_v1:
            await self._initialize_async_clients()
        
        pod_name = kwargs.get('pod_name')
        container = kwargs.get('container')
        namespace = kwargs.get('namespace', self.namespace)
        
        if not pod_name:
            raise ValueError("pod_name is required for Kubernetes command execution")
        
        # Implementation would use kubernetes-asyncio stream
        # For now, we'll run the sync version in an executor
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.execute_command, command, **kwargs)
    
    def upload_file(self, local_path: str, remote_path: str, **kwargs) -> bool:
        """
        Upload file to a pod
        
        Args:
            local_path: Local file path
            remote_path: Remote file path in pod
            pod_name: Name of the pod (from kwargs)
            container: Container name (optional, from kwargs)
            namespace: Namespace (optional, from kwargs)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Read local file
            with open(local_path, 'rb') as f:
                file_content = f.read()
            
            # Use kubectl cp equivalent via API
            # This is a simplified implementation
            import base64
            encoded_content = base64.b64encode(file_content).decode('utf-8')
            
            command = f"echo '{encoded_content}' | base64 -d > {remote_path}"
            stdout, stderr, exit_code = self.execute_command(command, **kwargs)
            
            return exit_code == 0
            
        except Exception:
            return False
    
    def download_file(self, remote_path: str, local_path: str, **kwargs) -> bool:
        """
        Download file from a pod
        
        Args:
            remote_path: Remote file path in pod
            local_path: Local file path
            pod_name: Name of the pod (from kwargs)
            container: Container name (optional, from kwargs)
            namespace: Namespace (optional, from kwargs)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            import base64
            
            # Read file from pod and encode it
            command = f"base64 {remote_path}"
            stdout, stderr, exit_code = self.execute_command(command, **kwargs)
            
            if exit_code != 0:
                return False
            
            # Decode and save locally
            file_content = base64.b64decode(stdout.strip())
            with open(local_path, 'wb') as f:
                f.write(file_content)
            
            return True
            
        except Exception:
            return False
    
    def get_cluster_info(self) -> Dict[str, Any]:
        """Get cluster information"""
        return self._cluster_info.copy()
    
    def list_namespaces(self) -> List[str]:
        """List all namespaces"""
        try:
            namespaces = self.v1.list_namespace()
            return [ns.metadata.name for ns in namespaces.items]
        except ApiException:
            return []
    
    def list_pods(self, namespace: Optional[str] = None, label_selector: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List pods in namespace
        
        Args:
            namespace: Namespace to list pods from (defaults to connection default)
            label_selector: Kubernetes label selector string
        
        Returns:
            List of pod information dictionaries
        """
        namespace = namespace or self.namespace
        
        try:
            pods = self.v1.list_namespaced_pod(
                namespace=namespace,
                label_selector=label_selector
            )
            
            return [
                {
                    'name': pod.metadata.name,
                    'namespace': pod.metadata.namespace,
                    'status': pod.status.phase,
                    'node': pod.spec.node_name,
                    'ip': pod.status.pod_ip,
                    'labels': pod.metadata.labels or {},
                    'annotations': pod.metadata.annotations or {},
                    'containers': [
                        {
                            'name': container.name,
                            'image': container.image,
                            'ready': any(
                                cs.name == container.name and cs.ready
                                for cs in pod.status.container_statuses or []
                            )
                        }
                        for container in pod.spec.containers
                    ]
                }
                for pod in pods.items
            ]
            
        except ApiException:
            return []
    
    def wait_for_reboot(self, check_interval: int = 30, max_wait_time: int = 300, **kwargs) -> bool:
        """
        Wait for pod to be ready after restart
        
        Args:
            check_interval: Seconds between checks
            max_wait_time: Maximum time to wait
            pod_name: Name of the pod (from kwargs)
            namespace: Namespace (optional, from kwargs)
        
        Returns:
            True if pod becomes ready, False if timeout
        """
        pod_name = kwargs.get('pod_name')
        namespace = kwargs.get('namespace', self.namespace)
        
        if not pod_name:
            return False
        
        import time
        
        start_time = time.time()
        while time.time() - start_time < max_wait_time:
            try:
                pod = self.v1.read_namespaced_pod(name=pod_name, namespace=namespace)
                
                # Check if pod is ready
                if pod.status.phase == 'Running':
                    # Check container readiness
                    if pod.status.container_statuses:
                        all_ready = all(cs.ready for cs in pod.status.container_statuses)
                        if all_ready:
                            return True
                
                time.sleep(check_interval)
                
            except ApiException:
                time.sleep(check_interval)
        
        return False