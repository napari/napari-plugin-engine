"""Call loop machinery.ƒ"""
import sys
from types import TracebackType
from typing import Any, List, Optional, Tuple, Union, Type
from .exceptions import PluginCallError, HookCallError
from .implementation import HookImpl


def _raise_wrapfail(wrap_controller, msg):
    co = wrap_controller.gi_code
    raise RuntimeError(
        "wrap_controller at %r %s:%d %s"
        % (co.co_name, co.co_filename, co.co_firstlineno, msg)
    )


ExcInfo = Union[
    Tuple[Type[BaseException], BaseException, TracebackType],
    Tuple[None, None, None],
]


class HookResult:
    """A class to store/modify results from a _multicall hook loop.

    Results are accessed in ``.result`` property, which will also raise
    any exceptions that occured during the hook loop.

    Parameters
    ----------
    results : List[Tuple[Any, HookImpl]]
        A list of (result, HookImpl) tuples, with the result and HookImpl
        object responsible for each result collected during a _multicall loop.
    excinfo : tuple
        The output of sys.exc_info() if raised during the multicall loop.
    firstresult : bool, optional
        Whether the hookspec had ``firstresult == True``, by default False.
        If True, self._result, and self.implementation will be single values,
        otherwise they will be lists.
    plugin_errors : list
        A list of any :class:`napari.plugins.exceptions.PluginCallError`
        instances that were created during the multicall loop.

    Attributes
    ----------
    result : list or any
        The result (if ``firstresult``) or results from the hook call.  The
        result property will raise any errors in ``excinfo`` when accessed.
    implementation : list or any
        The HookImpl instance (if ``firstresult``) or instances that were
        responsible for each result in ``result``.
    is_firstresult : bool
        Whether this HookResult came from a ``firstresult`` multicall.
    """

    def __init__(
        self,
        result: List[Tuple[Any, HookImpl]],
        excinfo: Optional[ExcInfo],
        firstresult: bool = False,
        plugin_errors: Optional[List[PluginCallError]] = None,
    ):
        self._result = None if firstresult else []
        self.implementation = None if firstresult else []
        if result:
            self._result, self.implementation = tuple(zip(*result))
            self._result = list(self._result)
            if firstresult and self._result:
                self._result = self._result[0]
                self.implementation = self.implementation[0]

        self._excinfo = excinfo
        self.is_firstresult = firstresult
        self.plugin_errors = plugin_errors
        # str with name of hookwrapper that override result
        self._modified_by: Optional[str] = None

    @property
    def excinfo(self):
        return self._excinfo

    @classmethod
    def from_call(cls, func):
        """Used when hookcall monitoring is enabled.

        https://pluggy.readthedocs.io/en/latest/#call-monitoring
        """
        __tracebackhide__ = True
        try:
            return func()
        except BaseException:
            return cls(None, sys.exc_info())

    def force_result(self, result: Any):
        """Force the result(s) to ``result``.

        This may be used by hookwrappers to alter this result object.

        If the hook was marked as a ``firstresult`` a single value should
        be set otherwise set a (modified) list of results. Any exceptions
        found during invocation will be deleted.
        """
        import inspect

        self._result = result
        self._excinfo = None
        self._modified_by = inspect.stack()[1].function

    @property
    def result(self) -> Union[Any, List[Any]]:
        """Return the result(s) for this hook call.

        If the hook was marked as a ``firstresult`` only a single value
        will be returned otherwise a list of results.
        """
        __tracebackhide__ = True
        if self._excinfo is not None:
            _type, value, traceback = self._excinfo
            if value:
                raise value.with_traceback(traceback)
        return self._result


def _multicall(
    hook_impls: List[HookImpl], caller_kwargs: dict, firstresult: bool = False,
) -> HookResult:
    """Loop through ``hook_impls`` with ``**caller_kwargs`` and return results.

    Parameters
    ----------
    hook_impls : list
        A sequence of hook implementation (HookImpl) objects
    caller_kwargs : dict
        Keyword:value pairs to pass to each ``hook_impl.function``.  Every
        key in the dict must be present in the ``argnames`` property for each
        ``hook_impl`` in ``hook_impls``.
    firstresult : bool, optional
        If ``True``, return the first non-null result found, otherwise, return
        a list of results from all hook implementations, by default False

    Returns
    -------
    outcome : HookResult
        A :class:`HookResult` object that contains the results returned by
        plugins along with other metadata about the call.

    Raises
    ------
    HookCallError
        If one or more of the keys in ``caller_kwargs`` is not present in one
        of the ``hook_impl.argnames``.
    PluginCallError
        If ``firstresult == True`` and a plugin raises an Exception.
    """
    __tracebackhide__ = True
    results = []
    errors: List['PluginCallError'] = []
    excinfo: Optional[ExcInfo] = None
    try:  # run impl and wrapper setup functions in a loop
        teardowns = []
        try:
            for hook_impl in reversed(hook_impls):
                # the `hook_impl.enabled` attribute is specific to napari
                # it is not recognized or implemented by pluggy
                if not getattr(hook_impl, 'enabled', True):
                    continue
                args: List[Any] = []
                try:
                    args = [
                        caller_kwargs[argname]
                        for argname in hook_impl.argnames
                    ]
                except KeyError:
                    for argname in hook_impl.argnames:
                        if argname not in caller_kwargs:
                            raise HookCallError(
                                "hook call must provide argument %r"
                                % (argname,)
                            )

                if hook_impl.hookwrapper:
                    try:
                        gen = hook_impl.function(*args)
                        next(gen)  # first yield
                        teardowns.append(gen)
                    except StopIteration:
                        _raise_wrapfail(gen, "did not yield")
                else:
                    res = None
                    # this is where the plugin function actually gets called
                    # we put it in a try/except so that if one plugin throws
                    # an exception, we don't lose the whole loop
                    try:
                        res = hook_impl.function(*args)
                    except Exception as exc:
                        # creating a PluginCallError will store it for later
                        # in plugins.exceptions.PLUGIN_ERRORS
                        errors.append(PluginCallError(hook_impl, cause=exc))
                        # if it was a `firstresult` hook, break and raise now.
                        if firstresult:
                            break

                    if res is not None:
                        results.append((res, hook_impl))
                        if firstresult:  # halt further impl calls
                            break
        except BaseException:
            excinfo = sys.exc_info()
    finally:
        if firstresult and errors:
            raise errors[-1]

        outcome = HookResult(
            results,
            excinfo=excinfo,
            firstresult=firstresult,
            plugin_errors=errors,
        )

        # run all wrapper post-yield blocks
        for gen in reversed(teardowns):
            try:
                gen.send(outcome)
                _raise_wrapfail(gen, "has second yield")
            except StopIteration:
                pass

        return outcome
