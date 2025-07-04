"""
Connection management modules
"""

from .base import BaseConnection
from .ssh import SSHConnection
from .winrm import WinRMConnection
from .container import DockerConnection

__all__ = [
    'BaseConnection',
    'SSHConnection',
    'WinRMConnection',
    'DockerConnection'
]