from typing import Optional, Union, Type, TYPE_CHECKING, List
from types import ModuleType

ClassOrModule = Union[ModuleType, Type]

if TYPE_CHECKING:
    from .manager import PluginManager  # noqa: F401


class PluginError(Exception):
    _record: List['PluginError'] = []

    def __init__(
        self,
        message: str = '',
        *,
        plugin_name: str = '',
        manager: Optional['PluginManager'] = None,
        cause: Optional[BaseException] = None,
    ):
        if not message:
            message = f'Error in plugin "{plugin_name}"'
            if cause:
                message += f': {cause}'
        super().__init__(message)
        self.manager = manager
        self.plugin_name = plugin_name
        self.__cause__ = cause
        # store all PluginError instances.  can be retrieved with get()
        PluginError._record.append(self)

    @property
    def plugin(self) -> Optional[ClassOrModule]:
        if self.manager:
            return self.manager.get_plugin(self.plugin_name)

    @classmethod
    def get(
        cls,
        manager: Optional['PluginManager'] = Ellipsis,
        plugin_name: str = Ellipsis,
        error_type: Type[BaseException] = Ellipsis,
    ) -> List['PluginError']:
        errors: List['PluginError'] = []
        for error in cls._record:
            if manager is not Ellipsis and error.manager != manager:
                continue
            if plugin_name is not Ellipsis and error.plugin_name != error:
                continue
            if error_type is not Ellipsis:
                import inspect

                if not (
                    inspect.isclass(error_type)
                    and issubclass(error_type, BaseException)
                ):
                    raise TypeError(
                        "The `error_type` argument must be an exception class"
                    )
                if not isinstance(error.__cause__, error_type):
                    continue
            errors.append(error)
        return errors


class PluginImportError(PluginError, ImportError):
    pass


class PluginRegistrationError(PluginError):
    pass


class HookCallError(PluginError):
    """ Hook was called wrongly. """


class PluginValidationError(PluginError):
    """ plugin failed validation.

    :param object plugin: the plugin which failed validation,
        may be a module or an arbitrary object.
    """

    pass


class PluginCallError(PluginError):
    """Raised when an error is raised when calling a plugin implementation."""

    def __init__(self, hook_implementation, msg=None, cause=None):
        plugin_name = hook_implementation.plugin_name
        specname = getattr(
            hook_implementation,
            'specname',
            hook_implementation.function.__name__,
        )

        if not msg:
            msg = f"Error in plugin '{plugin_name}', hook '{specname}'"
            if cause:
                msg += f": {str(cause)}"

        super().__init__(msg)
        if cause:
            self.__cause__ = cause
