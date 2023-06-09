# -*- coding: utf-8 -*-

"""
Compatability module for various pythons and environments.
"""

# stdlib
import sys

# !!!: MIGRATION. these move in webob 2.0
try:
    # webob 1.x
    from webob.compat import bytes_ as webob_bytes_
    from webob.compat import text_ as webob_text_
except ImportError as exc:  # noqa: F841
    # webob 2.x
    from webob.util import bytes_ as webob_bytes_
    from webob.util import text_ as webob_text_


# This moved in py3.10
if sys.version_info.major == 3:
    if sys.version_info.minor >= 10:
        import collections

        collections.Callable = collections.abc.Callable  # type: ignore[attr-defined]


# ==============================================================================
