import inspect
import sys
from functools import lru_cache, cached_property
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
    def module_name(self):
        if inspect.ismodule(self.object):
            return self.object.__name__
        else:
            return self.object.__module__

    @cached_property
    def dist(self) -> Optional[importlib_metadata.Distribution]:
        return module_to_dist().get(self.module_name.split('.', 1)[0])

    @property
    def version(self) -> str:
        version = self.dist.metadata.get('version')
        if not version and inspect.ismodule(self.object):
            version = getattr(self.object, '__version__')
        if not version:
            top_module = self.module_name.split('.', 1)[0]
            if top_module in sys.modules:
                version = getattr(sys.modules[top_module], '__version__')
        return str(version) if version else ''

    def get_metadata(self, *args: List[str]) -> Union[str, Dict[str, str]]:
        dist = self.dist
        dct = {}
        if dist:
            for a in args:
                if a == 'version':
                    dct[a] = self.version
                else:
                    dct[a] = self.dist.metadata.get(a)
        if dct and len(args) == 1:
            return dct[args[0]]
        return dct

    @property
    def standard_meta(self) -> dict:
        meta = dict(plugin_name=self.name)
        meta['package'] = self.get_metadata('name')
        meta.update(
            self.get_metadata('version', 'summary', 'author', 'license',)
        )
        meta['email'] = self.get_metadata('Author-Email') or self.get_metadata(
            'Maintainer-Email'
        )
        meta['url'] = self.get_metadata('Home-page') or self.get_metadata(
            'Download-Url'
        )
        return meta
