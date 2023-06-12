# -*- coding: utf-8 -*-

"""
Compatability module for various pythons and environments.
"""

# stdlib
import sys

# This moved in py3.10
if sys.version_info.major == 3:
    if sys.version_info.minor >= 10:
        import collections

        collections.Callable = collections.abc.Callable  # type: ignore[attr-defined]

# ==============================================================================
