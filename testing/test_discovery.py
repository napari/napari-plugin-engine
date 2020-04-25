import pytest
import os
from naplugi import (
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
    (tmp_path / "app_double_plugin.py").write_text(GOOD_PLUGIN)
    distinfo = tmp_path / "app_double_plugin-1.2.3.dist-info"
    distinfo.mkdir()
    (distinfo / "top_level.txt").write_text('app_double_plugin')
    (distinfo / "entry_points.txt").write_text(
        "[app.plugin]\ndouble = app_double_plugin"
    )
    (distinfo / "METADATA").write_text(
        "Metadata-Version: 2.1\n"
        "Name: double-package\n"
        "Version: 1.2.3\n"
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


@pytest.fixture
def app_invalid_plugin(tmp_path):
    (tmp_path / "app_invalid_plugin.py").write_text(INVALID_PLUGIN)


@pytest.fixture
def app_broken_plugin(tmp_path):
    (tmp_path / "app_broken_plugin.py").write_text('raise ValueError("broke")')


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
    """Plugins using both naming convention and entrypoints only register once.
    """

    @add_specification
    def test_specification(arg1, arg2):
        ...

    assert not test_plugin_manager.plugins
    cnt, err = test_plugin_manager.discover(tmp_path, **regkwargs)
    hook_caller = test_plugin_manager.hook.test_specification
    if regkwargs:
        assert cnt == 1
        assert len(hook_caller.get_hookimpls()) == 1
        if 'entry_point' in regkwargs:
            # if an entry_point with a matching group is provided
            # the plugin will be named after the entrypoint name
            assert 'double' in test_plugin_manager.plugins.keys()
        else:
            # if entry point discovery is disabled, but a dist-info folder for
            # the package is found, then the plugin will be named using the
            # package `Name` key in the METADATA file.
            assert 'double-package' in test_plugin_manager.plugins.keys()
        # (name convention modules that do not have associated METADATA will
        # just be named after the module)
    else:
        assert cnt == 0
        assert not hook_caller.get_hookimpls()
        assert 'double' not in test_plugin_manager.plugins.keys()


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

    # discover modules that begin with `app_`
    cnt, err = test_plugin_manager.discover(tmp_path, entry_point='app.plugin')
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
        test_plugin_manager.discover(
            tmp_path, entry_point='app.plugin', ignore_errors=False
        )


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


def test_discovery_all_together(
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

    hook_caller = test_plugin_manager.hook.test_specification
    cnt, err = test_plugin_manager.discover(
        tmp_path, entry_point='app.plugin', prefix='app_'
    )
    assert cnt == 3
    assert len(err) == 2

    assert len(hook_caller.get_hookimpls()) == 3
    assert len(test_plugin_manager.plugins) == 3
    assert 'double' in test_plugin_manager.plugins.keys()
    assert 'app_good_plugin' in test_plugin_manager.plugins.keys()
    assert 'good_entry' in test_plugin_manager.plugins.keys()


@pytest.mark.parametrize('thing', ['', 'ENTRYPOINT_', 'PREFIX_'])
def test_env_var_disable(
    thing,
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

    monkeypatch.setenv(f'NAPLUGI_DISABLE_{thing}PLUGINS', '1')
    if thing:
        cnt, err = test_plugin_manager.discover(
            tmp_path, entry_point='app.plugin', prefix='app_'
        )
    else:
        with pytest.warns(UserWarning):
            cnt, err = test_plugin_manager.discover(
                tmp_path, entry_point='app.plugin', prefix='app_'
            )
    assert cnt == (1 if thing else 0)

    if thing == 'ENTRYPOINT':
        assert 'app_good_plugin' in test_plugin_manager.plugins.keys()
        assert 'good_entry' not in test_plugin_manager.plugins.keys()
    elif thing == 'PREFIX':
        assert 'app_good_plugin' not in test_plugin_manager.plugins.keys()
        assert 'good_entry' in test_plugin_manager.plugins.keys()
    elif not thing:
        assert 'app_good_plugin' not in test_plugin_manager.plugins.keys()
        assert 'good_entry' not in test_plugin_manager.plugins.keys()

    monkeypatch.delenv(f'NAPLUGI_DISABLE_{thing}PLUGINS')
