try:
    from napari import config
except ImportError:

    class config:  # type: ignore
        def set(*args, **kwargs):
            pass

        def get(*args, **kwargs):
            pass
