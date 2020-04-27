import pytest


@pytest.fixture(
    params=[lambda spec: spec, lambda spec: spec()],
    ids=["spec-is-class", "spec-is-instance"],
)
def he_pm(request, pm):
    from napari_plugin_engine import HookSpecificationMarker

    hookspec = HookSpecificationMarker("example")

    class Hooks:
        @hookspec
        def he_method1(self, arg):
            ...

    pm.add_hookspecs(request.param(Hooks))
    return pm


@pytest.fixture
def pm():
    from napari_plugin_engine import PluginManager

    pm = PluginManager(project_name='example')
    return pm
