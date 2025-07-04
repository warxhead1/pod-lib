"""
Mock inventory classes
"""
from .base import MockVSphereObject
from typing import List


class MockFolder(MockVSphereObject):
    """Mock folder object"""
    
    def __init__(self, name: str):
        super().__init__()
        self._properties.update({
            'name': name,
            'childEntity': [],
            'childType': []
        })
    
    def add_child(self, child: MockVSphereObject) -> None:
        """Add child entity to folder"""
        super().add_child(child)
        if hasattr(self, '_properties') and 'childEntity' in self._properties:
            self._properties['childEntity'].append(child)


class MockDatacenter(MockVSphereObject):
    """Mock datacenter object"""
    
    def __init__(self, name: str):
        super().__init__()
        self._properties.update({
            'name': name,
            'vmFolder': MockFolder("vm"),
            'hostFolder': MockFolder("host"),
            'networkFolder': MockFolder("network"),
            'datastoreFolder': MockFolder("datastore")
        })


class MockClusterComputeResource(MockVSphereObject):
    """Mock cluster compute resource"""
    
    def __init__(self, name: str):
        super().__init__()
        self._properties.update({
            'name': name,
            'host': [],
            'resourcePool': MockResourcePool(),
            'summary': MockClusterComputeResourceSummary(),
            'configuration': MockClusterConfigInfo()
        })


class MockResourcePool(MockVSphereObject):
    """Mock resource pool"""
    
    def __init__(self):
        super().__init__()
        self._properties.update({
            'name': 'Resources',
            'resourcePool': [],
            'vm': []
        })


class MockClusterComputeResourceSummary(MockVSphereObject):
    """Mock cluster summary"""
    
    def __init__(self):
        super().__init__()
        self._properties.update({
            'numHosts': 3,
            'numCpuCores': 24,
            'totalCpu': 48000,
            'totalMemory': 137438953472,  # 128GB
            'numVmsInCluster': 10,
            'currentBalance': 100,
            'targetBalance': 100
        })


class MockClusterConfigInfo(MockVSphereObject):
    """Mock cluster configuration"""
    
    def __init__(self):
        super().__init__()
        self._properties.update({
            'dasConfig': MockClusterDasConfigInfo(),
            'drsConfig': MockClusterDrsConfigInfo()
        })


class MockClusterDasConfigInfo(MockVSphereObject):
    """Mock cluster DAS configuration"""
    
    def __init__(self):
        super().__init__()
        self._properties.update({
            'enabled': True,
            'failoverLevel': 1,
            'admissionControlEnabled': True
        })


class MockClusterDrsConfigInfo(MockVSphereObject):
    """Mock cluster DRS configuration"""
    
    def __init__(self):
        super().__init__()
        self._properties.update({
            'enabled': True,
            'vmotionRate': 3,
            'defaultVmBehavior': 'fullyAutomated'
        })