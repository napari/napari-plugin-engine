import inspect
import json
import os
from types import FunctionType
from typing import Callable, Dict, List, Tuple, Union

from napari.plugins import hook_specifications  # specification to be migrated
from pkginfo import SDist, Wheel

from napari_plugin_engine import HookImplementation, PluginManager

functions: Dict[Tuple[str, str], Callable] = dict()


def validate_artifacts(folder):
    """Validate the artifacts built for distribution.

    Parameters
    ----------
    folder : str
        artifacts folder after build with setuptools
    
    Raises
    ------
    AssertionError
        If the artifact is not build properly,
    """
    for pkgpath in os.listdir(folder):
        pkgpath = os.path.join(folder, pkgpath)
        if pkgpath.endswith('.tar.gz'):
            dist = SDist(pkgpath)
        elif pkgpath.endswith('.whl'):
            dist = Wheel(pkgpath)
        else:
            print(f'Not a valid format {pkgpath}')
            continue
        assert 'Framework :: napari' in dist.classifiers
        print(f'validated {pkgpath}')


def validate_function(
    args: Union[Callable, List[Callable]],
    hookimpl: HookImplementation,
):
    """
    Validate the function is properly implemented in napari supported format
    Raise AssertionError when function is not in supported format

    Parameters
    ----------
    args : function to validate
    hookimpl : implementation of the hook

    """
    plugin_name = hookimpl.plugin_name
    hook_name = '`napari_experimental_provide_function`'

    assert plugin_name is not None, "No plugin name specified"
    for func in args if isinstance(args, list) else [args]:
        assert not isinstance(func, tuple), (
            "To provide multiple function widgets "
            "please use a LIST of callables"
        )
        assert isinstance(func, FunctionType), (
            f'Plugin {plugin_name!r} provided a non-callable type to '
            f'{hook_name}: {type(func)!r}. Function widget ignored.'
        )

        # Get function name
        name = func.__name__.replace('_', ' ')

        key = (plugin_name, name)
        assert key not in functions, (
            "Plugin '{}' has already registered a function widget '{}' "
            "which has now been overwritten".format(*key)
        )

        functions[key] = func


def list_function_implementations(plugin_name=None):
    """
    List function implementations found when loaded by napari

    Parameters
    ----------
    plugin_name : if provided, only show functions from the given plugin name

    Returns
    -------
    json string for the list of function signatures

    Example:
    [{
        "plugin name": "napari-demo",
        "function name": "image arithmetic",
        "args": ["layerA", "operation", "layerB"],
        "annotations": {
            "return": "napari.types.ImageData",
            "layerA": "napari.types.ImageData",
            "operation": "<enum 'Operation'>",
            "layerB": "napari.types.ImageData"
        },
        "defaults": null
    }]
    """
    plugin_manager = PluginManager(
        'napari', discover_entry_point='napari.plugin'
    )
    with plugin_manager.discovery_blocked():
        plugin_manager.add_hookspecs(hook_specifications)
    fw_hook = plugin_manager.hook.napari_experimental_provide_function
    functions.clear()
    fw_hook.call_historic(result_callback=validate_function, with_impl=True)
    function_signatures = []
    for key, value in functions.items():
        spec = inspect.getfullargspec(value)
        if plugin_name is None or plugin_name == key[0]:
            function_signatures.append(
                {
                    'plugin name': key[0],
                    'function name': key[1],
                    'args': spec.args,
                    'annotations': spec.annotations,
                    'defaults': spec.defaults,
                }
            )
    return json.dumps(function_signatures, default=str)
