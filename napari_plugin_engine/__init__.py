try:
    from ._version import version as __version__
except ImportError:
    # broken installation, we don't even try
    # unknown only works because we do poor mans version compare
    __version__ = "unknown"

__all__ = [
    "HookCaller",
    "HookCallError",
    "HookImpl",
    "HookimplMarker",
    "HookResult",
    "HookSpec",
    "HookspecMarker",
    "napari_hook_implementation",
    "napari_hook_specification",
    "PluginCallError",
    "PluginError",
    "PluginImportError",
    "PluginImplementationError",
    "PluginManager",
    "PluginRegistrationError",
    "PluginValidationError",
]

from .callers import HookResult
from .exceptions import (
    HookCallError,
    PluginCallError,
    PluginError,
    PluginImportError,
    PluginRegistrationError,
    PluginValidationError,
    PluginImplementationError,
)
from .hooks import HookCaller
from .implementation import HookImpl, HookSpec
from .manager import PluginManager
from .markers import HookimplMarker, HookspecMarker

napari_hook_implementation = HookimplMarker("napari")
napari_hook_specification = HookspecMarker("napari")
