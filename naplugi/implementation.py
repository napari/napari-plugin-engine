import inspect
import sys
from types import ModuleType
from typing import Callable, Union, Type, Optional

ClassOrModule = Union[ModuleType, Type]


class HookImpl:
    def __init__(
        self,
        plugin: Optional[ClassOrModule],
        plugin_name: str,
        function: Callable,
        hook_impl_opts: dict,
        enabled: bool = True,
    ):
        self.function = function
        self.argnames, self.kwargnames = varnames(self.function)
        self.plugin = plugin
        self.opts = hook_impl_opts
        self.plugin_name = plugin_name
        self.hookwrapper: bool = False
        self.optionalhook: bool = False
        self.tryfirst: bool = False
        self.trylast: bool = False
        self.specname: str = ''
        self.enabled = enabled
        self.__dict__.update(hook_impl_opts)

    def __repr__(self) -> str:
        return "<HookImpl plugin_name=%r, plugin=%r>" % (
            self.plugin_name,
            self.plugin,
        )

    def __call__(self, *args):
        return self.function(*args)

    def get_specname(self) -> str:
        return self.specname or self.function.__name__


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
