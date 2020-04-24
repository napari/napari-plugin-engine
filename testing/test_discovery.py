import pytest
import os
from naplugi import (
    PluginRegistrationError,
    PluginImportError,
    PluginValidationError,
)
from naplugi.manager import temp_path_additions

GOOD_PLUGIN = """
from naplugi import HookimplMarker

@HookimplMarker("test")
def test_specification(arg1, arg2):
    return arg1 + arg2
"""

INVALID_PLUGIN = """
from naplugi import HookimplMarker

@HookimplMarker("test")
def test_specification(arg1, arg2, arg3):
    return arg1 + arg2 + arg3
"""


@pytest.fixture
def app_good_plugin(tmp_path):
    """A good plugin with a name prefix we will search for."""
    (tmp_path / "app_good_plugin.py").write_text(GOOD_PLUGIN)


@pytest.fixture
def random_good_plugin(tmp_path):
    """A good plugin that uses entry points."""
    (tmp_path / "random_good_plugin.py").write_text(GOOD_PLUGIN)
    distinfo = tmp_path / "random_good_plugin-1.2.3.dist-info"
    distinfo.mkdir()
    (distinfo / "top_level.txt").write_text('random_good_plugin')
    (distinfo / "entry_points.txt").write_text(
        "[app.plugin]\nrandom = random_good_plugin"
    )
    (distinfo / "METADATA").write_text(
        "Metadata-Version: 2.1\n"
        "Name: random\n"
        "Version: 1.2.3\n"
        "Author-Email: example@example.com\n"
        "Home-Page: https://www.example.com\n"
        "Requires-Python: >=3.6\n"
    )


@pytest.fixture
def app_invalid_plugin(tmp_path):
    (tmp_path / "app_invalid_plugin.py").write_text(INVALID_PLUGIN)


@pytest.fixture
def app_broken_plugin(tmp_path):
    (tmp_path / "app_broken_plugin.py").write_text('raise ValueError("broke")')


def test_plugin_discovery_by_prefix(
    tmp_path,
    add_specification,
    test_plugin_manager,
    app_good_plugin,
    app_invalid_plugin,
):
    """Make sure b
    """

    @add_specification
    def test_specification(arg1, arg2):
        ...

    assert test_plugin_manager.hook.test_specification.spec
    assert not test_plugin_manager.plugins

    # discover modules that begin with `app_`
    count, errs = test_plugin_manager.discover(tmp_path, prefix='app_')
    # we should have had one success and one error.
    assert count == len(errs) == 1

    # the app_good_plugin module should have been found, with one hookimpl
    assert 'app_good_plugin' in test_plugin_manager.plugins
    impls = test_plugin_manager.hook.test_specification.get_hookimpls()
    assert 'app_good_plugin' in [i.plugin_name for i in impls]

    # the plugin with the invalid spec is in the path that we loaded
    assert 'app_invalid_plugin.py' in os.listdir(tmp_path)
    # but it wasn't added to the plugin manager
    assert 'app_invalid_plugin' not in test_plugin_manager.plugins
    # However an error should have been logged for the invalid plugin
    assert not test_plugin_manager.get_errors('app_good_plugin')
    errs = test_plugin_manager.get_errors('app_invalid_plugin')
    assert errs
    assert isinstance(errs[0], PluginValidationError)
    # and it should now be blocked
    assert test_plugin_manager.is_blocked('app_invalid_plugin')

    # if we unblock the plugin and turn off ignore_errors
    # we'll get a registration error at discovery
    test_plugin_manager.set_blocked('app_invalid_plugin', False)
    with pytest.raises(PluginRegistrationError):
        test_plugin_manager.discover(
            tmp_path, prefix='app_', ignore_errors=False
        )


def test_plugin_discovery_by_prefix_with_bad_plugin(
    tmp_path, add_specification, test_plugin_manager, app_broken_plugin
):
    """Make sure b
    """

    with pytest.raises(PluginImportError):
        test_plugin_manager.discover(
            tmp_path, prefix='app_', ignore_errors=False
        )


def test_plugin_discovery_by_entry_point(
    tmp_path, add_specification, test_plugin_manager, random_good_plugin
):
    @add_specification
    def test_specification(arg1, arg2):
        ...

    hook_caller = test_plugin_manager.hook.test_specification
    assert hook_caller.spec
    assert not test_plugin_manager.plugins

    # discover modules that begin with `app_`
    cnt, err = test_plugin_manager.discover(tmp_path, entry_point='app.plugin')
    # we should have had one success and one error.
    assert cnt == 1

    # the app_good_plugin module should have been found, with one hookimpl
    assert 'random' in test_plugin_manager.plugins
    assert 'random' in [i.plugin_name for i in hook_caller.get_hookimpls()]


def test_lazy_autodiscovery(
    tmp_path, add_specification, test_plugin_manager, random_good_plugin
):
    test_plugin_manager.discover_entry_point = 'app.plugin'
    assert test_plugin_manager.hook._needs_discovery is True
    with test_plugin_manager.discovery_blocked():

        @add_specification
        def test_specification(arg1, arg2):
            ...

    assert test_plugin_manager.hook._needs_discovery is True

    assert not test_plugin_manager.plugins
    with temp_path_additions(tmp_path):
        hook_caller = test_plugin_manager.hook.test_specification

    assert hook_caller.spec
    assert test_plugin_manager.plugins.get('random')
    assert test_plugin_manager.hook._needs_discovery is False
