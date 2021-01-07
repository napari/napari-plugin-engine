"""Hook annotation decorators"""
from typing import Callable, Optional

from .implementation import HookImplementation, HookSpecification


class HookSpecificationMarker:
    """Decorator helper class for marking functions as hook specifications.

    You can instantiate it with a project_name to get a decorator. Calling
    :py:meth:`.PluginManager.add_hookspecs` later will discover all marked
    functions if the :py:class:`.PluginManager` uses the same project_name.
    """

    def __init__(self, project_name):
        self.project_name = project_name

    def __call__(
        self,
        function: Optional[Callable] = None,
        firstresult: bool = False,
        historic: bool = False,
        warn_on_impl=None,
    ):
        """if passed a function, directly sets attributes on the function
        which will make it discoverable to
        :py:meth:`.PluginManager.add_hookspecs`. If passed no function, returns
        a decorator which can be applied to a function later using the
        attributes supplied.

        If ``firstresult`` is ``True`` the 1:N hook call (N being the number of
        registered hook implementation functions) will stop at I<=N when the
        I'th function returns a non-``None`` result.

        If ``historic`` is ``True`` calls to a hook will be memorized and
        replayed on later registered plugins.

        """

        def setattr_hookspec_opts(func):
            if historic and firstresult:
                raise ValueError("cannot have a historic firstresult hook")
            setattr(
                func,
                HookSpecification.format_tag(self.project_name),
                dict(
                    firstresult=firstresult,
                    historic=historic,
                    warn_on_impl=warn_on_impl,
                ),
            )
            return func

        if function is not None:
            return setattr_hookspec_opts(function)
        else:
            return setattr_hookspec_opts


class HookImplementationMarker:
    """Decorator helper class for marking functions as hook implementations.

    You can instantiate with a ``project_name`` to get a decorator. Calling
    :meth:`.PluginManager.register` later will discover all marked functions if
    the :class:`.PluginManager` uses the same project_name.

    Parameters
    ----------
    project_name : str
        A namespace for plugin implementations.  Implementations decorated with
        this class will be discovered by ``PluginManager.register`` if and only
        if ``project_name`` matches the ``project_name`` of the
        ``PluginManager``.
    """

    def __init__(self, project_name: str):
        self.project_name = project_name

    def __call__(
        self,
        function: Optional[Callable] = None,
        *,
        hookwrapper: bool = False,
        optionalhook: bool = False,
        tryfirst: bool = False,
        trylast: bool = False,
        specname: str = '',
    ) -> Callable:
        """Call the marker instance.

        If passed a function, directly sets attributes on the function which
        will make it discoverable to :meth:`.PluginManager.register`. If passed
        no function, returns a decorator which can be applied to a function
        later using the attributes supplied.

        Parameters
        ----------
        function : callable, optional
            A function to decorate as a hook implementation, If ``function`` is
            None, this method returns a function that can be used to decorate
            other functions.
        hookwrapper : bool, optional
            Whether this hook implementation behaves as a hookwrapper.
            by default False
        optionalhook : bool, optional
            If ``True``, a missing matching hook specification will not result
            in an error (by default it is an error if no matching spec is
            found), by default False.
        tryfirst : bool, optional
            If ``True`` this hook implementation will run as early as possible
            in the chain of N hook implementations for a specification, by
            default False
        trylast : bool, optional
            If ``True`` this hook implementation will run as late as possible
            in the chain of N hook implementations, by default False
        specname : str, optional
            If provided, ``specname`` will be used instead of the function name
            when matching this hook implementation to a hook specification
            during registration, by default the implementation function name
            must match the name of the corresponding hook specification.

        Returns
        -------
        Callable
            If ``function`` is not ``None``, will decorate the function with
            attributes, and return the function.  If ``function`` is None, will
            return a decorator that can be used to decorate functions.
        """

        def set_hook_implementation_attributes(func):
            setattr(
                func,
                HookImplementation.format_tag(self.project_name),
                dict(
                    hookwrapper=hookwrapper,
                    optionalhook=optionalhook,
                    tryfirst=tryfirst,
                    trylast=trylast,
                    specname=specname,
                ),
            )
            return func

        if function is None:
            return set_hook_implementation_attributes
        else:
            return set_hook_implementation_attributes(function)
