"""
Example usage of the POD library
"""

import os
from pod import PODClient
from pod.os_abstraction.base import NetworkConfig

# Initialize POD client with vSphere credentials
# Use environment variables for security: export VSPHERE_PASSWORD=your_password
client = PODClient(
    vsphere_host="vcenter.example.com",
    vsphere_username="administrator@vsphere.local", 
    vsphere_password=os.getenv("VSPHERE_PASSWORD", "your_password_here"),
    vsphere_port=443,
    disable_ssl_verification=True  # For testing only
)

# Connect to vSphere
client.connect()

# Get a VM
vm = client.get_vm("test-linux-vm")

# Power on the VM if needed
if not vm.is_powered_on():
    print("Powering on VM...")
    vm.power_on(wait_for_ip=True)

# Get VM information
info = vm.get_info()
print(f"VM: {info['name']}")
print(f"OS Type: {info['guest']['os_type']}")
print(f"IP Address: {info['guest']['ip_address']}")

# Connect to the VM (automatically detects OS and uses appropriate connection)
vm.connect(username="root", password=os.getenv("VM_PASSWORD", "your_vm_password"))

# Execute commands
result = vm.execute_command("uname -a")
print(f"Kernel: {result.stdout}")

# Configure network - same API for all OS types
network_config = NetworkConfig(
    interface="eth1",
    ip_address="192.168.100.10",
    netmask="255.255.255.0",
    gateway="192.168.100.1",
    dns_servers=["8.8.8.8", "8.8.4.4"],
    vlan_id=100
)

print("Configuring network...")
result = vm.configure_network(network_config)
if result.success:
    print("Network configured successfully")
else:
    print(f"Network configuration failed: {result.stderr}")

# Configure VLAN on vSphere level
print("Configuring VLAN on vSphere...")
vm.configure_vlan("Network adapter 1", vlan_id=100)

# Get network interfaces
interfaces = vm.get_network_interfaces()
for iface in interfaces:
    print(f"Interface: {iface.name}")
    print(f"  MAC: {iface.mac_address}")
    print(f"  IPs: {', '.join(iface.ip_addresses)}")
    print(f"  State: {iface.state}")

# Install a package (works across all Linux distros)
print("Installing tcpdump...")
result = vm.install_package("tcpdump")
if result.success:
    print("Package installed successfully")

# Upload a test script
# Use secure temp directory
import tempfile
with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp:
    remote_path = f"/tmp/{os.path.basename(tmp.name)}"  # nosec B108
vm.upload_file("local_test_script.py", remote_path)

# Execute the test script
result = vm.execute_command("python3 /tmp/test_script.py")
print(f"Test output: {result.stdout}")

# Get system information
cpu_info = vm.get_cpu_info()
memory_info = vm.get_memory_info()
disk_usage = vm.get_disk_usage()

print(f"CPU: {cpu_info['count']} cores, {cpu_info['model']}")
print(f"Memory: {memory_info['total'] / 1024 / 1024 / 1024:.2f} GB")
print(f"Disk usage:")
for disk in disk_usage:
    print(f"  {disk['filesystem']}: {disk['use_percent']}% used")

# Work with Windows VM
windows_vm = client.get_vm("test-windows-vm")
windows_vm.connect(username="Administrator", password=os.getenv("WINDOWS_PASSWORD", "your_windows_password"))

# Same API works for Windows
result = windows_vm.execute_command("ipconfig /all")
print(f"Windows network config: {result.stdout}")

# Configure Windows network (same API)
windows_vm.configure_network(NetworkConfig(
    interface="Ethernet0",
    ip_address="192.168.100.20",
    netmask="255.255.255.0",
    gateway="192.168.100.1"
))

# Install software on Windows
windows_vm.install_package("7zip")  # Would use chocolatey or similar

# Execute PowerShell on Windows
result = windows_vm.execute_powershell("Get-Service | Where-Object {$_.Status -eq 'Running'}")
print(f"Running services: {result.stdout}")

# Batch operations across multiple VMs
vm_names = ["test-vm-1", "test-vm-2", "test-vm-3"]
vms = [client.get_vm(name) for name in vm_names]

# Configure all VMs in parallel
for i, vm in enumerate(vms):
    vm.configure_network(NetworkConfig(
        interface="eth1",
        ip_address=f"192.168.100.{10 + i}",
        netmask="255.255.255.0",
        gateway="192.168.100.1",
        vlan_id=100
    ))

# Clone a VM for testing
print("Cloning VM...")
new_vm = client.clone_vm(
    source_vm_name="test-template",
    new_vm_name="test-clone-01",
    power_on=True
)

# Work with containers (Rocky Linux 9)
container = client.get_container("rocky9-test")
container.connect()

# Same API for containers
result = container.execute_command("dnf update -y")
container.configure_network(network_config)

# Cleanup
vm.disconnect()
windows_vm.disconnect()
client.disconnect()