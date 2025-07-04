# Mock Infrastructure Implementation Plan

## Executive Summary
The failing tests expose a fundamental gap in our mock infrastructure - we need a comprehensive simulation of the vSphere API object hierarchy that mirrors real-world complexity while remaining testable. This document outlines the mock architecture and provides a detailed implementation roadmap.

## Mock Architecture Design

### Core Architectural Principles
1. **Hierarchical Object Model** - Mirror vSphere's nested object structure
2. **State Management** - Proper state transitions for VM power states, network connections
3. **Relationship Modeling** - Objects must reference each other correctly (VM→Host→Cluster→Datacenter)
4. **Behavior Simulation** - Methods must behave like real vSphere operations with proper side effects

### Mock Object Hierarchy
```
MockServiceInstance
├── MockContent
│   ├── MockRootFolder
│   │   └── MockDatacenter
│   │       ├── MockVmFolder
│   │       │   └── MockVirtualMachine[]
│   │       ├── MockHostFolder
│   │       │   └── MockClusterComputeResource[]
│   │       └── MockNetworkFolder
│   │           ├── MockNetwork[]
│   │           └── MockDistributedVirtualPortgroup[]
│   ├── MockViewManager
│   ├── MockSearchIndex
│   └── MockTaskManager
└── MockSessionManager
```

## Implementation To-Do List

### Phase 1: Core Mock Infrastructure (Priority: Critical)

#### Task 1.1: Create Base Mock Framework
**File**: `tests/mocks/vsphere_base.py`
- [ ] Create `MockVSphereObject` base class with:
  - Dynamic property access (`obj.name`, `obj.config.name`)
  - Property change tracking for state management
  - Weak reference management for object relationships
  - Event simulation for property changes

#### Task 1.2: Implement Mock Service Infrastructure
**File**: `tests/mocks/vsphere_service.py`
- [ ] Create `MockServiceInstance` class
- [ ] Implement `MockContent` with proper service managers
- [ ] Create `MockSessionManager` with authentication simulation
- [ ] Implement `MockTaskManager` for async operation simulation

#### Task 1.3: Build Mock View Management
**File**: `tests/mocks/vsphere_views.py`
- [ ] Create `MockViewManager` class
- [ ] Implement `MockContainerView` for object collection
- [ ] Create `MockSearchIndex` for find operations
- [ ] Add proper filtering and traversal logic

### Phase 2: VM Management Mock Layer (Priority: High)

#### Task 2.1: Virtual Machine Mock Implementation
**File**: `tests/mocks/vsphere_vm.py`
- [ ] Create `MockVirtualMachine` class with:
  - Power state management (`poweredOn`, `poweredOff`, `suspended`)
  - Guest OS information simulation
  - VMware Tools status simulation
  - Hardware configuration (CPU, memory, disks)
  - Network adapter collection

#### Task 2.2: VM Operations Mock
**File**: `tests/mocks/vsphere_vm_ops.py`
- [ ] Implement power operation methods:
  - `PowerOnVM_Task()` - returns MockTask, changes state
  - `PowerOffVM_Task()` - returns MockTask, changes state
  - `ResetVM_Task()` - returns MockTask, simulates restart
- [ ] Create `MockTask` class with:
  - Task state progression (`running` → `success`/`error`)
  - Progress tracking
  - Result value simulation

#### Task 2.3: VM Configuration Mock
**File**: `tests/mocks/vsphere_vm_config.py`
- [ ] Create `MockVirtualMachineConfigInfo` class
- [ ] Implement `MockVirtualMachineGuestSummary` class
- [ ] Create `MockVirtualMachineRuntimeInfo` class
- [ ] Add proper guest OS detection logic

### Phase 3: Network Configuration Mock Layer (Priority: High)

#### Task 3.1: Network Adapter Mock Infrastructure
**File**: `tests/mocks/vsphere_network_adapters.py`
- [ ] Create `MockVirtualEthernetCard` base class
- [ ] Implement specific adapter types:
  - `MockVirtualVmxnet3` class
  - `MockVirtualE1000` class  
  - `MockVirtualE1000e` class
- [ ] Add adapter configuration methods

