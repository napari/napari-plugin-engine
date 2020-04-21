import inspect
import sys
from types import ModuleType
from typing import Callable, Union, Type, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .manager import Plugin  # noqa: F401

ClassOrModule = Union[ModuleType, Type]


class HookImpl:
    def __init__(
        self,
        function: Callable,
        plugin: Optional['Plugin'] = None,
        hookwrapper: bool = False,
        optionalhook: bool = False,
        tryfirst: bool = False,
        trylast: bool = False,
        specname: str = '',
        enabled: bool = True,
    ):
        self.function = function
        self.argnames, self.kwargnames = varnames(self.function)
        self._plugin = plugin
        self.hookwrapper = hookwrapper
        self.optionalhook = optionalhook
        self.tryfirst = tryfirst
        self.trylast = trylast
        self._specname = specname
        self.enabled = enabled

    @property
    def plugin(self):
        return self._plugin.object if self._plugin else None

    @property
    def plugin_name(self):
        return self._plugin.name if self._plugin else None

    @property
    def opts(self):
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
        return "<HookImpl plugin_name=%r, plugin=%r>" % (
            self.plugin_name,
            self.plugin,
        )

    def __call__(self, *args):
        return self.function(*args)

    @property
    def specname(self) -> str:
        return self._specname or self.function.__name__


class HookSpec:
    def __init__(self, namespace: ClassOrModule, name: str, opts: dict):
        self.namespace = namespace
        self.function = function = getattr(namespace, name)
        self.name = name
        self.argnames, self.kwargnames = varnames(function)
        self.opts = opts
        self.warn_on_impl = opts.get("warn_on_impl")


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