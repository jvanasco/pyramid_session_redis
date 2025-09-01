# -*- coding: utf-8 -*-

# stdlib
import datetime
from enum import Enum
from functools import partial
from math import ceil
from secrets import token_urlsafe
from time import time as time_time
import typing
from typing import Any
from typing import Callable
from typing import Dict
from typing import Optional
from typing import Type
from typing import TYPE_CHECKING
from typing import Union
import warnings

# pypi
from pyramid.exceptions import ConfigurationError
from pyramid.settings import asbool
from redis.exceptions import WatchError
from typing_extensions import Protocol

# local
from .exceptions import InvalidSessionId_Deserialization
from .exceptions import InvalidSessionId_Serialization

if TYPE_CHECKING:
    from redis.client import Redis as RedisClient

    from .session import RedisSession

    # from webob.cookies import _Serializer

# ==============================================================================


# we use an Enum for typing support


# create a custom class+object instance for handling lazycreated ids
# (this is what dogpile cache's NO_VALUE does)
class LazyCreateSession(Enum):
    pass


# used to differentiate from `None`
class NotSpecified(Enum):
    pass


# this stored in the sessions. it is used to detect api version mismatches
SESSION_API_VERSION: int = 1


TYPING_COOKIE_EXPIRES = Union[datetime.timedelta, datetime.datetime, None, NotSpecified]
TYPING_KEY = Union[str, int]
TYPING_SESSION_ID = Union[str, Type[LazyCreateSession]]

# for ASSIGNMENT we need a `Type[NotSpecified]`
TYPING_COOKIE_EXPIRES__A = Union[
    datetime.timedelta, datetime.datetime, None, Type[NotSpecified]
]
TYPING_COOKIE_MAX_AGE__A = Union[int, None, Type[NotSpecified]]


# ------------------------------------------------------------------------------


def warn_future(message: str) -> None:
    warnings.warn(message, FutureWarning, stacklevel=2)


def is_integer(n: typing.Any) -> bool:
    try:
        r = float(n)
        return r.is_integer()
    except ValueError:
        return False


def to_binary(value: typing.AnyStr, enc: str = "UTF-8") -> bytes:
    if isinstance(value, str):
        return value.encode(enc)
    return value


def _generate_session_id() -> str:
    """
    Produces a base64 encoded, urlsafe random string with 48-byte
    cryptographically strong randomness as the session id. See

        http://security.stackexchange.com/questions/24850/
        choosing-a-session-id-algorithm-for-a-client-server-relationship

    for the algorithm of choosing a session id.

    The implementation of `os.urandom` varies by system, but you can always
    supply your own function in your ini file with:

        redis.sessions.id_generator = my_random_id_generator

    This uses 48 bytes instead of 32 to maintain backwards
    compatibility to pyramid_redis_sessions.  The earlier packaged used
    a 64character digest; however 48bits using the new method will
    encode to a 64 character url-safe string, while 32 bits will only be
    encoded to a 40 character string.
    """
    return token_urlsafe(48)


# ---------------------

# `_parse_settings` and `includeme` may need to coerce strings into other types
# these lists are maintained here as a public API, so implementers who need
# to customize their integration can do so without fear of breaking changes

# these we just ignore in code, but track here:
configs_str = (
    "secret",
    "cookie_name",
    "cookie_path",
    "cookie_domain",
    "cookie_comment",
    "cookie_samesite",
    "host",  # DEPRECATED in 1.7; REMOVING in 1.8
    "password",  # DEPRECATED in 1.7; REMOVING in 1.8
    "redis_host",
    "redis_password",
    "redis_unix_socket_path",
    "redis_encoding_errors",
    "redis_encoding",
    "redis_url",
    "url",  # DEPRECATED in 1.7; REMOVING in 1.8
)

# treat as strings here
configs_dotable = (
    "client_callable",  # DEPRECATED in 1.7; REMOVING in 1.8
    "cookie_signer",
    "deserialize",
    "func_check_response_allow_cookies",
    "func_invalid_logger",
    "id_generator",
    "redis_client_callable",
    "serialize",
)

