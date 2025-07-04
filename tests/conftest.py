"""
Shared test fixtures and configuration for POD library tests
"""

# Import legacy mocks first to handle missing dependencies
from . import legacy_mocks

import pytest
import paramiko
from unittest.mock import Mock, MagicMock, patch
from pyVmomi import vim, vmodl
from pod.connections.ssh import SSHConnection
from pod.connections.winrm import WinRMConnection
from pod.infrastructure.vsphere.client import VSphereClient
from pod.infrastructure.vsphere.vm_manager import VMManager
from pod.infrastructure.vsphere.network_config import NetworkConfigurator
from pod.os_abstraction.base import NetworkInterface, NetworkConfig, CommandResult
from pod.os_abstraction.linux import LinuxHandler


@pytest.fixture
def mock_vsphere_service_instance():
    """Mock vSphere service instance"""
    from tests.mocks.vsphere import MockServiceInstance
    return MockServiceInstance()


@pytest.fixture
def mock_vsphere_client():
    """Mock vSphere client"""
    client = Mock(spec=VSphereClient)
    client.host = "vcenter.example.com"
    client.username = "admin@vsphere.local"
    client.password = "password"
    client.port = 443
    client._service_instance = Mock()
    client._content = Mock()
    
    # Mock common methods
    client.connect = Mock()
    client.disconnect = Mock()
    client.get_vm = Mock()
    client.get_network = Mock()
    client.get_datacenter = Mock()
    client.wait_for_task = Mock(return_value=True)
    
    return client


@pytest.fixture
def mock_vm():
    """Mock vSphere VM object"""
    from tests.mocks.vsphere import MockVirtualMachine
    vm = MockVirtualMachine("test-vm", "poweredOn")
    
    # Set specific test values
    vm.config.uuid = "vm-uuid-123"
    vm.config.guestId = "rhel8_64Guest"
    vm.config.files.vmPathName = "[datastore1] test-vm/test-vm.vmx"
    vm.guest.hostName = "test-vm"
    vm.guest.ipAddress = "192.168.1.100"
    vm.guest.toolsStatus = "toolsOk"
    vm.guest.toolsVersion = "12345"
    vm.guest.guestFamily = "linuxGuest"
    
    return vm


@pytest.fixture
def mock_network():
    """Mock vSphere network object"""
    from tests.mocks.vsphere import MockNetwork
    network = MockNetwork("test-network")
    network.key = "network-key-123"
    return network


@pytest.fixture
def mock_dvs_portgroup():
    """Mock DVS portgroup"""
    from tests.mocks.vsphere import MockDistributedVirtualPortgroup
    portgroup = MockDistributedVirtualPortgroup("test-portgroup", "dvs-uuid-123")
    portgroup.key = "pg-key-123"
    return portgroup


@pytest.fixture
def mock_network_adapter():
    """Mock network adapter"""
    from tests.mocks.vsphere import MockVirtualVmxnet3
    from tests.mocks.vsphere.network_backing import MockVirtualEthernetCardNetworkBackingInfo
    
    adapter = MockVirtualVmxnet3(4000, "Network adapter 1")
    adapter.macAddress = "00:50:56:12:34:56"
    adapter.backing = MockVirtualEthernetCardNetworkBackingInfo("VM Network")
    return adapter


@pytest.fixture
def mock_ssh_client():
    """Mock SSH client"""
    client = Mock(spec=paramiko.SSHClient)
    client.connect = Mock()
    client.close = Mock()
    client.exec_command = Mock()
    client.open_sftp = Mock()
    client.get_transport = Mock()
    
    # Mock transport
    transport = Mock()
    transport.is_active.return_value = True
    client.get_transport.return_value = transport
    
    return client


@pytest.fixture
def mock_ssh_connection():
    """Mock SSH connection"""
    connection = Mock(spec=SSHConnection)
    connection.host = "192.168.1.100"
    connection.username = "root"
    connection.password = "password"
    connection.port = 22
    connection.timeout = 30
    connection._connected = True
    
    # Mock methods
    connection.connect = Mock()
    connection.disconnect = Mock()
    connection.execute_command = Mock()
    connection.upload_file = Mock(return_value=True)
    connection.download_file = Mock(return_value=True)
    connection.is_connected = Mock(return_value=True)
    
    return connection


@pytest.fixture
def mock_winrm_session():
    """Mock WinRM session"""
    session = Mock()
    session.run_cmd = Mock()
    session.run_ps = Mock()
    
    # Mock result
    result = Mock()
    result.std_out = b"Command output"
    result.std_err = b""
    result.status_code = 0
    session.run_cmd.return_value = result
    session.run_ps.return_value = result
    
    return session


