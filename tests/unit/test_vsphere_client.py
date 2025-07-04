"""
Unit tests for vSphere client
"""

import pytest
import ssl
from unittest.mock import Mock, patch, MagicMock
from pyVmomi import vim, vmodl
from pod.infrastructure.vsphere.client import VSphereClient
from pod.exceptions import ConnectionError, VMNotFoundError, AuthenticationError


class TestVSphereClient:
    """Test cases for VSphereClient"""

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

    def test_init_default_port(self):
        """Test client initialization with default port"""
        client = VSphereClient(
            host="vcenter.example.com",
            username="admin@vsphere.local",
            password="password"
        )
        
        assert client.port == 443

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
    @patch('ssl._create_unverified_context')
    def test_connect_with_ssl_disabled(self, mock_ssl_context, mock_smart_connect, mock_vsphere_service_instance):
        """Test connection with SSL verification disabled"""
        mock_smart_connect.return_value = mock_vsphere_service_instance
        mock_ssl_context.return_value = Mock()
        
        client = VSphereClient(
            host="vcenter.example.com",
            username="admin@vsphere.local",
            password="password",
            disable_ssl_verification=True
        )
        
        client.connect()
        
        mock_ssl_context.assert_called_once()
        mock_smart_connect.assert_called_once()

    @patch('pyVim.connect.SmartConnect')
    @patch('pod.infrastructure.vsphere.client.vim')
    def test_connect_authentication_error(self, mock_vim, mock_smart_connect):
        """Test connection with authentication error"""
        # Create the exception type that the code expects
        mock_vim.fault.InvalidLogin = Exception
        mock_smart_connect.side_effect = Exception("Invalid login")
        
        client = VSphereClient(
            host="vcenter.example.com",
            username="admin@vsphere.local",
            password="wrong_password"
        )
        
        with pytest.raises(AuthenticationError):
            client.connect()

    @patch('pyVim.connect.SmartConnect')
    def test_connect_general_error(self, mock_smart_connect):
        """Test connection with general error"""
        # Use a specific exception that won't be caught as InvalidLogin
        class SpecificConnectionError(Exception):
            pass
        
        # Create a separate auth exception class
        class MockInvalidLogin(Exception):
            pass
        
        mock_smart_connect.side_effect = SpecificConnectionError("Connection failed")
        
        client = VSphereClient(
            host="vcenter.example.com",
            username="admin@vsphere.local",
            password="password"
        )
        
        # Patch with specific mock auth exception
        with patch('pod.infrastructure.vsphere.client.vim.fault.InvalidLogin', MockInvalidLogin):
            with pytest.raises(ConnectionError):
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

    def test_content_property_connected(self):
        """Test content property when connected"""
        client = VSphereClient(
            host="vcenter.example.com",
            username="admin@vsphere.local",
            password="password"
        )
        
        mock_content = Mock()
        client._content = mock_content
        
        assert client.content == mock_content

    def test_content_property_not_connected(self):
        """Test content property when not connected"""
        client = VSphereClient(
            host="vcenter.example.com",
            username="admin@vsphere.local",
            password="password"
        )
        
        with pytest.raises(ConnectionError):
            _ = client.content

    def test_get_obj_found(self):
        """Test getting object when found"""
        client = VSphereClient(
            host="vcenter.example.com",
            username="admin@vsphere.local",
            password="password"
        )
        
        # Mock content and container view
        mock_content = Mock()
        mock_container = Mock()
        mock_vm = Mock()
        mock_vm.name = "test-vm"
        
        mock_container.view = [mock_vm]
        mock_content.viewManager.CreateContainerView.return_value = mock_container
        client._content = mock_content
        
        result = client.get_obj([vim.VirtualMachine], "test-vm")
        
        assert result == mock_vm
        mock_container.Destroy.assert_called_once()

    def test_get_obj_not_found(self):
        """Test getting object when not found"""
        client = VSphereClient(
            host="vcenter.example.com",
            username="admin@vsphere.local",
            password="password"
        )
        
        # Mock content and container view
        mock_content = Mock()
        mock_container = Mock()
        mock_container.view = []
        mock_content.viewManager.CreateContainerView.return_value = mock_container
        client._content = mock_content
        
        result = client.get_obj([vim.VirtualMachine], "non-existent-vm")
        
        assert result is None
        mock_container.Destroy.assert_called_once()

    def test_get_vm_found(self, mock_vm):
        """Test getting VM when found"""
        client = VSphereClient(
            host="vcenter.example.com",
            username="admin@vsphere.local",
            password="password"
        )
        
        with patch.object(client, 'get_obj', return_value=mock_vm):
            result = client.get_vm("test-vm")
            assert result == mock_vm

    def test_get_vm_not_found(self):
        """Test getting VM when not found"""
        client = VSphereClient(
            host="vcenter.example.com",
            username="admin@vsphere.local",
            password="password"
        )
        
        with patch.object(client, 'get_obj', return_value=None):
            with pytest.raises(VMNotFoundError):
                client.get_vm("non-existent-vm")

    def test_get_all_vms(self, mock_vm):
        """Test getting all VMs"""
        client = VSphereClient(
            host="vcenter.example.com",
            username="admin@vsphere.local",
            password="password"
        )
        
        # Mock content and container view
        mock_content = Mock()
        mock_container = Mock()
        mock_container.view = [mock_vm]
        mock_content.viewManager.CreateContainerView.return_value = mock_container
        client._content = mock_content
        
        result = client.get_all_vms()
        
        assert result == [mock_vm]
        mock_container.Destroy.assert_called_once()

    def test_get_network_found(self, mock_network):
        """Test getting network when found"""
        client = VSphereClient(
            host="vcenter.example.com",
            username="admin@vsphere.local",
            password="password"
        )
        
        with patch.object(client, 'get_obj', return_value=mock_network):
            result = client.get_network("test-network")
            assert result == mock_network

    def test_get_network_not_found(self):
        """Test getting network when not found"""
        client = VSphereClient(
            host="vcenter.example.com",
            username="admin@vsphere.local",
            password="password"
        )
        
        with patch.object(client, 'get_obj', return_value=None):
            with pytest.raises(VMNotFoundError):
                client.get_network("non-existent-network")

    def test_get_datacenter_by_name(self):
        """Test getting datacenter by name"""
        client = VSphereClient(
            host="vcenter.example.com",
            username="admin@vsphere.local",
            password="password"
        )
        
        mock_datacenter = Mock()
        with patch.object(client, 'get_obj', return_value=mock_datacenter):
            result = client.get_datacenter("Datacenter1")
            assert result == mock_datacenter

    def test_get_datacenter_first_available(self):
        """Test getting first available datacenter"""
        client = VSphereClient(
            host="vcenter.example.com",
            username="admin@vsphere.local",
            password="password"
        )
        
        # Mock content and container view
        mock_content = Mock()
        mock_container = Mock()
        mock_datacenter = Mock()
        mock_container.view = [mock_datacenter]
        mock_content.viewManager.CreateContainerView.return_value = mock_container
        client._content = mock_content
        
        result = client.get_datacenter()
        
        assert result == mock_datacenter
        mock_container.Destroy.assert_called_once()

    def test_get_datacenter_not_found(self):
        """Test getting datacenter when not found"""
        client = VSphereClient(
            host="vcenter.example.com",
            username="admin@vsphere.local",
            password="password"
        )
        
        with patch.object(client, 'get_obj', return_value=None):
            with pytest.raises(VMNotFoundError):
                client.get_datacenter("non-existent-datacenter")

    def test_get_datacenter_no_datacenters(self):
        """Test getting datacenter when none exist"""
        client = VSphereClient(
            host="vcenter.example.com",
            username="admin@vsphere.local",
            password="password"
        )
        
        # Mock content and container view
        mock_content = Mock()
        mock_container = Mock()
        mock_container.view = []
        mock_content.viewManager.CreateContainerView.return_value = mock_container
        client._content = mock_content
        
        with pytest.raises(VMNotFoundError):
            client.get_datacenter()

    def test_wait_for_task_success(self):
        """Test waiting for successful task"""
        client = VSphereClient(
            host="vcenter.example.com",
            username="admin@vsphere.local",
            password="password"
        )
        
        mock_task = Mock()
        mock_task.info.state = vim.TaskInfo.State.success
        
        result = client.wait_for_task(mock_task)
        assert result is True

    def test_wait_for_task_error(self):
        """Test waiting for failed task"""
        client = VSphereClient(
            host="vcenter.example.com",
            username="admin@vsphere.local",
            password="password"
        )
        
        mock_task = Mock()
        mock_task.info.state = vim.TaskInfo.State.error
        mock_task.info.error = "Task failed"
        
        with pytest.raises(Exception):
            client.wait_for_task(mock_task)

    def test_wait_for_task_running_then_success(self):
        """Test waiting for task that completes successfully"""
        client = VSphereClient(
            host="vcenter.example.com",
            username="admin@vsphere.local",
            password="password"
        )
        
        mock_task = Mock()
        # Mock state progression: first running, then success
        state_progression = [vim.TaskInfo.State.running, vim.TaskInfo.State.success]
        state_iter = iter(state_progression)
        
        def get_state():
            try:
                return next(state_iter)
            except StopIteration:
                return vim.TaskInfo.State.success
        
        # Set up the mock to change state on access
        type(mock_task.info).state = property(lambda self: get_state())
        
        result = client.wait_for_task(mock_task)
        assert result is True