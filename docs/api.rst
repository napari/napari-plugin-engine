###########
naplugi API
###########

.. currentmodule:: naplugi

.. autosummary::
   :toctree:
   :nosignatures:

   PluginManager
   HookCaller
   HookResult
   HookImpl
   HookSpec
   HookspecMarker
   HookimplMarker


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


HookSpec
========

.. autoclass:: HookSpec
   :members:

HookImpl
========

.. autoclass:: HookImpl
   :members:


Decorators & Markers
====================

HookspecMarker
--------------

.. autoclass:: HookspecMarker
   :members:
   :special-members:
   :exclude-members: __init__, __weakref__

HookimplMarker
--------------

.. autoclass:: HookimplMarker
   :members:
   :special-members:
   :exclude-members: __init__, __weakref__

Exceptions
==========

.. autosummary::
   :toctree:
   :nosignatures:

   PluginError
   HookCallError
   PluginValidationError
   PluginCallError

PluginError
-----------

.. autoclass:: PluginError
   :members:

HookCallError
-------------

.. autoclass:: HookCallError
   :members:

PluginValidationError
---------------------

.. autoclass:: PluginValidationError
   :members:

PluginCallError
---------------

.. autoclass:: PluginCallError
   :members:

Extra Functions
===============

.. autofunction:: naplugi.hooks._multicall

.. autofunction:: naplugi.manager.ensure_namespace

.. autofunction:: naplugi.manager.temp_path_additions


Types
=====

.. autodata:: naplugi.hooks.HookExecFunc