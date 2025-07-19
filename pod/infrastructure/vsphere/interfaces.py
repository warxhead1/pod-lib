from typing import Protocol, Any, List, Optional
from pyVmomi import vim # Import vim types for type hinting

class VSphereClientProtocol(Protocol):
    """
    Protocol defining the expected interface for a vSphere client
    to be used by VMManager and NetworkConfigurator.
    """
    host: str
    username: str
    password: str
    port: int
    disable_ssl_verification: bool

    @property
    def content(self) -> vim.ServiceInstanceContent:
        ...

    def connect(self) -> None:
        ...

    def disconnect(self) -> None:
        ...

    def get_obj(self, vimtype: List, name: str) -> Optional[Any]:
        ...

    def get_vm(self, vm_name: str) -> vim.VirtualMachine:
        ...

    def get_network(self, network_name: str) -> vim.Network:
        ...

    def get_datacenter(self, datacenter_name: Optional[str] = None) -> vim.Datacenter:
        ...

    def wait_for_task(self, task: vim.Task) -> bool:
        ...
