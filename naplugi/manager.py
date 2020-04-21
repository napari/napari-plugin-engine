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
            # TODO: make HookImpl accept a Plugin instance
            # TODO: maybe make this **hookimpl_opts?
            yield HookImpl(self.object, self.name, method, hookimpl_opts)

    @property
    def dist(self) -> Optional[importlib_metadata.Distribution]:
        top_level = self.object.__module__.split('.')[0]
        return module_to_dist().get(top_level)

    def get_metadata(self, name: str):
        dist = self.dist
        if dist:
            return self.dist.metadata.get(name)


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

        self._plugins: Dict[str, Plugin] = {}

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
                msg += "\n  ".join([str(p) for p in self._plugins.values()])
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
                    or self.name_is_registered(ep.name)
                    or self.is_blocked(ep.name)
                ):
                    continue

                try:
                    self._load_and_register(ep, ep.name)
                except PluginError as e:
                    errors.append(e)
                    self.set_blocked(name)
                    if ignore_errors:
                        continue
                    raise e

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
                dist = module_to_dist().get(mod_name)
                name = dist.metadata.get("name") if dist else mod_name
                if self.name_is_registered(name) or self.is_blocked(name):
                    continue

                try:
                    self._load_and_register(mod_name, name)
                except PluginError as e:
                    errors.append(e)
                    self.set_blocked(name)
                    if ignore_errors:
                        continue
                    raise e

                count += 1

        return count, errors

    def _load_and_register(
        self, mod: Union[str, importlib_metadata.EntryPoint], plugin_name
    ):
        try:
            if isinstance(mod, importlib_metadata.EntryPoint):
                mod_name = mod.value
                module = mod.load()
            else:
                mod_name = mod
                module = importlib.import_module(mod)
            if self.module_is_registered(module):
                return 0
        except Exception as exc:
            raise PluginImportError(
                f'Error while importing module {mod_name}',
                plugin_name=plugin_name,
                manager=self,
                cause=exc,
            )
        if not (inspect.isclass(module) or inspect.ismodule(module)):
            raise PluginValidationError(
                f'Plugin "{plugin_name}" declared entry_point "{mod_name}"'
                ' which is neither a module nor a class.',
                plugin_name=plugin_name,
                manager=self,
            )

        try:
            self.register(module, plugin_name)
        except Exception as exc:
            raise PluginRegistrationError(
                plugin_name=plugin_name, manager=self, cause=exc,
            )

    def register(self, class_or_module: ClassOrModule, name=None):
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
        plugin_name = name or Plugin.get_canonical_name(class_or_module)

        if self.is_blocked(plugin_name):
            return

        if self.name_is_registered(plugin_name):
            raise ValueError(f"Plugin name already registered: {plugin_name}")
        if self.module_is_registered(class_or_module):
            raise ValueError(
                f"Plugin module already registered: {class_or_module}"
            )

        _plugin = Plugin(class_or_module, plugin_name)
        self._plugins[plugin_name] = _plugin
        for hookimpl in _plugin.iter_implementations(self.project_name):
            name = hookimpl.get_specname()
            hook_caller = getattr(self.hook, name, None)
            # if we don't yet have a hookcaller by this name, create one.
            if hook_caller is None:
                hook_caller = HookCaller(name, self._hookexec)
                setattr(self.hook, name, hook_caller)
            # otherwise, if it has a specification, validate the new
            # hookimpl against the specification.
            elif hook_caller.has_spec():
                self._verify_hook(hook_caller, hookimpl)
                hook_caller._maybe_apply_history(hookimpl)
            # Finally, add the hookimpl to the hook_caller and the hook
            # caller to the list of callers for this plugin.
            hook_caller._add_hookimpl(hookimpl)
            _plugin._hookcallers.append(hook_caller)

        return plugin_name

    def unregister(
        self, plugin_name: str = '', module: Optional[ClassOrModule] = None,
    ) -> Plugin:
        """ unregister a plugin object and all its contained hook implementations
        from internal data structures. """

        if module is not None:
            if plugin_name:
                warnings.warn(
                    'Both plugin_name and module provided '
                    'to unregister.  Will use module'
                )
            plugin = self.get_plugin_for_module(module)
            if not plugin:
                warnings.warn(f'No plugins registered for module {module}')
                return
            plugin = self._plugins.pop(plugin.name)
        elif plugin_name:
            if plugin_name not in self._plugins:
                warnings.warn(
                    f'No plugins registered under the name {plugin_name}'
                )
                return
            plugin = self._plugins.pop(plugin_name)
        else:
            raise ValueError("One of plugin_name or module must be provided")

        for hook_caller in plugin._hookcallers:
            hook_caller._remove_plugin(plugin.object)

        return plugin

    def set_blocked(self, plugin_name: str, blocked=True):
        """ block registrations of the given name, unregister if already registered. """
        if blocked:
            self._blocked.add(plugin_name)
            if self.name_is_registered(plugin_name):
                self.unregister(plugin_name)
        else:
            if plugin_name in self._blocked:
                self._blocked.remove(plugin_name)

    def is_blocked(self, plugin_name: str) -> bool:
        """ return ``True`` if the given plugin name is blocked. """
        return plugin_name in self._blocked

    def add_hookspecs(self, module_or_class: ClassOrModule):
        """ add new hook specifications defined in the given ``module_or_class``.
        Functions are recognized if they have been decorated accordingly. """
        names = []
        for name in dir(module_or_class):
            method = getattr(module_or_class, name)
            # TODO: make `_spec` a class attribute of HookSpec
            spec_opts = getattr(method, self.project_name + "_spec", None)
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

    def module_is_registered(self, module):
        return any(p.object == module for p in self._plugins.values())

    def name_is_registered(self, plugin_name: str):
        """ Return ``True`` if the plugin is already registered. """
        return plugin_name in self._plugins

    def get_plugin(self, name: str):
        """ Return a plugin or ``None`` for the given name. """
        return self._plugins.get(name)

    def get_plugin_for_module(self, module: ClassOrModule):
        try:
            return next(
                p for p in self._plugins.values() if p.object == module
            )
        except StopIteration:
            return None

    def get_errors(
        self,
        plugin_name: str = Ellipsis,
        error_type: Type[BaseException] = Ellipsis,
    ) -> List[PluginError]:
        """Return a list of PluginErrors associated with this manager."""
        return PluginError.get(
            manager=self, plugin_name=plugin_name, error_type=error_type
        )

    def _verify_hook(self, hook_caller, hookimpl):
        if hook_caller.is_historic() and hookimpl.hookwrapper:
            raise PluginValidationError(
                f"Plugin {hookimpl.plugin_name!r}\nhook "
                f"{hook_caller.name!r}\nhistoric incompatible to hookwrapper",
                plugin_name=hookimpl.plugin_name,
                manager=self,
            )
        if hook_caller.spec.warn_on_impl:
            warnings.warn_explicit(
                hook_caller.spec.warn_on_impl,
                type(hook_caller.spec.warn_on_impl),
                lineno=hookimpl.function.__code__.co_firstlineno,
                filename=hookimpl.function.__code__.co_filename,
            )

        # positional arg checking
        notinspec = set(hookimpl.argnames) - set(hook_caller.spec.argnames)
        if notinspec:
            raise PluginValidationError(
                f"Plugin {hookimpl.plugin_name!r} for hook {hook_caller.name!r}"
                f"\nhookimpl definition: {_formatdef(hookimpl.function)}\n"
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

    def getHookCallers(self, plugin_name):
        """ get all hook callers for the specified plugin. """
        plugin = self._plugins.get(plugin_name)
        return plugin._hookcallers if plugin else None

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


def _formatdef(func):
    return f"{func.__name__}{str(inspect.signature(func))}"


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
def module_to_dist() -> Dict[str, importlib_metadata.Distribution]:
    mapping = {}
    for dist in importlib_metadata.distributions():
        modules = dist.read_text('top_level.txt')
        if modules:
            for mod in filter(None, modules.split('\n')):
                mapping[mod] = dist
    return mapping
