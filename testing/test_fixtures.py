import pytest
from typing import Callable

from naplugi import (
    HookCaller,
    HookImpl,
    HookimplMarker,
    HookspecMarker,
    PluginManager,
)


@pytest.fixture
def test_plugin_manager() -> PluginManager:
    return PluginManager(project_name='test')


@pytest.fixture
def test_hook_caller(test_plugin_manager) -> HookCaller:
    """Note, any implementations MUST be named test_spec."""

    class Hooks:
        @HookspecMarker("test")
        def test_spec(self, arg):
            pass

    test_plugin_manager.add_hookspecs(Hooks)
    return test_plugin_manager.hook.test_spec


@pytest.fixture
def add_specification(test_plugin_manager):
    def addspec(function=None, *, firstresult=False, historic=False):
        def wrap(func):
            test_hookspec = HookspecMarker("test")
            test_hookspec(firstresult=firstresult, historic=historic)(func)
            name = func.__name__
            namespace = type("Hook", (), {name: func})
            assert not hasattr(
                test_plugin_manager.hook, name
            ), f"Hook already exists with name: {name}"
            hook_caller = HookCaller(
                name, test_plugin_manager._hookexec, namespace, func.test_spec
            )
            setattr(test_plugin_manager.hook, name, hook_caller)

        return wrap(function) if function is not None else wrap

    return addspec


@pytest.fixture
def add_implementation(test_plugin_manager) -> Callable:
    def addimpl(
        function=None,
        *,
        tryfirst=False,
        trylast=False,
        hookwrapper=False,
        specname=None,
    ):
        def wrap(func):
            HookimplMarker("test")(
                tryfirst=tryfirst,
                trylast=trylast,
                hookwrapper=hookwrapper,
                specname=specname,
            )(func)
            _specname = specname or func.__name__
            hook_caller = getattr(test_plugin_manager.hook, _specname, None)
            assert hook_caller, f"No hook with with name: {_specname}"
            hook_caller._add_hookimpl(HookImpl(func, **func.test_impl))
            return func

        return wrap(function) if function is not None else wrap

    return addimpl


def test_spec(test_plugin_manager, add_specification):
    print(test_plugin_manager.hook.items())

    @add_specification
    def my_spec(arg1, arg2):
        ...

    print(test_plugin_manager.hook.items())
    print(test_plugin_manager.hook.my_spec.spec)


def test_impl(test_hook_caller, add_implementation):
    print(test_hook_caller.get_hookimpls())

    @add_implementation
    def test_spec(arg):
        return arg + 1

    print(test_hook_caller.get_hookimpls())


def test_full(test_plugin_manager, add_specification, add_implementation):
    print(test_plugin_manager.hook.items())

    @add_specification
    def my_spec(arg1, arg2):
        ...

    print(test_plugin_manager.hook.my_spec.get_hookimpls())

    @add_implementation(specname='my_spec')
    def ttt(arg):
        return arg + 1

    print(test_plugin_manager.hook.my_spec.get_hookimpls())
