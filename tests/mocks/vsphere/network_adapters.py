"""
Mock network adapter classes
"""
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


class MockVirtualVmxnet3(MockVirtualEthernetCard):
    """Mock VMware vmxnet3 adapter"""
    
    def __init__(self, key: int, device_info_label: str = "Network adapter 1"):
        super().__init__(key, device_info_label)
        self._properties['deviceInfo'].summary = "VM Network"


class MockVirtualE1000(MockVirtualEthernetCard):
    """Mock Intel E1000 adapter"""
    
    def __init__(self, key: int, device_info_label: str = "Network adapter 1"):
        super().__init__(key, device_info_label)
        self._properties['deviceInfo'].summary = "VM Network"


class MockVirtualE1000e(MockVirtualEthernetCard):
    """Mock Intel E1000e adapter"""
    
    def __init__(self, key: int, device_info_label: str = "Network adapter 1"):
        super().__init__(key, device_info_label)
        self._properties['deviceInfo'].summary = "VM Network"