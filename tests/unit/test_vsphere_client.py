"""
Unit and Integration tests for vSphere client
"""

import pytest
import ssl
from unittest.mock import Mock, patch, MagicMock
from pyVmomi import vim, vmodl
from pod.infrastructure.vsphere.client import VSphereClient
from pod.exceptions import ConnectionError, VMNotFoundError, AuthenticationError
from pod.infrastructure.vsphere.vm_manager import VMManager


@pytest.mark.unit
class TestVSphereClientUnit:
    """Unit test cases for VSphereClient using mocks"""

    def test_init(self):
        """Test client initialization"""
        client = VSphereClient(
            host="vcenter.example.com",
            username="admin@vsphere.local",
            password="password",
            port=443,
            disable_ssl_verification=True
        )
        
        assert client.host == "vcenter.example.com"
        assert client.username == "admin@vsphere.local"
        assert client.password == "password"
        assert client.port == 443
        assert client.disable_ssl_verification is True
        assert client._service_instance is None
        assert client._content is None

    @patch('pyVim.connect.SmartConnect')
    @patch('atexit.register')
    def test_connect_success(self, mock_atexit, mock_smart_connect, mock_vsphere_service_instance):
        """Test successful connection"""
        mock_smart_connect.return_value = mock_vsphere_service_instance
        
        client = VSphereClient(
            host="vcenter.example.com",
            username="admin@vsphere.local",
            password="password"
        )
        
        client.connect()
        
        assert client._service_instance == mock_vsphere_service_instance
        assert client._content is not None
        mock_smart_connect.assert_called_once()
        mock_atexit.assert_called_once()

    @patch('pyVim.connect.SmartConnect')
    def test_connect_authentication_error(self, mock_smart_connect):
        """Test connection with authentication error"""
        mock_smart_connect.side_effect = vim.fault.InvalidLogin()
        
        client = VSphereClient(
            host="vcenter.example.com",
            username="admin@vsphere.local",
            password="wrong_password"
        )
        
        with pytest.raises(AuthenticationError):
            client.connect()

    @patch('pyVim.connect.Disconnect')
    def test_disconnect(self, mock_disconnect):
        """Test disconnection"""
        client = VSphereClient(
            host="vcenter.example.com",
            username="admin@vsphere.local",
            password="password"
        )
        
        mock_service_instance = Mock()
        client._service_instance = mock_service_instance
        client._content = Mock()
        
        client.disconnect()
        
        mock_disconnect.assert_called_once_with(mock_service_instance)
        assert client._service_instance is None
        assert client._content is None


@pytest.mark.integration
class TestVSphereClientIntegration:
    """Integration test cases for VSphereClient using vcsim"""

    def test_connection(self, vsphere_client_integration):
        """Test that the client is connected to vcsim"""
        assert vsphere_client_integration._service_instance is not None
        assert vsphere_client_integration._content is not None
        assert "simulator" in vsphere_client_integration._service_instance.content.about.fullName.lower()

    def test_get_datacenter(self, vsphere_client_integration):
        """Test getting the default datacenter from vcsim"""
        dc = vsphere_client_integration.get_datacenter()
        assert dc is not None
        assert dc.name == "DC0"

    def test_get_vm_not_found(self, vsphere_client_integration):
        """Test that getting a non-existent VM raises an error"""
        with pytest.raises(VMNotFoundError):
            vsphere_client_integration.get_vm("non-existent-vm")

    def test_get_all_vms_empty(self, vsphere_client_integration):
        """Test that a new vcsim instance has no VMs"""
        vm_manager = VMManager(vsphere_client_integration)
        for vm in vm_manager.client.get_all_vms():
            vm_manager.delete_vm(vm.name)
        vms = vsphere_client_integration.get_all_vms()
        assert isinstance(vms, list)
        assert len(vms) == 0
