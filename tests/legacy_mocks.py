"""
Mock modules for external dependencies that may not be available during testing
"""

from unittest.mock import Mock, MagicMock
import sys


# Mock pyVmomi if not available
try:
    import pyVim
    import pyVmomi
except ImportError:
    # Create mock type classes for isinstance checks
    class MockVirtualMachineMeta(type):
        def __instancecheck__(cls, instance):
            # Allow our mock objects to pass isinstance checks
            from tests.mocks.vsphere.vm import MockVirtualMachine
            return isinstance(instance, MockVirtualMachine) or type.__instancecheck__(cls, instance)
    
    class MockVirtualMachine(metaclass=MockVirtualMachineMeta):
        pass
    
    class MockNetworkMeta(type):
        def __instancecheck__(cls, instance):
            from tests.mocks.vsphere.networks import MockNetwork as VSphereNetworkMock
            return isinstance(instance, VSphereNetworkMock) or type.__instancecheck__(cls, instance)
    
    class MockNetwork(metaclass=MockNetworkMeta):
        pass
    
    class MockDatacenter:
        pass
    
    class MockDistributedVirtualPortgroupMeta(type):
        def __instancecheck__(cls, instance):
            from tests.mocks.vsphere.networks import MockDistributedVirtualPortgroup as VSphereDVPortgroupMock
            return isinstance(instance, VSphereDVPortgroupMock) or type.__instancecheck__(cls, instance)
    
    class MockDistributedVirtualPortgroup(metaclass=MockDistributedVirtualPortgroupMeta):
        pass
    
    class MockVirtualEthernetCard:
        pass
    
    class MockVirtualVmxnet3(MockVirtualEthernetCard):
        pass
    
    class MockVirtualE1000(MockVirtualEthernetCard):
        pass
    
    class MockVirtualE1000e(MockVirtualEthernetCard):
        pass
    
    class MockVirtualDisk:
        pass
    
    class MockVirtualDeviceSpec:
        class Operation:
            add = "add"
            edit = "edit"
            remove = "remove"
    
    class MockConfigSpec:
        pass
    
    class MockCloneSpec:
        pass
    
    class MockRelocateSpec:
        pass
    
    class MockPortConnection:
        pass
    
    class MockClusterComputeResource:
        pass
    
    class MockComputeResource:
        pass
    
    class MockResourcePool:
        pass
    
    class MockFolder:
        pass
    
    class MockDescription:
        pass
    
    # Create mock modules
    mock_vim = MagicMock()
    mock_vim.VirtualMachine = MockVirtualMachine
    mock_vim.Network = MockNetwork
    mock_vim.Datacenter = MockDatacenter
    mock_vim.VirtualMachinePowerState = MagicMock()
    mock_vim.VirtualMachinePowerState.poweredOn = "poweredOn"
    mock_vim.VirtualMachinePowerState.poweredOff = "poweredOff"
    mock_vim.VirtualMachineToolsStatus = MagicMock()
    mock_vim.VirtualMachineToolsStatus.toolsOk = "toolsOk"
    mock_vim.VirtualMachineToolsStatus.toolsNotInstalled = "toolsNotInstalled"
    mock_vim.TaskInfo = MagicMock()
    mock_vim.TaskInfo.State = MagicMock()
    mock_vim.TaskInfo.State.success = "success"
    mock_vim.TaskInfo.State.error = "error"
    mock_vim.TaskInfo.State.running = "running"
    mock_vim.vm = MagicMock()
    mock_vim.vm.device = MagicMock()
    mock_vim.vm.device.VirtualEthernetCard = MockVirtualEthernetCard
    mock_vim.vm.device.VirtualVmxnet3 = MockVirtualVmxnet3
    mock_vim.vm.device.VirtualE1000 = MockVirtualE1000
    mock_vim.vm.device.VirtualE1000e = MockVirtualE1000e
    mock_vim.vm.device.VirtualDisk = MockVirtualDisk
    mock_vim.vm.device.VirtualDeviceSpec = MockVirtualDeviceSpec
    mock_vim.vm.ConfigSpec = MockConfigSpec
    mock_vim.vm.CloneSpec = MockCloneSpec
    mock_vim.vm.RelocateSpec = MockRelocateSpec
    
    # Create dvs module with proper structure
    mock_dvs = MagicMock()
    mock_dvs.DistributedVirtualPortgroup = MockDistributedVirtualPortgroup
    mock_dvs.PortConnection = MockPortConnection
    mock_vim.dvs = mock_dvs
    mock_vim.ClusterComputeResource = MockClusterComputeResource
    mock_vim.ComputeResource = MockComputeResource
    mock_vim.ResourcePool = MockResourcePool
    mock_vim.Folder = MockFolder
    mock_vim.Description = MockDescription
    # Create proper exception classes
    class MockInvalidLogin(Exception):
        pass
    
    # Create mock fault module
    fault_mock = MagicMock()
    fault_mock.InvalidLogin = MockInvalidLogin
    mock_vim.fault = fault_mock
    
    mock_vmodl = MagicMock()
    
    mock_pyVim = MagicMock()
    mock_pyVim.connect = MagicMock()
    mock_pyVim.connect.SmartConnect = MagicMock()
    mock_pyVim.connect.Disconnect = MagicMock()
    
    # Insert into sys.modules
    sys.modules['pyVmomi'] = MagicMock()
    sys.modules['pyVmomi.vim'] = mock_vim
    sys.modules['pyVmomi.vmodl'] = mock_vmodl
    sys.modules['pyVim'] = mock_pyVim
    sys.modules['pyVim.connect'] = mock_pyVim.connect
    
    # Register our mock objects for isinstance checks
    def register_mock_object(mock_obj, vim_type):
        """Register a mock object to pass isinstance checks"""
        original_bases = vim_type.__bases__ if hasattr(vim_type, '__bases__') else ()
        vim_type.__bases__ = original_bases + (type(mock_obj),)
    
    # This will be called later when our mock objects are created
    mock_vim._register_mock_object = register_mock_object
    
    # Patch isinstance to work with our mock objects
    import builtins
    original_isinstance = builtins.isinstance
    
    def patched_isinstance(obj, classinfo):
        """Patched isinstance that handles our mock objects"""
        # Check if classinfo is a MagicMock (from our vim module mocks)
        if hasattr(classinfo, '_mock_name'):
            mock_name = getattr(classinfo, '_mock_name', '')
            if 'DistributedVirtualPortgroup' in mock_name:
                from tests.mocks.vsphere.networks import MockDistributedVirtualPortgroup as VSphereDVPortgroupMock
                return original_isinstance(obj, VSphereDVPortgroupMock)
            elif 'Network' in mock_name and 'DistributedVirtualPortgroup' not in mock_name:
                from tests.mocks.vsphere.networks import MockNetwork as VSphereNetworkMock
                return original_isinstance(obj, VSphereNetworkMock)
            elif 'VirtualMachine' in mock_name:
                from tests.mocks.vsphere.vm import MockVirtualMachine as VSphereVMMock
                return original_isinstance(obj, VSphereVMMock)
            elif 'VirtualEthernetCard' in mock_name:
                from tests.mocks.vsphere.network_adapters import MockVirtualEthernetCard
                return original_isinstance(obj, MockVirtualEthernetCard)
            elif 'VirtualVmxnet3' in mock_name:
                from tests.mocks.vsphere.network_adapters import MockVirtualVmxnet3
                return original_isinstance(obj, MockVirtualVmxnet3)
            elif 'VirtualE1000e' in mock_name:
                from tests.mocks.vsphere.network_adapters import MockVirtualE1000e
                return original_isinstance(obj, MockVirtualE1000e)
            elif 'VirtualE1000' in mock_name:
                from tests.mocks.vsphere.network_adapters import MockVirtualE1000
                return original_isinstance(obj, MockVirtualE1000)
            elif 'VirtualDisk' in mock_name:
                # For VirtualDisk, just check if it's a Mock with the right attributes
                return hasattr(obj, 'deviceInfo') and hasattr(obj, 'capacityInKB')
        
        # Handle our specific mock type checks
        if classinfo is MockDistributedVirtualPortgroup:
            from tests.mocks.vsphere.networks import MockDistributedVirtualPortgroup as VSphereDVPortgroupMock
            return original_isinstance(obj, VSphereDVPortgroupMock)
        elif classinfo is MockNetwork:
            from tests.mocks.vsphere.networks import MockNetwork as VSphereNetworkMock
            return original_isinstance(obj, VSphereNetworkMock)
        elif classinfo is MockVirtualMachine:
            from tests.mocks.vsphere.vm import MockVirtualMachine as VSphereVMMock
            return original_isinstance(obj, VSphereVMMock)
        
        # Check if it's a type we can handle
        try:
            return original_isinstance(obj, classinfo)
        except TypeError:
            # If classinfo is not a valid type, just return False
            return False
    
    builtins.isinstance = patched_isinstance


