import os

import pytest

from napari_plugin_engine import (
    PluginError,
    PluginImportError,
    PluginValidationError,
)
from napari_plugin_engine.dist import get_version, standard_metadata
from napari_plugin_engine.manager import temp_path_additions

GOOD_PLUGIN = """
from napari_plugin_engine import HookImplementationMarker

@HookImplementationMarker("test")
def test_specification(arg1, arg2):
    return arg1 + arg2
"""

INVALID_PLUGIN = """
from napari_plugin_engine import HookImplementationMarker

@HookImplementationMarker("test")
def test_specification(arg1, arg2, arg3):
    return arg1 + arg2 + arg3
"""


@pytest.fixture
def app_good_plugin(tmp_path):
    """A good plugin with a name prefix we will search for."""
    (tmp_path / "app_good_plugin.py").write_text(GOOD_PLUGIN)


@pytest.fixture
def good_entrypoint_plugin(tmp_path):
    """A good plugin that uses entry points."""
    (tmp_path / "good_entrypoint_plugin.py").write_text(GOOD_PLUGIN)
    distinfo = tmp_path / "good_entrypoint_plugin-1.2.3.dist-info"
    distinfo.mkdir()
    (distinfo / "top_level.txt").write_text('good_entrypoint_plugin')
    (distinfo / "entry_points.txt").write_text(
        "[app.plugin]\ngood_entry = good_entrypoint_plugin"
    )
    (distinfo / "METADATA").write_text(
        "Metadata-Version: 2.1\n"
        "Name: good_entry\n"
        "Version: 1.2.3\n"
        "Author-Email: example@example.com\n"
        "Home-Page: https://www.example.com\n"
        "Requires-Python: >=3.6\n"
    )


@pytest.fixture
def double_convention_plugin(tmp_path):
    """A good plugin that uses entry points but ALSO has naming convention"""
    module_folder = tmp_path / "app_double_plugin"
    module_folder.mkdir()
    (module_folder / "__init__.py").write_text('')
    (module_folder / "module_a.py").write_text(GOOD_PLUGIN)
    (module_folder / "module_b.py").write_text(GOOD_PLUGIN)
    distinfo = tmp_path / "app_double_plugin-3.2.1.dist-info"
    distinfo.mkdir()
    (distinfo / "top_level.txt").write_text('app_double_plugin')
    (distinfo / "entry_points.txt").write_text(
        "[app.plugin]\n"
        "double_a = app_double_plugin.module_a\n"
        "double_b = app_double_plugin.module_b\n"
    )
    (distinfo / "METADATA").write_text(
        "Metadata-Version: 2.1\n"
        "Name: double-package\n"
        "Version: 3.2.1\n"
        "Author-Email: example@example.com\n"
        "Home-Page: https://www.example.com\n"
        "Requires-Python: >=3.6\n"
    )


@pytest.fixture
def invalid_entrypoint_plugin(tmp_path):
    """A good plugin that uses entry points."""
    (tmp_path / "invalid_entrypoint_plugin.py").write_text(INVALID_PLUGIN)
    distinfo = tmp_path / "invalid_entrypoint_plugin-1.2.3.dist-info"
    distinfo.mkdir()
    (distinfo / "top_level.txt").write_text('invalid_entrypoint_plugin')
    (distinfo / "entry_points.txt").write_text(
        "[app.plugin]\ninvalid = invalid_entrypoint_plugin"
    )
    (distinfo / "METADATA").write_text(
        "Metadata-Version: 2.1\n"
        "Name: invalid\n"
        "Version: 1.2.3\n"
        "Author-Email: example@example.com\n"
        "Home-Page: https://www.example.com\n"
        "Requires-Python: >=3.6\n"
    )
    return tmp_path


@pytest.fixture
def app_invalid_plugin(tmp_path):
    (tmp_path / "app_invalid_plugin.py").write_text(INVALID_PLUGIN)


@pytest.fixture
def app_broken_plugin(tmp_path):
    (tmp_path / "app_broken_plugin.py").write_text('raise ValueError("broke")')


@pytest.fixture
def full_plugin_manager(
    tmp_path,
    add_specification,
    test_plugin_manager,
    good_entrypoint_plugin,
    invalid_entrypoint_plugin,
    app_good_plugin,
    app_invalid_plugin,
    double_convention_plugin,
):
    @add_specification
    def test_specification(arg1, arg2):
        ...

    test_plugin_manager.discover_entry_point = 'app.plugin'
    test_plugin_manager.discover_prefix = 'app_'
    test_plugin_manager.discover_path = tmp_path

    cnt, err = test_plugin_manager.discover()
    assert cnt == 4
    assert len(err) == 2
    return test_plugin_manager


