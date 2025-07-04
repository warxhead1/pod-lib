"""
Mock service infrastructure classes
"""
from .base import MockVSphereObject
from .inventory import MockFolder, MockDatacenter
from .tasks import MockTask


class MockServiceInstance(MockVSphereObject):
    """Mock ServiceInstance"""
    
    def __init__(self):
        super().__init__()
        self.content = MockContent()
        self.serverClock = MockServerClock()
        
    def RetrieveContent(self):
        """Return the content object"""
        return self.content


class MockContent(MockVSphereObject):
    """Mock ServiceContent"""
    
    def __init__(self):
        super().__init__()
        # Create root folder with sample datacenter
        self.rootFolder = MockFolder("Datacenters")
        datacenter = MockDatacenter("Datacenter1")
        self.rootFolder.add_child(datacenter)
        
        self.viewManager = MockViewManager()
        self.sessionManager = MockSessionManager()
        self.taskManager = MockTaskManager()
        self.searchIndex = MockSearchIndex()
        self.about = MockAboutInfo()
        

class MockViewManager(MockVSphereObject):
    """Mock ViewManager"""
    
    def __init__(self):
        super().__init__()
    
    def CreateContainerView(self, container, type_list, recursive=True):
        """Create container view"""
        return MockContainerView(container, type_list, recursive)


class MockContainerView(MockVSphereObject):
    """Mock ContainerView"""
    
    def __init__(self, container, type_list, recursive=True):
        super().__init__()
        self.view = []
        self._collect_objects(container, type_list, recursive)
    
    def _collect_objects(self, container, type_list, recursive):
        """Collect objects from container"""
        # Simplified object collection - in real implementation would traverse hierarchy
        if hasattr(container, '_children'):
            for child_type, children in container._children.items():
                if any(t in child_type for t in type_list):
                    self.view.extend(children)
                if recursive:
                    for child in children:
                        self._collect_objects(child, type_list, recursive)
        
        # Also check direct properties for objects
        if hasattr(container, '_properties'):
            for prop_name, prop_value in container._properties.items():
                if hasattr(prop_value, '__class__'):
                    class_name = prop_value.__class__.__name__
                    if any(t in class_name for t in type_list):
                        self.view.append(prop_value)
    
    def Destroy(self):
        """Destroy the view"""
        self.view = []


class MockSessionManager(MockVSphereObject):
    """Mock SessionManager"""
    
    def __init__(self):
        super().__init__()
        self.currentSession = MockUserSession()
    
    def Login(self, username, password, locale=None):
        """Mock login"""
        return MockUserSession()
    
    def Logout(self):
        """Mock logout"""
        pass


class MockUserSession(MockVSphereObject):
    """Mock UserSession"""
    
    def __init__(self):
        super().__init__()
        self._properties.update({
            'key': 'session-key-123',
            'userName': 'admin@vsphere.local',
            'fullName': 'Administrator',
            'loginTime': '2023-01-01T00:00:00Z',
            'lastActiveTime': '2023-01-01T00:00:00Z'
        })


class MockTaskManager(MockVSphereObject):
    """Mock TaskManager"""
    
    def __init__(self):
        super().__init__()
        self.recentTask = []
    
    def CreateCollectorForTasks(self, filter_spec):
        """Create task collector"""
        return MockTaskHistoryCollector()


class MockTaskHistoryCollector(MockVSphereObject):
    """Mock TaskHistoryCollector"""
    
    def __init__(self):
        super().__init__()
        self.latestPage = []
    
    def ReadNextTasks(self, max_count):
        """Read next tasks"""
        return []
    
    def DestroyCollector(self):
        """Destroy collector"""
        pass


class MockSearchIndex(MockVSphereObject):
    """Mock SearchIndex"""
    
    def __init__(self):
        super().__init__()
    
    def FindByUuid(self, datacenter, uuid, vm_search=True, instance_uuid=None):
        """Find object by UUID"""
        return None
    
    def FindByInventoryPath(self, inventory_path):
        """Find object by inventory path"""
        return None


class MockAboutInfo(MockVSphereObject):
    """Mock AboutInfo"""
    
    def __init__(self):
        super().__init__()
        self._properties.update({
            'name': 'VMware vCenter Server',
            'fullName': 'VMware vCenter Server 7.0.0 build-12345',
            'vendor': 'VMware, Inc.',
            'version': '7.0.0',
            'build': '12345',
            'apiType': 'VirtualCenter',
            'apiVersion': '7.0',
            'productLineId': 'vpx'
        })


class MockServerClock(MockVSphereObject):
    """Mock server clock"""
    
    def __init__(self):
        super().__init__()
        import datetime
        self._properties.update({
            'time': datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
        })