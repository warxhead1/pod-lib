"""
Mock network backing classes
"""
from .base import MockVSphereObject


class MockVirtualEthernetCardNetworkBackingInfo(MockVSphereObject):
    """Mock network backing for standard vSwitch"""
    
    def __init__(self, network_name: str = "VM Network"):
        super().__init__()
        self._properties.update({
            'network': MockNetworkReference(network_name),
            'deviceName': network_name,
            'useAutoDetect': False,
            'inPassthroughMode': False
        })


class MockNetworkReference(MockVSphereObject):
    """Mock network reference"""
    
    def __init__(self, name: str):
        super().__init__()
        self._properties.update({
            'name': name,
            'type': 'Network'
        })


class MockVirtualEthernetCardDistributedVirtualPortBackingInfo(MockVSphereObject):
    """Mock DVS port backing"""
    
    def __init__(self, portgroup_key: str = "dvportgroup-123", switch_uuid: str = "dvs-uuid-123"):
        super().__init__()
        self._properties.update({
            'port': MockDistributedVirtualSwitchPortConnection(portgroup_key, switch_uuid)
        })


class MockDistributedVirtualSwitchPortConnection(MockVSphereObject):
    """Mock DVS port connection"""
    
    def __init__(self, portgroup_key: str, switch_uuid: str):
        super().__init__()
        self._properties.update({
            'switchUuid': switch_uuid,
            'portgroupKey': portgroup_key,
            'portKey': None,
            'connectionCookie': None
        })