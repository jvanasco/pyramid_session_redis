# -*- coding: utf-8 -*-

"""
Compatability module for various pythons and environments.
"""
from six.moves import cPickle as pickle
from six import ensure_binary, ensure_str
from six import PY2, PY3

# !!!: MIGRATION. these move in webob 2.0
try:
    # webon 1.x
    from webob.compat import bytes_ as webob_bytes_
    from webob.compat import text_ as webob_text_
except:
    # webon 2.x
    from webob.util import bytes_ as webob_bytes_
    from webob.util import text_ as webob_text_


# ==============================================================================


try:
    # python3.6 secrets module
    from secrets import token_urlsafe, token_hex
except ImportError:  # pragma: no cover
    import os
    import base64
    import binascii

    def token_bytes(nbytes=32):
        """
        :param nbytes: default 32
        """
        return os.urandom(nbytes)

    def token_urlsafe(nbytes=32):
        """
        :param nbytes: default 32
        """
        token = base64.urlsafe_b64encode(token_bytes(nbytes)).rstrip(b"=")
        return token.decode("ascii") if PY3 else token

    def token_hex(nbytes=32):
        """
        :param nbytes: default 32
        """
        token = binascii.hexlify(token_bytes(nbytes))
        return token.decode("ascii") if PY3 else token


def bytes_(s, encoding="latin-1", errors="strict"):
    return ensure_binary(s, encoding, errors)


def native_(s, encoding="latin-1", errors="strict"):
    return ensure_str(s, encoding, errors)


def to_unicode(value):  # pragma: no cover
    if PY2:
        value = unicode(value)
    return value
