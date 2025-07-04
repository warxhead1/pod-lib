"""
Mock device specification classes
"""
from unittest.mock import Mock
from pyVmomi import vim
from .base import MockVSphereObject


class MockVirtualDeviceSpec(MockVSphereObject):
    """Mock device specification"""
    
    def __init__(self, operation="add", device=None):
        super().__init__()
        self._properties.update({
            'operation': operation,
            'device': device,
            'fileOperation': None,
            'profile': []
        })


class MockVirtualMachineConfigSpec(MockVSphereObject):
    """Mock VM configuration specification"""
    
    def __init__(self):
        super().__init__()
        self._properties.update({
            'name': None,
            'annotation': None,
            'deviceChange': [],
            'files': None,
            'tools': None,
            'flags': None,
            'powerOpInfo': None,
            'numCPUs': None,
            'memoryMB': None
        })


def create_mock_virtual_disk(label: str = "Hard disk 1", capacity_kb: int = 20971520, thin_provisioned: bool = True):
    """Create a mock virtual disk that passes vim.vm.device.VirtualDisk type checks"""
    mock_disk = Mock(spec=vim.vm.device.VirtualDisk)
    
    # Mock device info
    mock_device_info = Mock()
    mock_device_info.label = label
    mock_disk.deviceInfo = mock_device_info
    
    # Mock capacity
    mock_disk.capacityInKB = capacity_kb
    
    # Mock backing
    mock_backing = Mock()
    mock_backing.thinProvisioned = thin_provisioned
    mock_disk.backing = mock_backing
    
    return mock_disk


def create_mock_resource_pool(name: str = "Resources"):
    """Create a mock resource pool that passes vim.ResourcePool type checks"""
    mock_pool = Mock(spec=vim.ResourcePool)
    mock_pool.name = name
    mock_pool.parent = Mock()
    mock_pool.owner = Mock()
    return mock_pool


class MockVirtualDeviceSpecOperation:
    """Mock device spec operation constants"""
    add = "add"
    edit = "edit" 
    remove = "remove"