import logging
from enum import Enum
from types import TracebackType
from typing import TYPE_CHECKING, Any, List, Optional, Tuple, Type, Union

from .dist import standard_metadata

if TYPE_CHECKING:
    from .manager import PluginManager  # noqa: F401


ExcInfoTuple = Tuple[Type[Exception], Exception, Optional[TracebackType]]


# https://www.python.org/dev/peps/pep-0484/#support-for-singleton-types-in-unions
class Empty(Enum):
    token = 0


_empty = Empty.token


class PluginError(Exception):
    """Base class for exceptions relating to plugins.

    Parameters
    ----------
    message : str, optional
        An optional error message, by default ''
    namespace : Optional[Any], optional
        The python object that caused the error, by default None
    cause : Exception, optional
        Exception that caused the error. Same as ``raise * from``.
        by default None
    """

    _record: List['PluginError'] = []

    def __init__(
        self,
        message: str = '',
        *,
        plugin: Optional[Any] = None,
        plugin_name: Optional[str] = None,
        cause: Optional[BaseException] = None,
    ):
        self.plugin = plugin
        self.plugin_name = plugin_name
        if not message:
            name = plugin_name or getattr(plugin, '__name__', str(id(plugin)))
            message = f'Error in plugin "{name}"'
            if cause:
                message += f': {cause}'
        super().__init__(message)
        self.__cause__ = cause
        # store all PluginError instances.  can be retrieved with get()
        PluginError._record.append(self)

    @classmethod
    def get(
        cls,
        *,
        plugin: Union[Any, Empty] = _empty,
        plugin_name: Union[str, Empty] = _empty,
        error_type: Union[Type['PluginError'], Empty] = _empty,
    ) -> List['PluginError']:
        """Return errors that have been logged, filtered by parameters.

        Parameters
        ----------
        manager : PluginManager, optional
            If provided, will restrict errors to those that are owned by
            ``manager``.
        plugin_name : str
            If provided, will restrict errors to those that were raised by
            ``plugin_name``.
        error_type : Exception
            If provided, will restrict errors to instances of ``error_type``.

        Returns
        -------
        list of PluginError
            A list of PluginErrors that have been instantiated during this
            session that match the provided parameters.

        Raises
        ------
        TypeError
            If ``error_type`` is provided and is not an exception class.
        """
        errors: List['PluginError'] = []
        for error in cls._record:
            if plugin is not _empty and error.plugin != plugin:
                continue
            if plugin_name is not _empty and error.plugin_name != plugin_name:
                continue
            if error_type is not _empty:
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

    def format(self, package_info: bool = True):
        msg = f'PluginError: {self}'
        if self.__cause__:
            msg = msg.replace(str(self.__cause__), '').strip(": ") + "\n"
            cause = repr(self.__cause__).replace("\n", "\n" + " " * 13)
            msg += f'  Cause was: {cause}'

            # show the exact file and line where the error occured
            cause_tb = self.__cause__.__traceback__
            if cause_tb:
                while True:
                    if not cause_tb.tb_next:
                        break
                    cause_tb = cause_tb.tb_next

                msg += f'\n    in file: {cause_tb.tb_frame.f_code.co_filename}'
                msg += f'\n    at line: {cause_tb.tb_lineno}'
        else:
            msg += "\n"

        if package_info and self.plugin:
            try:
                meta = standard_metadata(self.plugin)
                meta.pop('license', None)
                meta.pop('summary', None)
                if meta:
                    msg += "\n" + "\n".join(
                        [
                            f'{k: >11}: {v}'
                            for k, v in sorted(meta.items())
                            if v
                        ]
                    )
            except ValueError:
                pass
        msg += '\n'
        return msg

    def log(
        self,
        package_info: bool = True,
        logger: Union[logging.Logger, None, str] = None,
        level: int = logging.ERROR,
    ):
        """Log this error with metadata, optionally provide logger and level.

        Parameters
        ----------
        package_info : bool, optional
            If true, will include package metadata in log, by default True
        logger : logging.Logger or str, optional
            A Logger instance or name of a logger to use, by default None
        level : int, optional
            The logging level to use, by default logging.ERROR
        """
        if not isinstance(logger, logging.Logger):
            logger = logging.getLogger(logger)

        logger.log(level, self.format(package_info=package_info))

    def info(self) -> ExcInfoTuple:
        """Return info as would be returned from sys.exc_info()."""
        return (self.__class__, self, self.__traceback__)


class HookCallError(PluginError):
    """If a hook is called incorrectly.

    Usually this results when a HookCaller is called without the appropriate
    arguments.
    """


class PluginImportError(PluginError, ImportError):
    """Plugin module is unimportable."""


class PluginRegistrationError(PluginError):
    """If an unexpected error occurs during registration."""


class PluginImplementationError(PluginError):
    """Base class for errors pertaining to a specific hook implementation."""

    def __init__(self, hook_implementation, msg=None, cause=None):
        plugin = hook_implementation.plugin
        plugin_name = hook_implementation.plugin_name
        specname = hook_implementation.specname

        if not msg:
            msg = f"Error in plugin '{plugin_name}', hook '{specname}'"
            if cause:
                msg += f": {str(cause)}"

        super().__init__(
            msg,
            plugin=plugin,
            plugin_name=plugin_name,
            cause=cause,
        )


class PluginValidationError(PluginImplementationError):
    """When a plugin implementation fails validation."""


class PluginCallError(PluginImplementationError):
    """Raised when an error is raised when calling a plugin implementation."""
