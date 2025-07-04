"""
Mock task and task management classes
"""
import threading
import time
from typing import Any, Optional
from .base import MockVSphereObject


class MockTask(MockVSphereObject):
    """Mock Task object for async operations"""
    
    def __init__(self, operation: str = "GenericTask", result: Any = None):
        super().__init__()
        self._properties.update({
            'info': MockTaskInfo(operation, result),
            'key': f'task-{id(self)}'
        })
    
    def complete_successfully(self, result: Any = None):
        """Complete the task successfully"""
        self.info.state = 'success'
        if result is not None:
            self.info.result = result
    
    def fail_with_error(self, error: str):
        """Fail the task with an error"""
        self.info.state = 'error'
        self.info.error = MockTaskError(error)


class MockTaskInfo(MockVSphereObject):
    """Mock TaskInfo object"""
    
    def __init__(self, operation: str, result: Any = None):
        super().__init__()
        self._properties.update({
            'key': f'task-{id(self)}',
            'task': None,  # Will be set by parent task
            'name': f'vim.vm.{operation}',
            'descriptionId': operation,
            'entityName': 'mock-entity',
            'state': 'running',
            'cancelled': False,
            'cancelable': True,
            'error': None,
            'result': result,
            'progress': 0,
            'startTime': time.time(),
            'completeTime': None
        })


class MockTaskError(MockVSphereObject):
    """Mock task error"""
    
    def __init__(self, message: str):
        super().__init__()
        self._properties.update({
            'localizedMessage': message,
            'fault': MockFault(message)
        })


class MockFault(MockVSphereObject):
    """Mock fault object"""
    
    def __init__(self, message: str):
        super().__init__()
        self._properties.update({
            'msg': message
        })