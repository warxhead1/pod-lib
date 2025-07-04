"""
Base classes for vSphere mock objects
"""
import weakref
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock


class MockVSphereObject:
    """Base class for all vSphere mock objects"""
    
    def __init__(self):
        self._properties = {}
        self._children = {}
        self._parent = None
        self._ref_count = 0
        
    def __getattr__(self, name: str) -> Any:
        """Dynamic property access"""
        if name in self._properties:
            return self._properties[name]
        
        # Handle nested property access (e.g., config.name)
        if '.' in name:
            parts = name.split('.')
            obj = self
            for part in parts:
                if hasattr(obj, part):
                    obj = getattr(obj, part)
                elif hasattr(obj, '_properties') and part in obj._properties:
                    obj = obj._properties[part]
                else:
                    return None
            return obj
            
        # Return None for undefined attributes to avoid AttributeError
        return None
    
    def __setattr__(self, name: str, value: Any) -> None:
        """Property assignment tracking"""
        if name.startswith('_'):
            super().__setattr__(name, value)
        else:
            if not hasattr(self, '_properties'):
                super().__setattr__('_properties', {})
            self._properties[name] = value
    
    def __delattr__(self, name: str) -> None:
        """Handle attribute deletion for patching"""
        if name.startswith('_') or not hasattr(self, '_properties'):
            super().__delattr__(name)
        else:
            if name in self._properties:
                del self._properties[name]
            else:
                super().__delattr__(name)
    
    def add_child(self, child: 'MockVSphereObject') -> None:
        """Add child object relationship"""
        if hasattr(child, '_parent'):
            child._parent = weakref.ref(self)
        child_type = type(child).__name__
        if child_type not in self._children:
            self._children[child_type] = []
        self._children[child_type].append(child)
    
    def get_children(self, object_type: str) -> List['MockVSphereObject']:
        """Get children of specific type"""
        return self._children.get(object_type, [])


class MockDescription(MockVSphereObject):
    """Mock description object"""
    
    def __init__(self, label: str, summary: str = None):
        super().__init__()
        self._properties.update({
            'label': label,
            'summary': summary or label
        })


class MockVirtualDeviceConnectInfo(MockVSphereObject):
    """Mock device connection info"""
    
    def __init__(self, connected: bool = True, start_connected: bool = True):
        super().__init__()
        self._properties.update({
            'startConnected': start_connected,
            'allowGuestControl': True,
            'connected': connected,
            'status': 'ok'
        })