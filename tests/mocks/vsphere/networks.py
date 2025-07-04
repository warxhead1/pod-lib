"""
Mock network classes
"""
from .base import MockVSphereObject


class MockNetwork(MockVSphereObject):
    """Mock standard network"""
    
    def __init__(self, name: str = "VM Network"):
        super().__init__()
        self._properties.update({
            'name': name,
            'key': f'network-{hash(name) % 1000000:06d}',
            'summary': MockNetworkSummary(name)
        })
        


class MockNetworkSummary(MockVSphereObject):
    """Mock network summary"""
    
    def __init__(self, name: str):
        super().__init__()
        self._properties.update({
            'name': name,
            'network': None,  # Reference back to network
            'accessible': True,
            'ipPoolName': None,
            'ipPoolId': None
        })


class MockDistributedVirtualPortgroup(MockVSphereObject):
    """Mock DVS portgroup"""
    
    def __init__(self, name: str = "DVS-PG-1", switch_uuid: str = "dvs-uuid-123"):
        super().__init__()
        self._properties.update({
            'name': name,
            'key': f'dvportgroup-{hash(name) % 1000000:06d}',
            'config': MockDVPortgroupConfig(name, switch_uuid),
            'summary': MockDVPortgroupSummary(name)
        })
        


class MockDVPortgroupConfig(MockVSphereObject):
    """Mock DVS portgroup config"""
    
    def __init__(self, name: str, switch_uuid: str):
        super().__init__()
        self._properties.update({
            'name': name,
            'key': f'dvportgroup-{hash(name) % 1000000:06d}',
            'distributedVirtualSwitch': MockDVSwitch(switch_uuid),
            'numPorts': 128,
            'portNameFormat': 'Port {portIndex}',
            'type': 'earlyBinding'
        })


class MockDVSwitch(MockVSphereObject):
    """Mock DVS switch"""
    
    def __init__(self, uuid: str):
        super().__init__()
        self._properties.update({
            'uuid': uuid,
            'name': f'DVS-{uuid[-8:]}',
            'summary': MockDVSwitchSummary(uuid)
        })


class MockDVSwitchSummary(MockVSphereObject):
    """Mock DVS switch summary"""
    
    def __init__(self, uuid: str):
        super().__init__()
        self._properties.update({
            'name': f'DVS-{uuid[-8:]}',
            'uuid': uuid,
            'numPorts': 256,
            'productInfo': MockDVSProductSpec()
        })


class MockDVSProductSpec(MockVSphereObject):
    """Mock DVS product spec"""
    
    def __init__(self):
        super().__init__()
        self._properties.update({
            'name': 'VMware vSphere Distributed Switch',
            'vendor': 'VMware, Inc.',
            'version': '7.0.0'
        })


class MockDVPortgroupSummary(MockVSphereObject):
    """Mock DVS portgroup summary"""
    
    def __init__(self, name: str):
        super().__init__()
        self._properties.update({
            'name': name,
            'numPorts': 128
        })