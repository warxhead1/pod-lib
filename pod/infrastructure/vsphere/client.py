"""
vSphere Client wrapper for VM management
"""

import ssl
import atexit
from typing import Optional, Dict, Any, List
from pyVim import connect
from pyVmomi import vim, vmodl
from ...exceptions import ConnectionError, VMNotFoundError, AuthenticationError


class VSphereClient:
    """vSphere API client for VM operations"""
    
    def __init__(self, host: str, username: str, password: str, port: int = 443, 
                 disable_ssl_verification: bool = False):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.disable_ssl_verification = disable_ssl_verification
        self._service_instance = None
        self._content = None
        
    def connect(self) -> None:
        """Establish connection to vSphere"""
        try:
            context = None
            if self.disable_ssl_verification:
                # Lab environments may need unverified SSL context
                context = ssl._create_unverified_context()  # nosec B323
                
            self._service_instance = connect.SmartConnect(
                host=self.host,
                user=self.username,
                pwd=self.password,
                port=self.port,
                sslContext=context
            )
            
            atexit.register(connect.Disconnect, self._service_instance)
            self._content = self._service_instance.RetrieveContent()
            
        except vim.fault.InvalidLogin:
            raise AuthenticationError(f"Failed to authenticate to vSphere {self.host}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to vSphere: {str(e)}")
    
    def disconnect(self) -> None:
        """Disconnect from vSphere"""
        if self._service_instance:
            connect.Disconnect(self._service_instance)
            self._service_instance = None
            self._content = None
    
    @property
    def content(self):
        """Get vSphere content object"""
        if not self._content:
            raise ConnectionError("Not connected to vSphere")
        return self._content
    
    def get_obj(self, vimtype: List, name: str) -> Optional[Any]:
        """Get vSphere object by name"""
        obj = None
        container = self.content.viewManager.CreateContainerView(
            self.content.rootFolder, vimtype, True)
        
        for c in container.view:
            if c.name == name:
                obj = c
                break
                
        container.Destroy()
        return obj
    
    def get_vm(self, vm_name: str) -> vim.VirtualMachine:
        """Get VM object by name"""
        vm = self.get_obj([vim.VirtualMachine], vm_name)
        if not vm:
            raise VMNotFoundError(f"VM '{vm_name}' not found")
        return vm
    
    def get_all_vms(self) -> List[vim.VirtualMachine]:
        """Get all VMs in vSphere"""
        container = self.content.viewManager.CreateContainerView(
            self.content.rootFolder, [vim.VirtualMachine], True)
        vms = list(container.view)
        container.Destroy()
        return vms
    
    def get_network(self, network_name: str) -> vim.Network:
        """Get network object by name"""
        network = self.get_obj([vim.Network], network_name)
        if not network:
            raise VMNotFoundError(f"Network '{network_name}' not found")
        return network
    
    def get_datacenter(self, datacenter_name: Optional[str] = None) -> vim.Datacenter:
        """Get datacenter object"""
        if datacenter_name:
            dc = self.get_obj([vim.Datacenter], datacenter_name)
            if not dc:
                raise VMNotFoundError(f"Datacenter '{datacenter_name}' not found")
            return dc
        else:
            # Return first datacenter if name not specified
            container = self.content.viewManager.CreateContainerView(
                self.content.rootFolder, [vim.Datacenter], True)
            if container.view:
                dc = container.view[0]
                container.Destroy()
                return dc
            container.Destroy()
            raise VMNotFoundError("No datacenters found")
    
    def wait_for_task(self, task: vim.Task) -> bool:
        """Wait for vSphere task to complete"""
        while task.info.state not in [vim.TaskInfo.State.success, 
                                      vim.TaskInfo.State.error]:
            pass
            
        if task.info.state == vim.TaskInfo.State.error:
            raise Exception(f"Task failed: {task.info.error}")
            
        return True