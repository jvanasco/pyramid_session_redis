# -*- coding: utf-8 -*-

"""
Compatability module for various Pythons and Environments.
"""
from six.moves import cPickle as pickle
from six import PY2
from six import PY3


# !!!: MIGRATION. these move in webob 2.0
try:
    from webob.compat import bytes_ as webob_bytes_
    from webob.compat import text_ as webob_text_
except:
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


def to_unicode(value):  # pragma: no cover
    if PY2:
        value = unicode(value)
    return value
