"""
Mock device specification classes
"""
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


class MockVirtualDeviceSpecOperation:
    """Mock device spec operation constants"""
    add = "add"
    edit = "edit" 
    remove = "remove"