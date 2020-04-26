from types import TracebackType
from typing import Optional, Union, Type, TYPE_CHECKING, List, Tuple, Any
import logging
from .dist import standard_meta

if TYPE_CHECKING:
    from .manager import PluginManager  # noqa: F401


ExcInfoTuple = Tuple[Type[Exception], Exception, Optional[TracebackType]]


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
            message = f'Error in plugin "{plugin}"'
            if cause:
                message += f': {cause}'
        super().__init__(message)
        self.__cause__ = cause
        # store all PluginError instances.  can be retrieved with get()
        PluginError._record.append(self)

    # TODO: fix sentinel
    @classmethod
    def get(
        cls,
        *,
        plugin: Optional[Any] = '_NULL',
        plugin_name: Optional[str] = '_NULL',
        error_type: Union[Type['PluginError'], str] = '_NULL',
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
            if plugin != '_NULL' and error.plugin != plugin:
                continue
            if plugin_name != '_NULL' and error.plugin_name != plugin_name:
                continue
            if error_type != '_NULL':
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

        msg = f'PluginError: {self}\n'
        if self.__cause__:
            cause = str(self.__cause__).replace("\n", "\n" + " " * 13)
            msg += f'  Cause was: {cause}'

        if package_info and self.plugin:
            meta = standard_meta(self.plugin)
            meta.pop('license', None)
            meta.pop('summary', None)
            if meta:
                msg += "\n" + "\n".join(
                    [f'{k: >11}: {v}' for k, v in meta.items() if v]
                )
        msg += '\n'
        logger.log(level, msg)

    def info(self) -> ExcInfoTuple:
        """Return info as would be returned from sys.exc_info()."""
        return (self.__class__, self, self.__traceback__)


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
        plugin = hook_implementation.plugin
        specname = hook_implementation.specname

        if not msg:
            msg = f"Error in plugin '{plugin_name}', hook '{specname}'"
            if cause:
                msg += f": {str(cause)}"

        super().__init__(msg, plugin=plugin, cause=cause, manager=manager)
