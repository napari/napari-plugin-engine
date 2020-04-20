from .callers import HookCallError
from .markers import HookimplMarker, HookspecMarker
from .hooks import HookCaller
from .manager import PluginManager, PluginValidationError
from .implementation import HookImpl, HookSpec


__version__ = "0.0.0"

napari_hook_implementation = HookimplMarker("napari")
napari_hook_specification = HookspecMarker("napari")

__all__ = [
    "PluginManager",
    "PluginValidationError",
    "HookCallError",
    "HookImpl",
    "HookSpec",
    "HookCaller",
    "HookspecMarker",
    "HookimplMarker",
    "napari_hook_implementation",
    "napari_hook_specification",
]
