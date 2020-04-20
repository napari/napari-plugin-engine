from .exceptions import HookCallError, PluginValidationError, PluginCallError
from .markers import HookimplMarker, HookspecMarker
from .hooks import HookCaller
from .manager import PluginManager
from .implementation import HookImpl, HookSpec
from .callers import HookResult

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
    "PluginManager",
    "PluginCallError",
    "PluginValidationError",
]
