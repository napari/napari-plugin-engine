import importlib
import inspect
import os
import pkgutil
import sys
import warnings
from logging import getLogger
from types import ModuleType
from typing import (
    Dict,
    Generator,
    Optional,
    Tuple,
    Union,
    List,
    Callable,
    Type,
)

from . import _tracing
from .callers import HookResult
from .hooks import HookCaller, HookExecFunc
from .implementation import HookImpl
from .exceptions import (
    PluginError,
    PluginImportError,
    PluginRegistrationError,
    PluginValidationError,
)

if sys.version_info >= (3, 8):
    from importlib import metadata as importlib_metadata
else:
    import importlib_metadata


logger = getLogger(__name__)


class DistFacade:
    """Emulate a pkg_resources Distribution"""

    def __init__(self, dist: importlib_metadata.Distribution):
        self._dist = dist

    @property
    def project_name(self) -> str:
        return self.metadata["name"]

    def __getattr__(self, attr, default=None):
        return getattr(self._dist, attr, default)

    def __dir__(self):
        return sorted(dir(self._dist) + ["_dist", "project_name"])


class PluginManager:
    """ Core :py:class:`.PluginManager` class which manages registration
    of plugin objects and 1:N hook calling.

    You can register new hooks by calling
    :py:meth:`add_hookspecs(module_or_class) <.PluginManager.add_hookspecs>`.
    You can register plugin objects (which contain hooks) by calling
    :py:meth:`register(plugin) <.PluginManager.register>`.  The
    :py:class:`.PluginManager` is initialized with a prefix that is searched
    for in the names of the dict of registered plugin objects.

    For debugging purposes you can call
    :py:meth:`.PluginManager.enable_tracing` which will subsequently send debug
    information to the trace helper.
    """

    def __init__(
        self,
        project_name: str,
        *,
        autodiscover: Union[bool, str] = False,
        discover_entrypoint: str = '',
        discover_prefix: str = '',
    ):
        self.project_name = project_name
        # mapping of name -> module
        self._name2plugin: Dict[str, ModuleType] = {}
        # mapping of name -> module
        self._plugin2hookcallers: Dict[ModuleType, List[HookCaller]] = {}
        self._plugin_distinfo: List[Tuple[ModuleType, DistFacade]] = []
        self.trace = _tracing.TagTracer().get("pluginmanage")
        self.hook = _HookRelay(self)
        self.hook._needs_discovery = True

        # a dict to store package metadata for each plugin, will be populated
        # during self._register_module
        # possible keys for this dict will be set by fetch_module_metadata()
        # TODO: merge this with _plugin_distinfo
        self._plugin_meta: Dict[str, Dict[str, str]] = dict()

        # discover external plugins
        self.discover_entrypoint = discover_entrypoint
        self.discover_prefix = discover_prefix
        if autodiscover:
            if isinstance(autodiscover, str):
                self.discover(autodiscover)
            else:
                self.discover()

        self._inner_hookexec: HookExecFunc = lambda c, m, k: c.multicall(
            m, k, firstresult=c.is_firstresult
        )

    @property
    def hooks(self) -> '_HookRelay':
        """An alias for PluginManager.hook"""
        return self.hook

    def _hookexec(
        self, caller: HookCaller, methods: List[HookImpl], kwargs: dict
    ) -> HookResult:
        # called from all hookcaller instances.
        # enable_tracing will set its own wrapping function at
        # self._inner_hookexec
        return self._inner_hookexec(caller, methods, kwargs)

    def discover(self, path: Optional[str] = None) -> int:
        """Discover modules by both naming convention and entry_points

        1) Using naming convention:
            plugins installed in the environment that follow a naming
            convention (e.g. "napari_plugin"), can be discovered using
            `pkgutil`. This also enables easy discovery on pypi

        2) Using package metadata:
            plugins that declare a special key (self.PLUGIN_ENTRYPOINT) in
            their setup.py `entry_points`.  discovered using `pkg_resources`.

        https://packaging.python.org/guides/creating-and-discovering-plugins/

        Parameters
        ----------
        path : str, optional
            If a string is provided, it is added to sys.path before importing,
            and removed at the end. by default True

        Returns
        -------
        count : int
            The number of plugin modules successfully loaded.
        """
        if path is None:
            self.hook._needs_discovery = False

        # allow debugging escape hatch
        if os.environ.get("naplugi_DISABLE_PLUGINS"):
            import warnings

            warnings.warn(
                'Plugin discovery disabled due to '
                'environmental variable "naplugi_DISABLE_PLUGINS"'
            )
            return 0

        if path:
            sys.path.insert(0, path)

        count = 0
        for plugin_name, module_name, meta in iter_plugin_modules(
            prefix=self.discover_prefix, group=self.discover_entrypoint
        ):
            if self.get_plugin(plugin_name) or self.is_blocked(plugin_name):
                continue
            try:
                self._register_module(plugin_name, module_name, meta)
                count += 1
            except PluginError as exc:
                logger.error(exc.format_with_contact_info())
                self.unregister(name=plugin_name)
            except Exception as exc:
                logger.error(
                    f'Unexpected error loading plugin "{plugin_name}": {exc}'
                )
                self.unregister(name=plugin_name)

        if count:
            msg = f'loaded {count} plugins:\n  '
            msg += "\n  ".join([n for n, m in self.list_name_plugin()])
            logger.info(msg)

        if path:
            sys.path.remove(path)

        return count

    # TODO: look to merge this with register()
    def _register_module(
        self, plugin_name: str, module_name: str, meta: Optional[dict] = None
    ):
        """Try to register `module_name` as a plugin named `plugin_name`.

        Parameters
        ----------
        plugin_name : str
            The name given to the plugin in the plugin manager.
        module_name : str
            The importable module name
        meta : dict, optional
            Metadata to be associated with ``plugin_name``.

        Raises
        ------
        PluginImportError
            If an error is raised when trying to import `module_name`
        PluginRegistrationError
            If an error is raised when trying to register the plugin (such as
            a PluginValidationError.)
        """
        if meta:
            meta.update({'plugin': plugin_name})
            self._plugin_meta[plugin_name] = meta
        try:
            mod = importlib.import_module(module_name)
        except Exception as exc:
            raise PluginImportError(plugin_name, module_name) from exc
        try:
            # prevent double registration (e.g. from entry_points)
            if self.is_registered(mod):
                return
            self.register(mod, name=plugin_name)
        except Exception as exc:
            raise PluginRegistrationError(plugin_name, module_name) from exc

    def register(self, plugin: ModuleType, name=None):
        """Register a plugin and return its canonical name or ``None``.

        Parameters
        ----------
        plugin : ModuleType
            The module to register
        name : str, optional
            Optional name for plugin, by default ``get_canonical_name(plugin)``

        Returns
        -------
        str or None
            canonical plugin name, or ``None`` if the name is blocked from
            registering.

        Raises
        ------
        ValueError
            if the plugin is already registered.
        """
        plugin_name = name or self.get_canonical_name(plugin)

        if (
            plugin_name in self._name2plugin
            or plugin in self._plugin2hookcallers
        ):
            if self._name2plugin.get(plugin_name, -1) is None:
                # blocked plugin, return None to indicate no registration
                return
            raise ValueError(
                "Plugin already registered: %s=%s\n%s"
                % (plugin_name, plugin, self._name2plugin)
            )

        # XXX if an error happens we should make sure no state has been
        # changed at point of return
        self._name2plugin[plugin_name] = plugin

        # register matching hook implementations of the plugin
        self._plugin2hookcallers[plugin] = []
        for name in dir(plugin):
            hookimpl_opts = self.parse_hookimpl_opts(plugin, name)
            if hookimpl_opts is not None:
                method = getattr(plugin, name)
                hookimpl = HookImpl(plugin, plugin_name, method, hookimpl_opts)
                name = hookimpl_opts.get("specname") or name
                hook = getattr(self.hook, name, None)
                if hook is None:
                    hook = HookCaller(name, self._hookexec)
                    setattr(self.hook, name, hook)
                elif hook.has_spec():
                    self._verify_hook(hook, hookimpl)
                    hook._maybe_apply_history(hookimpl)
                hook._add_hookimpl(hookimpl)
                self._plugin2hookcallers[plugin].append(hook)
        return plugin_name

    def parse_hookimpl_opts(self, plugin, name):
        method = getattr(plugin, name)
        if not inspect.isroutine(method):
            return
        try:
            res = getattr(method, self.project_name + "_impl", None,)
        except Exception:
            res = {}
        if res is not None and not isinstance(res, dict):
            # false positive
            res = None
        return res

    def unregister(self, plugin=None, name=None):
        """ unregister a plugin object and all its contained hook implementations
        from internal data structures. """
        if name is None:
            assert (
                plugin is not None
            ), "one of name or plugin needs to be specified"
            name = self.get_name(plugin)

        if plugin is None:
            plugin = self.get_plugin(name)

        # if self._name2plugin[name] == None registration was blocked: ignore
        if self._name2plugin.get(name):
            del self._name2plugin[name]

        for hookcaller in self._plugin2hookcallers.pop(plugin, []):
            hookcaller._remove_plugin(plugin)

        return plugin

    def set_blocked(self, name):
        """ block registrations of the given name, unregister if already registered. """
        self.unregister(name=name)
        self._name2plugin[name] = None

    def is_blocked(self, name):
        """ return ``True`` if the given plugin name is blocked. """
        return name in self._name2plugin and self._name2plugin[name] is None

    def add_hookspecs(self, module_or_class):
        """ add new hook specifications defined in the given ``module_or_class``.
        Functions are recognized if they have been decorated accordingly. """
        names = []
        for name in dir(module_or_class):
            spec_opts = self.parse_hookspec_opts(module_or_class, name)
            if spec_opts is not None:
                hc = getattr(self.hook, name, None,)
                if hc is None:
                    hc = HookCaller(
                        name, self._hookexec, module_or_class, spec_opts,
                    )
                    setattr(
                        self.hook, name, hc,
                    )
                else:
                    # plugins registered this hook without knowing the spec
                    hc.set_specification(
                        module_or_class, spec_opts,
                    )
                    for hookfunction in hc.get_hookimpls():
                        self._verify_hook(
                            hc, hookfunction,
                        )
                names.append(name)

        if not names:
            raise ValueError(
                "did not find any %r hooks in %r"
                % (self.project_name, module_or_class,)
            )

    def parse_hookspec_opts(
        self, module_or_class: Union[ModuleType, Type], name: str
    ) -> Optional[dict]:
        method = getattr(module_or_class, name)
        return getattr(method, self.project_name + "_spec", None)

    def get_plugins(self):
        """ return the set of registered plugins. """
        return set(self._plugin2hookcallers)

    def is_registered(self, plugin):
        """ Return ``True`` if the plugin is already registered. """
        return plugin in self._plugin2hookcallers

    def get_canonical_name(self, plugin):
        """ Return canonical name for a plugin object. Note that a plugin
        may be registered under a different name which was specified
        by the caller of :py:meth:`register(plugin, name) <.PluginManager.register>`.
        To obtain the name of an registered plugin use :py:meth:`get_name(plugin)
        <.PluginManager.get_name>` instead."""
        return getattr(plugin, "__name__", None) or str(id(plugin))

    def get_plugin(self, name):
        """ Return a plugin or ``None`` for the given name. """
        return self._name2plugin.get(name)

    def has_plugin(self, name):
        """ Return ``True`` if a plugin with the given name is registered. """
        return self.get_plugin(name) is not None

    def get_name(self, plugin):
        """ Return name for registered plugin or ``None`` if not registered. """
        for (name, val,) in self._name2plugin.items():
            if plugin == val:
                return name

    def _verify_hook(self, hook, hookimpl):
        if hook.is_historic() and hookimpl.hookwrapper:
            raise PluginValidationError(
                hookimpl.plugin,
                "Plugin %r\nhook %r\nhistoric incompatible to hookwrapper"
                % (hookimpl.plugin_name, hook.name,),
            )
        if hook.spec.warn_on_impl:
            warnings.warn_explicit(
                hook.spec.warn_on_impl,
                type(hook.spec.warn_on_impl),
                lineno=hookimpl.function.__code__.co_firstlineno,
                filename=hookimpl.function.__code__.co_filename,
            )

        # positional arg checking
        notinspec = set(hookimpl.argnames) - set(hook.spec.argnames)
        if notinspec:
            raise PluginValidationError(
                hookimpl.plugin,
                "Plugin %r for hook %r\nhookimpl definition: %s\n"
                "Argument(s) %s are declared in the hookimpl but "
                "can not be found in the hookspec"
                % (
                    hookimpl.plugin_name,
                    hook.name,
                    _formatdef(hookimpl.function),
                    notinspec,
                ),
            )

    def check_pending(self):
        """ Verify that all hooks which have not been verified against
        a hook specification are optional, otherwise raise
        :class:`.PluginValidationError`."""
        for name in self.hook.__dict__:
            if name[0] != "_":
                hook = getattr(self.hook, name)
                if not hook.has_spec():
                    for hookimpl in hook.get_hookimpls():
                        if not hookimpl.optionalhook:
                            raise PluginValidationError(
                                hookimpl.plugin,
                                "unknown hook %r in plugin %r"
                                % (name, hookimpl.plugin,),
                            )

    def load_setuptools_entrypoints(self, group, name=None):
        """ Load modules from querying the specified setuptools ``group``.

        :param str group: entry point group to load plugins
        :param str name: if given, loads only plugins with the given ``name``.
        :rtype: int
        :return: return the number of loaded plugins by this call.
        """
        count = 0
        for dist in importlib_metadata.distributions():
            for ep in dist.entry_points:
                if (
                    ep.group != group
                    or (name is not None and ep.name != name)
                    # already registered
                    or self.get_plugin(ep.name)
                    or self.is_blocked(ep.name)
                ):
                    continue
                plugin = ep.load()
                self.register(plugin, name=ep.name)
                self._plugin_distinfo.append((plugin, DistFacade(dist),))
                count += 1
        return count

    def list_plugin_distinfo(self):
        """ return list of distinfo/plugin tuples for all setuptools registered
        plugins. """
        return list(self._plugin_distinfo)

    def list_name_plugin(self):
        """ return list of name/plugin pairs. """
        return list(self._name2plugin.items())

    def getHookCallers(self, plugin):
        """ get all hook callers for the specified plugin. """
        return self._plugin2hookcallers.get(plugin)

    def add_hookcall_monitoring(
        self,
        before: Callable[[str, List[HookImpl], dict], None],
        after: Callable[[HookResult, str, List[HookImpl], dict], None],
    ) -> Callable[[], None]:
        """ add before/after tracing functions for all hooks
        and return an undo function which, when called,
        will remove the added tracers.

        ``before(hook_name, hook_impls, kwargs)`` will be called ahead
        of all hook calls and receive a hookcaller instance, a list
        of HookImpl instances and the keyword arguments for the hook call.

        ``after(outcome, hook_name, hook_impls, kwargs)`` receives the
        same arguments as ``before`` but also a :py:class:`naplugi.callers._Result` object
        which represents the result of the overall hook call.
        """
        oldcall = self._inner_hookexec

        def traced_hookexec(
            caller: HookCaller, impls: List[HookImpl], kwargs: dict
        ):
            before(caller.name, impls, kwargs)
            outcome = HookResult.from_call(
                lambda: oldcall(caller, impls, kwargs)
            )
            after(outcome, caller.name, impls, kwargs)
            return outcome

        self._inner_hookexec = traced_hookexec

        def undo():
            self._inner_hookexec = oldcall

        return undo

    def enable_tracing(self):
        """ enable tracing of hook calls and return an undo function. """
        hooktrace = self.trace.root.get("hook")

        def before(hook_name, methods, kwargs):
            hooktrace.root.indent += 1
            hooktrace(hook_name, kwargs)

        def after(
            outcome, hook_name, methods, kwargs,
        ):
            if outcome.excinfo is None:
                hooktrace(
                    "finish", hook_name, "-->", outcome.result,
                )
            hooktrace.root.indent -= 1

        return self.add_hookcall_monitoring(before, after)

    def subset_hook_caller(self, name, remove_plugins):
        """ Return a new :py:class:`.hooks.HookCaller` instance for the named method
        which manages calls to all registered plugins except the
        ones from remove_plugins. """
        orig = getattr(self.hook, name)
        plugins_to_remove = [
            plug for plug in remove_plugins if hasattr(plug, name)
        ]
        if plugins_to_remove:
            hc = HookCaller(
                orig.name, orig._hookexec, orig.spec.namespace, orig.spec.opts,
            )
            for hookimpl in orig.get_hookimpls():
                plugin = hookimpl.plugin
                if plugin not in plugins_to_remove:
                    hc._add_hookimpl(hookimpl)
                    # we also keep track of this hook caller so it
                    # gets properly removed on plugin unregistration
                    self._plugin2hookcallers.setdefault(plugin, []).append(hc)
            return hc
        return orig


