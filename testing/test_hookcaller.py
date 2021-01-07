import pytest

from napari_plugin_engine import (
    HookImplementation,
    HookImplementationMarker,
    HookSpecification,
    HookSpecificationMarker,
    PluginValidationError,
)

example_hookspec = HookSpecificationMarker("example")
example_implementation = HookImplementationMarker("example")


@pytest.fixture
def hook_caller(pm):
    class Hooks:
        @example_hookspec
        def method1(self, arg):
            pass

    pm.add_hookspecs(Hooks)
    return pm.hook.method1


@pytest.fixture
def addmeth(hook_caller):
    def addmeth(tryfirst=False, trylast=False, hookwrapper=False):
        def wrap(func):
            example_implementation(
                tryfirst=tryfirst, trylast=trylast, hookwrapper=hookwrapper
            )(func)
            hook_caller._add_hookimpl(
                HookImplementation(func, **func.example_impl)
            )
            return func

        return wrap

    return addmeth


def funcs(hookmethods):
    return [hookmethod.function for hookmethod in hookmethods]


def test_adding_nonwrappers(hook_caller, addmeth):
    @addmeth()
    def method1():
        pass

    @addmeth()
    def method2():
        pass

    @addmeth()
    def method3():
        pass

    assert funcs(hook_caller._nonwrappers) == [method1, method2, method3]


def test_adding_nonwrappers_trylast(hook_caller, addmeth):
    @addmeth()
    def method1_middle():
        pass

    @addmeth(trylast=True)
    def method1():
        pass

    @addmeth()
    def method1_b():
        pass

    assert funcs(hook_caller._nonwrappers) == [
        method1,
        method1_middle,
        method1_b,
    ]


def test_adding_nonwrappers_trylast3(hook_caller, addmeth):
    @addmeth()
    def method1_a():
        pass

    @addmeth(trylast=True)
    def method1_b():
        pass

    @addmeth()
    def method1_c():
        pass

    @addmeth(trylast=True)
    def method1_d():
        pass

    assert funcs(hook_caller._nonwrappers) == [
        method1_d,
        method1_b,
        method1_a,
        method1_c,
    ]


def test_adding_nonwrappers_trylast2(hook_caller, addmeth):
    @addmeth()
    def method1_middle():
        pass

    @addmeth()
    def method1_b():
        pass

    @addmeth(trylast=True)
    def method1():
        pass

    assert funcs(hook_caller._nonwrappers) == [
        method1,
        method1_middle,
        method1_b,
    ]


def test_adding_nonwrappers_tryfirst(hook_caller, addmeth):
    @addmeth(tryfirst=True)
    def method1():
        pass

    @addmeth()
    def method1_middle():
        pass

    @addmeth()
    def method1_b():
        pass

    assert funcs(hook_caller._nonwrappers) == [
        method1_middle,
        method1_b,
        method1,
    ]


def test_adding_wrappers_ordering(hook_caller, addmeth):
    @addmeth(hookwrapper=True)
    def method1():
        pass

    @addmeth()
    def method1_middle():
        pass

    @addmeth(hookwrapper=True)
    def method3():
        pass

    assert funcs(hook_caller._nonwrappers) == [method1_middle]
    assert funcs(hook_caller._wrappers) == [method1, method3]


def test_adding_wrappers_ordering_tryfirst(hook_caller, addmeth):
    @addmeth(hookwrapper=True, tryfirst=True)
    def method1():
        pass

    @addmeth(hookwrapper=True)
    def method2():
        pass

    assert hook_caller._nonwrappers == []
    assert funcs(hook_caller._wrappers) == [method2, method1]


def test_hookspec(pm):
    class HookSpecification:
        @example_hookspec()
        def he_myhook1(arg1):
            pass

        @example_hookspec(firstresult=True)
        def he_myhook2(arg1):
            pass

        @example_hookspec(firstresult=False)
        def he_myhook3(arg1):
            pass

    pm.add_hookspecs(HookSpecification)
    assert not pm.hook.he_myhook1.spec.firstresult
    assert pm.hook.he_myhook2.spec.firstresult
    assert not pm.hook.he_myhook3.spec.firstresult


def test_hookspec_reserved_argnames(pm):
    """Certain argument names are reserved and cannot be used in specs."""

    class HookSpecificationA:
        @example_hookspec()
        def he_myhook1(_plugin):
            pass

    class HookSpecificationB:
        @example_hookspec()
        def he_myhook1(_skip_impls):
            pass

    for cls in (HookSpecificationA, HookSpecificationB):
        with pytest.raises(ValueError):
            pm.add_hookspecs(cls)


@pytest.mark.parametrize(
    "name", ["hookwrapper", "optionalhook", "tryfirst", "trylast"]
)
@pytest.mark.parametrize("val", [True, False])
def test_hookimpl(name, val):
    @example_implementation(**{name: val})
    def he_myhook1(arg1):
        pass

    if val:
        assert he_myhook1.example_impl.get(name)
    else:
        assert not hasattr(he_myhook1, name)


def test_hookrelay_registry(pm):
    """Verify hook caller instances are registered by name onto the relay
    and can be likewise unregistered."""

    class Api:
        @example_hookspec
        def hello(self, arg):
            "api hook 1"

    pm.add_hookspecs(Api)
    hook = pm.hook
    assert hasattr(hook, "hello")
    assert repr(hook.hello).find("hello") != -1

    class Plugin:
        @example_implementation
        def hello(self, arg):
            return arg + 1

    plugin = Plugin()
    pm.register(plugin)
    out = hook.hello(arg=3)
    assert out == [4]
    assert not hasattr(hook, "world")
    pm.unregister(plugin)
    assert hook.hello(arg=3) == []


def test_hookrelay_registration_by_specname(pm):
    """Verify hook caller instances may also be registered by specifying a
    specname option to the hookimpl"""

    class Api:
        @example_hookspec
        def hello(self, arg):
            "api hook 1"

    pm.add_hookspecs(Api)
    hook = pm.hook
    assert hasattr(hook, "hello")
    assert len(pm.hook.hello.get_hookimpls()) == 0

    class Plugin:
        @example_implementation(specname="hello")
        def foo(self, arg):
            return arg + 1

    plugin = Plugin()
    pm.register(plugin)
    out = hook.hello(arg=3)
    assert out == [4]


def test_hookrelay_registration_by_specname_raises(pm):
    """Verify using specname still raises the types of errors during registration as it
    would have without using specname."""

    class Api:
        @example_hookspec
        def hello(self, arg):
            "api hook 1"

    pm.add_hookspecs(Api)

    # make sure a bad signature still raises an error when using specname
    class Plugin:
        @example_implementation(specname="hello")
        def foo(self, arg, too, many, args):
            return arg + 1

    with pytest.raises(PluginValidationError):
        pm.register(Plugin())

    # make sure check_pending still fails if specname doesn't have a
    # corresponding spec.  EVEN if the function name matches one.
    class Plugin2:
        @example_implementation(specname="bar")
        def hello(self, arg):
            return arg + 1

    pm.register(Plugin2())
    with pytest.raises(PluginValidationError):
        pm.check_pending()


def test_legacy_specimpl_opt():
    impl = HookImplementation(lambda x: x)
    assert impl.opts

    spec = HookSpecification(type("Hook", (), {'x': lambda x: x}), 'x')
    assert spec.opts
