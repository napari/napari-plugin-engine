import pytest
from contextlib import contextmanager

from naplugi import (
    HookCaller,
    HookImpl,
    HookimplMarker,
    HookspecMarker,
    PluginManager,
)


@pytest.fixture
def test_plugin_manager() -> PluginManager:
    """A plugin manager fixture with the project name 'test'."""
    return PluginManager(project_name='test')


@pytest.fixture
def add_specification(test_plugin_manager):
    """Return a decorator that adds a HookSpec to test_plugin_manager."""

    def addspec(function=None, *, firstresult=False, historic=False):
        def wrap(func):
            project = test_plugin_manager.project_name
            test_hookspec = HookspecMarker(project)
            test_hookspec(firstresult=firstresult, historic=historic)(func)
            name = func.__name__
            namespace = type("Hook", (), {name: func})
            assert not hasattr(
                test_plugin_manager.hook, name
            ), f"Hook already exists with name: {name}"
            opts = getattr(func, f'{project}_spec')
            hook_caller = HookCaller(
                name, test_plugin_manager._hookexec, namespace, opts
            )
            setattr(test_plugin_manager.hook, name, hook_caller)

        return wrap(function) if function is not None else wrap

    return addspec


@pytest.fixture
def add_implementation(test_plugin_manager):
    """Return a decorator that adds a HookImpl to test_plugin_manager."""

    def addimpl(
        function=None,
        *,
        specname=None,
        tryfirst=False,
        trylast=False,
        hookwrapper=False,
    ):
        def wrap(func):
            project = test_plugin_manager.project_name
            HookimplMarker(project)(
                tryfirst=tryfirst,
                trylast=trylast,
                hookwrapper=hookwrapper,
                specname=specname,
            )(func)
            _specname = specname or func.__name__
            hook_caller = getattr(test_plugin_manager.hook, _specname, None)
            assert hook_caller, f"No hook with with name: {_specname}"
            opts = getattr(func, f'{project}_impl')
            hook_caller._add_hookimpl(HookImpl(func, **opts))
            return func

        return wrap(function) if function is not None else wrap

    return addimpl


@pytest.fixture
def caller_from_implementation(
    test_plugin_manager, add_specification, add_implementation
):
    """Return hook caller with implementation as its own spec definition.

    Adds a specification and implementation to the test_plugin_manager based on
    a single function definition (e.g. assumes that the implementation has the
    correct signature).  Returns the hook caller instance prepopulated with the
    hook implementation.
    """

    def wrap(func, spec_kwargs={}, impl_kwargs={}):
        add_specification(func, **spec_kwargs)
        add_implementation(func, **impl_kwargs)
        name = spec_kwargs.get('specname') or func.__name__
        return getattr(test_plugin_manager.hook, name)

    return wrap


@pytest.fixture
def temporary_hookimpl(test_plugin_manager):
    """A fixture that can be used to insert a HookImpl in the hook call loop.

    Use as a context manager, which will return the hook_caller for the
    corresponding hook specification.

    Example
    -------
    .. code-block: python

        def my_hook_implementation(arg):
            raise ValueError("shoot!")

        with temporary_hookimpl(my_hook_implementation) as hook_caller:
            with pytest.raises(PluginCallError):
                hook_caller(arg=42)
    """

    @contextmanager
    def wrap(func, specname=None, *, tryfirst=True, trylast=None):
        project = test_plugin_manager.project_name
        marker = HookimplMarker(project)
        marker(tryfirst=tryfirst, trylast=trylast, specname=specname)(func)
        _specname = specname or func.__name__
        hook_caller = getattr(test_plugin_manager.hook, _specname, None)
        assert hook_caller, f"No hook with with name: {_specname}"
        opts = getattr(func, f'{project}_impl')
        impl = HookImpl(func, **opts)
        hook_caller._add_hookimpl(impl)
        try:
            yield hook_caller
        finally:
            if impl in hook_caller._nonwrappers:
                hook_caller._nonwrappers.remove(impl)
            if impl in hook_caller._wrappers:
                hook_caller._wrappers.remove(impl)
            assert impl not in hook_caller.get_hookimpls()

    return wrap
