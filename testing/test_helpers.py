import sys

import pytest

from napari_plugin_engine.implementation import varnames
from napari_plugin_engine.manager import (
    _formatdef,
    ensure_namespace,
    temp_path_additions,
)


def test_varnames():
    def f(x):
        i = 3  # noqa

    class A:
        def f(self, y):
            pass

    class B:
        def __call__(self, z):
            pass

    assert varnames(f) == (("x",), ())
    assert varnames(A().f) == (("y",), ())
    assert varnames(B()) == (("z",), ())


def test_varnames_default():
    def f(x, y=3):
        pass

    assert varnames(f) == (("x",), ("y",))


def test_varnames_class():
    class C:
        def __init__(self, x):
            pass

    class D:
        pass

    class E:
        def __init__(self, x):
            pass

    class F:
        pass

    assert varnames(C) == (("x",), ())
    assert varnames(D) == ((), ())
    assert varnames(E) == (("x",), ())
    assert varnames(F) == ((), ())


@pytest.mark.skipif(
    sys.version_info < (3,), reason="Keyword only arguments are Python 3 only"
)
def test_varnames_keyword_only():
    # SyntaxError on Python 2, so we exec
    ns = {}
    exec(
        "def f1(x, *, y): pass\n"
        "def f2(x, *, y=3): pass\n"
        "def f3(x=1, *, y=3): pass\n",
        ns,
    )

    assert varnames(ns["f1"]) == (("x",), ())
    assert varnames(ns["f2"]) == (("x",), ())
    assert varnames(ns["f3"]) == ((), ("x",))


def test_formatdef():
    def function1():
        pass

    assert _formatdef(function1) == "function1()"

    def function2(arg1):
        pass

    assert _formatdef(function2) == "function2(arg1)"

    def function3(arg1, arg2="qwe"):
        pass

    assert _formatdef(function3) == "function3(arg1, arg2='qwe')"

    def function4(arg1, *args, **kwargs):
        pass

    assert _formatdef(function4) == "function4(arg1, *args, **kwargs)"


def test_ensure_namespace():
    a = {'x': 1}
    assert not getattr(a, 'x', None)
    b = ensure_namespace(a)
    assert getattr(b, 'x') == 1
    assert a != b

    with pytest.raises(ValueError):
        # '0' is not a valid identifyer
        ensure_namespace({0: 1})

    class AlreadyNameSpace:
        x = 1

    # doesn't touch things that are already valid namespaces
    assert ensure_namespace(AlreadyNameSpace) == AlreadyNameSpace


def test_temp_path():
    import sys

    orig_path = set(sys.path)

    with temp_path_additions('/path/') as pth:
        assert sys.path == pth
        assert '/path/' in sys.path

    assert set(sys.path) == orig_path
