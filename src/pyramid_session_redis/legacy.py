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

The following functions are taken from Pyramid and appear
under their licensing.

* `pyramid.session.signed_serialize`
* `pyramid.sessionsigned_deserialize`

See LICENSE.TXT for more details
"""
# stdlib
import base64
import binascii
import hashlib
import hmac
import pickle
from types import ModuleType
from typing import Any
from typing import AnyStr
from typing import Optional
from typing import Union

# pypi
from pyramid.util import strings_differ
from typing_extensions import Protocol
from webob.cookies import SignedSerializer

# local
from .util import _StringSerializer
from .util import warn_future

# ==============================================================================


# originally in _compat
def bytes_(
    s: str,
    encoding: str = "latin-1",
    errors: str = "strict",
) -> bytes:
    warn_future("`bytes_` is deprecated and will be removed in the next minor version")
    return _ensure_binary(s, encoding, errors)


# lifted from six
def _ensure_binary(
    s: str,
    encoding: str = "utf-8",
    errors: str = "strict",
) -> bytes:
    """Coerce **s** to six.binary_type.

    For Python 2:
      - `unicode` -> encoded to `str`
      - `str` -> `str`

    For Python 3:
      - `str` -> encoded to `bytes`
      - `bytes` -> `bytes`
    """
    warn_future(
        "`_ensure_binary` is deprecated and will be removed in the next minor version"
    )
    if isinstance(s, bytes):
        return s
    if isinstance(s, str):
        return s.encode(encoding, errors)
    raise TypeError("not expecting type '%s'" % type(s))


# - - -


def _fallback_conversion(
    secret: AnyStr,
) -> bytes:
    warn_future(
        "`_fallback_conversion` is deprecated and will be removed in the next minor version"
    )
    _secret: bytes
    if isinstance(secret, str):
        _secret = bytes_(secret, "utf-8")
    else:
        _secret = secret
    return _secret


def signed_serialize(
    data: Any,
    secret: AnyStr,
) -> str:
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
    warn_future(
        "`signed_serialize` is deprecated and will be removed in the next minor version"
    )
    _pickled: bytes = pickle.dumps(data, pickle.HIGHEST_PROTOCOL)
    _secret: bytes = _fallback_conversion(secret)
    sig: str = hmac.new(_secret, _pickled, hashlib.sha1).hexdigest()
    return sig + base64.b64encode(_pickled).decode()


def signed_deserialize(
    serialized: str,
    secret: AnyStr,
    hmac: ModuleType = hmac,
) -> Any:
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
    warn_future(
        "`signed_deserialize` is deprecated and will be removed in the next minor version"
    )
    try:
        input_sig: bytes = bytes_(serialized[:40])
        pickled: bytes = base64.b64decode(bytes_(serialized[40:]))
    except (binascii.Error, TypeError) as e:
        # Badly formed data can make base64 die
        raise ValueError("Badly formed base64 data: %s" % e)
    _secret: bytes = _fallback_conversion(secret)
    sig: bytes = bytes_(hmac.new(_secret, pickled, hashlib.sha1).hexdigest())

    # Avoid timing attacks (see
    # http://seb.dbzteam.org/crypto/python-oauth-timing-hmac.pdf)
    if strings_differ(sig, input_sig):
        raise ValueError("Invalid signature")

    return pickle.loads(pickled)


# ==============================================================================


class LegacyCookieSerializer(object):
    secret: bytes

    def __init__(self, secret: AnyStr):
        """
        :param secret: The secret for this serializer
        """
        warn_future(
            "`LegacyCookieSerializer` is deprecated and will be removed in the next minor version"
        )
        _secret: bytes = _fallback_conversion(secret)
        self.secret = _secret

    def dumps(self, data: Any) -> bytes:
        """
        :param data: data to be serialized
        """
        return signed_serialize(data, self.secret).encode()

    def loads(self, data: Union[bytes, str]) -> Any:
        """
        :param data: data to be deserialized
        """
        if isinstance(data, bytes):
            data = data.decode()
        return signed_deserialize(data, self.secret)


class LoggingHookInterface(Protocol):

    def attempt(self, value: str) -> None: ...

    def success(self, value: str) -> None: ...


class GracefulCookieSerializer(object):
    """
    `GracefulCookieSerializer` is designed to help developers migrate sessions
    across Pyramid/pyramid_session_redis versions by catching deserialization
    failures due to a change in how cookies are signed/checked.

    This class will:
      * attempt to deserialize with new format, and fallback to the legacy
        if that fails
      * serialize into the new format

    By providing a `logging_hook` (see tests for example usage), a developer
    can profile their app to understand how the migration of users is
    progressing.

    !!!!! IMPORTANT !!!!!

    Using this or any pickle-based serializer is not recommended, as it can
    lead to a code exploit during deserialization. This is only provided as
    a temporary migration tool.


    webob docs `SignedSerializer`:
    An object with two methods: `loads`` and ``dumps``.  The ``loads`` method
    should accept bytes and return a Python object.  The ``dumps`` method
    should accept a Python object and return bytes.
    """

    secret: bytes
    serializer_current: SignedSerializer  # has .dumps/.loads
    serializer_legacy: LegacyCookieSerializer  # has .dumps/.loads
    logging_hook: Optional[LoggingHookInterface]  # has .attempt, .success

    def __init__(
        self,
        secret: AnyStr,
        logging_hook: Optional[LoggingHookInterface] = None,
    ):
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
        warn_future(
            "`GracefulCookieSerializer` is deprecated and will be removed in the next minor version"
        )
        _secret: bytes = _fallback_conversion(secret)
        self.secret = _secret
        # SignedSerializer(secret, salt, hashalg="sha512", serializer=None)
        self.serializer_current = SignedSerializer(
            secret,
            "pyramid_session_redis.",
            "sha512",
            serializer=_StringSerializer(),
        )
        self.serializer_legacy = LegacyCookieSerializer(_secret)
        self.logging_hook = logging_hook

    def dumps(self, data: Any) -> bytes:
        """
        :param data: data to be serialized
        """
        return self.serializer_current.dumps(data)

    def loads(self, data: bytes) -> Any:
        """
        :param data: data to be deserialized
        """
        if self.logging_hook is not None:
            _hook = self.logging_hook
            _hook.attempt("global")
            try:
                _hook.attempt("current")
                val = self.serializer_current.loads(data)
                _hook.success("current")
                return val
            except Exception:
                _hook.attempt("legacy")
                val = self.serializer_legacy.loads(data)
                _hook.success("legacy")
                return val

        # no hooks configured
        try:
            return self.serializer_current.loads(data)
        except Exception:
            return self.serializer_legacy.loads(data)