@pytest.fixture
def mock_winrm_connection():
    """Mock WinRM connection"""
    connection = Mock(spec=WinRMConnection)
    connection.host = "192.168.1.101"
    connection.username = "Administrator"
    connection.password = "password"
    connection.port = 5985
    connection.timeout = 30
    connection._connected = True
    
    # Mock methods
    connection.connect = Mock()
    connection.disconnect = Mock()
    connection.execute_command = Mock()
    connection.execute_powershell = Mock()
    connection.upload_file = Mock(return_value=True)
    connection.download_file = Mock(return_value=True)
    connection.is_connected = Mock(return_value=True)
    
    return connection


@pytest.fixture
def sample_command_result():
    """Sample command result"""
    return CommandResult(
        stdout="Command executed successfully",
        stderr="",
        exit_code=0,
        success=True,
        command="echo 'test'",
        duration=0.1
    )


@pytest.fixture
def sample_network_interface():
    """Sample network interface"""
    return NetworkInterface(
        name="eth0",
        mac_address="00:50:56:12:34:56",
        ip_addresses=["192.168.1.100"],
        netmask="255.255.255.0",
        gateway="192.168.1.1",
        vlan_id=None,
        mtu=1500,
        state="up",
        type="ethernet"
    )


@pytest.fixture
def sample_network_config():
    """Sample network configuration"""
    return NetworkConfig(
        interface="eth1",
        ip_address="192.168.100.10",
        netmask="255.255.255.0",
        gateway="192.168.100.1",
        dns_servers=["8.8.8.8", "8.8.4.4"],
        vlan_id=100,
        mtu=1500
    )


@pytest.fixture
def linux_handler_with_mock_connection(mock_ssh_connection):
    """Linux handler with mock SSH connection"""
    handler = LinuxHandler(mock_ssh_connection)
    return handler


@pytest.fixture
def mock_vm_manager(mock_vsphere_client):
    """Mock VM manager"""
    manager = VMManager(mock_vsphere_client)
    return manager


@pytest.fixture
def mock_network_configurator(mock_vsphere_client):
    """Mock network configurator"""
    configurator = NetworkConfigurator(mock_vsphere_client)
    return configurator


@pytest.fixture
def mock_os_release_content():
    """Mock /etc/os-release content"""
    return '''NAME="Rocky Linux"
VERSION="9.0 (Blue Onyx)"
ID="rocky"
ID_LIKE="rhel centos fedora"
VERSION_ID="9.0"
PLATFORM_ID="platform:el9"
PRETTY_NAME="Rocky Linux 9.0 (Blue Onyx)"
ANSI_COLOR="0;32"
CPE_NAME="cpe:/o:rocky:rocky:9::baseos"
HOME_URL="https://rockylinux.org/"
BUG_REPORT_URL="https://bugs.rockylinux.org/"
ROCKY_SUPPORT_PRODUCT="Rocky Linux"
ROCKY_SUPPORT_PRODUCT_VERSION="9"
REDHAT_SUPPORT_PRODUCT="Rocky Linux"
REDHAT_SUPPORT_PRODUCT_VERSION="9"'''


@pytest.fixture
def mock_ip_addr_json():
    """Mock ip addr show JSON output"""
    return '''[
    {
        "ifindex": 1,
        "ifname": "lo",
        "flags": ["LOOPBACK", "UP", "LOWER_UP"],
        "mtu": 65536,
        "qdisc": "noqueue",
        "operstate": "UNKNOWN",
        "group": "default",
        "link_type": "loopback",
        "address": "00:00:00:00:00:00",
        "broadcast": "00:00:00:00:00:00",
        "addr_info": [
            {
                "family": "inet",
                "local": "127.0.0.1",
                "prefixlen": 8,
                "scope": "host",
                "label": "lo",
                "valid_life_time": 4294967295,
                "preferred_life_time": 4294967295
            }
        ]
    },
    {
        "ifindex": 2,
        "ifname": "eth0",
        "flags": ["BROADCAST", "MULTICAST", "UP", "LOWER_UP"],
        "mtu": 1500,
        "qdisc": "fq_codel",
        "operstate": "UP",
        "group": "default",
        "link_type": "ether",
        "address": "00:50:56:12:34:56",
        "broadcast": "ff:ff:ff:ff:ff:ff",
        "addr_info": [
            {
                "family": "inet",
                "local": "192.168.1.100",
                "prefixlen": 24,
                "scope": "global",
                "label": "eth0",
                "valid_life_time": 4294967295,
                "preferred_life_time": 4294967295
            }
        ]
    }
]'''


@pytest.fixture
def mock_ps_aux_output():
    """Mock ps aux output"""
    return '''USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
root         1  0.0  0.1 170504  9088 ?        Ss   Oct01   0:01 /usr/lib/systemd/systemd --switched-root --system --deserialize 18
root         2  0.0  0.0      0     0 ?        S    Oct01   0:00 [kthreadd]
root         3  0.0  0.0      0     0 ?        I<   Oct01   0:00 [rcu_gp]
root         4  0.0  0.0      0     0 ?        I<   Oct01   0:00 [rcu_par_gp]
testuser  1234  0.1  0.5  12345  4096 pts/0    S+   10:30   0:00 python3 test_script.py'''


