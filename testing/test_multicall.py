import pytest

from napari_plugin_engine import (
    HookCallError,
    HookImplementation,
    HookImplementationMarker,
    HookSpecificationMarker,
)
from napari_plugin_engine.callers import _multicall

hookspec = HookSpecificationMarker("example")
example_implementation = HookImplementationMarker("example")


def multicall(methods, kwargs, firstresult=False):
    """utility function to execute the hook implementations loop"""
    caller = _multicall
    hookfuncs = []
    for method in methods:
        f = HookImplementation(method, **method.example_impl)
        hookfuncs.append(f)
    # our _multicall function returns our own HookResult object.
    # so to make these pluggy tests pass, we have to access .result to mimic
    # the old behavior (that directly returns results).
    return caller(hookfuncs, kwargs, firstresult=firstresult).result


def test_multicall_passing():
    class Plugin1:
        @example_implementation
        def method(self, x):
            return 17

    class Plugin2:
        @example_implementation
        def method(self, x):
            return 23

    p1 = Plugin1()
    p2 = Plugin2()
    result_list = multicall([p1.method, p2.method], {"x": 23})
    assert len(result_list) == 2
    # ensure reversed order
    assert result_list == [23, 17]


def test_keyword_args():
    @example_implementation
    def func(x):
        return x + 1

    class Plugin:
        @example_implementation
        def func(self, x, y):
            return x + y

    reslist = multicall([func, Plugin().func], {"x": 23, "y": 24})
    assert reslist == [24 + 23, 24]


def test_keyword_args_with_defaultargs():
    @example_implementation
    def func(x, z=1):
        return x + z

    reslist = multicall([func], {"x": 23, "y": 24})
    assert reslist == [24]


def test_tags_call_error():
    @example_implementation
    def func(x):
        return x

    with pytest.raises(HookCallError):
        multicall([func], {})


def test_call_subexecute():
    @example_implementation
    def func1():
        return 2

    @example_implementation
    def func2():
        return 1

    assert multicall([func2, func1], {}, firstresult=True) == 2


def test_call_none_is_no_result():
    @example_implementation
    def func1():
        return 1

    @example_implementation
    def func2():
        return None

    assert multicall([func1, func2], {}, firstresult=True) == 1
    assert multicall([func1, func2], {}, {}) == [1]


def test_hookwrapper():
    out = []

    @example_implementation(hookwrapper=True)
    def func1():
        out.append("func1 init")
        yield None
        out.append("func1 finish")

    @example_implementation
    def func2():
        out.append("func2")
        return 2

    assert multicall([func2, func1], {}) == [2]
    assert out == ["func1 init", "func2", "func1 finish"]
    out = []
    assert multicall([func2, func1], {}, firstresult=True) == 2
    assert out == ["func1 init", "func2", "func1 finish"]


def test_hookwrapper_order():
    out = []

    @example_implementation(hookwrapper=True)
    def func1():
        out.append("func1 init")
        yield 1
        out.append("func1 finish")

    @example_implementation(hookwrapper=True)
    def func2():
        out.append("func2 init")
        yield 2
        out.append("func2 finish")

    assert multicall([func2, func1], {}) == []
    assert out == ["func1 init", "func2 init", "func2 finish", "func1 finish"]


def test_hookwrapper_not_yield():
    @example_implementation(hookwrapper=True)
    def func1():
        pass

    with pytest.raises(TypeError):
        multicall([func1], {})


def test_hookwrapper_too_many_yield():
    @example_implementation(hookwrapper=True)
    def func1():
        yield 1
        yield 2

    with pytest.raises(RuntimeError) as ex:
        multicall([func1], {})
    assert "func1" in str(ex.value)
    assert __file__ in str(ex.value)


@pytest.mark.parametrize("exc", [SystemExit])
def test_hookwrapper_exception(exc):
    out = []

    @example_implementation(hookwrapper=True)
    def func1():
        out.append("func1 init")
        yield None
        out.append("func1 finish")

    @example_implementation
    def func2():
        raise exc()

    with pytest.raises(exc):
        multicall([func2, func1], {})
    assert out == ["func1 init", "func1 finish"]
