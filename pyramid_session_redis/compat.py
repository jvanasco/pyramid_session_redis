# -*- coding: utf-8 -*-

"""
Compatability module for various pythons and environments.
"""
import six
from six.moves import cPickle as pickle
from six import PY2
from six import PY3


# ==============================================================================


try:
    # python3.6 secrets module
    from secrets import token_urlsafe, token_hex
except ImportError:  # pragma: no cover
    import os
    import base64
    import binascii

    def token_bytes(nbytes=32):
        return os.urandom(nbytes)

    def token_urlsafe(nbytes=32):
        token = base64.urlsafe_b64encode(token_bytes(nbytes)).rstrip(b"=")
        return token.decode("ascii") if PY3 else token

    def token_hex(nbytes=32):
        token = binascii.hexlify(token_bytes(nbytes))
        return token.decode("ascii") if PY3 else token
