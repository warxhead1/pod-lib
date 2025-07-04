"""
Mock Virtual Machine classes
"""
from unittest.mock import MagicMock
from .base import MockVSphereObject
from .tasks import MockTask


class MockVirtualMachine(MockVSphereObject):
    """Mock VirtualMachine object"""
    
    def __init__(self, name: str, power_state: str = "poweredOn"):
        super().__init__()
        self._properties.update({
            'name': name,
            'runtime': MockVirtualMachineRuntimeInfo(power_state),
            'config': MockVirtualMachineConfigInfo(name),
            'guest': MockVirtualMachineGuestSummary(),
            'summary': MockVirtualMachineSummary(name, power_state)
        })
        
        # Create MagicMock methods for testing flexibility
        self.PowerOnVM_Task = MagicMock()
        self.PowerOffVM_Task = MagicMock()
        self.ResetVM_Task = MagicMock()
        self.RebootGuest = MagicMock()
        self.ShutdownGuest = MagicMock()
        self.ReconfigVM_Task = MagicMock()
        self.Clone = MagicMock()
        self.Destroy_Task = MagicMock()
        
        # Set up default return values - tests can override these
        self.PowerOnVM_Task.return_value = self._power_on_vm_task()
        self.PowerOffVM_Task.return_value = self._power_off_vm_task()
        self.ResetVM_Task.return_value = self._reset_vm_task()
        self.RebootGuest.return_value = None
        self.ShutdownGuest.return_value = None  # Tests can override with side_effect
        # ReconfigVM_Task needs to take spec parameter, so use side_effect
        self.ReconfigVM_Task.side_effect = self._reconfig_vm_task
        self.Clone.side_effect = self._clone
        self.Destroy_Task.return_value = self._destroy_task()
    
    def _power_on_vm_task(self) -> MockTask:
        """Power on VM operation"""
        task = MockTask(operation="PowerOnVM")
        # Simulate state change
        self.runtime.powerState = 'poweredOn'
        task.complete_successfully()
        return task
    
    def _power_off_vm_task(self) -> MockTask:
        """Power off VM operation"""
        task = MockTask(operation="PowerOffVM")
        self.runtime.powerState = 'poweredOff'
        task.complete_successfully()
        return task
    
    def _reset_vm_task(self) -> MockTask:
        """Reset VM operation"""
        task = MockTask(operation="ResetVM")
        # Simulate reset (brief power off then on)
        self.runtime.powerState = 'poweredOn'
        task.complete_successfully()
        return task
    
    def _reboot_guest(self) -> None:
        """Reboot guest OS"""
        # Guest reboot doesn't change power state
        pass
    
    def _shutdown_guest(self) -> None:
        """Shutdown guest OS"""
        # In a real scenario, this would initiate shutdown but not immediately change state
        # The power state change would happen after some time
        # For testing, we'll allow tests to control when this happens
        pass
    
    def _reconfig_vm_task(self, spec) -> MockTask:
        """Reconfigure VM operation"""
        # If test has set a return_value, use that instead
        if hasattr(self.ReconfigVM_Task, 'return_value') and self.ReconfigVM_Task.return_value is not MagicMock.return_value:
            return self.ReconfigVM_Task.return_value
            
        task = MockTask(operation="ReconfigVM")
        # Apply configuration changes
        if hasattr(spec, 'deviceChange') and spec.deviceChange:
            for device_change in spec.deviceChange:
                if device_change.operation == 'add':
                    self.config.hardware.device.append(device_change.device)
                elif device_change.operation == 'remove':
                    self.config.hardware.device = [
                        d for d in self.config.hardware.device 
                        if d.key != device_change.device.key
                    ]
                elif device_change.operation == 'edit':
                    for i, device in enumerate(self.config.hardware.device):
                        if device.key == device_change.device.key:
                            self.config.hardware.device[i] = device_change.device
                            break
        task.complete_successfully()
        return task
    
    def _clone(self, folder, name, spec) -> MockTask:
        """Clone VM operation"""
        task = MockTask(operation="CloneVM")
        # Create cloned VM object
        cloned_vm = MockVirtualMachine(name, "poweredOff")
        task.complete_successfully(cloned_vm)
        return task
    
    def _destroy_task(self) -> MockTask:
        """Destroy VM operation"""
        task = MockTask(operation="DestroyVM")
        task.complete_successfully()
        return task


