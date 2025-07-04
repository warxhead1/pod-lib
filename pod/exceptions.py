"""
POD Library Exceptions
"""

class PODError(Exception):
    """Base exception for all POD errors"""
    def __init__(self, message, code=None, details=None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


class ConnectionError(PODError):
    """Connection-related errors"""
    pass


class OSError(PODError):
    """OS operation errors"""
    pass


class NetworkConfigError(PODError):
    """Network configuration errors"""
    pass


class VMNotFoundError(PODError):
    """VM not found in infrastructure"""
    pass


class AuthenticationError(PODError):
    """Authentication failure"""
    pass


class TimeoutError(PODError):
    """Operation timeout"""
    pass


class CommandExecutionError(PODError):
    """Command execution failure"""
    pass


class ProviderError(PODError):
    """Infrastructure provider errors"""
    pass