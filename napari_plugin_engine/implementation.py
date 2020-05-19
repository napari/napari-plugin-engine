import inspect
import sys
from typing import Callable, Optional, Any, List
from .config import napari_config


class HookImplementation:
    """A class to encapsulate hook implementations."""

    TAG_SUFFIX = "_impl"

    def __init__(
        self,
        function: Callable,
        plugin: Optional[Any] = None,
        plugin_name: str = '',
        hookwrapper: bool = False,
        optionalhook: bool = False,
        tryfirst: bool = False,
        trylast: bool = False,
        specname: str = '',
        enabled: bool = True,
    ):
        self.function = function
        self.argnames, self.kwargnames = varnames(self.function)
        self.plugin = plugin
        self.plugin_name = plugin_name
        self.hookwrapper = hookwrapper
        self.optionalhook = optionalhook
        self.tryfirst = tryfirst
        self.trylast = trylast
        self._specname = specname
        self._config_key = (
            f"plugin_manager.hooks.{self.specname}.disabled_plugins"
        )
        self._enabled = enabled

    @property
    def enabled(self):
        if self.plugin_name in (napari_config.get(self._config_key, []) or []):
            return False
        else:
            return self._enabled

    @enabled.setter
    def enabled(self, val: bool):
        if val == self._enabled:
            return
        self._enabled = val
        disabled: List[str] = list(
            napari_config.get(self._config_key, []) or []
        )
        if not val:
            disabled = list(set(disabled + [self.plugin_name]))
        else:
            try:
                disabled.remove(self.plugin_name)
            except ValueError:
                pass
        # if there's nothing left, clean up the key entirely
        if disabled:
            napari_config.set({self._config_key: disabled})
        else:
            napari_config.pop(self._config_key)

    @classmethod
    def format_tag(cls, project_name):
        return project_name + cls.TAG_SUFFIX

    @property
    def opts(self) -> dict:
        # legacy
        return {
            x: getattr(self, x)
            for x in [
                'hookwrapper',
                'optionalhook',
                'tryfirst',
                'trylast',
                'specname',
            ]
        }

    def __repr__(self) -> str:
        # these are all False by default
        truthy = [
            attr
            for attr in ('hookwrapper', 'optionalhook', 'tryfirst', 'trylast')
            if getattr(self, attr)
        ]
        suffix = (' ' + " ".join(truthy)) if truthy else ''
        disabled = not self.enabled
        return (
            f"<HookImplementation plugin={self.plugin_name!r} spec="
            f"{self.specname!r}{suffix}{' DISABLED' if disabled else ''}>"
        )

    def __call__(self, *args):
        return self.function(*args)

    @property
    def specname(self) -> str:
        return self._specname or self.function.__name__


class HookSpecification:
    """A class to encapsulate hook specifications."""

    TAG_SUFFIX = "_spec"

    def __init__(
        self,
        namespace: Any,
        name: str,
        *,
        firstresult: bool = False,
        historic: bool = False,
        warn_on_impl: Optional[Warning] = None,
    ):
        self.namespace = namespace
        self.name = name
        self.function = getattr(namespace, name)
        self.argnames, self.kwargnames = varnames(self.function)
        for reserved in ('_plugin', '_skip_impls'):
            if reserved in self.argnames:
                raise ValueError(
                    f'Hook specifications may not have argument: "{reserved}".'
                )
        self.firstresult = firstresult
        self.historic = historic
        self.warn_on_impl = warn_on_impl

    @classmethod
    def format_tag(cls, project_name):
        return project_name + cls.TAG_SUFFIX

    @property
    def opts(self) -> dict:
        # legacy
        return {
            'firstresult': self.firstresult,
            'historic': self.historic,
            'warn_on_impl': self.warn_on_impl,
        }

    def __repr__(self) -> str:
        # these are all False by default
        truthy = [
            attr
            for attr in ('firstresult', 'historic', 'warn_on_impl')
            if getattr(self, attr)
        ]
        suffix = (' ' + " ".join(truthy)) if truthy else ''
        return (
            f"<HookSpecification {self.name!r} args={self.argnames!r}{suffix}>"
        )


# TODO: can this be improved?
def varnames(func):
    """Return tuple of positional and keywrord argument names for a function,
    method, class or callable.

    In case of a class, its ``__init__`` method is considered.
    For methods the ``self`` parameter is not included.
    """
    cache = getattr(func, "__dict__", {})
    try:
        return cache["_varnames"]
    except KeyError:
        pass

    if inspect.isclass(func):
        try:
            func = func.__init__
        except AttributeError:
            return (), ()
    elif not inspect.isroutine(func):  # callable object?
        try:
            func = getattr(func, "__call__", func)
        except Exception:
            return (), ()

    try:  # func MUST be a function or method here or we won't parse any args
        spec = inspect.getfullargspec(func)
    except TypeError:
        return (), ()

    args, defaults = tuple(spec.args), spec.defaults
    if defaults:
        index = -len(defaults)
        args, kwargs = args[:index], tuple(args[index:])
    else:
        kwargs = ()

    # strip any implicit instance arg
    # pypy3 uses "obj" instead of "self" for default dunder methods
    _PYPY3 = hasattr(sys, "pypy_version_info") and sys.version_info.major == 3
    implicit_names = ("self",) if not _PYPY3 else ("self", "obj")
    if args:
        if inspect.ismethod(func) or (
            "." in getattr(func, "__qualname__", ())
            and args[0] in implicit_names
        ):
            args = args[1:]

    try:
        cache["_varnames"] = args, kwargs
    except TypeError:
        pass
    return args, kwargs
