class PluginError(Exception):
    pass


class PluginImportError(PluginError, ImportError):
    pass


class PluginRegistrationError(PluginError):
    def __init__(self, plugin, message=''):
        self.plugin = plugin
        super().__init__(message)


class HookCallError(PluginError):
    """ Hook was called wrongly. """


class PluginValidationError(PluginError):
    """ plugin failed validation.

    :param object plugin: the plugin which failed validation,
        may be a module or an arbitrary object.
    """

    def __init__(self, plugin, message=''):
        self.plugin = plugin
        super().__init__(message)


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
