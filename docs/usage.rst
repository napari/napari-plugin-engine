##############
Usage Overview
##############


Create a plugin manager
=======================

.. currentmodule:: napari_plugin_engine

A :class:`PluginManager` is the main object that registers and organizes
plugins.  It is instantiated with a ``project_name``:

.. code-block:: python

   plugin_manager = PluginManager('my_project')

All :ref:`hook specifications <hook-specifications>` and :ref:`hook
implementations <hook-implementations>`  must use the same ``project_name`` if
they are to be recognized by this ``plugin_manager`` instance.

.. _hook-specifications:

Add some hook specifications
============================

You add `hook specifications
<https://pluggy.readthedocs.io/en/latest/#specifications>`_ which outline the
function signatures plugins may implement:

.. code-block:: python

   plugin_manager.add_hookspecs(some_class_or_module)

... where "``some_class_or_module``"  is any `namespace
<https://docs.python.org/3/tutorial/classes.html#python-scopes-and-namespaces>`_
object (such as a class or module) that has some functions that have been
decorated as hook specifications for ``'my_project'`` using a
:class:`HookSpecificationMarker` decorator.

.. code-block:: python

   # some_class_or_module.py

   from napari_plugin_engine import HookSpecificationMarker

   my_project_hook_specification = HookSpecificationMarker('my_project')

   @my_project_hook_specification
   def do_something(arg1: int, arg2: int): -> int:
       """Take two integers and return one integer."""

After calling :meth:`~PluginManager.add_hookspecs`, your ``plugin_manager``
instance will have a new :class:`HookCaller` instance created under the
``plugin_manager.hooks`` namespace, for each hook specification discovered.
In this case, there will be a new one at ``plugin_manager.hooks.do_something``.

.. _hook-implementations:

(Plugins) write hook implementations
====================================

Plugins may then provide *implementations* for your hook specifications, by
creating classes or modules that contain functions that are decorated with an
instance of a :class:`HookImplementationMarker` that has been created using the *same*
project name (in this example: ``'my_project'``)

.. code-block:: python

   # some_plugin.py

   from napari_plugin_engine import HookImplementationMarker

   my_project_hook_implementation = HookImplementationMarker('my_project')

   @my_project_hook_implementation
   def do_something(arg1, arg2):
       return arg1 + arg2

Register plugins
================

You may directly *register* these modules with the ``plugin_manager`` ... 

.. code-block:: python

   import some_plugin

   plugin_manager.register(some_plugin)

Autodiscover plugins in the environment
---------------------------------------

However, it is more often the case that you will want to *discover* plugins in
your environment.  ``napari-plugin-engine`` provides two ways to discover
plugins via two different conventions:

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
functions decorated with the appropriate :class:`HookImplementationMarker` (as
shown above in ``some_plugin.py``)

.. code-block:: python

   plugin_manager.discover(
      entry_point='my_project.plugin', prefix='my_project_'
   )

Use (call) the plugin implementations
=====================================

Your :class:`HookCaller` should now be populated with any of the
implementations found in plugins, as :class:`HookImplementation` objects on the
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

How the ``plugin_name`` is chosen
=================================

**1. If plugin discovery via entry_points is used**

(e.g. ``plugin_manager.discover(entry_point='app.plugin')``), then plugins
will be named using the name of the entry_point provided by each plugin.  Note,
a single package may provide multiple plugins via entry points.  For example,
if a package had the following ``entry_points`` declared in their ``setup.py``
file:

.. code-block:: python

   # setup.py

   setup(
   ...
   entry_points={'app.plugin': ['plugin1 = module_a', 'plugin2 = module_b']},
   ...
   )

... then ``manager.discover(entry_point='app.plugin')`` would register two
plugins, named ``"plugin1"`` (which would inspect ``module_a`` for
implementations) and ``"plugin2"`` (which would inspect ``module_b`` for
implementations).

**2. If plugin discovery via naming convention is used**

(e.g. ``plugin_manager.discover(prefix='app_')``), then... 

   **2a. If a** ``dist-info`` **folder is found for the module**
   
   Then the plugin will be named using the `Name key
   <https://packaging.python.org/specifications/core-metadata/#name>`_ in the
   distribution ``METADATA`` file if one is available.  Usually, this will come
   from having a ``setup(name="distname", ...)`` entry in a ``setup.py`` file.
   See `Core metadata specifications
   <https://packaging.python.org/specifications/core-metadata/#name>`_ and `PEP
   566 <https://www.python.org/dev/peps/pep-0566/>`_ for details.

   **2a. If no distribution metadata can be located**

   The the plugin will be named using the name of the module itself.

**3. If a plugin is directly registered**

(e.g. ``plugin_manager.register(object, name)``), then if a ``name`` argument
is provided to the :meth:`PluginManager.register` method, it will be used as
the ``plugin_name``, otherwise, the string form of the object is used:
``str(id(object))``