"""
Mock network classes
"""
from unittest.mock import Mock
from pyVmomi import vim
from .base import MockVSphereObject


def create_mock_network(name: str = "VM Network"):
    """Create a mock network that passes vim.Network type checks"""
    mock_network = Mock(spec=vim.Network)
    mock_network.name = name
    mock_network.key = f'network-{hash(name) % 1000000:06d}'
    mock_network.summary = Mock()
    mock_network.summary.name = name
    mock_network.summary.accessible = True
    return mock_network


class MockNetwork(MockVSphereObject):
    """Mock standard network"""
    
    def __init__(self, name: str = "VM Network"):
        super().__init__()
        self._properties.update({
            'name': name,
            'key': f'network-{hash(name) % 1000000:06d}',
            'summary': MockNetworkSummary(name)
        })
        
    @classmethod  
    def create_typed_mock(cls, name: str = "VM Network"):
        """Create a mock that passes vim.Network type checks"""
        return create_mock_network(name)
        


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


def create_mock_dvs_portgroup(name: str = "DVS-PG-1", switch_uuid: str = "dvs-uuid-123"):
    """Create a mock DVS portgroup that passes vim.dvs.DistributedVirtualPortgroup type checks"""
    mock_portgroup = Mock(spec=vim.dvs.DistributedVirtualPortgroup)
    mock_portgroup.name = name
    mock_portgroup.key = f'dvportgroup-{hash(name) % 1000000:06d}'
    
    # Mock config
    mock_config = Mock()
    mock_config.name = name
    mock_config.key = mock_portgroup.key
    mock_config.distributedVirtualSwitch = Mock()
    mock_config.distributedVirtualSwitch.uuid = switch_uuid
    mock_portgroup.config = mock_config
    
    # Mock summary
    mock_summary = Mock()
    mock_summary.name = name
    mock_portgroup.summary = mock_summary
    
    return mock_portgroup


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
        
    @classmethod
    def create_typed_mock(cls, name: str = "DVS-PG-1", switch_uuid: str = "dvs-uuid-123"):
        """Create a mock that passes vim.dvs.DistributedVirtualPortgroup type checks"""
        return create_mock_dvs_portgroup(name, switch_uuid)
        


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