configs_bool = (
    "cookie_httponly",
    "cookie_on_exception",
    "cookie_secure",
    "deserialized_fails_new",
    "detect_changes",
    "invalidate_empty_session",
    "python_expires",
    "set_redis_ttl_readheavy",
    "set_redis_ttl",
)

configs_int = (
    "db",  # DEPRECATED in 1.7; REMOVING in 1.8
    "port",  # DEPRECATED in 1.7; REMOVING in 1.8
    "redis_db",
    "redis_port",
)

configs_int_none = (
    "cookie_max_age",
    "redis_socket_timeout",
    "timeout",
    "timeout_trigger",
)

configs_unsupported = (
    "cookie_expires",  # datetime objects
    "redis_connection_pool",  # ConnectionPool
)


# ---------------------


def prefixed_id(prefix: str = "session:") -> str:
    """
    :param prefix: string. the prefix
    Adds a prefix to the unique session id, for cases where you want to
    visually distinguish keys in redis.
    """
    session_id: str = _generate_session_id()
    prefixed_id: str = prefix + session_id
    return prefixed_id


def int_time() -> int:
    return int(ceil(time_time()))


def empty_session_payload(
    timeout: int = 0,
    python_expires: Optional[bool] = None,
) -> Dict:
    """
    creates an empty session payload

    :param timeout: int. default 0.
    :param python_expires: bool. default None.
    """
    _created = int_time()
    data = {
        "m": {},  # managed_dict
        "c": _created,  # created
        "v": SESSION_API_VERSION,  # session
    }
    if timeout:
        data["t"] = timeout  # timeout
        if python_expires:
            data["x"] = _created + timeout
    return data


def encode_session_payload(
    managed_dict: Dict,
    created: int,
    timeout: int,  # = 0?
    expires: int,  # = 0?
    timeout_trigger: Optional[int] = None,
    python_expires: Optional[bool] = None,
) -> Dict:
    """
    called by a session to recode for storage;
    inverse of ``decode_session_payload``

    :param managed_dict: internal dict for encoding.
    :param created: int. time created.
    :param timeout: int. seconds.
    :param expires: int. time expiry.
    :param timeout_trigger: int. default None.
    :param python_expires: bool. default None.
    """
    data = {
        "m": managed_dict,  # managed_dict
        "c": created,  # created
        "v": SESSION_API_VERSION,  # session_api version
    }
    if expires and python_expires:
        data["x"] = expires
    if timeout:
        data["t"] = timeout  # timeout
        if python_expires:
            time_now = int_time()
            if not timeout_trigger or (time_now >= (expires - timeout_trigger)):
                data["x"] = time_now + timeout  # expires
    return data


def decode_session_payload(payload: Dict) -> Dict:
    """
    decode a serialized session payload to kwargs
    inverse of ``encode_session_payload``

    :param payload: dict with encoding compatible with `encode_session_payload`
    :returns payload: dict with legacy/readble format.
    """
    return {
        "managed_dict": payload["m"],
        "created": payload["c"],
        "version": payload["v"],
        "timeout": payload.get("t"),
        "expires": payload.get("x"),
    }


