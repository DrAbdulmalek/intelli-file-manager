"""نظام الإضافات — Plugin System for IntelliFile Manager

Allows extending functionality through plugins that register:
  - Custom file classifiers
  - Custom search engines
  - Custom NER extractors
  - Custom tag generators
  - Custom file processors

Plugins are discovered from:
  1. src/plugins/ directory (built-in plugins)
  2. ~/.intellifile/plugins/ directory (user plugins)
  3. PYTHONPATH-accessible packages with intellifile_plugin entry point
"""

from __future__ import annotations

import importlib
import inspect
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class IntelliFilePlugin(ABC):
    """Base class for all IntelliFile plugins."""
    
    name: str = "unnamed_plugin"
    version: str = "0.1.0"
    description: str = ""
    
    @abstractmethod
    def initialize(self, context: 'PluginContext') -> None:
        """Initialize the plugin with the application context."""
        pass
    
    def shutdown(self) -> None:
        """Cleanup when the plugin is unloaded."""
        pass


class PluginContext:
    """Application context passed to plugins during initialization.
    
    Provides access to core engines and plugin registration methods.
    """
    
    def __init__(self):
        self._classifiers: dict[str, Callable] = {}
        self._search_engines: dict[str, Any] = {}
        self._ner_extractors: dict[str, Callable] = {}
        self._tag_generators: dict[str, Callable] = {}
        self._file_processors: dict[str, Callable] = {}
    
    def register_classifier(self, name: str, fn: Callable) -> None:
        self._classifiers[name] = fn
        logger.info(f"Plugin registered classifier: {name}")
    
    def register_search_engine(self, name: str, engine: Any) -> None:
        self._search_engines[name] = engine
        logger.info(f"Plugin registered search engine: {name}")
    
    def register_ner_extractor(self, name: str, fn: Callable) -> None:
        self._ner_extractors[name] = fn
        logger.info(f"Plugin registered NER extractor: {name}")
    
    def register_tag_generator(self, name: str, fn: Callable) -> None:
        self._tag_generators[name] = fn
        logger.info(f"Plugin registered tag generator: {name}")
    
    def register_file_processor(self, name: str, fn: Callable) -> None:
        self._file_processors[name] = fn
        logger.info(f"Plugin registered file processor: {name}")
    
    @property
    def classifiers(self) -> dict:
        return self._classifiers
    
    @property
    def search_engines(self) -> dict:
        return self._search_engines
    
    @property
    def ner_extractors(self) -> dict:
        return self._ner_extractors
    
    @property
    def tag_generators(self) -> dict:
        return self._tag_generators
    
    @property
    def file_processors(self) -> dict:
        return self._file_processors


class PluginManager:
    """Manages plugin discovery, loading, and lifecycle."""
    
    def __init__(self):
        self._plugins: dict[str, IntelliFilePlugin] = {}
        self._context = PluginContext()
    
    def discover_plugins(self) -> list[str]:
        """Discover plugins from built-in and user plugin directories."""
        plugin_dirs = [
            Path(__file__).parent,  # src/plugins/
            Path.home() / ".intellifile" / "plugins",
        ]
        
        discovered = []
        for plugin_dir in plugin_dirs:
            if not plugin_dir.is_dir():
                continue
            for item in plugin_dir.iterdir():
                if item.is_file() and item.suffix == ".py" and not item.name.startswith("_"):
                    discovered.append(item.stem)
                elif item.is_dir() and (item / "__init__.py").exists():
                    discovered.append(item.name)
        
        logger.info(f"Discovered {len(discovered)} plugins: {discovered}")
        return discovered
    
    def load_plugin(self, name: str) -> bool:
        """Load a plugin by name."""
        if name in self._plugins:
            logger.warning(f"Plugin {name} already loaded")
            return True
        
        try:
            # Try built-in plugins first
            module_name = f"src.plugins.{name}"
            try:
                mod = importlib.import_module(module_name)
            except ImportError:
                mod = importlib.import_module(name)
            
            # Find plugin classes
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if (inspect.isclass(attr) 
                    and issubclass(attr, IntelliFilePlugin) 
                    and attr is not IntelliFilePlugin):
                    plugin = attr()
                    plugin.initialize(self._context)
                    self._plugins[plugin.name] = plugin
                    logger.info(f"Loaded plugin: {plugin.name} v{plugin.version}")
                    return True
            
            logger.warning(f"No IntelliFilePlugin subclass found in {name}")
            return False
        except Exception as exc:
            logger.error(f"Failed to load plugin {name}: {exc}")
            return False
    
    def load_all(self) -> int:
        """Discover and load all plugins."""
        count = 0
        for name in self.discover_plugins():
            if self.load_plugin(name):
                count += 1
        return count
    
    def unload_plugin(self, name: str) -> None:
        """Unload a plugin."""
        if name in self._plugins:
            self._plugins[name].shutdown()
            del self._plugins[name]
            logger.info(f"Unloaded plugin: {name}")
    
    def shutdown_all(self) -> None:
        """Shutdown all plugins."""
        for name in list(self._plugins.keys()):
            self.unload_plugin(name)
    
    @property
    def context(self) -> PluginContext:
        return self._context
    
    @property
    def loaded_plugins(self) -> list[str]:
        return list(self._plugins.keys())
