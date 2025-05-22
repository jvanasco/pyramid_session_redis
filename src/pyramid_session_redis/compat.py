# -*- coding: utf-8 -*-

"""
Compatability module for various pythons and environments.
"""

# stdlib
import sys


# internal use only
_PY_3_9_OR_ABOVE = False


if sys.version_info.major == 3:

    if sys.version_info.minor >= 9:
        # hashlib.md5 will accept `usedforsecurity=False` kwarg
        _PY_3_9_OR_ABOVE = True

    if sys.version_info.minor >= 10:

        # This moved in py3.10
        import collections

        collections.Callable = collections.abc.Callable  # type: ignore[attr-defined]


# ==============================================================================
