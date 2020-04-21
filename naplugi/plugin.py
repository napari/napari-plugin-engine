import inspect
import sys
from functools import lru_cache
from types import ModuleType
from typing import Dict, List, Optional, Type, Union

from .hooks import HookCaller
from .implementation import HookImpl

ClassOrModule = Union[ModuleType, Type]

if sys.version_info >= (3, 8):
    from importlib import metadata as importlib_metadata
else:
    import importlib_metadata


@lru_cache(maxsize=1)
def module_to_dist() -> Dict[str, importlib_metadata.Distribution]:
    mapping = {}
    for dist in importlib_metadata.distributions():
        modules = dist.read_text('top_level.txt')
        if modules:
            for mod in filter(None, modules.split('\n')):
                mapping[mod] = dist
    return mapping


class Plugin:
    def __init__(
        self, class_or_module: ClassOrModule, name: Optional[str] = None
    ):
        self.object = class_or_module
        self._name = name
        self._hookcallers: List[HookCaller] = []

    def __repr__(self):
        return (
            f'<Plugin "{self.name}" from '
            f'"{self.object}" with {self.nhooks} hooks>'
        )

    @property
    def file(self):
        return self.object.__file__

    @property
    def nhooks(self):
        return len(self._hookcallers)

    @property
    def name(self):
        return self._name or self.get_canonical_name(self.object)

    @classmethod
    def get_canonical_name(cls, plugin: ClassOrModule):
        """ Return canonical name for a plugin object.
        Note that a plugin may be registered under a different name which was
        specified by the caller of :meth:`PluginManager.register(plugin, name)
        <.PluginManager.register>`. To obtain the name of a registered plugin
        use :meth:`get_name(plugin) <.PluginManager.get_name>` instead."""
        return getattr(plugin, "__name__", None) or str(id(plugin))

    def iter_implementations(self, project_name):
        # register matching hook implementations of the plugin
        for name in dir(self.object):
            # check all attributes/methods of plugin and look for functions or
            # methods that have a "{self.project_name}_impl" attribute.
            method = getattr(self.object, name)
            if not inspect.isroutine(method):
                continue
            # TODO, make "_impl" a HookImpl class attribute
            hookimpl_opts = getattr(method, project_name + "_impl", None)
            if not hookimpl_opts:
                continue

            # create the HookImpl instance for this method
            yield HookImpl(method, self, **hookimpl_opts)

    @property
    def dist(self) -> Optional[importlib_metadata.Distribution]:
        top_level = self.object.__module__.split('.')[0]
        return module_to_dist().get(top_level)

    def get_metadata(self, name: str):
        dist = self.dist
        if dist:
            return self.dist.metadata.get(name)
