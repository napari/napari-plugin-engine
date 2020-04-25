from .callers import HookResult
from .exceptions import (
    HookCallError,
    PluginCallError,
    PluginError,
    PluginImportError,
    PluginRegistrationError,
    PluginValidationError,
)
from .hooks import HookCaller
from .implementation import HookImpl, HookSpec
from .manager import PluginManager
from .markers import HookimplMarker, HookspecMarker
from .plugin import Plugin

__version__ = "0.0.0"

napari_hook_implementation = HookimplMarker("napari")
napari_hook_specification = HookspecMarker("napari")

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
    "Plugin",
    "PluginCallError",
    "PluginError",
    "PluginImportError",
    "PluginManager",
    "PluginRegistrationError",
    "PluginValidationError",
]
