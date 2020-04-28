#############
API Reference
#############

.. currentmodule:: napari_plugin_engine

.. autosummary::
   :nosignatures:

   PluginManager
   HookCaller
   HookResult
   HookImplementation
   HookSpecification
   HookSpecificationMarker
   HookImplementationMarker


PluginManager
=============

.. autoclass:: PluginManager
   :members:
   :private-members:
   :exclude-members: _load_and_register

HookCaller
==========

.. autoclass:: HookCaller
   :members:
   :private-members:
   :special-members:
   :exclude-members:
      __init__,
      __repr__,
      __weakref__,
      _check_call_kwargs,
      _maybe_apply_history,

HookResult
==========

.. autoclass:: HookResult
   :members:


HookSpecification
=================

.. autoclass:: HookSpecification
   :members:

HookImplementation
==================

.. autoclass:: HookImplementation
   :members:


Decorators & Markers
====================

HookSpecificationMarker
-----------------------

.. autoclass:: HookSpecificationMarker
   :members:
   :special-members:
   :exclude-members: __init__, __weakref__

HookImplementationMarker
------------------------

.. autoclass:: HookImplementationMarker
   :members:
   :special-members:
   :exclude-members: __init__, __weakref__

Exceptions
==========

.. autosummary::
   :nosignatures:

   PluginError
   PluginImportError
   PluginRegistrationError
   PluginImplementationError
   PluginValidationError
   PluginCallError
   HookCallError

PluginError
-----------

.. autoclass:: PluginError
   :members:
   :show-inheritance:

PluginImportError
-----------------

.. autoclass:: PluginImportError
   :members:
   :show-inheritance:

PluginRegistrationError
------------------------

.. autoclass:: PluginRegistrationError
   :members:
   :show-inheritance:

PluginImplementationError
-------------------------

.. autoclass:: PluginImplementationError
   :members:
   :show-inheritance:

PluginValidationError
---------------------

.. autoclass:: PluginValidationError
   :members:
   :show-inheritance:

PluginCallError
---------------

.. autoclass:: PluginCallError
   :members:
   :show-inheritance:

HookCallError
-------------

.. autoclass:: HookCallError
   :members:
   :show-inheritance:

Extra Functions
===============

.. autofunction:: napari_plugin_engine.hooks._multicall

.. autofunction:: napari_plugin_engine.manager.ensure_namespace

.. autofunction:: napari_plugin_engine.manager.temp_path_additions

.. autofunction:: napari_plugin_engine.dist.get_dist


Types
=====

.. autodata:: napari_plugin_engine.hooks.HookExecFunc