def test_plugin_meta(
    tmp_path,
    add_specification,
    test_plugin_manager,
    app_good_plugin,
    good_entrypoint_plugin,
    double_convention_plugin,
):

    test_plugin_manager.discover_entry_point = 'app.plugin'
    test_plugin_manager.discover_prefix = 'app_'

    with temp_path_additions(tmp_path):

        cnt, err = test_plugin_manager.discover()
        assert set(test_plugin_manager.plugins) == {
            'double_a',
            'double_b',
            'good_entry',
            'app_good_plugin',
        }

        versions = {
            'double_a': '3.2.1',
            'double_b': '3.2.1',
            'good_entry': '1.2.3',
            'app_good_plugin': '',
        }
        for name, plug in test_plugin_manager.plugins.items():
            assert versions[name] == get_version(plug)
            if name == 'app_good_plugin':
                # this one doesn't have any metadata.. but it will have plugin_name
                assert standard_metadata(plug) == {}
            else:
                assert get_version(plug) == standard_metadata(plug).get(
                    'version'
                )


@pytest.mark.parametrize(
    'regkwargs',
    [
        {},
        {'entry_point': 'app.plugin'},
        {'prefix': 'app_'},
        {'entry_point': 'app.plugin', 'prefix': 'app_'},
    ],
    ids=['neither', 'entry_point', 'prefix', 'both'],
)
def test_double_convention(
    regkwargs,
    tmp_path,
    add_specification,
    test_plugin_manager,
    double_convention_plugin,
):
    """Plugins using both naming convention and entrypoints only register once."""

    @add_specification
    def test_specification(arg1, arg2):
        ...

    assert not test_plugin_manager.plugins

    if 'entry_point' in regkwargs:
        test_plugin_manager.discover_entry_point = regkwargs['entry_point']
    if 'prefix' in regkwargs:
        test_plugin_manager.discover_prefix = regkwargs['prefix']
    test_plugin_manager.discover_path = tmp_path

    cnt, _ = test_plugin_manager.discover()
    hook_caller = test_plugin_manager.hook.test_specification
    plugin_names = list(test_plugin_manager.plugins.keys())
    if regkwargs:
        if 'entry_point' in regkwargs:
            # if an entry_point with a matching group is provided
            # the plugin will be named after the entrypoint name
            assert 'double_a' in plugin_names
            assert 'double_b' in plugin_names
            assert 'double-package' not in test_plugin_manager.plugins
            assert len(hook_caller.get_hookimpls()) == 2
        else:  # just prefix
            # if entry point discovery is disabled, but a top-level module
            # matches the naming convnetion, then the plugin will be named using
            # the top level module
            assert 'app_double_plugin' in plugin_names
            # however, in this case, there are no implementations in the
            # top level module (which is the only way naming convention
            # works)
            assert len(hook_caller.get_hookimpls()) == 0
    else:
        assert cnt == 0
        assert not hook_caller.get_hookimpls()
        assert 'double' not in plugin_names


def test_plugin_discovery_by_prefix(
    tmp_path,
    add_specification,
    test_plugin_manager,
    app_good_plugin,
    app_invalid_plugin,
):
    """Make sure discovery by package prefix works"""

    @add_specification
    def test_specification(arg1, arg2):
        ...

    assert test_plugin_manager.hook.test_specification.spec
    assert not test_plugin_manager.plugins

    test_plugin_manager.discover_prefix = 'app_'
    test_plugin_manager.discover_path = tmp_path

    # discover modules that begin with `app_`
    count, errs = test_plugin_manager.discover()
    # we should have had one success and one error.
    assert count == len(errs) == 1

    # the app_good_plugin module should have been found, with one hookimpl
    assert 'app_good_plugin' in test_plugin_manager.plugins.keys()
    impls = test_plugin_manager.hook.test_specification.get_hookimpls()
    assert 'app_good_plugin' in [i.plugin_name for i in impls]

    # the plugin with the invalid spec is in the path that we loaded
    assert 'app_invalid_plugin.py' in os.listdir(tmp_path)
    # but it wasn't added to the plugin manager
    assert 'app_invalid_plugin' not in test_plugin_manager.plugins.keys()
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
    with pytest.raises(PluginValidationError):
        test_plugin_manager.discover(ignore_errors=False)


def test_plugin_discovery_by_prefix_with_bad_plugin(
    tmp_path, add_specification, test_plugin_manager, app_broken_plugin
):
    """Make sure bad plugins can raise errors"""

    test_plugin_manager.discover_prefix = 'app_'
    test_plugin_manager.discover_path = tmp_path

    with pytest.raises(PluginImportError):
        test_plugin_manager.discover(ignore_errors=False)


