"""
Network configuration for vSphere VMs
"""

from typing import Optional, List, Dict, Any
from pyVmomi import vim
from .client import VSphereClient
from ...exceptions import NetworkConfigError


class NetworkConfigurator:
    """Configure VM network adapters and VLANs"""
    
    def __init__(self, vsphere_client: VSphereClient):
        self.client = vsphere_client
        
    def configure_vlan(self, vm_name: str, adapter_label: str, vlan_id: int, 
                      network_name: Optional[str] = None) -> bool:
        """Configure VLAN for VM network adapter"""
        vm = self.client.get_vm(vm_name)
        
        # Find the network adapter
        adapter = self._get_network_adapter(vm, adapter_label)
        if not adapter:
            raise NetworkConfigError(f"Network adapter '{adapter_label}' not found")
            
        # Create reconfigure spec
        spec = vim.vm.ConfigSpec()
        
        # Configure network backing based on type
        if network_name:
            # Use specific network/portgroup
            network = self.client.get_network(network_name)
            if isinstance(network, vim.dvs.DistributedVirtualPortgroup):
                # Distributed vSwitch
                backing = vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo()
                backing.port = vim.dvs.PortConnection()
                backing.port.portgroupKey = network.key
                backing.port.switchUuid = network.config.distributedVirtualSwitch.uuid
            else:
                # Standard vSwitch
                backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
                backing.network = network
                backing.deviceName = network.name
        else:
            # Configure VLAN ID on existing backing
            if hasattr(adapter.backing, 'port'):
                # DVS - need to find/create portgroup with VLAN
                pg_name = f"VLAN-{vlan_id}"
                try:
                    network = self.client.get_network(pg_name)
                except:
                    # Would need to create portgroup - simplified for now
                    raise NetworkConfigError(f"Portgroup for VLAN {vlan_id} not found")
                    
                backing = vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo()
                backing.port = vim.dvs.PortConnection()
                backing.port.portgroupKey = network.key
                backing.port.switchUuid = network.config.distributedVirtualSwitch.uuid
            else:
                raise NetworkConfigError("Cannot set VLAN ID without distributed vSwitch")
                
        # Create device change spec
        device_change = vim.vm.device.VirtualDeviceSpec()
        device_change.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
        device_change.device = adapter
        device_change.device.backing = backing
        
        spec.deviceChange = [device_change]
        
        # Apply configuration
        task = vm.ReconfigVM_Task(spec=spec)
        self.client.wait_for_task(task)
        
        return True
    
    def add_network_adapter(self, vm_name: str, network_name: str, 
                           adapter_type: str = 'vmxnet3') -> str:
        """Add new network adapter to VM"""
        vm = self.client.get_vm(vm_name)
        network = self.client.get_network(network_name)
        
        # Create network adapter
        if adapter_type == 'vmxnet3':
            adapter = vim.vm.device.VirtualVmxnet3()
        elif adapter_type == 'e1000':
            adapter = vim.vm.device.VirtualE1000()
        elif adapter_type == 'e1000e':
            adapter = vim.vm.device.VirtualE1000e()
        else:
            raise NetworkConfigError(f"Unknown adapter type: {adapter_type}")
            
        # Configure adapter
        adapter.deviceInfo = vim.Description()
        adapter.deviceInfo.label = f"Network adapter {self._get_next_adapter_number(vm)}"
        adapter.deviceInfo.summary = network_name
        
        # Configure backing
        if isinstance(network, vim.dvs.DistributedVirtualPortgroup):
            adapter.backing = vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo()
            adapter.backing.port = vim.dvs.PortConnection()
            adapter.backing.port.portgroupKey = network.key
            adapter.backing.port.switchUuid = network.config.distributedVirtualSwitch.uuid
        else:
            adapter.backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
            adapter.backing.network = network
            adapter.backing.deviceName = network.name
            
        # Configure connection
        adapter.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
        adapter.connectable.startConnected = True
        adapter.connectable.allowGuestControl = True
        adapter.connectable.connected = True
        
        # Create spec
        spec = vim.vm.ConfigSpec()
        device_change = vim.vm.device.VirtualDeviceSpec()
        device_change.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
        device_change.device = adapter
        spec.deviceChange = [device_change]
        
        # Apply configuration
        task = vm.ReconfigVM_Task(spec=spec)
        self.client.wait_for_task(task)
        
        return adapter.deviceInfo.label
    
    def remove_network_adapter(self, vm_name: str, adapter_label: str) -> bool:
        """Remove network adapter from VM"""
        vm = self.client.get_vm(vm_name)
        adapter = self._get_network_adapter(vm, adapter_label)
        
        if not adapter:
            raise NetworkConfigError(f"Network adapter '{adapter_label}' not found")
            
        # Create spec
        spec = vim.vm.ConfigSpec()
        device_change = vim.vm.device.VirtualDeviceSpec()
        device_change.operation = vim.vm.device.VirtualDeviceSpec.Operation.remove
        device_change.device = adapter
        spec.deviceChange = [device_change]
        
        # Apply configuration
        task = vm.ReconfigVM_Task(spec=spec)
        self.client.wait_for_task(task)
        
        return True
    
    def connect_adapter(self, vm_name: str, adapter_label: str, connected: bool = True) -> bool:
        """Connect or disconnect network adapter"""
        vm = self.client.get_vm(vm_name)
        adapter = self._get_network_adapter(vm, adapter_label)
        
        if not adapter:
            raise NetworkConfigError(f"Network adapter '{adapter_label}' not found")
            
        # Create spec
        spec = vim.vm.ConfigSpec()
        device_change = vim.vm.device.VirtualDeviceSpec()
        device_change.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
        device_change.device = adapter
        device_change.device.connectable.connected = connected
        spec.deviceChange = [device_change]
        
        # Apply configuration  
        task = vm.ReconfigVM_Task(spec=spec)
        self.client.wait_for_task(task)
        
        return True
    
    def get_network_adapters(self, vm_name: str) -> List[Dict[str, Any]]:
        """Get all network adapters for VM"""
        vm = self.client.get_vm(vm_name)
        adapters = []
        
        for device in vm.config.hardware.device:
            if isinstance(device, vim.vm.device.VirtualEthernetCard):
                network_name = 'Unknown'
                vlan_id = None
                
                if hasattr(device.backing, 'network'):
                    network_name = device.backing.network.name
                elif hasattr(device.backing, 'port'):
                    network_name = device.backing.port.portgroupKey
                    # Would need to query portgroup for VLAN ID
                    
                adapters.append({
                    'label': device.deviceInfo.label,
                    'type': type(device).__name__,
                    'network': network_name,
                    'mac_address': device.macAddress,
                    'connected': device.connectable.connected,
                    'vlan_id': vlan_id,
                    'key': device.key,
                })
                
        return adapters
    
    def _get_network_adapter(self, vm: vim.VirtualMachine, adapter_label: str) -> Optional[vim.vm.device.VirtualEthernetCard]:
        """Get network adapter by label"""
        for device in vm.config.hardware.device:
            if isinstance(device, vim.vm.device.VirtualEthernetCard):
                if device.deviceInfo.label == adapter_label:
                    return device
        return None
    
    def _get_next_adapter_number(self, vm: vim.VirtualMachine) -> int:
        """Get next available adapter number"""
        max_num = 0
        for device in vm.config.hardware.device:
            if isinstance(device, vim.vm.device.VirtualEthernetCard):
                # Extract number from label like "Network adapter 1"
                try:
                    num = int(device.deviceInfo.label.split()[-1])
                    max_num = max(max_num, num)
                except (ValueError, AttributeError, IndexError):
                    # Device label may not have expected format or be None
                    continue
        return max_num + 1