class MockVirtualMachineRuntimeInfo(MockVSphereObject):
    """Mock VM runtime information"""
    
    def __init__(self, power_state: str):
        super().__init__()
        self._properties.update({
            'powerState': power_state,
            'toolsRunningStatus': 'guestToolsRunning',
            'bootTime': '2023-01-01T00:00:00Z',
            'host': None,
            'maxCpuUsage': 2000,
            'maxMemoryUsage': 4096
        })


class MockVirtualMachineConfigInfo(MockVSphereObject):
    """Mock VM configuration information"""
    
    def __init__(self, name: str):
        super().__init__()
        self._properties.update({
            'name': name,
            'uuid': f'vm-{hash(name) % 1000000:06d}',
            'guestId': 'rhel8_64Guest',
            'guestFullName': 'Red Hat Enterprise Linux 8 (64-bit)',
            'hardware': MockVirtualHardware(),
            'annotation': '',
            'files': MockVirtualMachineFileInfo(name)
        })


class MockVirtualMachineFileInfo(MockVSphereObject):
    """Mock VM file information"""
    
    def __init__(self, name: str):
        super().__init__()
        self._properties.update({
            'vmPathName': f'[datastore1] {name}/{name}.vmx'
        })


class MockVirtualHardware(MockVSphereObject):
    """Mock VM hardware configuration"""
    
    def __init__(self):
        super().__init__()
        self._properties.update({
            'numCPU': 2,
            'memoryMB': 4096,
            'device': []  # Will contain network adapters, disks, etc.
        })


class MockVirtualMachineGuestSummary(MockVSphereObject):
    """Mock VM guest summary"""
    
    def __init__(self):
        super().__init__()
        self._properties.update({
            'hostName': 'test-vm',
            'ipAddress': '192.168.1.100',
            'toolsStatus': 'toolsOk',
            'toolsVersion': '12345',
            'guestFamily': 'linuxGuest',
            'guestFullName': 'Red Hat Enterprise Linux 8 (64-bit)',
            'guestId': 'rhel8_64Guest'
        })


class MockVirtualMachineSummary(MockVSphereObject):
    """Mock VM summary"""
    
    def __init__(self, name: str, power_state: str):
        super().__init__()
        self._properties.update({
            'config': MockVirtualMachineSummaryConfigSummary(name),
            'runtime': MockVirtualMachineSummaryRuntimeSummary(power_state),
            'guest': MockVirtualMachineGuestSummary(),
            'storage': MockVirtualMachineStorageSummary()
        })


class MockVirtualMachineSummaryConfigSummary(MockVSphereObject):
    """Mock VM config summary"""
    
    def __init__(self, name: str):
        super().__init__()
        self._properties.update({
            'name': name,
            'uuid': f'vm-{hash(name) % 1000000:06d}',
            'numCpu': 2,
            'memorySizeMB': 4096,
            'guestId': 'rhel8_64Guest',
            'guestFullName': 'Red Hat Enterprise Linux 8 (64-bit)'
        })


class MockVirtualMachineSummaryRuntimeSummary(MockVSphereObject):
    """Mock VM runtime summary"""
    
    def __init__(self, power_state: str):
        super().__init__()
        self._properties.update({
            'powerState': power_state
        })


class MockVirtualMachineStorageSummary(MockVSphereObject):
    """Mock VM storage summary"""
    
    def __init__(self):
        super().__init__()
        self._properties.update({
            'committed': 20971520000,  # 20GB
            'uncommitted': 0,
            'unshared': 20971520000
        })