# -*- coding: utf-8 -*-
"""

PLEASE DO NOT USE ME.
PLEASE DO NOT USE ME.
PLEASE DO NOT USE ME.
PLEASE DO NOT USE ME.
PLEASE DO NOT USE ME.
PLEASE DO NOT USE ME.
PLEASE DO NOT USE ME.

The functions in this namespace are provided for migrating sessions only.

The legacy system has security issues.

The following functions are taken from Pyramid and appear under their licensing.

* `pyramid.session.signed_serialize`
* `pyramid.sessionsigned_deserialize`

See LICENSE.TXT for more details
"""
# stdlib
import base64
import binascii
import hashlib
import hmac

# pypi
from pyramid.util import strings_differ
from webob.cookies import SignedSerializer


# local
from .compat import bytes_
from .compat import native_
from .compat import pickle
from .util import _NullSerializer


# ==============================================================================


def signed_serialize(data, secret):
    """Serialize any pickleable structure (``data``) and sign it
    using the ``secret`` (must be a string).  Return the
    serialization, which includes the signature as its first 40 bytes.
    The ``signed_deserialize`` method will deserialize such a value.
    This function is useful for creating signed cookies.  For example:
    .. code-block:: python
       cookieval = signed_serialize({'a':1}, 'secret')
       response.set_cookie('signed_cookie', cookieval)
    :param data: data to serialize
    :param secret: secret for signing
    :returns signature: a signed string, compatible with `signed_deserialize`
    """
    pickled = pickle.dumps(data, pickle.HIGHEST_PROTOCOL)
    try:
        # bw-compat with pyramid <= 1.5b1 where latin1 is the default
        secret = bytes_(secret)
    except UnicodeEncodeError:
        secret = bytes_(secret, "utf-8")
    sig = hmac.new(secret, pickled, hashlib.sha1).hexdigest()
    return sig + native_(base64.b64encode(pickled))


def signed_deserialize(serialized, secret, hmac=hmac):
    """Deserialize the value returned from ``signed_serialize``.  If
    the value cannot be deserialized for any reason, a
    :exc:`ValueError` exception will be raised.
    This function is useful for deserializing a signed cookie value
    created by ``signed_serialize``.  For example:
    .. code-block:: python
       cookieval = request.cookies['signed_cookie']
       data = signed_deserialize(cookieval, 'secret')
    :param serialized: a serialized string
    :param secret: secret for signing
    :returns data: the input which was serialized via `signed_serialize`
    """
    # hmac parameterized only for unit tests
    try:
        input_sig, pickled = (
            bytes_(serialized[:40]),
            base64.b64decode(bytes_(serialized[40:])),
        )
    except (binascii.Error, TypeError) as e:
        # Badly formed data can make base64 die
        raise ValueError("Badly formed base64 data: %s" % e)

    try:
        # bw-compat with pyramid <= 1.5b1 where latin1 is the default
        secret = bytes_(secret)
    except UnicodeEncodeError:
        secret = bytes_(secret, "utf-8")
    sig = bytes_(hmac.new(secret, pickled, hashlib.sha1).hexdigest())

    # Avoid timing attacks (see
    # http://seb.dbzteam.org/crypto/python-oauth-timing-hmac.pdf)
    if strings_differ(sig, input_sig):
        raise ValueError("Invalid signature")

    return pickle.loads(pickled)


# ==============================================================================


class LegacyCookieSerializer(object):
    secret = None

    def __init__(self, secret):
        """
        :param secret: The secret for this serializer
        """
        self.secret = secret

    def loads(self, data):
        """
        :param data: data to be deserialized
        """
        return signed_deserialize(data, self.secret)

    def dumps(self, data):
        """
        :param data: data to be serialized
        """
        return signed_serialize(data, self.secret)


class GracefulCookieSerializer(object):
    """
    `GracefulCookieSerializer` is designed to help developers migrate sessions
    across Pyramid/pyramid_session_redis versions by catching deserialization
    failures due to a change in how cookies are signed/checked.

    This class will:
        * attempt to deserialize with new format, and fallback to the legacy if that fails
        * serialize into the new format

    By providing a `logging_hook` (see tests for example usage), a developer can profile
    their app to understand how the migration of users is progressing.

    !!!!! IMPORTANT !!!!!

    Using this or any pickle-based serializer is not recommended, as it can lead to
    a code exploit during deserialization. This is only provided as a temporary migration tool.
    """

    secret = None
    serializer_current = None
    serializer_legacy = None
    logging_hook = None

    def __init__(self, secret, logging_hook=None):
        """
        :param secret: string. the secret
        :param logging_hook: callable; default None.

        `logging_hook` is a callable that supports at least two methods
            * `LoggingHook.attempt("current")`
            * `LoggingHook.success("current")`
        Each method will be invoked with a string, which will have one of 3
        possible values:
            "global" (only attempt), a global attempt was made
            "current" - attempt/success for the current serializer
            "legacy" - attempt/success for the legacy serializer
        """
        self.secret = secret
        self.serializer_current = SignedSerializer(
            secret, "pyramid_session_redis.", "sha512", serializer=_NullSerializer()
        )
        self.serializer_legacy = LegacyCookieSerializer(secret)
        self.logging_hook = logging_hook

    def loads(self, data):
        """
        :param data: data to be deserialized
        """
        if self.logging_hook:
            _hook = self.logging_hook
            _hook.attempt("global")
            try:
                _hook.attempt("current")
                val = self.serializer_current.loads(data)
                _hook.success("current")
                return val
            except:
                _hook.attempt("legacy")
                val = self.serializer_legacy.loads(data)
                _hook.success("legacy")
                return val

        # no hooks configured
        try:
            return self.serializer_current.loads(data)
        except:
            return self.serializer_legacy.loads(data)

    def dumps(self, data):
        """
        :param data: data to be serialized
        """
        return self.serializer_current.dumps(data)
