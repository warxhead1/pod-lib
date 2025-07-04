"""
OS abstraction layer modules
"""

from .base import BaseOSHandler, CommandResult, NetworkInterface, NetworkConfig
from .linux import LinuxHandler
from .windows import WindowsHandler
from .container import ContainerHandler, ContainerConnection
from .kubernetes import KubernetesHandler
from .factory import OSHandlerFactory

__all__ = [
    'BaseOSHandler',
    'CommandResult',
    'NetworkInterface',
    'NetworkConfig',
    'LinuxHandler',
    'WindowsHandler',
    'ContainerHandler',
    'ContainerConnection',
    'KubernetesHandler',
    'OSHandlerFactory'
]