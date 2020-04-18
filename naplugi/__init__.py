from .callers import HookCallError
from .hooks import HookimplMarker, HookspecMarker
from .manager import PluginManager, PluginValidationError

__version__ = "0.1.0"

napari_hook_implementation = HookimplMarker("napari")
napari_hook_specification = HookspecMarker("napari")

__all__ = [
    "PluginManager",
    "PluginValidationError",
    "HookCallError",
    "HookspecMarker",
    "HookimplMarker",
    "napari_hook_implementation",
    "napari_hook_specification",
]
