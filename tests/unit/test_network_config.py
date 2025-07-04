"""
Unit tests for Network Configuration
"""

import pytest
from unittest.mock import Mock, patch
from pyVmomi import vim
from pod.infrastructure.vsphere.network_config import NetworkConfigurator
from pod.exceptions import NetworkConfigError


class TestNetworkConfigurator:
    """Test cases for NetworkConfigurator"""

    def test_init(self, mock_vsphere_client):
        """Test network configurator initialization"""
        configurator = NetworkConfigurator(mock_vsphere_client)
        assert configurator.client == mock_vsphere_client

    def test_configure_vlan_with_network_name(self, mock_vsphere_client, mock_vm, mock_dvs_portgroup, mock_network_adapter):
        """Test VLAN configuration with specific network name"""
        mock_vsphere_client.get_vm.return_value = mock_vm
        mock_vsphere_client.get_network.return_value = mock_dvs_portgroup
        mock_vm.config.hardware.device = [mock_network_adapter]
        mock_task = Mock()
        mock_vm.ReconfigVM_Task.return_value = mock_task
        
        configurator = NetworkConfigurator(mock_vsphere_client)
        
        with patch.object(configurator, '_get_network_adapter', return_value=mock_network_adapter):
            result = configurator.configure_vlan("test-vm", "Network adapter 1", 100, "test-portgroup")
        
        assert result is True
        mock_vm.ReconfigVM_Task.assert_called_once()
        mock_vsphere_client.wait_for_task.assert_called_once_with(mock_task)

    def test_configure_vlan_adapter_not_found(self, mock_vsphere_client, mock_vm):
        """Test VLAN configuration with non-existent adapter"""
        mock_vsphere_client.get_vm.return_value = mock_vm
        
        configurator = NetworkConfigurator(mock_vsphere_client)
        
        with patch.object(configurator, '_get_network_adapter', return_value=None):
            with pytest.raises(NetworkConfigError):
                configurator.configure_vlan("test-vm", "Non-existent adapter", 100)

    def test_configure_vlan_standard_vswitch(self, mock_vsphere_client, mock_vm, mock_network, mock_network_adapter):
        """Test VLAN configuration with standard vSwitch"""
        mock_vsphere_client.get_vm.return_value = mock_vm
        mock_vsphere_client.get_network.return_value = mock_network
        mock_vm.config.hardware.device = [mock_network_adapter]
        mock_task = Mock()
        mock_vm.ReconfigVM_Task.return_value = mock_task
        
        configurator = NetworkConfigurator(mock_vsphere_client)
        
        with patch.object(configurator, '_get_network_adapter', return_value=mock_network_adapter):
            result = configurator.configure_vlan("test-vm", "Network adapter 1", 100, "test-network")
        
        assert result is True
        mock_vm.ReconfigVM_Task.assert_called_once()

    def test_add_network_adapter_vmxnet3(self, mock_vsphere_client, mock_vm, mock_network):
        """Test adding vmxnet3 network adapter"""
        mock_vsphere_client.get_vm.return_value = mock_vm
        mock_vsphere_client.get_network.return_value = mock_network
        mock_vm.config.hardware.device = []
        mock_task = Mock()
        mock_vm.ReconfigVM_Task.return_value = mock_task
        
        configurator = NetworkConfigurator(mock_vsphere_client)
        
        with patch.object(configurator, '_get_next_adapter_number', return_value=2):
            result = configurator.add_network_adapter("test-vm", "test-network", "vmxnet3")
        
        assert result == "Network adapter 2"
        mock_vm.ReconfigVM_Task.assert_called_once()
        mock_vsphere_client.wait_for_task.assert_called_once_with(mock_task)

    def test_add_network_adapter_e1000(self, mock_vsphere_client, mock_vm, mock_network):
        """Test adding e1000 network adapter"""
        mock_vsphere_client.get_vm.return_value = mock_vm
        mock_vsphere_client.get_network.return_value = mock_network
        mock_vm.config.hardware.device = []
        mock_task = Mock()
        mock_vm.ReconfigVM_Task.return_value = mock_task
        
        configurator = NetworkConfigurator(mock_vsphere_client)
        
        with patch.object(configurator, '_get_next_adapter_number', return_value=1):
            result = configurator.add_network_adapter("test-vm", "test-network", "e1000")
        
        assert result == "Network adapter 1"
        mock_vm.ReconfigVM_Task.assert_called_once()

    def test_add_network_adapter_e1000e(self, mock_vsphere_client, mock_vm, mock_network):
        """Test adding e1000e network adapter"""
        mock_vsphere_client.get_vm.return_value = mock_vm
        mock_vsphere_client.get_network.return_value = mock_network
        mock_vm.config.hardware.device = []
        mock_task = Mock()
        mock_vm.ReconfigVM_Task.return_value = mock_task
        
        configurator = NetworkConfigurator(mock_vsphere_client)
        
        with patch.object(configurator, '_get_next_adapter_number', return_value=1):
            result = configurator.add_network_adapter("test-vm", "test-network", "e1000e")
        
        assert result == "Network adapter 1"
        mock_vm.ReconfigVM_Task.assert_called_once()

    def test_add_network_adapter_unknown_type(self, mock_vsphere_client, mock_vm, mock_network):
        """Test adding unknown adapter type"""
        mock_vsphere_client.get_vm.return_value = mock_vm
        mock_vsphere_client.get_network.return_value = mock_network
        
        configurator = NetworkConfigurator(mock_vsphere_client)
        
        with pytest.raises(NetworkConfigError):
            configurator.add_network_adapter("test-vm", "test-network", "unknown_type")

    def test_add_network_adapter_dvs(self, mock_vsphere_client, mock_vm, mock_dvs_portgroup):
        """Test adding network adapter to DVS portgroup"""
        mock_vsphere_client.get_vm.return_value = mock_vm
        mock_vsphere_client.get_network.return_value = mock_dvs_portgroup
        mock_vm.config.hardware.device = []
        mock_task = Mock()
        mock_vm.ReconfigVM_Task.return_value = mock_task
        
        configurator = NetworkConfigurator(mock_vsphere_client)
        
        with patch.object(configurator, '_get_next_adapter_number', return_value=1):
            result = configurator.add_network_adapter("test-vm", "test-portgroup", "vmxnet3")
        
        assert result == "Network adapter 1"
        mock_vm.ReconfigVM_Task.assert_called_once()

    def test_remove_network_adapter_success(self, mock_vsphere_client, mock_vm, mock_network_adapter):
        """Test successful network adapter removal"""
        mock_vsphere_client.get_vm.return_value = mock_vm
        mock_task = Mock()
        mock_vm.ReconfigVM_Task.return_value = mock_task
        
        configurator = NetworkConfigurator(mock_vsphere_client)
        
        with patch.object(configurator, '_get_network_adapter', return_value=mock_network_adapter):
            result = configurator.remove_network_adapter("test-vm", "Network adapter 1")
        
        assert result is True
        mock_vm.ReconfigVM_Task.assert_called_once()
        mock_vsphere_client.wait_for_task.assert_called_once_with(mock_task)

    def test_remove_network_adapter_not_found(self, mock_vsphere_client, mock_vm):
        """Test removing non-existent network adapter"""
        mock_vsphere_client.get_vm.return_value = mock_vm
        
        configurator = NetworkConfigurator(mock_vsphere_client)
        
        with patch.object(configurator, '_get_network_adapter', return_value=None):
            with pytest.raises(NetworkConfigError):
                configurator.remove_network_adapter("test-vm", "Non-existent adapter")

    def test_connect_adapter_success(self, mock_vsphere_client, mock_vm, mock_network_adapter):
        """Test successful adapter connection"""
        mock_vsphere_client.get_vm.return_value = mock_vm
        mock_task = Mock()
        mock_vm.ReconfigVM_Task.return_value = mock_task
        
        configurator = NetworkConfigurator(mock_vsphere_client)
        
        with patch.object(configurator, '_get_network_adapter', return_value=mock_network_adapter):
            result = configurator.connect_adapter("test-vm", "Network adapter 1", True)
        
        assert result is True
        assert mock_network_adapter.connectable.connected is True
        mock_vm.ReconfigVM_Task.assert_called_once()

    def test_connect_adapter_disconnect(self, mock_vsphere_client, mock_vm, mock_network_adapter):
        """Test adapter disconnection"""
        mock_vsphere_client.get_vm.return_value = mock_vm
        mock_task = Mock()
        mock_vm.ReconfigVM_Task.return_value = mock_task
        
        configurator = NetworkConfigurator(mock_vsphere_client)
        
        with patch.object(configurator, '_get_network_adapter', return_value=mock_network_adapter):
            result = configurator.connect_adapter("test-vm", "Network adapter 1", False)
        
        assert result is True
        assert mock_network_adapter.connectable.connected is False

    def test_connect_adapter_not_found(self, mock_vsphere_client, mock_vm):
        """Test connecting non-existent adapter"""
        mock_vsphere_client.get_vm.return_value = mock_vm
        
        configurator = NetworkConfigurator(mock_vsphere_client)
        
        with patch.object(configurator, '_get_network_adapter', return_value=None):
            with pytest.raises(NetworkConfigError):
                configurator.connect_adapter("test-vm", "Non-existent adapter", True)

    def test_get_network_adapters(self, mock_vsphere_client, mock_vm, mock_network_adapter):
        """Test getting network adapters"""
        mock_network_adapter.backing.network.name = "VM Network"
        mock_vm.config.hardware.device = [mock_network_adapter]
        mock_vsphere_client.get_vm.return_value = mock_vm
        
        configurator = NetworkConfigurator(mock_vsphere_client)
        adapters = configurator.get_network_adapters("test-vm")
        
        assert len(adapters) == 1
        assert adapters[0]['label'] == "Network adapter 1"
        assert adapters[0]['network'] == "VM Network"
        assert adapters[0]['mac_address'] == "00:50:56:12:34:56"
        assert adapters[0]['connected'] is True

    def test_get_network_adapters_dvs(self, mock_vsphere_client, mock_vm, mock_network_adapter):
        """Test getting network adapters with DVS"""
        # Mock DVS backing
        mock_network_adapter.backing = Mock()
        mock_network_adapter.backing.port = Mock()
        mock_network_adapter.backing.port.portgroupKey = "pg-123"
        del mock_network_adapter.backing.network  # Remove network attribute
        
        mock_vm.config.hardware.device = [mock_network_adapter]
        mock_vsphere_client.get_vm.return_value = mock_vm
        
        configurator = NetworkConfigurator(mock_vsphere_client)
        adapters = configurator.get_network_adapters("test-vm")
        
        assert len(adapters) == 1
        assert adapters[0]['network'] == "pg-123"

    def test_get_network_adapter_found(self, mock_vsphere_client, mock_vm, mock_network_adapter):
        """Test finding network adapter by label"""
        mock_vm.config.hardware.device = [mock_network_adapter]
        
        configurator = NetworkConfigurator(mock_vsphere_client)
        result = configurator._get_network_adapter(mock_vm, "Network adapter 1")
        
        assert result == mock_network_adapter

    def test_get_network_adapter_not_found(self, mock_vsphere_client, mock_vm, mock_network_adapter):
        """Test not finding network adapter by label"""
        mock_vm.config.hardware.device = [mock_network_adapter]
        
        configurator = NetworkConfigurator(mock_vsphere_client)
        result = configurator._get_network_adapter(mock_vm, "Non-existent adapter")
        
        assert result is None

    def test_get_next_adapter_number_empty(self, mock_vsphere_client, mock_vm):
        """Test getting next adapter number when no adapters exist"""
        mock_vm.config.hardware.device = []
        
        configurator = NetworkConfigurator(mock_vsphere_client)
        result = configurator._get_next_adapter_number(mock_vm)
        
        assert result == 1

    def test_get_next_adapter_number_with_existing(self, mock_vsphere_client, mock_vm, mock_network_adapter):
        """Test getting next adapter number with existing adapters"""
        # Create additional adapters
        from tests.mocks.vsphere.network_adapters import MockVirtualVmxnet3
        adapter2 = MockVirtualVmxnet3(4001, "Network adapter 2")
        adapter3 = MockVirtualVmxnet3(4002, "Network adapter 3")
        
        mock_vm.config.hardware.device = [mock_network_adapter, adapter2, adapter3]
        
        configurator = NetworkConfigurator(mock_vsphere_client)
        result = configurator._get_next_adapter_number(mock_vm)
        
        assert result == 4

    def test_get_next_adapter_number_invalid_label(self, mock_vsphere_client, mock_vm):
        """Test getting next adapter number with invalid label"""
        from tests.mocks.vsphere.network_adapters import MockVirtualVmxnet3
        adapter = MockVirtualVmxnet3(4000, "Invalid adapter name")
        mock_vm.config.hardware.device = [adapter]
        
        configurator = NetworkConfigurator(mock_vsphere_client)
        result = configurator._get_next_adapter_number(mock_vm)
        
        assert result == 1

    def test_get_network_adapters_empty(self, mock_vsphere_client, mock_vm):
        """Test getting network adapters when none exist"""
        mock_vm.config.hardware.device = []
        mock_vsphere_client.get_vm.return_value = mock_vm
        
        configurator = NetworkConfigurator(mock_vsphere_client)
        adapters = configurator.get_network_adapters("test-vm")
        
        assert len(adapters) == 0

    def test_get_network_adapters_mixed_devices(self, mock_vsphere_client, mock_vm, mock_network_adapter):
        """Test getting network adapters with mixed device types"""
        # Add non-network device
        disk_device = Mock()  # Simple Mock without spec
        mock_vm.config.hardware.device = [mock_network_adapter, disk_device]
        mock_vsphere_client.get_vm.return_value = mock_vm
        
        configurator = NetworkConfigurator(mock_vsphere_client)
        adapters = configurator.get_network_adapters("test-vm")
        
        # Should only return network adapters
        assert len(adapters) == 1
        assert adapters[0]['label'] == "Network adapter 1"