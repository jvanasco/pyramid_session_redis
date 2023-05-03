# -*- coding: utf-8 -*-

"""
Compatability module for various pythons and environments.
"""

# stdlib
import sys
from typing import AnyStr

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


def bytes_(s: str, encoding: str = "latin-1", errors: str = "strict") -> bytes:
    return ensure_binary(s, encoding, errors)


def native_(s, encoding: str = "latin-1", errors: str = "strict"):
    return ensure_str(s, encoding, errors)


# lifted from six
def ensure_binary(s: str, encoding: str = "utf-8", errors: str = "strict") -> bytes:
    """Coerce **s** to six.binary_type.

    For Python 2:
      - `unicode` -> encoded to `str`
      - `str` -> `str`

    For Python 3:
      - `str` -> encoded to `bytes`
      - `bytes` -> `bytes`
    """
    if isinstance(s, bytes):
        return s
    if isinstance(s, str):
        return s.encode(encoding, errors)
    raise TypeError("not expecting type '%s'" % type(s))


# lifted from six
def ensure_str(s: AnyStr, encoding: str = "utf-8", errors: str = "strict") -> str:
    """Coerce *s* to `str`.

    For Python 2:
      - `unicode` -> encoded to `str`
      - `str` -> `str`

    For Python 3:
      - `str` -> `str`
      - `bytes` -> decoded to `str`
    """
    # Optimization: Fast return for the common case.
    # mypy does not like this
    # if type(s) is str:
    #    return s
    if isinstance(s, str):
        return s
    if isinstance(s, bytes):
        return s.decode(encoding, errors)
    elif not isinstance(s, (str, bytes)):
        raise TypeError("not expecting type '%s'" % type(s))
    return s
