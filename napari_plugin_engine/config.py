try:
    from napari import config
except ImportError:

    class config:  # type: ignore
        def set(*args, **kwargs):
            pass

        def get(*args, **kwargs):
            return dict().get(*args, **kwargs)

        def pop(*args, **kwargs):
            return None
