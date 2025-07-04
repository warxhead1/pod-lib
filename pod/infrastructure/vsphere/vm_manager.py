"""
VM lifecycle management for vSphere
"""

import time
from typing import Dict, Any, Optional, List
from pyVmomi import vim
from .client import VSphereClient
from ...exceptions import VMNotFoundError, OSError


class VMManager:
    """Manages VM lifecycle operations"""
    
    def __init__(self, vsphere_client: VSphereClient):
        self.client = vsphere_client
        
    def get_vm_info(self, vm_name: str) -> Dict[str, Any]:
        """Get detailed VM information"""
        vm = self.client.get_vm(vm_name)
        
        # Get guest info
        guest_info = {
            'os_type': self._detect_os_type(vm),
            'hostname': vm.guest.hostName,
            'ip_address': vm.guest.ipAddress,
            'tools_status': vm.guest.toolsStatus,
            'tools_version': vm.guest.toolsVersion,
        }
        
        # Get hardware info
        hardware_info = {
            'cpu_count': vm.config.hardware.numCPU,
            'memory_mb': vm.config.hardware.memoryMB,
            'disks': self._get_disk_info(vm),
            'networks': self._get_network_info(vm),
        }
        
        # Get power state
        power_state = vm.runtime.powerState
        
        return {
            'name': vm.name,
            'uuid': vm.config.uuid,
            'power_state': power_state,
            'guest': guest_info,
            'hardware': hardware_info,
            'path': vm.config.files.vmPathName,
        }
    
    def power_on(self, vm_name: str, wait_for_ip: bool = True) -> bool:
        """Power on VM"""
        vm = self.client.get_vm(vm_name)
        
        if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOn:
            return True
            
        task = vm.PowerOnVM_Task()
        self.client.wait_for_task(task)
        
        if wait_for_ip:
            self._wait_for_ip(vm)
            
        return True
    
    def power_off(self, vm_name: str, force: bool = False) -> bool:
        """Power off VM"""
        vm = self.client.get_vm(vm_name)
        
        if vm.runtime.powerState == vim.VirtualMachinePowerState.poweredOff:
            return True
            
        if force or vm.guest.toolsStatus != vim.VirtualMachineToolsStatus.toolsOk:
            task = vm.PowerOffVM_Task()
            self.client.wait_for_task(task)
        else:
            # Try graceful shutdown first
            try:
                vm.ShutdownGuest()
                # Wait for shutdown
                timeout = 60
                start_time = time.time()
                while vm.runtime.powerState != vim.VirtualMachinePowerState.poweredOff:
                    if time.time() - start_time > timeout:
                        # Force power off after timeout
                        task = vm.PowerOffVM_Task()
                        self.client.wait_for_task(task)
                        break
                    time.sleep(1)
            except Exception:
                # Fallback to force power off
                task = vm.PowerOffVM_Task()
                self.client.wait_for_task(task)
                
        return True
    
    def restart(self, vm_name: str, wait_for_ip: bool = True) -> bool:
        """Restart VM"""
        vm = self.client.get_vm(vm_name)
        
        if vm.runtime.powerState != vim.VirtualMachinePowerState.poweredOn:
            return self.power_on(vm_name, wait_for_ip)
            
        if vm.guest.toolsStatus == vim.VirtualMachineToolsStatus.toolsOk:
            vm.RebootGuest()
        else:
            task = vm.ResetVM_Task()
            self.client.wait_for_task(task)
            
        if wait_for_ip:
            # Wait for VM to come back up
            time.sleep(10)  # Give it time to actually restart
            self._wait_for_ip(vm)
            
        return True
    
    def clone_vm(self, source_vm_name: str, new_vm_name: str, 
                 datacenter_name: Optional[str] = None,
                 folder_path: Optional[str] = None,
                 resource_pool_name: Optional[str] = None,
                 datastore_name: Optional[str] = None) -> vim.VirtualMachine:
        """Clone a VM"""
        source_vm = self.client.get_vm(source_vm_name)
        datacenter = self.client.get_datacenter(datacenter_name)
        
        # Get destination folder
        if folder_path:
            dest_folder = self._get_folder_by_path(datacenter, folder_path)
        else:
            dest_folder = datacenter.vmFolder
            
        # Get resource pool
        if resource_pool_name:
            resource_pool = self.client.get_obj([vim.ResourcePool], resource_pool_name)
        else:
            resource_pool = self._get_default_resource_pool(datacenter)
            
        # Clone spec
        relocate_spec = vim.vm.RelocateSpec()
        relocate_spec.pool = resource_pool
        
        if datastore_name:
            datastore = self.client.get_obj([vim.Datastore], datastore_name)
            relocate_spec.datastore = datastore
            
        clone_spec = vim.vm.CloneSpec()
        clone_spec.location = relocate_spec
        clone_spec.powerOn = False
        
        task = source_vm.Clone(
            folder=dest_folder,
            name=new_vm_name,
            spec=clone_spec
        )
        
        self.client.wait_for_task(task)
        return self.client.get_vm(new_vm_name)
    
    def delete_vm(self, vm_name: str) -> bool:
        """Delete VM"""
        vm = self.client.get_vm(vm_name)
        
        # Power off first if needed
        if vm.runtime.powerState != vim.VirtualMachinePowerState.poweredOff:
            self.power_off(vm_name, force=True)
            
        task = vm.Destroy_Task()
        self.client.wait_for_task(task)
        return True
    
    def _detect_os_type(self, vm: vim.VirtualMachine) -> str:
        """Detect OS type from VM"""
        guest_id = vm.config.guestId.lower()
        guest_family = vm.guest.guestFamily
        
        if 'windows' in guest_id or guest_family == 'windowsGuest':
            return 'windows'
        elif 'linux' in guest_id or guest_family == 'linuxGuest':
            # Check if it's a container
            if self._is_container(vm):
                return 'container'
            return 'linux'
        else:
            return 'unknown'
    
    def _is_container(self, vm: vim.VirtualMachine) -> bool:
        """Check if VM is actually a container"""
        # This is a simplified check - in practice you might check annotations
        # or custom attributes to identify containers
        return 'container' in vm.name.lower() or 'docker' in vm.name.lower()
    
    def _get_disk_info(self, vm: vim.VirtualMachine) -> List[Dict[str, Any]]:
        """Get disk information for VM"""
        disks = []
        for device in vm.config.hardware.device:
            if isinstance(device, vim.vm.device.VirtualDisk):
                disks.append({
                    'label': device.deviceInfo.label,
                    'capacity_gb': device.capacityInKB / 1024 / 1024,
                    'thin_provisioned': device.backing.thinProvisioned if hasattr(device.backing, 'thinProvisioned') else False,
                })
        return disks
    
    def _get_network_info(self, vm: vim.VirtualMachine) -> List[Dict[str, Any]]:
        """Get network adapter information"""
        networks = []
        for device in vm.config.hardware.device:
            if isinstance(device, vim.vm.device.VirtualEthernetCard):
                network_name = 'Unknown'
                if hasattr(device.backing, 'network'):
                    network_name = device.backing.network.name
                elif hasattr(device.backing, 'port'):
                    network_name = device.backing.port.portgroupKey
                    
                networks.append({
                    'label': device.deviceInfo.label,
                    'network': network_name,
                    'mac_address': device.macAddress,
                    'connected': device.connectable.connected,
                    'type': type(device).__name__,
                })
        return networks
    
    def _wait_for_ip(self, vm: vim.VirtualMachine, timeout: int = 300) -> str:
        """Wait for VM to get an IP address"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if vm.guest.ipAddress:
                return vm.guest.ipAddress
            time.sleep(2)
            
        raise OSError(f"Timeout waiting for IP address on VM {vm.name}")
    
    def _get_folder_by_path(self, datacenter: vim.Datacenter, path: str) -> vim.Folder:
        """Get folder by path"""
        # Simple implementation - in practice this would handle nested paths
        folders = path.split('/')
        current_folder = datacenter.vmFolder
        
        for folder_name in folders:
            if folder_name:
                found = False
                for child in current_folder.childEntity:
                    if isinstance(child, vim.Folder) and child.name == folder_name:
                        current_folder = child
                        found = True
                        break
                if not found:
                    raise VMNotFoundError(f"Folder '{folder_name}' not found in path '{path}'")
                    
        return current_folder
    
    def _get_default_resource_pool(self, datacenter: vim.Datacenter) -> vim.ResourcePool:
        """Get default resource pool"""
        for child in datacenter.hostFolder.childEntity:
            if isinstance(child, vim.ClusterComputeResource):
                return child.resourcePool
            elif isinstance(child, vim.ComputeResource):
                return child.resourcePool
                
        raise VMNotFoundError("No resource pool found")