# Mock paramiko if not available
try:
    import paramiko
except ImportError:
    # Create proper exception classes
    class MockAuthenticationException(Exception):
        pass
    
    class MockSSHException(Exception):
        pass
    
    mock_paramiko = MagicMock()
    mock_paramiko.SSHClient = MagicMock()
    mock_paramiko.AutoAddPolicy = MagicMock()
    mock_paramiko.AuthenticationException = MockAuthenticationException
    mock_paramiko.SSHException = MockSSHException
    mock_paramiko.SFTPClient = MagicMock()
    
    sys.modules['paramiko'] = mock_paramiko


# Mock winrm if not available
try:
    import winrm
except ImportError:
    # Create proper exception classes
    class MockWinRMError(Exception):
        pass
    
    class MockWinRMTransportError(Exception):
        pass
    
    mock_winrm = MagicMock()
    mock_winrm.Session = MagicMock()
    mock_winrm.protocol = MagicMock()
    mock_winrm.protocol.Protocol = MagicMock()
    mock_winrm.exceptions = MagicMock()
    mock_winrm.exceptions.WinRMError = MockWinRMError
    mock_winrm.exceptions.WinRMTransportError = MockWinRMTransportError
    
    sys.modules['winrm'] = mock_winrm
    sys.modules['winrm.protocol'] = mock_winrm.protocol
    sys.modules['winrm.exceptions'] = mock_winrm.exceptions


# Mock docker if not available
try:
    import docker
except ImportError:
    mock_docker = MagicMock()
    sys.modules['docker'] = mock_docker