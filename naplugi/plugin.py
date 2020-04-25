import inspect
import sys
from functools import lru_cache
from typing import (
    Any,
    Dict,
    Generator,
    List,
    Optional,
    overload,
)

from .hooks import HookCaller
from .implementation import HookImpl

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
    """A registered plugin object.

    The actual plugin object that was registered is available at
    ``Plugin.object``, and the plugin name is ``Plugin.name``.

    Metadata from ``dist-info`` is available via :meth:`~.Plugin.get_metadata`
    or :data:`~.Plugin.standard_meta`

    Parameters
    ----------
    namespace : Any
        [description]
    name : Optional[str], optional
        [description], by default None
    """

    def __init__(self, namespace: Any, name: Optional[str] = None):
        self.object = namespace
        self._name = name
        self._hookcallers: List[HookCaller] = []

    def __repr__(self) -> str:
        return (
            f'<Plugin "{self.name}" from '
            f'"{self.object}" with {self.nhooks} hooks>'
        )

    @property
    def nhooks(self) -> int:
        return len(self._hookcallers)

    @property
    def name(self) -> str:
        return self._name or self.get_canonical_name(self.object)

    @classmethod
    def get_canonical_name(cls, namespace: Any) -> str:
        """ Return canonical name for a plugin object.
        Note that a plugin may be registered under a different name which was
        specified by the caller of :meth:`PluginManager.register(plugin, name)
        <.PluginManager.register>`. To obtain the name of a registered plugin
        use :meth:`get_name(plugin) <.PluginManager.get_name>` instead."""
        return getattr(namespace, "__name__", None) or str(id(namespace))

    def iter_implementations(
        self, project_name: str
    ) -> Generator[HookImpl, None, None]:
        # register matching hook implementations of the plugin
        namespace = self.object
        for name in dir(namespace):
            # check all attributes/methods of plugin and look for functions or
            # methods that have a "{self.project_name}_impl" attribute.
            method = getattr(namespace, name)
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

    @property
    def dist(self) -> Optional[importlib_metadata.Distribution]:
        return module_to_dist().get(self.module_name.split('.', 1)[0])

    @property
    def version(self) -> str:
        version = ''
        if self.dist:
            version = self.dist.metadata.get('version')
        if not version and inspect.ismodule(self.object):
            version = getattr(self.object, '__version__')
        if not version:
            top_module = self.module_name.split('.', 1)[0]
            if top_module in sys.modules:
                version = getattr(sys.modules[top_module], '__version__')
        return str(version) if version else ''

    @overload
    def get_metadata(self, arg: str, *args: None) -> Optional[str]:
        ...

    @overload  # noqa: F811
    def get_metadata(  # noqa: F811
        self, arg: str, *args: str
    ) -> Dict[str, Optional[str]]:
        ...

    def get_metadata(self, *args):  # noqa: F811
        """Get metadata for this plugin.

        Valid arguments are any keys from the Core metadata specifications:
        https://packaging.python.org/specifications/core-metadata/

        Parameters
        ----------
        *args : str
            (Case insensitive) names of metadata entries to retrieve.

        Returns
        -------
        str or dict, optional
            If a single argument is provided, the value for that entry is
            returned (which may be ``None``).
            If multiple arguments are provided, a dict of {arg: value} is
            returned.
        """
        dist = self.dist
        dct = {}
        if dist:
            for a in args:
                if a == 'version':
                    dct[a] = self.version
                else:
                    dct[a] = dist.metadata.get(a)
        if dct and len(args) == 1:
            return dct[args[0]]
        return dct

    @property
    def standard_meta(self) -> Dict[str, Optional[str]]:
        meta: Dict[str, Optional[str]] = {'plugin_name': self.name}
        meta['package'] = self.get_metadata('name')
        meta.update(
            self.get_metadata('version', 'summary', 'author', 'license')
        )
        meta['email'] = self.get_metadata('Author-Email') or self.get_metadata(
            'Maintainer-Email'
        )
        meta['url'] = self.get_metadata('Home-page') or self.get_metadata(
            'Download-Url'
        )
        if meta['url'] == 'UNKNOWN':
            meta['url'] = None
        return meta