#### Task 3.2: Network Backing Mock
**File**: `tests/mocks/vsphere_network_backing.py`
- [ ] Create `MockVirtualEthernetCardNetworkBackingInfo` class
- [ ] Implement `MockVirtualEthernetCardDistributedVirtualPortBackingInfo` class
- [ ] Create `MockDistributedVirtualSwitchPortConnection` class
- [ ] Add VLAN configuration simulation

#### Task 3.3: Network Management Mock
**File**: `tests/mocks/vsphere_networks.py`
- [ ] Create `MockNetwork` class for standard networks
- [ ] Implement `MockDistributedVirtualPortgroup` class
- [ ] Create `MockVirtualSwitch` class
- [ ] Add network discovery and configuration methods

### Phase 4: Advanced Mock Features (Priority: Medium)

#### Task 4.1: Clone Operations Mock
**File**: `tests/mocks/vsphere_clone.py`
- [ ] Create `MockVirtualMachineCloneSpec` class
- [ ] Implement `MockVirtualMachineRelocateSpec` class
- [ ] Create clone task simulation with proper state management
- [ ] Add customization spec simulation

#### Task 4.2: Inventory Management Mock
**File**: `tests/mocks/vsphere_inventory.py`
- [ ] Create `MockFolder` class with child object management
- [ ] Implement `MockDatacenter` class
- [ ] Create `MockClusterComputeResource` class
- [ ] Add inventory traversal and search methods

#### Task 4.3: Error Simulation Mock
**File**: `tests/mocks/vsphere_exceptions.py`
- [ ] Create mock exception classes matching pyVmomi exceptions
- [ ] Implement error condition simulation
- [ ] Add timeout and connection failure simulation
- [ ] Create authentication error simulation

### Phase 5: Test Factory Integration (Priority: Medium)

#### Task 5.1: Mock Factory Classes
**File**: `tests/mocks/factories.py`
- [ ] Create `MockVSphereEnvironmentFactory` class
- [ ] Implement scenario-based factory methods:
  - `create_test_datacenter()`
  - `create_test_vm_with_network()`
  - `create_test_cluster()`
- [ ] Add factory configuration options

#### Task 5.2: Test Fixture Updates
**File**: `tests/conftest.py`
- [ ] Update existing fixtures to use new mock infrastructure
- [ ] Create comprehensive test environment fixtures
- [ ] Add fixture parameterization for different scenarios
- [ ] Implement fixture cleanup and state reset

#### Task 5.3: Test Migration
**Files**: `tests/unit/test_*.py`
- [ ] Update network configuration tests to use new mocks
- [ ] Update VM manager tests to use new mocks
- [ ] Update vSphere client tests to use new mocks
- [ ] Add proper mock assertions and state verification

### Phase 6: Validation & Documentation (Priority: Low)

#### Task 6.1: Mock Validation
**File**: `tests/mocks/validation.py`
- [ ] Create mock behavior validation tests
- [ ] Implement real vs mock API comparison utilities
- [ ] Add mock coverage analysis tools
- [ ] Create mock performance benchmarks

#### Task 6.2: Documentation & Examples
**File**: `tests/mocks/README.md`
- [ ] Document mock architecture and usage patterns
- [ ] Create example test scenarios
- [ ] Add troubleshooting guide for common mock issues
- [ ] Document mock limitations and real API differences

## Implementation Guidelines

### Mock Object Design Patterns
1. **Property Simulation**: Use `__getattr__` for dynamic property access
2. **State Consistency**: Maintain object state consistency across operations
3. **Relationship Management**: Use weak references to avoid circular dependencies
4. **Error Injection**: Support controlled error injection for negative testing

### Example Mock Structure
```python
class MockVirtualMachine(MockVSphereObject):
    def __init__(self, name, power_state="poweredOn"):
        super().__init__()
        self._properties.update({
            'name': name,
            'runtime.powerState': power_state,
            'config.guestId': 'ubuntu64Guest',
            'config.hardware.device': []
        })
    
    def PowerOnVM_Task(self):
        task = MockTask()
        # Simulate async operation
        self._properties['runtime.powerState'] = 'poweredOn'
        return task
```

### Testing Strategy
1. **Unit Tests**: Test individual mock objects in isolation
2. **Integration Tests**: Test mock object interactions
3. **Contract Tests**: Verify mock behavior matches real API
4. **Performance Tests**: Ensure mocks don't impact test performance

## Detailed Implementation Examples

