"""
POD - Platform-agnostic OS Deployment Library
A unified interface for multi-OS testing with network devices
"""

__version__ = "0.1.0"
__author__ = "POD Development Team"

from .client import PODClient
from .exceptions import PODError, ConnectionError, OSError, NetworkConfigError

__all__ = [
    "PODClient",
    "PODError",
    "ConnectionError",
    "OSError",
    "NetworkConfigError",
]