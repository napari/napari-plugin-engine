import importlib
import inspect
import os
import pkgutil
import sys
import warnings
from contextlib import contextmanager
from functools import lru_cache
from logging import getLogger
from types import ModuleType
from typing import (
    Callable,
    Dict,
    Generator,
    List,
    Optional,
    Tuple,
    Type,
    Union,
    Set,
)

from . import _tracing
from .callers import HookResult
from .exceptions import (
    PluginError,
    PluginImportError,
    PluginRegistrationError,
    PluginValidationError,
)
from .hooks import HookCaller, HookExecFunc
from .implementation import HookImpl

if sys.version_info >= (3, 8):
    from importlib import metadata as importlib_metadata
else:
    import importlib_metadata


logger = getLogger(__name__)
ClassOrModule = Union[ModuleType, Type]


@contextmanager
def temp_path_additions(path: Optional[Union[str, List[str]]]) -> Generator:
    if isinstance(path, str):
        path = [path]
    to_add = [p for p in path if p not in sys.path] if path else []
    for p in to_add:
        sys.path.insert(0, p)
    try:
        yield sys.path
    finally:
        for p in to_add:
            sys.path.remove(p)


class DistFacade:
    """Emulate a pkg_resources Distribution"""

    def __init__(self, dist: Optional[importlib_metadata.Distribution]):
        self._dist = dist

    @property
    def project_name(self) -> str:
        return self.metadata["name"] if self._dist else ''

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
        self._name2plugin: Dict[str, ClassOrModule] = {}
        # mapping of name -> module
        self._plugin2hookcallers: Dict[ClassOrModule, List[HookCaller]] = {}
        self._plugin_distinfo: Dict[ClassOrModule, DistFacade] = {}
        self.trace = _tracing.TagTracer().get("pluginmanage")
        self.hook = _HookRelay(self)
        self.hook._needs_discovery = True
        self._blocked: Set[str] = set()
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

    def discover(
        self, path: Optional[str] = None
    ) -> Tuple[int, List[PluginError]]:
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
        self.hook._needs_discovery = False
        # allow debugging escape hatch
        if os.environ.get("NAPLUGI_DISABLE_PLUGINS"):
            warnings.warn(
                'Plugin discovery disabled due to '
                'environmental variable "NAPLUGI_DISABLE_PLUGINS"'
            )
            return 0, []

        errs: List[PluginError] = []
        with temp_path_additions(path):
            count = 0
            count, errs = self.load_entrypoints(self.discover_entrypoint)
            n, err = self.load_modules_by_prefix(self.discover_prefix)
            count += n
            errs += err
            if count:
                msg = f'loaded {count} plugins:\n  '
                msg += "\n  ".join([n for n, m in self.list_name_plugin()])
                logger.info(msg)

        return count, errs

    @contextmanager
    def discovery_blocked(self) -> Generator:
        current = self.hook._needs_discovery
        self.hook._needs_discovery = False
        try:
            yield
        finally:
            self.hook._needs_discovery = current

    def load_entrypoints(
        self, group: str, name: str = '', ignore_errors=True
    ) -> Tuple[int, List[PluginError]]:
        if (not group) or os.environ.get("NAPLUGI_DISABLE_ENTRYPOINT_PLUGINS"):
            return 0, []
        count = 0
        errors: List[PluginError] = []
        for dist in importlib_metadata.distributions():
            for ep in dist.entry_points:
                if (
                    ep.group != group  # type: ignore
                    or (name and ep.name != name)
                    # already registered
                    or self.get_plugin(ep.name)
                    or self.is_blocked(ep.name)
                ):
                    continue
                err: Optional[PluginError] = None
                try:
                    # this will be a module, class, or possibly function/attr
                    plugin = ep.load()
                except Exception as exc:
                    err = PluginImportError(
                        f'Error while importing plugin "{ep.name}" entry_point'
                        f' "{ep.value}": {str(exc)}',
                        plugin_name=ep.name,
                        manager=self,
                        cause=exc,
                    )
                    errors.append(err)
                    self.set_blocked(ep.name)
                    if ignore_errors:
                        continue
                    raise err
                if not (inspect.isclass(plugin) or inspect.ismodule(plugin)):
                    err = PluginValidationError(
                        f'Plugin "{ep.name}" declared entry_point "{ep.value}"'
                        ' which is neither a module nor a class.',
                        plugin_name=ep.name,
                        manager=self,
                    )
                    errors.append(err)
                    self.set_blocked(ep.name)
                    if ignore_errors:
                        continue
                    raise err
                if self.is_registered(plugin):
                    continue

                self._plugin_distinfo[plugin] = DistFacade(dist)

                try:
                    self.register(plugin, name=ep.name)
                except Exception as exc:
                    err = PluginRegistrationError(
                        plugin_name=ep.name, manager=self, cause=exc,
                    )
                    errors.append(err)
                    self.set_blocked(ep.name)
                    if ignore_errors:
                        continue
                    raise err

                count += 1
        return count, errors

    def load_modules_by_prefix(
        self, prefix: str, ignore_errors=True
    ) -> Tuple[int, List[PluginError]]:
        if not prefix:
            return 0, []
        count = 0
        errors: List[PluginError] = []
        for finder, mod_name, ispkg in pkgutil.iter_modules():
            if mod_name.startswith(prefix):
                if self.get_plugin(mod_name) or self.is_blocked(mod_name):
                    continue
                err: Optional[PluginError] = None
                dist_facade = DistFacade(module_to_dist().get(mod_name))
                name = dist_facade.project_name or mod_name
                try:
                    plugin = importlib.import_module(mod_name)
                except Exception as exc:
                    err = PluginImportError(
                        f'Error while importing module {mod_name}',
                        plugin_name=name,
                        manager=self,
                        cause=exc,
                    )
                    errors.append(err)
                    self.set_blocked(mod_name)
                    if ignore_errors:
                        continue
                    raise err
                if self.is_registered(plugin):
                    continue

                self._plugin_distinfo[plugin] = dist_facade
                try:
                    self.register(plugin, name)
                except Exception as exc:
                    err = PluginRegistrationError(
                        plugin_name=name, manager=self, cause=exc,
                    )
                    errors.append(err)
                    self.set_blocked(name)
                    if ignore_errors:
                        continue
                    raise err

                count += 1

        return count, errors

    def register(self, plugin: ClassOrModule, name=None):
        """Register a plugin and return its canonical name or ``None``.

        Parameters
        ----------
        plugin : ClassOrModule
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

        if self.is_blocked(plugin_name):
            return

        if (
            plugin_name in self._name2plugin
            or plugin in self._plugin2hookcallers
        ):
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

    def set_blocked(self, plugin_name: str, blocked=True):
        """ block registrations of the given name, unregister if already registered. """
        if blocked:
            self.unregister(name=plugin_name)
            self._blocked.add(plugin_name)
        else:
            if plugin_name in self._blocked:
                self._blocked.remove(plugin_name)

    def is_blocked(self, plugin_name: str) -> bool:
        """ return ``True`` if the given plugin name is blocked. """
        return plugin_name in self._blocked

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
        self, module_or_class: ClassOrModule, name: str
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

    def get_errors(
        self,
        plugin_name: str = Ellipsis,
        error_type: Type[BaseException] = Ellipsis,
    ) -> List[PluginError]:
        """Return a list of PluginErrors associated with this manager."""
        return PluginError.get(
            manager=self, plugin_name=plugin_name, error_type=error_type
        )

    def _verify_hook(self, hook, hookimpl):
        if hook.is_historic() and hookimpl.hookwrapper:
            raise PluginValidationError(
                f"Plugin {hookimpl.plugin_name!r}\nhook "
                f"{hook.name!r}\nhistoric incompatible to hookwrapper",
                plugin_name=hookimpl.plugin_name,
                manager=self,
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
                f"Plugin {hookimpl.plugin_name!r} for hook {hook.name!r}\n"
                f"hookimpl definition: {_formatdef(hookimpl.function)}\n"
                f"Argument(s) {notinspec} are declared in the hookimpl but "
                "can not be found in the hookspec",
                plugin_name=hookimpl.plugin_name,
                manager=self,
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
                                f"unknown hook {name!r} in "
                                f"plugin {hookimpl.plugin!r}",
                                plugin_name=hookimpl.plugin_name,
                                manager=self,
                            )

    def list_plugin_distinfo(self):
        """ return list of distinfo/plugin tuples for all setuptools registered
        plugins. """
        return list(self._plugin_distinfo.items())

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


@lru_cache(maxsize=1)
def module_to_dist():
    mapping = {}
    for dist in importlib_metadata.distributions():
        modules = dist.read_text('top_level.txt')
        if modules:
            for mod in filter(None, modules.split('\n')):
                mapping[mod] = dist
    return mapping
