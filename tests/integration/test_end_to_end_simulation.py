"""
End-to-end simulation tests using vcsim
"""

import pytest
from unittest.mock import patch, Mock
from pod.infrastructure.vsphere.vm_manager import VMManager
from pod.os_abstraction.factory import OSHandlerFactory
from pod.os_abstraction.linux import LinuxHandler
from pod.exceptions import VMNotFoundError


@pytest.mark.integration
class TestEndToEndSimulation:
    """Test end-to-end scenarios using vcsim and mocked connections"""

    def test_create_and_identify_rockylinux(self, vsphere_client_integration, mock_ssh_connection, mock_os_release_content):
        """Test creating a VM, identifying it as Rocky Linux, and interacting with it"""
        vm_manager = VMManager(vsphere_client_integration)
        vm_name = "rockylinux9-test-vm"

        try:
            # 1. Create a new VM in vcsim to represent a Rocky Linux 9 host
            vm = vm_manager.create_vm_from_spec(
                vm_name,
                guest_id="rhel9_64Guest" # Use a guest ID that vcsim recognizes
            )
            assert vm is not None
            assert vm.name == vm_name

            # 2. Power on the simulated VM
            vm_manager.power_on(vm_name, wait_for_ip=False) # Can't wait for a real IP

            # 3. Get the VM info and patch the IP address for the next step
            # vcsim doesn't assign IPs, so we set one manually for the test
            vm.guest.ipAddress = "127.0.0.1"

            # 4. Use the OSFactory to get a handler for the VM
            # We patch the SSH connection to return our mock connection
            with patch('pod.connections.ssh.SSHConnection', return_value=mock_ssh_connection):
                os_handler = OSHandlerFactory.create_handler(mock_ssh_connection, {"guest_id": "rhel9_64Guest"})

                # 5. Configure the mock connection to return Rocky 9 os-release info
                mock_ssh_connection.execute_command.return_value = (mock_os_release_content, "", 0)

                # 6. Verify the handler is a LinuxHandler and can get OS info
                assert isinstance(os_handler, LinuxHandler)
                os_info = os_handler.get_os_info()

                assert os_info["name"] == "Rocky Linux"
                assert os_info["version"] == "9.0 (Blue Onyx)"

        finally:
            # 7. Clean up the created VM
            try:
                vm_manager.delete_vm(vm_name)
            except VMNotFoundError:
                pass # VM might not have been created if the test failed early