def _formatdef(func):
    return "%s%s" % (func.__name__, str(inspect.signature(func)),)


class _HookRelay:
    """Hook holder object for storing HookCaller instances.

    This object triggers (lazy) discovery of plugins as follows:  When a plugin
    hook is accessed (e.g. plugin_manager.hook.napari_get_reader), if
    ``self._needs_discovery`` is True, then it will trigger autodiscovery on
    the parent plugin_manager. Note that ``PluginManager.__init__`` sets
    ``self.hook._needs_discovery = True`` *after* hook_specifications and
    builtins have been discovered, but before external plugins are loaded.
    """

    def __init__(self, manager: PluginManager):
        self._manager = manager
        self._needs_discovery = False

    def __getattribute__(self, name):
        """Trigger manager plugin discovery when accessing hook first time."""
        if name not in ("_needs_discovery", "_manager",):
            if self._needs_discovery:
                self._manager.discover()
        return object.__getattribute__(self, name)

    def items(self):
        """Iterate through hookcallers, removing private attributes."""
        return [
            (k, val) for k, val in vars(self).items() if not k.startswith("_")
        ]


def entry_points_for(
    group: str,
) -> Generator[
    Tuple[importlib_metadata.Distribution, importlib_metadata.EntryPoint],
    None,
    None,
]:
    """Yield all entry_points matching "group", from any distribution.

    Distribution here refers more specifically to the information in the
    dist-info folder that usually accompanies an installed package.  If a
    package in the environment does *not* have a ``dist-info/entry_points.txt``
    file, then it will not be discovered by this function.

    Note: a single package may provide multiple entrypoints for a given group.

    Parameters
    ----------
    group : str
        The name of the entry point to search.

    Yields
    -------
    tuples
        (Distribution, EntryPoint) objects for each matching EntryPoint
        that matches the provided ``group`` string.

    Example
    -------
    >>> list(entry_points_for('napari.plugin'))
    [(<importlib.metadata.PathDistribution at 0x124f0fe80>,
      EntryPoint(name='napari-reg',value='napari_reg',group='napari.plugin')),
     (<importlib.metadata.PathDistribution at 0x1041485b0>,
      EntryPoint(name='myplug',value='another.module',group='napari.plugin'))]
    """
    for dist in importlib_metadata.distributions():
        for ep in dist.entry_points:
            if ep.group == group:  # type: ignore
                yield dist, ep


