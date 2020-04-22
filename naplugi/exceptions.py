from typing import Optional, Union, Type, TYPE_CHECKING, List
from types import ModuleType
import logging

ClassOrModule = Union[ModuleType, Type]

if TYPE_CHECKING:
    from .manager import PluginManager  # noqa: F401
    from .plugin import Plugin  # noqa: F401


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
    def plugin(self) -> Optional['Plugin']:
        if self.manager:
            return self.manager.plugins.get(self.plugin_name)

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
            if (
                plugin_name is not Ellipsis
                and error.plugin_name != plugin_name
            ):
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

    def log(self, package_info=True, logger=None, level=logging.ERROR):
        if not isinstance(logger, logging.Logger):
            logger = logging.getLogger(logger)

        msg = f'PluginError: {self}\n'
        if self.__cause__:
            cause = str(self.__cause__).replace("\n", "\n" + " " * 13)
            msg += f'  Cause was: {cause}'

        if package_info and self.plugin:
            meta = self.plugin.standard_meta
            meta.pop('license', None)
            meta.pop('summary', None)
            if meta:
                msg += "\n" + "\n".join(
                    [f'{k: >11}: {v}' for k, v in meta.items() if v]
                )
        msg += '\n'
        logger.log(level, msg)


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

    def __init__(
        self, hook_implementation, msg=None, cause=None, manager=None
    ):
        plugin_name = hook_implementation.plugin_name
        specname = hook_implementation.specname

        if not msg:
            msg = f"Error in plugin '{plugin_name}', hook '{specname}'"
            if cause:
                msg += f": {str(cause)}"

        super().__init__(
            msg, plugin_name=plugin_name, cause=cause, manager=manager
        )
