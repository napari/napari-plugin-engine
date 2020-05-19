# this weirdness is to avoid circular imports.
# because napari also depends on napari_plugin_engine


class napari_config:
    @staticmethod
    def set(*args, **kwargs):
        import napari.config

        napari.config.set(*args, **kwargs)

    @staticmethod
    def get(*args, **kwargs):
        import napari.config

        return napari.config.get(*args, **kwargs)

    @staticmethod
    def pop(*args, **kwargs):
        import napari.config

        return napari.config.pop(*args, **kwargs)
