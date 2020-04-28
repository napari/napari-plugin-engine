import inspect
import sys
from functools import lru_cache
from typing import Dict, Any, Optional, overload

if sys.version_info >= (3, 8):
    from importlib import metadata as importlib_metadata
else:
    import importlib_metadata


@lru_cache(maxsize=1)
def _top_level_module_to_dist() -> Dict[str, importlib_metadata.Distribution]:
    mapping = {}
    for dist in importlib_metadata.distributions():
        modules = dist.read_text('top_level.txt')
        if modules:
            for mod in filter(None, modules.split('\n')):
                mapping[mod] = dist
    return mapping


def _object_to_top_level_module(obj: Any) -> Optional[str]:
    module = inspect.getmodule(obj)
    name = getattr(module, '__name__', None)
    return name.split('.')[0] if name else None


@lru_cache(maxsize=128)
def get_dist(obj) -> Optional[importlib_metadata.Distribution]:
    """Return a :class:`importlib.metadata.Distribution` for any python object.

    Parameters
    ----------
    obj : Any
        A python object

    Returns
    -------
    dist: Distribution
        The distribution object for the corresponding package, if found.
    """
    top_level = _object_to_top_level_module(obj)
    return _top_level_module_to_dist().get(top_level or '')


def get_version(plugin) -> str:
    version = ''
    dist = get_dist(plugin)
    if dist:
        version = dist.metadata.get('version')
    if not version and inspect.ismodule(plugin):
        version = getattr(plugin, '__version__', None)
    if not version:
        top_module = _object_to_top_level_module(plugin)
        if top_module in sys.modules:
            version = getattr(sys.modules[top_module], '__version__', None)
    return str(version) if version else ''


@overload
def get_metadata(plugin, arg: str, *args: None) -> Optional[str]:
    ...


@overload  # noqa: F811
def get_metadata(  # noqa: F811
    plugin, arg: str, *args: str
) -> Dict[str, Optional[str]]:
    ...


def get_metadata(plugin, *args):  # noqa: F811
    """Get metadata for this plugin.

    Valid arguments are any keys from the Core metadata specifications:
    https://packaging.python.org/specifications/core-metadata/

    Parameters
    ----------
    *args : str
        (Case insensitive) names of metadata entries to retrieve.

    Returns
    -------
    str or dict, optional
        If a single argument is provided, the value for that entry is
        returned (which may be ``None``).
        If multiple arguments are provided, a dict of {arg: value} is
        returned.
    """
    dist = get_dist(plugin)
    dct = {}
    if dist:
        for a in args:
            if a == 'version':
                dct[a] = get_version(plugin)
            else:
                dct[a] = dist.metadata.get(a)
    if len(args) == 1:
        return dct[args[0]] if dct else None
    return dct


def standard_metadata(plugin: Any) -> Dict[str, Optional[str]]:
    """Return a standard metadata dict for ``plugin``.

    Parameters
    ----------
    plugin : Any
        A python object.

    Returns
    -------
    metadata : dict
        A  dicts with plugin object metadata. The dict is guaranteed to have
        the following keys:

        - **package**: The name of the package
        - **version**: The version of the plugin package
        - **summary**: A one-line summary of what the distribution does
        - **author**: The author’s name
        - **email**: The author’s (or maintainer's) e-mail address.
        - **license**: The license covering the distribution
        - **url**: The home page for the package, or dowload url if N/A.
    """
    meta = {}
    if get_dist(plugin):
        meta = get_metadata(
            plugin,
            'name',
            'version',
            'summary',
            'author',
            'license',
            'Author-Email',
            'Home-page',
        )
        meta['package'] = meta.pop('name')
        meta['email'] = meta.pop('Author-Email') or get_metadata(
            plugin, 'Maintainer-Email'
        )
        meta['url'] = meta.pop('Home-page') or get_metadata(
            plugin, 'Download-Url'
        )
        if meta['url'] == 'UNKNOWN':
            meta['url'] = None
    return meta