def test_plugin_discovery_by_entry_point(
    tmp_path,
    add_specification,
    test_plugin_manager,
    good_entrypoint_plugin,
    invalid_entrypoint_plugin,
):
    @add_specification
    def test_specification(arg1, arg2):
        ...

    hook_caller = test_plugin_manager.hook.test_specification
    assert hook_caller.spec
    assert not test_plugin_manager.plugins

    test_plugin_manager.discover_entry_point = 'app.plugin'
    test_plugin_manager.discover_path = tmp_path

    # discover modules that begin with `app_`
    cnt, err = test_plugin_manager.discover()
    # we should have had one success and one error.
    assert cnt == len(err) == 1

    # the app_good_plugin module should have been found, with one hookimpl
    assert 'good_entry' in test_plugin_manager.plugins.keys()
    assert 'good_entry' in [i.plugin_name for i in hook_caller.get_hookimpls()]

    # the plugin with the invalid spec is in the path that we loaded
    assert 'invalid_entrypoint_plugin.py' in os.listdir(tmp_path)
    # but it wasn't added to the plugin manager
    assert 'invalid' not in test_plugin_manager.plugins.keys()
    # However an error should have been logged for the invalid plugin
    assert not test_plugin_manager.get_errors('good_entry')
    errs = test_plugin_manager.get_errors('invalid')
    assert errs
    assert isinstance(errs[0], PluginValidationError)
    # and it should now be blocked
    assert test_plugin_manager.is_blocked('invalid')

    # if we unblock the plugin and turn off ignore_errors
    # we'll get a registration error at discovery
    test_plugin_manager.set_blocked('invalid', False)
    with pytest.raises(PluginValidationError):
        test_plugin_manager.discover(ignore_errors=False)


def test_lazy_autodiscovery(
    tmp_path, add_specification, test_plugin_manager, good_entrypoint_plugin
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
    assert test_plugin_manager.plugins.get('good_entry')
    assert test_plugin_manager.hook._needs_discovery is False


def test_discovery_all_together(full_plugin_manager):
    hook_caller = full_plugin_manager.hook.test_specification
    assert len(hook_caller.get_hookimpls()) == 4
    assert len(full_plugin_manager.plugins) == 4
    assert 'double_a' in full_plugin_manager.plugins.keys()
    assert 'double_b' in full_plugin_manager.plugins.keys()
    assert 'app_good_plugin' in full_plugin_manager.plugins.keys()
    assert 'good_entry' in full_plugin_manager.plugins.keys()


def test_getting_errors(invalid_entrypoint_plugin, caplog):
    with temp_path_additions(invalid_entrypoint_plugin):
        import invalid_entrypoint_plugin as mod

    try:
        raise ValueError('I caused this')
    except ValueError as e:
        err = PluginError(plugin=mod, plugin_name='invalid', cause=e)
    errs = PluginError.get(plugin=mod)
    assert mod in {p.plugin for p in errs}
    errs = PluginError.get(plugin_name='invalid')
    assert 'invalid' in {p.plugin_name for p in errs}

    assert 'I caused this' in err.format()
    err.log()
    assert ' Error in plugin "invalid"' in caplog.text


@pytest.mark.parametrize('blocked', ['ALL', 'ENTRYPOINT', 'PREFIX'])
def test_env_var_disable(
    blocked,
    tmp_path,
    add_specification,
    test_plugin_manager,
    good_entrypoint_plugin,
    app_good_plugin,
    monkeypatch,
):
    @add_specification
    def test_specification(arg1, arg2):
        ...

    test_plugin_manager.discover_entry_point = 'app.plugin'
    test_plugin_manager.discover_prefix = 'app_'
    test_plugin_manager.discover_path = tmp_path

    monkeypatch.setenv(f'DISABLE_{blocked}_PLUGINS', '1')
    if blocked == 'ALL':
        with pytest.warns(UserWarning):
            cnt, err = test_plugin_manager.discover()
    else:
        cnt, err = test_plugin_manager.discover()
    assert cnt == (0 if blocked == 'ALL' else 1)

    if blocked == 'ENTRYPOINT':
        assert 'app_good_plugin' in test_plugin_manager.plugins.keys()
        assert 'good_entry' not in test_plugin_manager.plugins.keys()
    elif blocked == 'PREFIX':
        assert 'app_good_plugin' not in test_plugin_manager.plugins.keys()
        assert 'good_entry' in test_plugin_manager.plugins.keys()
    elif blocked == 'ALL':
        assert 'app_good_plugin' not in test_plugin_manager.plugins.keys()
        assert 'good_entry' not in test_plugin_manager.plugins.keys()

    monkeypatch.delenv(f'DISABLE_{blocked}_PLUGINS')
