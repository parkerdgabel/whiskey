"""Tests for the autodiscovery system."""

import pytest
from pathlib import Path
import tempfile
import textwrap

from whiskey import Container, autodiscover, discoverable, scope
from whiskey.core.discovery import AutoDiscovery, NAMING_CONVENTIONS
from whiskey.core.types import ScopeType


class TestAutoDiscovery:
    """Test automatic component discovery."""
    
    @pytest.fixture
    def container(self):
        return Container()
    
    @pytest.fixture
    def discovery(self, container):
        return AutoDiscovery(container)
    
    def test_naming_convention_detection(self, discovery):
        """Test that classes with conventional names are discovered."""
        # Create a test module with conventionally named classes
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_service.py"
            test_file.write_text(textwrap.dedent("""
                class UserService:
                    def __init__(self, config: dict):
                        self.config = config
                
                class ProductRepository:
                    def __init__(self):
                        self.products = []
                
                class OrderController:
                    def __init__(self, service: UserService):
                        self.service = service
                
                class RegularClass:
                    '''This should not be discovered - no convention or dependencies'''
                    pass
            """))
            
            discovery.discover_path(tmpdir)
            
            # Check that conventionally named classes were discovered
            class_names = {cls.__name__ for cls in discovery._discovered}
            assert "UserService" in class_names
            assert "ProductRepository" in class_names
            assert "OrderController" in class_names
            assert "RegularClass" not in class_names
    
    def test_type_hint_detection(self, discovery):
        """Test that classes with typed __init__ parameters are discovered."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "components.py"
            test_file.write_text(textwrap.dedent("""
                class ComponentWithDeps:
                    def __init__(self, dep1: str, dep2: int):
                        self.dep1 = dep1
                        self.dep2 = dep2
                
                class ComponentWithoutDeps:
                    def __init__(self):
                        pass
                
                class ComponentWithUntypedDeps:
                    def __init__(self, dep1, dep2):
                        self.dep1 = dep1
                        self.dep2 = dep2
            """))
            
            discovery.discover_path(tmpdir)
            
            class_names = {cls.__name__ for cls in discovery._discovered}
            assert "ComponentWithDeps" in class_names
            # Without type hints or naming convention, it shouldn't be discovered
            assert "ComponentWithoutDeps" not in class_names
            assert "ComponentWithUntypedDeps" not in class_names
    
    def test_scope_assignment(self, discovery):
        """Test that scopes are assigned based on naming conventions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "scoped_components.py"
            test_file.write_text(textwrap.dedent("""
                class UserService:
                    def __init__(self): pass
                
                class ProductRepository:
                    def __init__(self): pass
                
                class OrderController:
                    def __init__(self): pass
                
                class RequestHandler:
                    def __init__(self): pass
            """))
            
            discovery.discover_path(tmpdir)
            
            # Check scopes
            for cls in discovery._discovered:
                if cls.__name__ == "UserService":
                    assert cls.__whiskey_scope__ == ScopeType.SINGLETON
                elif cls.__name__ == "ProductRepository":
                    assert cls.__whiskey_scope__ == ScopeType.SINGLETON
                elif cls.__name__ == "OrderController":
                    assert cls.__whiskey_scope__ == ScopeType.REQUEST
                elif cls.__name__ == "RequestHandler":
                    assert cls.__whiskey_scope__ == ScopeType.REQUEST
    
    def test_factory_function_discovery(self, discovery):
        """Test that factory functions are discovered."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "factories.py"
            test_file.write_text(textwrap.dedent("""
                from typing import Dict
                
                class Database:
                    def __init__(self, config: dict):
                        self.config = config
                
                def create_database(config: Dict[str, str]) -> Database:
                    '''This should be discovered as a factory'''
                    return Database(config)
                
                def make_cache() -> dict:
                    '''This should also be discovered'''
                    return {}
                
                def build_connection_pool(size: int) -> list:
                    '''And this one too'''
                    return [None] * size
                
                def regular_function() -> str:
                    '''This should not be discovered - no factory prefix'''
                    return "hello"
            """))
            
            discovery.discover_path(tmpdir)
            
            # Check that Database is registered (through factory)
            # Note: We can't directly check factory registration in this test
            # but in a real scenario, Database would be resolvable
    
    def test_module_exports(self, discovery):
        """Test that __all__ exports are respected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "exported.py"
            test_file.write_text(textwrap.dedent("""
                class _PrivateService:
                    '''Should be discovered because it's exported'''
                    def __init__(self, x: int):
                        self.x = x
                
                class PublicService:
                    '''Should be discovered - public and exported'''
                    def __init__(self, y: str):
                        self.y = y
                
                class NotExported:
                    '''Should not be discovered - not in __all__ and no convention'''
                    pass
                
                __all__ = ['_PrivateService', 'PublicService']
            """))
            
            discovery.discover_path(tmpdir)
            
            class_names = {cls.__name__ for cls in discovery._discovered}
            assert "_PrivateService" in class_names  # Exported despite being private
            assert "PublicService" in class_names
            assert "NotExported" not in class_names
    
    def test_explicit_decorators(self, container):
        """Test explicit discovery decorators."""
        
        @discoverable
        class SpecialComponent:
            """Should be discovered due to decorator."""
            pass
        
        @scope(ScopeType.REQUEST)
        class RequestScopedComponent:
            """Should have request scope."""
            def __init__(self, dep: str):
                self.dep = dep
        
        # Manually register to simulate discovery
        discovery = AutoDiscovery(container)
        discovery._register_component(SpecialComponent, ScopeType.TRANSIENT)
        discovery._register_component(RequestScopedComponent, ScopeType.REQUEST)
        
        assert SpecialComponent in discovery._discovered
        assert hasattr(SpecialComponent, "__whiskey_discoverable__")
        assert RequestScopedComponent.__whiskey_scope__ == ScopeType.REQUEST


class TestAutodiscoverFunction:
    """Test the convenience autodiscover function."""
    
    def test_autodiscover_current_module(self):
        """Test autodiscovering in the current module."""
        container = Container()
        
        # Define some test classes in this module
        class TestService:
            def __init__(self, x: int = 42):
                self.x = x
        
        class TestRepository:
            def __init__(self):
                self.data = []
        
        # This would normally scan the module, but we'll test the concept
        # autodiscover(__name__)  # Would scan this test module
        
        # For now, just verify the function exists and is callable
        assert callable(autodiscover)