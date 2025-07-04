"""
vSphere mock infrastructure for testing
"""
from .base import MockVSphereObject
from .service import MockServiceInstance
from .vm import MockVirtualMachine
from .network_adapters import MockVirtualEthernetCard, MockVirtualVmxnet3, MockVirtualE1000, MockVirtualE1000e
from .network_backing import MockVirtualEthernetCardNetworkBackingInfo, MockVirtualEthernetCardDistributedVirtualPortBackingInfo
from .networks import MockNetwork, MockDistributedVirtualPortgroup
from .inventory import MockDatacenter, MockFolder
from .tasks import MockTask
from .device_specs import MockVirtualDeviceSpec, MockVirtualMachineConfigSpec

__all__ = [
    'MockVSphereObject',
    'MockServiceInstance', 
    'MockVirtualMachine',
    'MockVirtualEthernetCard',
    'MockVirtualVmxnet3',
    'MockVirtualE1000', 
    'MockVirtualE1000e',
    'MockVirtualEthernetCardNetworkBackingInfo',
    'MockVirtualEthernetCardDistributedVirtualPortBackingInfo',
    'MockNetwork',
    'MockDistributedVirtualPortgroup',
    'MockDatacenter',
    'MockFolder',
    'MockTask',
    'MockVirtualDeviceSpec',
    'MockVirtualMachineConfigSpec'
]