.. naplugi documentation master file, created by
   sphinx-quickstart on Thu Apr 23 12:51:14 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to naplugi's documentation!
===================================

naplugi is a fork of `pluggy <https://github.com/pytest-dev/pluggy>`_ modified
by the `napari <https://github.com/napari/napari>`_ team for use in napari.

While much of the original API described in the `pluggy docs
<https://pluggy.readthedocs.io/en/latest/>`_ will still be valid here, there
are definitely some breaking changes and different conventions here.

Usage overview
------------

.. currentmodule:: naplugi

A :class:`PluginManager` is instantiated with a ``project_name``:

.. code-block:: python

   plugin_manager = PluginManager('my_project')

You add `hook specifications
<https://pluggy.readthedocs.io/en/latest/#specifications>`_ which outline the
possible functions that plugins can implement:

.. code-block:: python

   plugin_manager.add_hookspecs(some_class_or_module)

... where "``some_class_or_module``"  is any `namespace
<https://docs.python.org/3/tutorial/classes.html#python-scopes-and-namespaces>`_
object (such as a class or module) that has some functions that have been
decorated as hook specifications for ``'my_project'`` using a
:class:`HookspecMarker` decorator.

.. code-block:: python

   # some_class_or_module.py

   from naplugi import HookspecMarker

   my_project_hook_specification = HookspecMarker('my_project')

   @my_project_hook_specification
   def do_something(arg1: int, arg2: int): -> int:
       """Take two integers and return one integer."""

After calling :meth:`~PluginManager.add_hookspecs`, your ``plugin_manager``
instance will have a new :class:`HookCaller` instance created under the
``plugin_manager.hooks`` namespace, for each hook specification discovered.
In this case, there will be a new one at ``plugin_manager.hooks.do_something``.

Plugins may then provide *implementations* for your hook specifications, by
creating classes or modules that contain functions that are decorated with an
instance of a :class:`HookimplMarker` that has been created using the *same*
project name (in this example: ``'my_project'``)

.. code-block:: python

   # some_plugin.py

   from naplugi import HookimplMarker

   my_project_hook_implementation = HookimplMarker('my_project')

   @my_project_hook_implementation
   def do_something(arg1, arg2):
       return arg1 + arg2

You may directly *register* these modules with the `plugin_manager` ... 

.. code-block:: python

   import some_plugin

   plugin_manager.register(some_plugin)

However, it is more often the case that you will want to *discover* plugins in
your environment.  ``naplugi`` provides two ways to discover plugins via two
different conventions:

1. `Using package metadata
<https://packaging.python.org/guides/creating-and-discovering-plugins/#using-package-metadata>`_:
looking for distributions that declare a specific `entry_point
<https://setuptools.readthedocs.io/en/latest/setuptools.html#dynamic-discovery-of-services-and-plugins>`_
in their ``setup.py`` file.

2. `Using naming convention
<https://packaging.python.org/guides/creating-and-discovering-plugins/#using-naming-convention>`_:
looking for modules that begin with a specific prefix.

You can look for either or both, in single call to
:meth:`~PluginManager.discover`, which will import any modules or entry_points
that follow one of the aforementioned conventions, and search them for
functions decorated with the appropriate :class:`HookimplMarker` (as shown
above in ``some_plugin.py``)

.. code-block:: python

   plugin_manager.discover(
      entry_point='my_project.plugin', prefix='my_project_'
   )

Your :class:`HookCaller` should now be populated with any of the
implementations found in plugins, as :class:`HookImpl` objects on the
:class:`HookCaller`.

.. code-block:: python

   # show all implementations for do_something
   plugin_manager.hooks.do_something.get_hookimpls()

Finally, you can call some or all of the plugin implementation functions by
directly calling the :class:`HookCaller` object:

.. code-block:: python

   result = plugin_manager.hooks.do_something(arg1=2, arg2=7)

   # assuming only some_plugin.py from above is registered: 
   print(result)  # [9]

By default, *all* plugin implementations are called, and all non-``None``
results are returned in a list.  However, this is configurable and depends on
how the ``@my_project_hook_specification`` was used, and how the
:class:`HookCaller` was called


.. toctree::
   :maxdepth: 3
   :caption: API reference:

   api