def modules_starting_with(prefix: str) -> Generator[str, None, None]:
    """Yield all module names in sys.path that begin with `prefix`.

    Parameters
    ----------
    prefix : str
        The prefix to search

    Yields
    -------
    module_name : str
        Yields names of modules that start with prefix

    """
    for finder, name, ispkg in pkgutil.iter_modules():
        if name.startswith(prefix):
            yield name


def iter_plugin_modules(
    prefix: Optional[str] = None, group: Optional[str] = None
) -> Generator[Tuple[str, str, dict], None, None]:
    """Discover plugins using naming convention and/or entry points.

    This function makes sure that packages that *both* follow the naming
    convention (i.e. starting with `prefix`) *and* provide and an entry point
    `group` will only be yielded once.  Precedence is given to entry points:
    that is, if a package satisfies both critera, only the modules specifically
    listed in the entry points will be yielded.  These MAY or MAY NOT be the
    top level module in the package... whereas with naming convention, it is
    always the top level module that gets imported and registered with the
    plugin manager.

    The NAME of yielded plugins will be the name of the package provided in
    the package METADATA file when found.  This allows for the possibility that
    the plugin name and the module name are not the same: for instance...
    ("napari-plugin", "napari_plugin").

    Plugin packages may also provide multiple entry points, which will be
    registered as plugins of different names.  For instance, the following
    ``setup.py`` entry would register two plugins under the names
    ``myplugin.register`` and ``myplugin.segment``

    .. code-block:: python

        import sys

        setup(
            name="napari-plugin",
            entry_points={
                "napari.plugin": [
                    "myplugin.register = napari_plugin.registration",
                    "myplugin.segment = napari_plugin.segmentation"
                ],
            },
            packages=find_packages(),
        )


    Parameters
    ----------
    prefix : str, optional
        A prefix by which to search module names.  If None, discovery by naming
        convention is disabled., by default None
    group : str, optional
        An entry point group string to search.  If None, discovery by Entry
        Points is disabled, by default None

    Yields
    -------
    plugin_info : tuple
        (plugin_name, module_name, metadata)
    """
    seen_modules = set()
    if group and not os.environ.get("NAPARI_DISABLE_ENTRYPOINT_PLUGINS"):
        for dist, ep in entry_points_for(group):
            match = ep.pattern.match(ep.value)  # type: ignore
            if match:
                module = match.group('module')
                seen_modules.add(module.split(".")[0])
                yield ep.name, module, fetch_module_metadata(dist)
    if prefix and not os.environ.get("NAPARI_DISABLE_NAMEPREFIX_PLUGINS"):
        for module in modules_starting_with(prefix):
            if module not in seen_modules:
                try:
                    name = importlib_metadata.metadata(module).get('Name')
                except Exception:
                    name = None
                yield name or module, module, fetch_module_metadata(module)


def fetch_module_metadata(
    dist: Union[importlib_metadata.Distribution, str]
) -> Dict[str, str]:
    """Attempt to retrieve name, version, contact email & url for a package.

    Parameters
    ----------
    distname : str or Distribution
        Distribution object or name of a distribution.  If a string, it must
        match the *name* of the package in the METADATA file... not the name of
        the module.

    Returns
    -------
    package_info : dict
        A dict with metadata about the package
        Returns None of the distname cannot be found.
    """
    if isinstance(dist, importlib_metadata.Distribution):
        meta = dist.metadata
    else:
        try:
            meta = importlib_metadata.metadata(dist)
        except importlib_metadata.PackageNotFoundError:
            return {}
    return {
        'package': meta.get('Name', ''),
        'version': meta.get('Version', ''),
        'summary': meta.get('Summary', ''),
        'url': meta.get('Home-page') or meta.get('Download-Url', ''),
        'author': meta.get('Author', ''),
        'email': meta.get('Author-Email') or meta.get('Maintainer-Email', ''),
        'license': meta.get('License', ''),
    }