### Base Mock Framework Example
```python
# tests/mocks/vsphere_base.py
import weakref
from typing import Any, Dict, List, Optional

class MockVSphereObject:
    """Base class for all vSphere mock objects"""
    
    def __init__(self):
        self._properties = {}
        self._children = {}
        self._parent = None
        self._ref_count = 0
        
    def __getattr__(self, name: str) -> Any:
        """Dynamic property access"""
        if name in self._properties:
            return self._properties[name]
        
        # Handle nested property access (e.g., config.name)
        if '.' in name:
            parts = name.split('.')
            obj = self
            for part in parts:
                if hasattr(obj, part):
                    obj = getattr(obj, part)
                elif hasattr(obj, '_properties') and part in obj._properties:
                    obj = obj._properties[part]
                else:
                    return None
            return obj
            
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
    
    def __setattr__(self, name: str, value: Any) -> None:
        """Property assignment tracking"""
        if name.startswith('_'):
            super().__setattr__(name, value)
        else:
            self._properties[name] = value
    
    def add_child(self, child: 'MockVSphereObject') -> None:
        """Add child object relationship"""
        child._parent = weakref.ref(self)
        child_type = type(child).__name__
        if child_type not in self._children:
            self._children[child_type] = []
        self._children[child_type].append(child)
    
    def get_children(self, object_type: str) -> List['MockVSphereObject']:
        """Get children of specific type"""
        return self._children.get(object_type, [])
```

### VM Mock Implementation Example
```python
# tests/mocks/vsphere_vm.py
from .vsphere_base import MockVSphereObject
from .vsphere_vm_ops import MockTask

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
    
    def PowerOnVM_Task(self) -> MockTask:
        """Power on VM operation"""
        task = MockTask(operation="PowerOnVM")
        # Simulate state change
        self._properties['runtime'].powerState = 'poweredOn'
        task.complete_successfully()
        return task
    
    def PowerOffVM_Task(self) -> MockTask:
        """Power off VM operation"""
        task = MockTask(operation="PowerOffVM")
        self._properties['runtime'].powerState = 'poweredOff'
        task.complete_successfully()
        return task
    
    def ResetVM_Task(self) -> MockTask:
        """Reset VM operation"""
        task = MockTask(operation="ResetVM")
        # Simulate reset (brief power off then on)
        self._properties['runtime'].powerState = 'poweredOn'
        task.complete_successfully()
        return task

class MockVirtualMachineRuntimeInfo(MockVSphereObject):
    """Mock VM runtime information"""
    
    def __init__(self, power_state: str):
        super().__init__()
        self._properties.update({
            'powerState': power_state,
            'toolsRunningStatus': 'guestToolsRunning',
            'bootTime': '2023-01-01T00:00:00Z'
        })

class MockVirtualMachineConfigInfo(MockVSphereObject):
    """Mock VM configuration information"""
    
    def __init__(self, name: str):
        super().__init__()
        self._properties.update({
            'name': name,
            'guestId': 'ubuntu64Guest',
            'guestFullName': 'Ubuntu Linux (64-bit)',
            'hardware': MockVirtualHardware(),
            'annotation': ''
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
```

### Network Mock Implementation Example
```python
# tests/mocks/vsphere_network_adapters.py
from .vsphere_base import MockVSphereObject

class MockVirtualEthernetCard(MockVSphereObject):
    """Base class for network adapters"""
    
    def __init__(self, key: int, device_info_label: str):
        super().__init__()
        self._properties.update({
            'key': key,
            'deviceInfo': MockDescription(device_info_label),
            'backing': None,
            'connectable': MockVirtualDeviceConnectInfo(),
            'macAddress': self._generate_mac_address()
        })
    
    def _generate_mac_address(self) -> str:
        """Generate a fake MAC address"""
        return "00:50:56:12:34:56"

class MockVirtualVmxnet3(MockVirtualEthernetCard):
    """Mock VMware vmxnet3 adapter"""
    
    def __init__(self, key: int, device_info_label: str = "Network adapter 1"):
        super().__init__(key, device_info_label)

class MockVirtualE1000(MockVirtualEthernetCard):
    """Mock Intel E1000 adapter"""
    
    def __init__(self, key: int, device_info_label: str = "Network adapter 1"):
        super().__init__(key, device_info_label)

class MockVirtualDeviceConnectInfo(MockVSphereObject):
    """Mock device connection info"""
    
    def __init__(self):
        super().__init__()
        self._properties.update({
            'startConnected': True,
            'allowGuestControl': True,
            'connected': True,
            'status': 'ok'
        })

class MockDescription(MockVSphereObject):
    """Mock description object"""
    
    def __init__(self, label: str):
        super().__init__()
        self._properties.update({
            'label': label,
            'summary': label
        })
```

