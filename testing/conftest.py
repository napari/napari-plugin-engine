import pytest


@pytest.fixture(
    params=[lambda spec: spec, lambda spec: spec()],
    ids=["spec-is-class", "spec-is-instance"],
)
def he_pm(request, pm):
    from naplugi import HookspecMarker

    hookspec = HookspecMarker("example")

    class Hooks:
        @hookspec
        def he_method1(self, arg):
            ...

    pm.add_hookspecs(request.param(Hooks))
    return pm


@pytest.fixture
def pm():
    from naplugi import PluginManager

    pm = PluginManager(project_name='example', autodiscover=False)
    return pm
