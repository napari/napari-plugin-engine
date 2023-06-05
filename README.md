# napari plugin engine

[![License](https://img.shields.io/pypi/l/napari-plugin-engine.svg?color=green)](https://github.com/napari/napari-plugin-engine/raw/master/LICENSE)
[![Build Status](https://travis-ci.com/napari/napari-plugin-engine.svg?branch=master)](https://travis-ci.com/napari/napari-plugin-engine)
[![Docs Status](https://readthedocs.org/projects/napari-plugin-engine/badge/?version=latest)](https://readthedocs.org/projects/napari_plugin_engine/)
[![codecov](https://codecov.io/gh/napari/napari/branch/master/graph/badge.svg)](https://codecov.io/gh/napari/napari)
[![Python Version](https://img.shields.io/pypi/pyversions/napari-plugin-engine.svg?color=green)](https://python.org)
[![PyPI](https://img.shields.io/pypi/v/napari-plugin-engine.svg?color=green)](https://pypi.org/project/napari-plugin-engine)

`napari-plugin-engine` is the first generation napari plugin engine. We
recommend new plugins should use the second generation [npe2](https://github.com/napari/npe2).

`napari-plugin-engine` is a fork of [pluggy](https://github.com/pytest-dev/pluggy),
modified by the [napari](https://github.com/napari/napari) team.

There are some API and feature changes, including:

- discovery via [naming
  convention](https://packaging.python.org/guides/creating-and-discovering-plugins/#using-naming-convention)
  as well as
  [entry_points](https://packaging.python.org/guides/creating-and-discovering-plugins/#using-package-metadata)
- support for reordering of hook calls after registration.
- enhanced API for retrieving plugin package metadata.
- modified plugin call and registration exception handling
- modified `HookResult` object and hook call loop, with ability to retrieve the
  `HookImplementation` responsible for the result.
- lazy plugin discovery
- some changes to variable and attribute naming
- removed all deprecated code
- type annotations on everything
- pytest fixtures for testing
- a couple napari-specific convenience imports

For usage overview and a reference for the `napari-plugin-engine` API, see our
[Documentation](https://napari-plugin-engine.readthedocs.io/en/latest/)

(see also: the [pluggy documentation](https://pluggy.readthedocs.io/en/latest/))

## install

```shell
pip install napari-plugin-engine
```

## Usage

see [documentation](https://napari-plugin-engine.readthedocs.io/en/latest/usage.html)