@pytest.fixture
def mock_df_output():
    """Mock df -h output"""
    return '''Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        20G  5.2G   14G  28% /
devtmpfs        2.0G     0  2.0G   0% /dev
tmpfs           2.0G     0  2.0G   0% /dev/shm
tmpfs           2.0G  8.8M  2.0G   1% /run
tmpfs           2.0G     0  2.0G   0% /sys/fs/cgroup
/dev/sda2       5.0G  1.1G  3.9G  22% /var
tmpfs           394M     0  394M   0% /run/user/1000'''


@pytest.fixture
def mock_free_output():
    """Mock free -b output"""
    return '''              total        used        free      shared  buff/cache   available
Mem:     4147159040   524288000  3000000000    16777216   622870000  3500000000
Swap:    2147483648           0  2147483648           0           0  2147483648'''


@pytest.fixture
def mock_lscpu_output():
    """Mock lscpu output"""
    return '''Architecture:        x86_64
CPU op-mode(s):      32-bit, 64-bit
Byte Order:          Little Endian
CPU(s):              4
On-line CPU(s) list: 0-3
Thread(s) per core:  1
Core(s) per socket:  4
Socket(s):           1
NUMA node(s):        1
Vendor ID:           GenuineIntel
CPU family:          6
Model:               158
Model name:          Intel(R) Core(TM) i7-8565U CPU @ 1.80GHz
Stepping:            10
CPU MHz:             1800.000
CPU max MHz:         4600.0000
CPU min MHz:         400.0000
BogoMIPS:            4001.60
Virtualization:      VT-x
L1d cache:           32K
L1i cache:           32K
L2 cache:            256K
L3 cache:            8192K
NUMA node0 CPU(s):   0-3
Flags:               fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush dts acpi mmx fxsr sse sse2 ss ht tm pbe syscall nx pdpe1gb rdtscp lm constant_tsc art arch_perfmon pebs bts rep_good nopl xtopology nonstop_tsc cpuid aperfmperf tsc_known_freq pni pclmulqdq dtes64 monitor ds_cpl vmx est tm2 ssse3 sdbg fma cx16 xtpr pdcm pcid sse4_1 sse4_2 x2apic movbe popcnt tsc_deadline_timer aes xsave avx f16c rdrand lahf_lm abm 3dnowprefetch cpuid_fault epb invpcid_single pti ssbd ibrs ibpb stibp tpr_shadow vnmi flexpriority ept vpid ept_ad fsgsbase tsc_adjust bmi1 hle avx2 smep bmi2 erms invpcid rtm mpx rdseed adx smap clflushopt intel_pt xsaveopt xsavec xgetbv1 xsaves dtherm ida arat pln pts hwp hwp_notify hwp_act_window hwp_epp md_clear flush_l1d'''


# Mock decorators for common patches
@pytest.fixture
def patch_paramiko_ssh_client():
    """Patch paramiko.SSHClient"""
    with patch('paramiko.SSHClient') as mock:
        yield mock


@pytest.fixture
def patch_winrm_session():
    """Patch winrm.Session"""
    with patch('winrm.Session') as mock:
        yield mock


@pytest.fixture
def patch_vsphere_connect():
    """Patch vSphere connect"""
    with patch('pyVim.connect.SmartConnect') as mock:
        yield mock


@pytest.fixture
def patch_vsphere_disconnect():
    """Patch vSphere disconnect"""
    with patch('pyVim.connect.Disconnect') as mock:
        yield mock


# Test data fixtures
@pytest.fixture
def vm_test_data():
    """Test data for VM operations"""
    return {
        'vm_name': 'test-vm',
        'vm_uuid': 'vm-uuid-123',
        'ip_address': '192.168.1.100',
        'hostname': 'test-vm.example.com',
        'os_type': 'linux',
        'power_state': 'poweredOn'
    }


@pytest.fixture
def network_test_data():
    """Test data for network operations"""
    return {
        'interface': 'eth1',
        'ip_address': '192.168.100.10',
        'netmask': '255.255.255.0',
        'gateway': '192.168.100.1',
        'vlan_id': 100,
        'network_name': 'test-network',
        'adapter_label': 'Network adapter 1'
    }


@pytest.fixture
def connection_test_data():
    """Test data for connection operations"""
    return {
        'ssh_host': '192.168.1.100',
        'ssh_username': 'root',
        'ssh_password': 'password',
        'ssh_port': 22,
        'winrm_host': '192.168.1.101',
        'winrm_username': 'Administrator',
        'winrm_password': 'password',
        'winrm_port': 5985
    }


@pytest.fixture
def vsphere_test_data():
    """Test data for vSphere operations"""
    return {
        'host': 'vcenter.example.com',
        'username': 'admin@vsphere.local',
        'password': 'password',
        'port': 443,
        'datacenter': 'Datacenter1',
        'cluster': 'Cluster1',
        'datastore': 'datastore1'
    }