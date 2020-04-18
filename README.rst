====================================
naplugi - pluggy modified for napari
====================================

|pypi| |versions| |travis| |appveyor| |black| |codecov|

this is a fork of `pluggy`_, modified by the `napari`_ team.


An example
==========

.. code-block:: python

    import naplugi

    hookspec = naplugi.HookspecMarker("myproject")
    hookimpl = naplugi.HookimplMarker("myproject")


    class MySpec(object):
        """A hook specification namespace.
        """

        @hookspec
        def myhook(self, arg1, arg2):
            """My special little hook that you can customize.
            """


    class Plugin_1(object):
        """A hook implementation namespace.
        """

        @hookimpl
        def myhook(self, arg1, arg2):
            print("inside Plugin_1.myhook()")
            return arg1 + arg2


    class Plugin_2(object):
        """A 2nd hook implementation namespace.
        """

        @hookimpl
        def myhook(self, arg1, arg2):
            print("inside Plugin_2.myhook()")
            return arg1 - arg2


    # create a manager and add the spec
    pm = naplugi.PluginManager("myproject")
    pm.add_hookspecs(MySpec)

    # register plugins
    pm.register(Plugin_1())
    pm.register(Plugin_2())

    # call our ``myhook`` hook
    results = pm.hook.myhook(arg1=1, arg2=2)
    print(results)


Running this directly gets us::

    $ python docs/examples/toy-example.py
    inside Plugin_2.myhook()
    inside Plugin_1.myhook()
    [-1, 3]


.. badges

.. |pypi| image:: https://img.shields.io/pypi/v/naplugi.svg
    :target: https://pypi.org/pypi/naplugi

.. |versions| image:: https://img.shields.io/pypi/pyversions/naplugi.svg
    :target: https://pypi.org/pypi/naplugi

.. |travis| image:: https://img.shields.io/travis/napari/naplugi/master.svg
    :target: https://travis-ci.org/napari/naplugi

.. |appveyor| image:: https://img.shields.io/appveyor/ci/pytestbot/naplugi/master.svg
    :target: https://ci.appveyor.com/project/pytestbot/naplugi

.. |black| image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/ambv/black

.. |codecov| image:: https://codecov.io/gh/napari/naplugi/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/napari/naplugi
    :alt: Code coverage Status

.. links
.. _pytest:
    http://pytest.org
.. _tox:
    https://tox.readthedocs.org
.. _napari:
    http://github.com/napari/napari
.. _pluggy:
    https://github.com/pytest-dev/pluggy
