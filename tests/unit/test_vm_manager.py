"""
Unit tests for VM Manager
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from pyVmomi import vim
from pod.infrastructure.vsphere.vm_manager import VMManager
from pod.exceptions import VMNotFoundError, OSError


class TestVMManager:
    """Test cases for VMManager"""

    def test_init(self, mock_vsphere_client):
        """Test VM manager initialization"""
        manager = VMManager(mock_vsphere_client)
        assert manager.client == mock_vsphere_client

    def test_get_vm_info_linux(self, mock_vsphere_client, mock_vm):
        """Test getting VM info for Linux VM"""
        mock_vsphere_client.get_vm.return_value = mock_vm
        
        # Mock network adapter
        mock_adapter = Mock()
        mock_adapter.deviceInfo.label = "Network adapter 1"
        mock_adapter.macAddress = "00:50:56:12:34:56"
        mock_adapter.connectable.connected = True
        mock_adapter.backing.network.name = "VM Network"
        mock_vm.config.hardware.device = [mock_adapter]
        
        manager = VMManager(mock_vsphere_client)
        
        with patch.object(manager, '_detect_os_type', return_value='linux'):
            with patch.object(manager, '_get_disk_info', return_value=[]):
                with patch.object(manager, '_get_network_info', return_value=[]):
                    info = manager.get_vm_info("test-vm")
        
        assert info['name'] == "test-vm"
        assert info['uuid'] == "vm-uuid-123"
        assert info['power_state'] == "poweredOn"
        assert info['guest']['os_type'] == 'linux'
        assert info['guest']['hostname'] == "test-vm"
        assert info['guest']['ip_address'] == "192.168.1.100"
        assert info['hardware']['cpu_count'] == 2
        assert info['hardware']['memory_mb'] == 4096

    def test_detect_os_type_linux(self, mock_vsphere_client, mock_vm):
        """Test OS type detection for Linux"""
        mock_vm.config.guestId = "rhel8_64Guest"
        mock_vm.guest.guestFamily = "linuxGuest"
        
        manager = VMManager(mock_vsphere_client)
        os_type = manager._detect_os_type(mock_vm)
        
        assert os_type == 'linux'

    def test_detect_os_type_windows(self, mock_vsphere_client, mock_vm):
        """Test OS type detection for Windows"""
        mock_vm.config.guestId = "windows2019srv_64Guest"
        mock_vm.guest.guestFamily = "windowsGuest"
        
        manager = VMManager(mock_vsphere_client)
        os_type = manager._detect_os_type(mock_vm)
        
        assert os_type == 'windows'

    def test_detect_os_type_container(self, mock_vsphere_client, mock_vm):
        """Test OS type detection for container"""
        mock_vm.config.guestId = "ubuntu64Guest"
        mock_vm.guest.guestFamily = "linuxGuest"
        mock_vm.name = "docker-container-test"
        
        manager = VMManager(mock_vsphere_client)
        
        with patch.object(manager, '_is_container', return_value=True):
            os_type = manager._detect_os_type(mock_vm)
        
        assert os_type == 'container'

    def test_is_container_true(self, mock_vsphere_client, mock_vm):
        """Test container detection - positive case"""
        mock_vm.name = "container-test-vm"
        
        manager = VMManager(mock_vsphere_client)
        result = manager._is_container(mock_vm)
        
        assert result is True

    def test_is_container_false(self, mock_vsphere_client, mock_vm):
        """Test container detection - negative case"""
        mock_vm.name = "regular-test-vm"
        
        manager = VMManager(mock_vsphere_client)
        result = manager._is_container(mock_vm)
        
        assert result is False

    def test_power_on_already_on(self, mock_vsphere_client, mock_vm):
        """Test powering on VM that's already on"""
        mock_vsphere_client.get_vm.return_value = mock_vm
        mock_vm.runtime.powerState = vim.VirtualMachinePowerState.poweredOn
        
        manager = VMManager(mock_vsphere_client)
        result = manager.power_on("test-vm", wait_for_ip=False)
        
        assert result is True
        mock_vm.PowerOnVM_Task.assert_not_called()

    def test_power_on_success(self, mock_vsphere_client, mock_vm):
        """Test successful power on"""
        mock_vsphere_client.get_vm.return_value = mock_vm
        mock_vm.runtime.powerState = vim.VirtualMachinePowerState.poweredOff
        mock_task = Mock()
        mock_vm.PowerOnVM_Task.return_value = mock_task
        
        manager = VMManager(mock_vsphere_client)
        result = manager.power_on("test-vm", wait_for_ip=False)
        
        assert result is True
        mock_vm.PowerOnVM_Task.assert_called_once()
        mock_vsphere_client.wait_for_task.assert_called_once_with(mock_task)

    def test_power_on_with_wait_for_ip(self, mock_vsphere_client, mock_vm):
        """Test power on with waiting for IP"""
        mock_vsphere_client.get_vm.return_value = mock_vm
        mock_vm.runtime.powerState = vim.VirtualMachinePowerState.poweredOff
        mock_task = Mock()
        mock_vm.PowerOnVM_Task.return_value = mock_task
        
        manager = VMManager(mock_vsphere_client)
        
        with patch.object(manager, '_wait_for_ip', return_value="192.168.1.100"):
            result = manager.power_on("test-vm", wait_for_ip=True)
        
        assert result is True

    def test_power_off_already_off(self, mock_vsphere_client, mock_vm):
        """Test powering off VM that's already off"""
        mock_vsphere_client.get_vm.return_value = mock_vm
        mock_vm.runtime.powerState = vim.VirtualMachinePowerState.poweredOff
        
        manager = VMManager(mock_vsphere_client)
        result = manager.power_off("test-vm")
        
        assert result is True
        mock_vm.PowerOffVM_Task.assert_not_called()

    def test_power_off_force(self, mock_vsphere_client, mock_vm):
        """Test force power off"""
        mock_vsphere_client.get_vm.return_value = mock_vm
        mock_vm.runtime.powerState = vim.VirtualMachinePowerState.poweredOn
        mock_task = Mock()
        mock_vm.PowerOffVM_Task.return_value = mock_task
        
        manager = VMManager(mock_vsphere_client)
        result = manager.power_off("test-vm", force=True)
        
        assert result is True
        mock_vm.PowerOffVM_Task.assert_called_once()
        mock_vsphere_client.wait_for_task.assert_called_once_with(mock_task)

    def test_power_off_graceful(self, mock_vsphere_client, mock_vm):
        """Test graceful power off"""
        mock_vsphere_client.get_vm.return_value = mock_vm
        mock_vm.runtime.powerState = vim.VirtualMachinePowerState.poweredOn
        mock_vm.guest.toolsStatus = vim.VirtualMachineToolsStatus.toolsOk
        
        # Set up the mock to simulate successful graceful shutdown
        # After ShutdownGuest is called, the power state should become poweredOff
        def shutdown_side_effect():
            mock_vm.runtime.powerState = vim.VirtualMachinePowerState.poweredOff
        
        mock_vm.ShutdownGuest.side_effect = shutdown_side_effect
        
        manager = VMManager(mock_vsphere_client)
        
        with patch('time.sleep'):
            result = manager.power_off("test-vm", force=False)
        
        assert result is True
        mock_vm.ShutdownGuest.assert_called_once()

    def test_power_off_graceful_timeout(self, mock_vsphere_client, mock_vm):
        """Test graceful power off with timeout"""
        mock_vsphere_client.get_vm.return_value = mock_vm
        mock_vm.runtime.powerState = vim.VirtualMachinePowerState.poweredOn
        mock_vm.guest.toolsStatus = vim.VirtualMachineToolsStatus.toolsOk
        mock_task = Mock()
        mock_vm.PowerOffVM_Task.return_value = mock_task
        
        manager = VMManager(mock_vsphere_client)
        
        with patch('time.sleep'):
            with patch('time.time', side_effect=[0, 30, 70]):  # Simulate timeout
                result = manager.power_off("test-vm", force=False)
        
        assert result is True
        mock_vm.ShutdownGuest.assert_called_once()
        mock_vm.PowerOffVM_Task.assert_called_once()

    def test_restart_powered_off(self, mock_vsphere_client, mock_vm):
        """Test restart of powered off VM"""
        mock_vsphere_client.get_vm.return_value = mock_vm
        mock_vm.runtime.powerState = vim.VirtualMachinePowerState.poweredOff
        
        manager = VMManager(mock_vsphere_client)
        
        with patch.object(manager, 'power_on', return_value=True) as mock_power_on:
            result = manager.restart("test-vm")
        
        assert result is True
        mock_power_on.assert_called_once_with("test-vm", True)

    def test_restart_powered_on_with_tools(self, mock_vsphere_client, mock_vm):
        """Test restart of powered on VM with tools"""
        mock_vsphere_client.get_vm.return_value = mock_vm
        mock_vm.runtime.powerState = vim.VirtualMachinePowerState.poweredOn
        mock_vm.guest.toolsStatus = vim.VirtualMachineToolsStatus.toolsOk
        
        manager = VMManager(mock_vsphere_client)
        
        with patch.object(manager, '_wait_for_ip', return_value="192.168.1.100"):
            with patch('time.sleep'):
                result = manager.restart("test-vm")
        
        assert result is True
        mock_vm.RebootGuest.assert_called_once()

    def test_restart_powered_on_without_tools(self, mock_vsphere_client, mock_vm):
        """Test restart of powered on VM without tools"""
        mock_vsphere_client.get_vm.return_value = mock_vm
        mock_vm.runtime.powerState = vim.VirtualMachinePowerState.poweredOn
        mock_vm.guest.toolsStatus = vim.VirtualMachineToolsStatus.toolsNotInstalled
        mock_task = Mock()
        mock_vm.ResetVM_Task.return_value = mock_task
        
        manager = VMManager(mock_vsphere_client)
        
        with patch.object(manager, '_wait_for_ip', return_value="192.168.1.100"):
            with patch('time.sleep'):
                result = manager.restart("test-vm")
        
        assert result is True
        mock_vm.ResetVM_Task.assert_called_once()
        mock_vsphere_client.wait_for_task.assert_called_once_with(mock_task)

    def test_clone_vm_success(self, mock_vsphere_client, mock_vm):
        """Test successful VM cloning"""
        mock_source_vm = Mock()
        mock_datacenter = Mock()
        mock_datacenter.vmFolder = Mock()
        
        # Use typed mock for resource pool
        from tests.mocks.vsphere.device_specs import create_mock_resource_pool
        mock_resource_pool = create_mock_resource_pool()
        mock_task = Mock()
        
        mock_vsphere_client.get_vm.side_effect = [mock_source_vm, mock_vm]
        mock_vsphere_client.get_datacenter.return_value = mock_datacenter
        mock_source_vm.Clone.return_value = mock_task
        
        manager = VMManager(mock_vsphere_client)
        
        with patch.object(manager, '_get_default_resource_pool', return_value=mock_resource_pool):
            result = manager.clone_vm("source-vm", "new-vm")
        
        assert result == mock_vm
        mock_source_vm.Clone.assert_called_once()
        mock_vsphere_client.wait_for_task.assert_called_once_with(mock_task)

    def test_delete_vm_success(self, mock_vsphere_client, mock_vm):
        """Test successful VM deletion"""
        mock_vsphere_client.get_vm.return_value = mock_vm
        mock_vm.runtime.powerState = vim.VirtualMachinePowerState.poweredOff
        mock_task = Mock()
        mock_vm.Destroy_Task.return_value = mock_task
        
        manager = VMManager(mock_vsphere_client)
        result = manager.delete_vm("test-vm")
        
        assert result is True
        mock_vm.Destroy_Task.assert_called_once()
        mock_vsphere_client.wait_for_task.assert_called_once_with(mock_task)

    def test_delete_vm_powered_on(self, mock_vsphere_client, mock_vm):
        """Test VM deletion when powered on"""
        mock_vsphere_client.get_vm.return_value = mock_vm
        mock_vm.runtime.powerState = vim.VirtualMachinePowerState.poweredOn
        mock_task = Mock()
        mock_vm.Destroy_Task.return_value = mock_task
        
        manager = VMManager(mock_vsphere_client)
        
        with patch.object(manager, 'power_off', return_value=True):
            result = manager.delete_vm("test-vm")
        
        assert result is True
        mock_vm.Destroy_Task.assert_called_once()

    def test_get_disk_info(self, mock_vsphere_client, mock_vm):
        """Test getting disk information"""
        # Use typed mock for disk device
        from tests.mocks.vsphere.device_specs import create_mock_virtual_disk
        mock_disk = create_mock_virtual_disk("Hard disk 1", 20971520, True)
        mock_vm.config.hardware.device = [mock_disk]
        
        manager = VMManager(mock_vsphere_client)
        disks = manager._get_disk_info(mock_vm)
        
        assert len(disks) == 1
        assert disks[0]['label'] == "Hard disk 1"
        assert disks[0]['capacity_gb'] == 20
        assert disks[0]['thin_provisioned'] is True

    def test_get_network_info(self, mock_vsphere_client, mock_vm, mock_network_adapter):
        """Test getting network information"""
        mock_network_adapter.backing.network.name = "VM Network"
        mock_vm.config.hardware.device = [mock_network_adapter]
        
        manager = VMManager(mock_vsphere_client)
        networks = manager._get_network_info(mock_vm)
        
        assert len(networks) == 1
        assert networks[0]['label'] == "Network adapter 1"
        assert networks[0]['network'] == "VM Network"
        assert networks[0]['mac_address'] == "00:50:56:12:34:56"
        assert networks[0]['connected'] is True

    def test_wait_for_ip_success(self, mock_vsphere_client, mock_vm):
        """Test successful waiting for IP"""
        mock_vm.guest.ipAddress = "192.168.1.100"
        
        manager = VMManager(mock_vsphere_client)
        result = manager._wait_for_ip(mock_vm, timeout=1)
        
        assert result == "192.168.1.100"

    def test_wait_for_ip_timeout(self, mock_vsphere_client, mock_vm):
        """Test timeout waiting for IP"""
        mock_vm.guest.ipAddress = None
        
        manager = VMManager(mock_vsphere_client)
        
        with patch('time.sleep'):
            with pytest.raises(OSError):
                manager._wait_for_ip(mock_vm, timeout=1)

    def test_get_folder_by_path_root(self, mock_vsphere_client):
        """Test getting folder by path - root"""
        mock_datacenter = Mock()
        mock_datacenter.vmFolder = Mock()
        
        manager = VMManager(mock_vsphere_client)
        result = manager._get_folder_by_path(mock_datacenter, "")
        
        assert result == mock_datacenter.vmFolder

    def test_get_folder_by_path_nested(self, mock_vsphere_client):
        """Test getting folder by path - nested"""
        mock_datacenter = Mock()
        mock_root_folder = Mock()
        mock_subfolder = Mock()
        mock_subfolder.name = "subfolder"
        mock_root_folder.childEntity = [mock_subfolder]
        mock_datacenter.vmFolder = mock_root_folder
        
        manager = VMManager(mock_vsphere_client)
        
        # Mock the isinstance function in the vm_manager module
        with patch('pod.infrastructure.vsphere.vm_manager.isinstance', return_value=True):
            result = manager._get_folder_by_path(mock_datacenter, "subfolder")
        
        assert result == mock_subfolder

    def test_get_folder_by_path_not_found(self, mock_vsphere_client):
        """Test getting folder by path - not found"""
        mock_datacenter = Mock()
        mock_root_folder = Mock()
        mock_root_folder.childEntity = []
        mock_datacenter.vmFolder = mock_root_folder
        
        manager = VMManager(mock_vsphere_client)
        
        with pytest.raises(VMNotFoundError):
            manager._get_folder_by_path(mock_datacenter, "nonexistent")

    def test_get_default_resource_pool_cluster(self, mock_vsphere_client):
        """Test getting default resource pool from cluster"""
        mock_datacenter = Mock()
        mock_cluster = Mock()
        mock_cluster.resourcePool = Mock()
        mock_datacenter.hostFolder.childEntity = [mock_cluster]
        
        manager = VMManager(mock_vsphere_client)
        
        # Mock isinstance to return True for cluster check
        with patch('pod.infrastructure.vsphere.vm_manager.isinstance', side_effect=lambda obj, cls: obj == mock_cluster and cls == vim.ClusterComputeResource):
            result = manager._get_default_resource_pool(mock_datacenter)
        
        assert result == mock_cluster.resourcePool

    def test_get_default_resource_pool_standalone(self, mock_vsphere_client):
        """Test getting default resource pool from standalone host"""
        mock_datacenter = Mock()
        mock_compute_resource = Mock()
        mock_compute_resource.resourcePool = Mock()
        mock_datacenter.hostFolder.childEntity = [mock_compute_resource]
        
        manager = VMManager(mock_vsphere_client)
        
        # Mock isinstance to return True for compute resource check
        with patch('pod.infrastructure.vsphere.vm_manager.isinstance', side_effect=lambda obj, cls: obj == mock_compute_resource and cls == vim.ComputeResource):
            result = manager._get_default_resource_pool(mock_datacenter)
        
        assert result == mock_compute_resource.resourcePool

    def test_get_default_resource_pool_not_found(self, mock_vsphere_client):
        """Test getting default resource pool - not found"""
        mock_datacenter = Mock()
        mock_datacenter.hostFolder.childEntity = []
        
        manager = VMManager(mock_vsphere_client)
        
        with pytest.raises(VMNotFoundError):
            manager._get_default_resource_pool(mock_datacenter)