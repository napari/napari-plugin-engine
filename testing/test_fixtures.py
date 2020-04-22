import pytest

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
def add_implementation(test_hook_caller):
    def addimpl(
        function=None, *, tryfirst=False, trylast=False, hookwrapper=False
    ):
        def wrap(func):
            HookimplMarker("test")(
                tryfirst=tryfirst, trylast=trylast, hookwrapper=hookwrapper
            )(func)
            test_hook_caller._add_hookimpl(HookImpl(func, **func.test_impl))
            return func

        return wrap(function) if function is not None else wrap

    return addimpl


def test_spec(test_plugin_manager, add_specification):
    print(test_plugin_manager.hook.items())
    @add_specification
    def my_spec(arg1, arg2): ...
    print(test_plugin_manager.hook.items())
    print(test_plugin_manager.hook.my_spec.spec)