### Factory Pattern Example
```python
# tests/mocks/factories.py
from typing import List, Dict, Any
from .vsphere_service import MockServiceInstance
from .vsphere_inventory import MockDatacenter, MockFolder
from .vsphere_vm import MockVirtualMachine
from .vsphere_networks import MockNetwork, MockDistributedVirtualPortgroup

class MockVSphereEnvironmentFactory:
    """Factory for creating complete vSphere test environments"""
    
    @staticmethod
    def create_standard_environment() -> MockServiceInstance:
        """Create a standard test environment with datacenter, VMs, and networks"""
        si = MockServiceInstance()
        
        # Create datacenter
        datacenter = MockDatacenter("TestDatacenter")
        si.content.rootFolder.add_child(datacenter)
        
        # Create VM folder with test VMs
        vm_folder = MockFolder("VMs")
        datacenter.vmFolder = vm_folder
        
        # Add test VMs
        vm1 = MockVirtualMachine("test-vm-1", "poweredOn")
        vm2 = MockVirtualMachine("test-vm-2", "poweredOff")
        vm_folder.add_child(vm1)
        vm_folder.add_child(vm2)
        
        # Create network folder with test networks
        network_folder = MockFolder("Networks")
        datacenter.networkFolder = network_folder
        
        # Add test networks
        network1 = MockNetwork("VM Network")
        network2 = MockDistributedVirtualPortgroup("DVS-PG-1")
        network_folder.add_child(network1)
        network_folder.add_child(network2)
        
        return si
    
    @staticmethod
    def create_vm_with_network_adapters(name: str, adapter_count: int = 2) -> MockVirtualMachine:
        """Create a VM with specified number of network adapters"""
        vm = MockVirtualMachine(name)
        
        # Add network adapters
        for i in range(adapter_count):
            adapter = MockVirtualVmxnet3(
                key=4000 + i,
                device_info_label=f"Network adapter {i + 1}"
            )
            vm.config.hardware.device.append(adapter)
        
        return vm
```

### Test Migration Example
```python
# Example of how to update existing tests
# tests/unit/test_vm_manager.py (updated)

@pytest.fixture
def mock_vm_environment():
    """Create a mock vSphere environment for VM testing"""
    from tests.mocks.factories import MockVSphereEnvironmentFactory
    return MockVSphereEnvironmentFactory.create_standard_environment()

def test_power_on_vm(mock_vm_environment):
    """Test VM power on operation"""
    # Get the mock VM
    vm = mock_vm_environment.content.rootFolder.childEntity[0].vmFolder.childEntity[1]  # test-vm-2 (powered off)
    
    # Create VM manager with mock client
    mock_client = Mock()
    mock_client.service_instance = mock_vm_environment
    vm_manager = VMManager(mock_client)
    
    # Test power on
    vm_manager.power_on(vm)
    
    # Verify state change
    assert vm.runtime.powerState == 'poweredOn'
```

## Success Metrics
- **All 48 failing tests pass** with proper mock infrastructure
- **Test execution time** remains under 1 second for full suite
- **Mock coverage** of 90%+ of used vSphere API surface
- **Zero test flakiness** due to mock state issues

## Risk Mitigation
1. **Incremental Implementation**: Build mocks incrementally, test frequently
2. **Real API Validation**: Periodically validate mock behavior against real vSphere
3. **Performance Monitoring**: Track test execution time throughout implementation
4. **Rollback Strategy**: Keep existing mocks functional during transition

## Implementation Order
1. **Phase 1** (Critical): Base infrastructure and service mocks
2. **Phase 2** (High): VM management mocks to fix VM manager tests
3. **Phase 3** (High): Network mocks to fix network configuration tests
4. **Phase 4** (Medium): Advanced features for comprehensive coverage
5. **Phase 5** (Medium): Test integration and migration
6. **Phase 6** (Low): Validation and documentation

This comprehensive mock infrastructure will provide a solid foundation for reliable, fast unit testing while accurately representing the complexity of real vSphere environments.