def _insert_session_id_if_unique(
    redis: "RedisClient",
    timeout: int,
    session_id: str,
    serialize: Callable[[Any], bytes],
    set_redis_ttl: bool,
    data_payload: Optional[dict] = None,
    new_payload_func: Optional[Callable[..., Dict]] = None,
    python_expires: Optional[bool] = None,
) -> Optional[str]:
    """
    Attempt to insert a given ``session_id`` AND empty payload; returning the
    successful id or ``None``.

    ``timeout`` could be 0/None, in that case do-not track
    the timeout data.

    This will create an empty/null session and redis entry for the id.

    The return value will be the input `session_id` upon success, or `None` upon
    a failure.

    ``data_payload`` = payload to use
    ``new_payload_func`` = specify a fallback function to generate a payload
    if both are ``None``, then `empty_session_payload`

    :param redis: redis connection
    :param timeout: int seconds. used to initialize empty session.
    :param session_id: string.
    :param serialize: callable. used to serialize an empty session.
    :param set_redis_ttl:  bool
    :param data_payload: dict. default None. initialize session with this payload.
    :param new_payload_func: callable. default None. create a new payload with this.
    :param python_expires: bool. default None.
    :returns session_id: string.
    """
    if data_payload is None:
        if new_payload_func is not None:
            data_payload = new_payload_func()
        else:
            data_payload = empty_session_payload(
                timeout,
                python_expires=python_expires,
            )
    _payload = serialize(data_payload)
    with redis.pipeline() as pipe:
        try:
            # start pipeline with a watch
            pipe.watch(session_id)
            # after `watch` the pipline is in immediate execution mode
            value = pipe.get(session_id)
            if value is not None:
                return None
            # enter buffered mode
            pipe.multi()
            if timeout and set_redis_ttl:
                pipe.setex(session_id, timeout, _payload)
            else:
                pipe.set(session_id, _payload)
            pipe.execute()
            # if a WatchError wasn't raised during execution, everything
            # we just did happened atomically
            return session_id
        except WatchError:
            return None


def create_unique_session_id(
    redis: "RedisClient",
    timeout: int,
    serialize: Callable[[Any], bytes],
    generator: Callable[[], str] = _generate_session_id,
    set_redis_ttl: bool = True,
    data_payload: Optional[Dict] = None,
    new_payload_func: Optional[Callable[..., Dict]] = None,
    python_expires: Optional[bool] = None,
) -> str:
    """
    Returns a unique session id after inserting it successfully in Redis.

    :param redis: redis connection
    :param timeout: int seconds. used to initialize empty session.
    :param serialize: callable. used to serialize an empty session.
    :param generator: callable. used to generate an id.
    :param set_redis_ttl:  bool
    :param data_payload: dict. default None. initialize session with this payload.
    :param new_payload_func: callable. default None. create a new payload with this.
    :param python_expires: bool. default None.
    :returns:
    """
    while 1:
        session_id: str = generator()
        # attempt will be the session_id
        attempt = _insert_session_id_if_unique(
            redis,
            timeout,
            session_id,
            serialize,
            set_redis_ttl,
            data_payload=data_payload,
            new_payload_func=new_payload_func,
            python_expires=python_expires,
        )
        if attempt is not None:
            return attempt


def _parse_settings(settings: Dict) -> Dict:
    """
    Convenience function to collect settings prefixed by 'redis.sessions' and
    coerce settings to ``int``, ``float``, and ``bool`` as needed.

    :param settings: dict
    """
    keys = [s for s in settings if s.startswith("redis.sessions.")]

    options = {}

    for k in keys:
        param = k.split(".")[-1]
        value = settings[k]
        options[param] = value

    # check unsupported
    _unsupported = []
    for u in configs_unsupported:
        if u in options:
            _unsupported.append(u)
    if _unsupported:
        raise ConfigurationError(
            "Detcted config settings that are not compatible with this parser: %s."
            % _unsupported
        )

    _secret_cookiesigner = (options.get("secret"), options.get("cookie_signer"))
    if all(_secret_cookiesigner) or not any(_secret_cookiesigner):
        raise ConfigurationError(
            "One, and only one, of `redis.sessions.secret` and `redis.sessions.cookie_signer` must be provided."
        )

    # coerce bools
    for b in configs_bool:
        if b in options:
            options[b] = asbool(options[b])

    # coerce ints
    for i in configs_int:
        if i in options:
            options[i] = int(options[i])

    # allow "None" to be a value for some ints
    for i in configs_int_none:
        if i in options:
            if options[i] == "None":
                options[i] = None
            else:
                options[i] = int(options[i])
                if not options[i]:
                    options[i] = None

    # coerce float
    if "redis_socket_timeout" in options:
        options["redis_socket_timeout"] = float(options["redis_socket_timeout"])

    # check for settings conflict
    if "prefix" in options and "id_generator" in options:
        err = "cannot specify custom id_generator and a key prefix"
        raise ConfigurationError(err)

    # convenience setting for overriding key prefixes
    if "prefix" in options:
        prefix = options.pop("prefix")
        options["id_generator"] = partial(prefixed_id, prefix=prefix)

    return options


