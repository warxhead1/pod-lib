"""
Mock network adapter classes
"""
from unittest.mock import Mock
from pyVmomi import vim
from .base import MockVSphereObject, MockDescription, MockVirtualDeviceConnectInfo


class MockVirtualEthernetCard(MockVSphereObject):
    """Base class for network adapters"""
    
    def __init__(self, key: int, device_info_label: str = "Network adapter 1"):
        super().__init__()
        self._properties.update({
            'key': key,
            'deviceInfo': MockDescription(device_info_label),
            'backing': None,
            'connectable': MockVirtualDeviceConnectInfo(),
            'macAddress': self._generate_mac_address(key),
            'addressType': 'generated',
            'wakeOnLanEnabled': True
        })
    
    def _generate_mac_address(self, key: int) -> str:
        """Generate a fake MAC address based on key"""
        return f"00:50:56:{(key % 256):02x}:{((key >> 8) % 256):02x}:{((key >> 16) % 256):02x}"


def create_mock_vmxnet3(key: int, device_info_label: str = "Network adapter 1"):
    """Create a mock vmxnet3 adapter that passes vim.vm.device.VirtualVmxnet3 type checks"""
    mock_adapter = Mock(spec=vim.vm.device.VirtualVmxnet3)
    mock_adapter.key = key
    
    # Mock device info
    mock_device_info = Mock()
    mock_device_info.label = device_info_label
    mock_adapter.deviceInfo = mock_device_info
    
    # Mock backing
    mock_adapter.backing = None
    
    # Mock connectable
    mock_connectable = Mock()
    mock_connectable.connected = True
    mock_connectable.startConnected = True
    mock_adapter.connectable = mock_connectable
    
    # Mock MAC address
    mock_adapter.macAddress = f"00:50:56:{(key % 256):02x}:{((key >> 8) % 256):02x}:{((key >> 16) % 256):02x}"
    mock_adapter.addressType = 'generated'
    mock_adapter.wakeOnLanEnabled = True
    
    return mock_adapter


class MockVirtualVmxnet3(MockVirtualEthernetCard):
    """Mock VMware vmxnet3 adapter"""
    
    def __init__(self, key: int, device_info_label: str = "Network adapter 1"):
        super().__init__(key, device_info_label)
        
    @classmethod
    def create_typed_mock(cls, key: int, device_info_label: str = "Network adapter 1"):
        """Create a mock that passes vim.vm.device.VirtualVmxnet3 type checks"""
        return create_mock_vmxnet3(key, device_info_label)


def create_mock_e1000(key: int, device_info_label: str = "Network adapter 1"):
    """Create a mock e1000 adapter that passes vim.vm.device.VirtualE1000 type checks"""
    mock_adapter = Mock(spec=vim.vm.device.VirtualE1000)
    mock_adapter.key = key
    
    # Mock device info
    mock_device_info = Mock()
    mock_device_info.label = device_info_label
    mock_device_info.summary = "VM Network"
    mock_adapter.deviceInfo = mock_device_info
    
    # Mock backing
    mock_adapter.backing = None
    
    # Mock connectable
    mock_connectable = Mock()
    mock_connectable.connected = True
    mock_connectable.startConnected = True
    mock_adapter.connectable = mock_connectable
    
    # Mock MAC address
    mock_adapter.macAddress = f"00:50:56:{(key % 256):02x}:{((key >> 8) % 256):02x}:{((key >> 16) % 256):02x}"
    mock_adapter.addressType = 'generated'
    mock_adapter.wakeOnLanEnabled = True
    
    return mock_adapter


def create_mock_e1000e(key: int, device_info_label: str = "Network adapter 1"):
    """Create a mock e1000e adapter that passes vim.vm.device.VirtualE1000e type checks"""
    mock_adapter = Mock(spec=vim.vm.device.VirtualE1000e)
    mock_adapter.key = key
    
    # Mock device info
    mock_device_info = Mock()
    mock_device_info.label = device_info_label
    mock_device_info.summary = "VM Network"
    mock_adapter.deviceInfo = mock_device_info
    
    # Mock backing
    mock_adapter.backing = None
    
    # Mock connectable
    mock_connectable = Mock()
    mock_connectable.connected = True
    mock_connectable.startConnected = True
    mock_adapter.connectable = mock_connectable
    
    # Mock MAC address
    mock_adapter.macAddress = f"00:50:56:{(key % 256):02x}:{((key >> 8) % 256):02x}:{((key >> 16) % 256):02x}"
    mock_adapter.addressType = 'generated'
    mock_adapter.wakeOnLanEnabled = True
    
    return mock_adapter


class MockVirtualE1000(MockVirtualEthernetCard):
    """Mock Intel E1000 adapter"""
    
    def __init__(self, key: int, device_info_label: str = "Network adapter 1"):
        super().__init__(key, device_info_label)
        self._properties['deviceInfo'].summary = "VM Network"
        
    @classmethod
    def create_typed_mock(cls, key: int, device_info_label: str = "Network adapter 1"):
        """Create a mock that passes vim.vm.device.VirtualE1000 type checks"""
        return create_mock_e1000(key, device_info_label)


class MockVirtualE1000e(MockVirtualEthernetCard):
    """Mock Intel E1000e adapter"""
    
    def __init__(self, key: int, device_info_label: str = "Network adapter 1"):
        super().__init__(key, device_info_label)
        self._properties['deviceInfo'].summary = "VM Network"
        
    @classmethod
    def create_typed_mock(cls, key: int, device_info_label: str = "Network adapter 1"):
        """Create a mock that passes vim.vm.device.VirtualE1000e type checks"""
        return create_mock_e1000e(key, device_info_label)