try:
    from ._version import version as __version__
except ImportError:
    # broken installation, we don't even try
    # unknown only works because we do poor mans version compare
    __version__ = "unknown"

__all__ = [
    "get_metadata",
    "HookCaller",
    "HookCallError",
    "HookImplementation",
    "HookImplementationMarker",
    "HookResult",
    "HookSpecification",
    "HookSpecificationMarker",
    "napari_hook_implementation",
    "napari_hook_specification",
    "PluginCallError",
    "PluginError",
    "PluginImplementationError",
    "PluginImportError",
    "PluginManager",
    "PluginRegistrationError",
    "PluginValidationError",
    "standard_metadata",
]

from .callers import HookResult
from .dist import get_metadata, standard_metadata
from .exceptions import (
    HookCallError,
    PluginCallError,
    PluginError,
    PluginImplementationError,
    PluginImportError,
    PluginRegistrationError,
    PluginValidationError,
)
from .hooks import HookCaller
from .implementation import HookImplementation, HookSpecification
from .manager import PluginManager
from .markers import HookImplementationMarker, HookSpecificationMarker

napari_hook_implementation = HookImplementationMarker("napari")
napari_hook_specification = HookSpecificationMarker("napari")