def persist(wrapped: Callable) -> Callable:
    """
    Decorator to persist in Redis all the data that needs to be persisted for
    this session and reset the expire time.
    This will mark the `_session_state.please_persist` as True, to be
    handled in a callback.
    To immediately persist a session, call `session.do_persist`.

    :param wrapped: a function to wrap with this decorator.
    :returns wrapped_refresh: a wrapped function.
    """

    def wrapped_persist(session: "RedisSession", *arg, **kw):
        result = wrapped(session, *arg, **kw)
        session._session_state.please_persist = True
        return result

    return wrapped_persist


def recookie(wrapped: Callable) -> Callable:
    """
    Decorator to mark a session as needing to recookie.
    This is necessary when setting a new max-age/etc

    :param wrapped: a function to wrap with this decorator.
    :returns wrapped_recookie: a wrapped function.
    """

    def wrapped_recookie(session: "RedisSession", *arg, **kw):
        result = wrapped(session, *arg, **kw)
        session._session_state.please_recookie = True
        return result

    return wrapped_recookie


def refresh(wrapped: Callable) -> Callable:
    """
    Decorator to reset the expire time for this session's key in Redis.
    This will mark the `_session_state.please_refresh` as True, to be
    handled in a callback.
    To immediately persist a session, call `session.do_refresh`.

    :param wrapped: a function to wrap with this decorator.
    :returns wrapped_refresh: a wrapped function.
    """

    def wrapped_refresh(session: "RedisSession", *arg, **kw):
        result = wrapped(session, *arg, **kw)
        session._session_state.please_refresh = True
        return result

    return wrapped_refresh


class SignedSerializerInterface(Protocol):
    def dumps(self, s: str) -> bytes: ...
    def loads(self, s: bytes) -> str: ...


# `SerializerInterface` ; DEPRECATED in 1.7; REMOVING in 1.8
SerializerInterface = SignedSerializerInterface


class _StringSerializer(SignedSerializerInterface):
    """
    A cheap serializer for compatibility with ``webob.cookies.SignedSerializer``.
    Our usage is only for encoding a signed session_id.

    By default, webob uses json loads/dumps.  As this library only uses strings
    for session, id, we can have a quick savings here.

    The webob interface dictates for ``SignedSerializer``
        https://github.com/Pylons/webob/blob/main/src/webob/cookies.py#L663

        An object with two methods: `loads`` and ``dumps``.  The ``loads`` method
        should accept bytes and return a Python object.  The ``dumps`` method
        should accept a Python object and return bytes.  A ``ValueError`` should
        be raised for malformed inputs.  Default: ``None`, which will use a
        derivation of :func:`json.dumps` and ``json.loads``.

    Additionally:
        SignedSerializer.dumps: expects Any and coverts to bytes;
           `SignedSerializer.dumps::self.serializer.dumps` expects Any and coverts to bytes;
                we only need to operate on strings, so can lock this down
        SignedSerializer.loads: expects Any and coverts to bytes;
           `SignedSerializer.dumps::self.serializer.dumps` expects Any and coverts to bytes;
                we only need to operate on strings, so can lock this down
    """

    def dumps(self, s: str) -> bytes:
        try:
            return s.encode("utf-8", "strict")
        except Exception as exc:
            raise InvalidSessionId_Serialization(exc)

    def loads(self, s: bytes) -> str:
        try:
            return str(s, "utf-8", "strict")
        except Exception as exc:
            raise InvalidSessionId_Deserialization(exc)


# `_NullSerializer` DEPRECATED in 1.7; REMOVING in 1.8
_NullSerializer = _StringSerializer
