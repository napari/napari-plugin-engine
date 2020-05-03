class config:
    def set(*args, **kwargs):
        import napari.config

        return napari.config.set(*args, **kwargs)

    def get(*args, **kwargs):
        import napari.config

        return napari.config.get(*args, **kwargs)

    def pop(*args, **kwargs):
        import napari.config

        return napari.config.pop(*args, **kwargs)
