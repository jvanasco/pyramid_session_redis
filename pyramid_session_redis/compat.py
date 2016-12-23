# -*- coding: utf-8 -*-

"""
Compatability module for various pythons and environments.
"""
import sys

PY3 = sys.version_info[0] == 3


try:
    import cPickle
except ImportError:  # pragma: no cover
    # python 3 pickle module
    import pickle as cPickle


try:
    # python3.6 secretc module
    from secrets import token_urlsafe, token_hex
except ImportError: # pragma: no cover
    import os
    import base64
    import binascii

    def token_bytes(nbytes=32):
        return os.urandom(nbytes)

    def token_urlsafe(nbytes=32):
        token = base64.urlsafe_b64encode(token_bytes(nbytes)).rstrip(b'=')
        return token.decode('ascii') if PY3 else token

    def token_hex(nbytes=32):
        token = binascii.hexlify(token_bytes(nbytes))
        return token.decode('ascii') if PY3 else token
