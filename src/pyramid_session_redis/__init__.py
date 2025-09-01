# -*- coding: utf-8 -*-
# stdlib
import functools
import pickle
from typing import Any
from typing import Callable
from typing import Dict
from typing import Optional
from typing import TYPE_CHECKING

# pypi
from webob.cookies import SignedSerializer

# local
from . import compat  # noqa: F401 ; trigger compat routines
from .connection import get_default_connection
from .exceptions import InvalidSession
from .exceptions import InvalidSession_NoSessionCookie
from .session import RedisSession
from .util import _generate_session_id
from .util import _parse_settings
from .util import _StringSerializer
from .util import configs_bool  # noqa: F401 ; included for legacy
from .util import configs_dotable
from .util import create_unique_session_id
from .util import empty_session_payload
from .util import LazyCreateSession
from .util import NotSpecified
from .util import TYPING_COOKIE_EXPIRES
from .util import TYPING_SESSION_ID
from .util import warn_future

if TYPE_CHECKING:
    from pyramid.config import Configurator
    from redis.client import Redis as RedisClient
    from redis.connection import ConnectionPool
    from webob.request import Request
    from webob.response import Response

    from .util import SignedSerializerInterface

    # from pyramid.request import Request  # webob has stubs; pyramid does not
    # from pyramid.response import Response  # webob has stubs; pyramid does not


__VERSION__ = "1.7.2"


# ==============================================================================


# in 1.7 this is False
# in 1.8 this will be True
INVALIDATE_EMPTY_SESSION = False


def check_response_allow_cookies(response: "Response") -> bool:
    """
    reference implementation for ``func_check_response_allow_cookies``
    If view has set any of these response headers, do not add a session
    cookie on this response. This way views generating cacheable content,
    like images, can signal the downstream web server that this content
    is safe. Otherwise if we set a cookie on these responses it could
    result to user session leakage.
    """
    # The view signals this is cacheable response
    # and we should not stamp a session cookie on it
    cookieless_headers = ["expires", "cache-control"]
    for header in cookieless_headers:
        if header in response.headers:
            return False
    return True


def includeme(config: "Configurator") -> None:
    """
    This function is detected by Pyramid so that you can easily include
    `pyramid_session_redis` in your `main` method like so::

        config.include('pyramid_session_redis')

    Parameters:

    ``config``
    A Pyramid ``config.Configurator``
    """
    settings = config.registry.settings

    # special rule for converting dotted python paths to callables
    for option in configs_dotable:
        key = "redis.sessions.%s" % option
        if key in settings:
            settings[key] = config.maybe_dotted(settings[key])
    session_factory = session_factory_from_settings(settings)
    config.set_session_factory(session_factory)


def session_factory_from_settings(settings: Dict) -> Callable:
    """
    Convenience method to construct a ``RedisSessionFactory`` callable from
    Paste config settings. Only settings prefixed with "redis.sessions" will be
    inspected and, if needed, coerced to their appropriate types (for example,
    casting the ``timeout`` value as an `int`).

    Parameters:

    ``settings``
        A dict of Pyramid application settings
    """
    options = _parse_settings(settings)
    return RedisSessionFactory(**options)


def RedisSessionFactory(
    secret: Optional[str] = None,  # alternate is `cookie_signer`
    timeout: Optional[int] = 1200,
    cookie_name: str = "session",
    cookie_max_age: Optional[int] = None,
    cookie_path: str = "/",
    cookie_domain: Optional[str] = None,
    cookie_secure: bool = False,
    cookie_httponly: bool = True,
    cookie_expires: TYPING_COOKIE_EXPIRES = None,  # TYPING_COOKIE_EXPIRES includes None
    cookie_comment: Optional[str] = None,
    cookie_samesite: Optional[str] = None,
    cookie_on_exception: bool = True,
    url: Optional[str] = None,  # DEPRECATED in 1.7; REMOVING in 1.8
    redis_url: Optional[str] = None,
    host: Optional[str] = None,
    redis_host: str = "localhost",  # DEPRECATED in 1.7; REMOVING in 1.8
    port: Optional[int] = None,  # DEPRECATED in 1.7; REMOVING in 1.8
    redis_port: int = 6379,
    db: Optional[int] = None,  # DEPRECATED in 1.7; REMOVING in 1.8
    redis_db: int = 0,
    password: Optional[str] = None,  # DEPRECATED in 1.7; REMOVING in 1.8
    redis_password: Optional[str] = None,
    client_callable: Optional[
        Callable[..., "RedisClient"]
    ] = None,  # DEPRECATED in 1.7; REMOVING in 1.8
    redis_client_callable: Optional[Callable[..., "RedisClient"]] = None,
    serialize: Callable[[Dict], bytes] = pickle.dumps,  # dict->bytes
    deserialize: Callable[[bytes], Dict] = pickle.loads,  # bytes->dict
    id_generator: Callable[[], str] = _generate_session_id,
    set_redis_ttl: bool = True,
    set_redis_ttl_readheavy: Optional[bool] = None,
    detect_changes: bool = True,
    deserialized_fails_new: Optional[bool] = None,
    func_check_response_allow_cookies: Optional[
        Optional[Callable[["Response"], bool]]
    ] = None,
    func_invalid_logger: Optional[Callable] = None,
    timeout_trigger: Optional[int] = None,
    python_expires: bool = True,
    cookie_signer: Optional[
        "SignedSerializerInterface"
    ] = None,  # alternate for `secret`
    redis_socket_timeout: Optional[int] = None,
    redis_connection_pool: Optional["ConnectionPool"] = None,
    redis_encoding: Optional[str] = None,
    redis_encoding_errors: Optional[str] = None,
    redis_unix_socket_path: Optional[str] = None,
    invalidate_empty_session: bool = INVALIDATE_EMPTY_SESSION,
) -> Callable:
    """
    Constructs and returns a session factory that will provide session data
    from a Redis server. The returned factory can be supplied as the
    ``session_factory`` argument of a :class:`pyramid.config.Configurator`
    constructor, or used as the ``session_factory`` argument of the
    :meth:`pyramid.config.Configurator.set_session_factory` method.

    Parameters:

    ``secret``
    A string which is used to sign the cookie.  As an alternate, you can set
    this to ``None`` and provide a ``cookie_signer`` argument.

    ``timeout``
    A number of seconds of inactivity before a session times out.
    If set to 0 or None, no timeout will occur or be managed in Redis or Python.

    ``cookie_name``
    The name of the cookie used for sessioning. Default: ``session``.
    This is passed on to the underlying ``WebOb.response.Response.set_cookie``
    framework as ``name``.

    ``cookie_max_age``
    The maximum age of the cookie used for sessioning (in seconds).
    Default: ``None`` (browser scope).
    This is passed on to the underlying ``WebOb.response.Response.set_cookie``
    framework as ``max_age``.

    ``cookie_path``
    The path used for the session cookie. Default: ``/``.
    This is passed on to the underlying ``WebOb.response.Response.set_cookie``
    framework as ``path``.

    ``cookie_domain``
    The domain used for the session cookie. Default: ``None`` (no domain).
    This is passed on to the underlying ``WebOb.response.Response.set_cookie``
    framework as ``domain``.

    ``cookie_secure``
    Boolean value; Default: ``False``.
    The 'secure' flag of the session cookie.
    This is passed on to the underlying ``WebOb.response.Response.set_cookie``
    framework as ``secure``.

    ``cookie_httponly``
    Boolean value; Default: ``True``.
    The 'httpOnly' flag of the session cookie.
    This is passed on to the underlying ``WebOb.response.Response.set_cookie``
    framework as ``httponly``.

    ``cookie_expires``
    Default: ``None``.
    Passed to `WebOb.response.Response.set_cookie` as ``expires``.
    This is a ``datetime.datetime``, ``datetime.timedelta``, or ``None``.
    BEWARE: WebOb may be removing this in 1.9.

    ``cookie_comment``
    Default: ``None``.
    The 'comment' attribute of the session cookie.
    This is paseed on to the underlying ``WebOb.response.Response.set_cookie``
    framework as ``comment``.
    If set to ``None`` or not specified, it will not be passed on.

    ``cookie_samesite``
    Default: ``None``.
    The 'SameSite' attribute of the session cookie.
    This is paseed on to the underlying ``WebOb.response.Response.set_cookie``
    framework as ``samesite`` and **requires WebOb 1.8.0 or higher**.
    If set to ``None`` or not specified, it will not be passed on.
    Should only be ``"strict"``, ``"lax"`` or ``"none"``.

    ``cookie_on_exception``
    Boolean value; Default: ``True``.
    If ``True``, set a session cookie even if an exception occurs
    while rendering a view.

    ``url`` DEPRECATED in 1.7; REMOVING in 1.8
    ``redis_url`` replacement
    Default: ``None``.
    A connection string for a Redis server, in the format:
    redis://username:password@localhost:6379/0

    ``host`` DEPRECATED in 1.7; REMOVING in 1.8
    ``redis_host`` replacement
    Default: ``localhost``.
    A string representing the IP of your Redis server.

    ``port`` DEPRECATED in 1.7; REMOVING in 1.8
    ``redis_port`` replacement
    Default: ``6379``.
    An integer representing the port of your Redis server.

    ``db`` DEPRECATED in 1.7; REMOVING in 1.8
    ``redis_db`` replacement
    Integer value; Default: ``0``
    An integer to select a specific database on your Redis server.

    ``password`` DEPRECATED in 1.7; REMOVING in 1.8
    ``redis_password`` replacement
    Default: ``None``.
    A string password to connect to your Redis server/database if
    required.

    ``client_callable`` DEPRECATED in 1.7; REMOVING in 1.8
    ``redis_client_callable`` replacement
    Default: ``None``.
    A python callable that accepts a Pyramid `request` and Redis config options
    and returns a Redis client such as redis-py's `StrictRedis`.

    ``serialize``
    Default: ``pickle.dumps``
    A function to serialize the session dict for storage in Redis.

    ``deserialize``
    Default: ``pickle.loads``.
    A function to deserialize the stored session data in Redis.

    ``id_generator``
    Default: private function that uses sha1 with the time and random elements
    to create a 40 character unique ID.
    A function to create a unique ID to be used as the session key when a
    session is first created.
    As of `v1.7`, ``id_generator`` MUST return a str.

    ``set_redis_ttl``
    Boolean value;  Default `True`.
    If set to ``True``, will set a TTL. If
    ``False`` will not set a TTL and assumes that Redis is configured as a
    least-recently-used cache [http://redis.io/topics/lru-cache] and will NOT
    send EXPIRY data of sessions to Redis (the value of `timeout` will be
    ignored if set). This does not require or imply that no ``timeout`` data is
    handled within the Python payload, it just determines if Redis will be
    involved with timeout logic.

    ``set_redis_ttl_readheavy``
     Boolean value; Default: ``None``.
     If ``True``, sets TTL data in Redis within
     a PIPELINE via GET+EXPIRE and supresses automatic TTL refresh during the
     deferred cleanup phase. If not ``True``, an EXPIRE is sent as a separate
     action during the deferred cleanup phase.  The optimized behavior improves
     performance on read-heavy operations, but may degrade performance on
     write-heavy operations.
     This requires a ``timeout`` and ``set_redis_ttl`` to be True; it is not
     compatible with ``timeout_trigger`` or ``python_expires``.

    ``detect_changes``
    Boolean value; Default: ``True``.
    If set to ``True``, will calculate nested changes after
    serialization to ensure persistence of nested data.

    ``deserialized_fails_new``
    Boolean value; Default: ``None``.
    If ``True`` will handle deserializtion errors
    by creating a new session.

    ``func_check_response_allow_cookies``
    Default: ``None``.
    A callable function that accepts a response, returning ``True`` if the
    cookie can be sent and ``False`` if it should not.
     An example callable is available in
    ``check_response_allow_cookies``, which checks for `expires` and
    `cache-control` cookies.

    ``func_invalid_logger``
    Default: ``None``.
    A callable function that expects a single argument of a raised
    `InvalidSession` exception. If not ``None``, this will be called so your
    application can monitor.

    ``timeout_trigger``
    Integer value; Default ``None``.
    If unset or ``0``, timeouts will be updated on
    every access by setting an EXPIRY in Redis and/or updating the ``expires``
    value in the  session payload.  If set to an INT, the updates will only be
    set once the threshold is crossed.

    ``python_expires``
    Boolean value; Default ``True``.
    If ``True``, allows for timeout logic to be
    tracked in Python.

    ``cookie_signer``
    Default: ``None``
    If specified,  ``secret`` MUST be ``None``.
    An object with two methods, ``loads`` and ``dumps``::
        The ``loads`` method should accept bytes and return a Python string.
        The ``dumps`` method should accept a Python string and return bytes.
        A ``ValueError`` should be raised for malformed inputs.

    ``redis_socket_timeout``
    Default: ``None``.
    Passthrough argument to the `StrictRedis` constructor.

    ``redis_connection_pool``
    Default: ``None``.
    Passthrough argument to the `StrictRedis` constructor.

    ``redis_encoding``
    Default: ``utf-8``.
    Passthrough argument to the `StrictRedis` constructor.

    ``redis_encoding_errors``
    Default: ``strict``.
    Passthrough argument to the `StrictRedis` constructor.

    ``redis_unix_socket_path``
    Default: ``None``.
    Passthrough argument to the `StrictRedis` constructor.

    ``invalidate_empty_session``
    Default: ``False``
    Will invalidate an empty session, deleting the cookie and expiring
    the backend storage.
    * Added in 1.7
    * IMPORTANT: This will default to `True` in 1.8

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    Timeout Example
    ---------------

    Given this example:

        timeout = 1200
        timeout_trigger = 600

    The following timeline would occur

        time | action | timeout | next threshold
        -----+--------+---------+--------------
           0 | CREATE | 1200    | 600
         599 |        | 1200    | 600
         600 | UPDATE | 1800    | 1200
         599 |        | 1800    | 1200
        1200 | UPDATE | 2400    | 1800

    The feature has the ability to significantly lower the amount of processing
    on Redis, however it means a session timeout expires after the last trigger
    and not the last usage.

    For example, with a timeout trigger of 10 minutes on a 1 hour session, if a
    user leaves the site at 49 minutes and returns at 61 minutes, the trigger
    will not have been made and the session will have expired.

    Redis **kwargs
    ---------------

    The following arguments are passed straight to the ``StrictRedis``
    constructor and allow you to further configure the Redis client::

        modern                 | previously deprecated name
        -----------------------+--------------------
        redis_socket_timeout   | socket_timeout
        redis_connection_pool  | connection_pool
        redis_encoding         | charset
        redis_encoding_errors  | errors
        redis_unix_socket_path | unix_socket_path
    """
    if timeout == 0:
        timeout = None

    if timeout_trigger and not python_expires:  # fix this
        python_expires = True

    # optimize a `TTL refresh` under certain conditions
    if set_redis_ttl_readheavy:
        if (not timeout) or (not set_redis_ttl):
            raise ValueError(
                "`set_redis_ttl_readheavy` requires a `timeout` and `set_redis_ttl`"
            )
        if timeout_trigger or python_expires:
            raise ValueError(
                "`set_redis_ttl_readheavy` is not compatible with"
                "`timeout_trigger` and `python_expires`"
            )
    # optimize_redis_ttl = False

    _set_redis_ttl_onexit = False
    if (timeout and set_redis_ttl) and (
        not timeout_trigger and not python_expires and not set_redis_ttl_readheavy
    ):
        _set_redis_ttl_onexit = True

    # good for all factory() requests
    set_cookie_kwargs: Dict[str, Any] = {
        "max_age": cookie_max_age,
        "path": cookie_path,
        "domain": cookie_domain,
        "secure": cookie_secure,
        "httponly": cookie_httponly,
    }
    if cookie_comment is not None:
        set_cookie_kwargs["comment"] = cookie_comment
    if cookie_expires is not None:
        set_cookie_kwargs["expires"] = cookie_expires
    if cookie_samesite is not None:
        set_cookie_kwargs["samesite"] = cookie_samesite

    # handle redis deprecations
    if host is not None:
        warn_future("`host` has been deprecated in favor of `redis_host`")
        if redis_host:
            raise ValueError(
                "Submit only one of `redis_host` (preferred); `host` (deprecated)."
            )
        redis_host = host
    if port is not None:
        warn_future("`port` has been deprecated in favor of `redis_port`")
        if redis_port:
            raise ValueError(
                "Submit only one of `redis_port` (preferred); `port` (deprecated)."
            )
        redis_port = port
    if db is not None:
        warn_future("`db` has been deprecated in favor of `redis_db`")
        if redis_db:
            raise ValueError(
                "Submit only one of `redis_db` (preferred); `db` (deprecated)."
            )
        redis_db = db
    if password is not None:
        warn_future("`password` has been deprecated in favor of `redis_password`")
        if redis_password:
            raise ValueError(
                "Submit only one of `redis_password` (preferred); `password` (deprecated)."
            )
        redis_password = password
    if url is not None:
        warn_future("`url` has been deprecated in favor of `redis_url`")
        if redis_url:
            raise ValueError(
                "Submit only one of `redis_url` (preferred); `url` (deprecated)."
            )
        redis_url = url
    if client_callable is not None:
        warn_future(
            "`client_callable` has been deprecated in favor of `redis_client_callable`"
        )
        if redis_client_callable:
            raise ValueError(
                "Submit only one of `redis_client_callable` (preferred); `client_callable` (deprecated)."
            )
        redis_client_callable = client_callable

    # good for all factory() requests
    redis_options = dict(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        password=redis_password,
        socket_timeout=redis_socket_timeout,
        connection_pool=redis_connection_pool,
        unix_socket_path=redis_unix_socket_path,
    )

    # accept newer encoding and encoding_errors args while
    # retaining backwards compatibility
    if redis_encoding is not None:
        redis_options["encoding"] = redis_encoding
    if redis_encoding_errors is not None:
        redis_options["encoding_errors"] = redis_encoding_errors

    # good for all factory() requests
    new_payload_func = functools.partial(
        empty_session_payload,
        timeout=timeout or 0,
        python_expires=python_expires,
    )

    # good for all factory() requests
    delete_cookie_func = functools.partial(
        _delete_cookie,
        cookie_name=cookie_name,
        cookie_path=cookie_path,
        cookie_domain=cookie_domain,
    )

    _secret_cookiesigner = (secret, cookie_signer)
    _cookie_signer: "SignedSerializerInterface"
    if all(_secret_cookiesigner) or not any(_secret_cookiesigner):
        raise ValueError(
            "One, and only one, of `secret` and `cookie_signer` must be provided."
        )
    if secret is not None:
        # the second argument is the salt.
        # customizing this would needlessly complicate integration

        # webob docs `SignedSerializer`:
        # An object with two methods: `loads`` and ``dumps``.  The ``loads`` method
        # should accept bytes and return a Python object.  The ``dumps`` method
        # should accept a Python object and return bytes.

        # since we use a string session_id, utilizing `_StringSerializer`
        # saves the overhead of using the default JSON serializer

        # SignedSerializer(secret, salt, hashalg="sha512", serializer=None)
        _cookie_signer = SignedSerializer(
            secret,
            "pyramid_session_redis.",
            "sha512",
            serializer=_StringSerializer(),  # convert to a string, not json
        )
    else:
        if TYPE_CHECKING:
            assert cookie_signer is not None
        _cookie_signer = cookie_signer

    def factory(
        request: "Request",
        new_session_id_func: Callable[..., str] = create_unique_session_id,
    ) -> RedisSession:
        # an explicit client callable gets priority over the default
        redis_conn: "RedisClient" = (
            redis_client_callable(request, **redis_options)
            if redis_client_callable is not None
            else get_default_connection(request, url=redis_url, **redis_options)  # type: ignore[arg-type]
        )

        new_session_func = functools.partial(
            new_session_id_func,
            redis=redis_conn,
            timeout=timeout,
            serialize=serialize,
            generator=id_generator,
            set_redis_ttl=set_redis_ttl,
            # set_redis_ttl_readheavy=set_redis_ttl_readheavy,  # not needed on NEW
            # _set_redis_ttl_onexit=_set_redis_ttl_onexit,  # not needed on NEW
            new_payload_func=new_payload_func,
            python_expires=python_expires,
        )

        session_id: Optional[TYPING_SESSION_ID]
        try:
            # attempt to retrieve a session_id from the cookie
            session_id = _get_session_id_from_cookie(
                request=request,
                cookie_name=cookie_name,
                cookie_signer=_cookie_signer,
            )
            if not session_id:
                raise InvalidSession_NoSessionCookie("No `session_id` in cookie.")
            session_cookie_was_valid = True
            session = RedisSession(
                redis=redis_conn,
                session_id=session_id,
                new=False,
                new_session=new_session_func,
                new_payload_func=new_payload_func,
                serialize=serialize,
                deserialize=deserialize,
                set_redis_ttl=set_redis_ttl,
                set_redis_ttl_readheavy=set_redis_ttl_readheavy,
                _set_redis_ttl_onexit=_set_redis_ttl_onexit,
                detect_changes=detect_changes,
                deserialized_fails_new=deserialized_fails_new,
                timeout_trigger=timeout_trigger,
                timeout=timeout,
                python_expires=python_expires,
            )
        except InvalidSession as e:
            if func_invalid_logger is not None:
                # send the instance for logging
                func_invalid_logger(request, e)
            session_id = LazyCreateSession
            session_cookie_was_valid = False
            session = RedisSession(
                redis=redis_conn,
                session_id=session_id,
                new=True,
                new_session=new_session_func,
                new_payload_func=new_payload_func,
                serialize=serialize,
                deserialize=deserialize,
                set_redis_ttl=set_redis_ttl,
                # set_redis_ttl_readheavy=set_redis_ttl_readheavy,  # not needed on NEW
                # _set_redis_ttl_onexit=_set_redis_ttl_onexit,  # not needed on NEW
                detect_changes=detect_changes,
                timeout_trigger=timeout_trigger,
                timeout=timeout,
                python_expires=python_expires,
            )

        set_cookie_func = functools.partial(
            _set_cookie,
            session,
            cookie_signer=_cookie_signer,
            cookie_name=cookie_name,
            **set_cookie_kwargs,
        )
        cookie_callback = functools.partial(
            _cookie_callback,
            session,
            session_cookie_was_valid=session_cookie_was_valid,
            cookie_on_exception=cookie_on_exception,
            set_cookie_func=set_cookie_func,
            delete_cookie_func=delete_cookie_func,
            func_check_response_allow_cookies=func_check_response_allow_cookies,
            invalidate_empty_session=invalidate_empty_session,
        )
        request.add_response_callback(cookie_callback)
        request.add_finished_callback(session._deferred_callback)
        return session

    return factory


def _get_session_id_from_cookie(
    request: "Request",
    cookie_name: str,
    cookie_signer: "SignedSerializerInterface",  # has `.loads`, `.dumps`; MUST return a str
) -> Optional[str]:
    """
    Attempts to retrieve and return a session ID from a session cookie in the
    current request. Returns None if the cookie isn't found or the value cannot
    be deserialized for any reason.
    """
    cookieval = request.cookies.get(cookie_name)
    if cookieval is not None:
        try:
            session_id = cookie_signer.loads(cookieval.encode())
            if TYPE_CHECKING:
                # because we load this, it can't be a `LazyCreateSession`
                assert isinstance(session_id, str)
            return session_id
        except ValueError:
            pass

    return None


def _set_cookie(
    session: RedisSession,
    request: "Request",
    response: "Response",
    cookie_signer: "SignedSerializerInterface",  # has `.loads`, `.dumps`; MUST return a str
    cookie_name: str,
    **kwargs,
) -> None:
    """
    `session` is via functools.partial
    `request` and `response` are appended by add_response_callback
    """
    cookieval = cookie_signer.dumps(session.session_id)
    # `.dumps` generates bytes; `.set_cookie` expects str
    response.set_cookie(cookie_name, cookieval.decode(), **kwargs)


def _delete_cookie(
    response: "Response",
    cookie_name: str,
    cookie_path: str,
    cookie_domain: Optional[str] = None,
) -> None:
    response.delete_cookie(cookie_name, path=cookie_path, domain=cookie_domain)


def _cookie_callback(
    session: RedisSession,
    request: "Request",
    response: "Response",
    session_cookie_was_valid: bool,
    cookie_on_exception: bool,
    set_cookie_func: Callable[..., None],
    delete_cookie_func: Callable[..., None],
    func_check_response_allow_cookies: Optional[Callable[["Response"], bool]],
    invalidate_empty_session: bool,
) -> None:
    """
    Response callback to set the appropriate Set-Cookie header.
    `session` is via functools.partial
    `request` and `response` are appended by add_response_callback

    Important: `invalidate_empty_session` must remain an option so people
    can keep empty sessions if using a workaround.
    see: https://github.com/jvanasco/pyramid_session_redis/issues/67
    """

    # `session._session_state` will not exist after `invalidate` and other methods
    # so we will extract some info from it...
    please_recookie = None
    _override_args = {}
    if "_session_state" in session.__dict__:
        if session._session_state.please_recookie:
            please_recookie = True
            if session._session_state.cookie_expires != NotSpecified:
                _override_args["expires"] = session._session_state.cookie_expires
            if session._session_state.cookie_max_age != NotSpecified:
                _override_args["max_age"] = session._session_state.cookie_max_age

    # helper function for multiple contexts
    # note how this helper function uses the above-set `_override_args`
    def _set_cookie_and_response() -> None:
        set_cookie_func(request=request, response=response, **_override_args)

        # If we set a cookie we need to make sure that downstream
        # web servicess do not serve this response from a cache
        # for requests coming in with a different session cookie.
        # Otherwise we might leak sessions between users.
        varies = ("Cookie",)
        vary = set(response.vary if response.vary is not None else [])
        vary |= set(varies)
        response.vary = vary

    if func_check_response_allow_cookies is not None:
        if not func_check_response_allow_cookies(response):
            # if we don't want to send cookies on this response,
            # we might not want to persist or refresh
            # session._session_state.dont_persist = True
            # session._session_state.dont_refresh = True
            return

    # gate this function against `session._invalidated`
    # `session.new` will create a new `_session_state` if invalidated
    # creating a new _session_state will lose the invalidated check
    if invalidate_empty_session and not session._invalidated:
        # if the session is empty...
        if not session.managed_dict:
            if session.new:
                # mark this session to not persist
                session._session_state.dont_persist = True
                session._session_state.dont_refresh = True
            else:
                # invalidate the session, clearing Redis and setting a marker
                session.invalidate()
                # the next block will delete the cookie and return

    if session._invalidated:
        if session_cookie_was_valid:
            delete_cookie_func(response=response)
        return

    if session.new:
        if not session.session_id_safecheck:
            return
        if request.exception is None or cookie_on_exception is True:
            _set_cookie_and_response()
        elif session_cookie_was_valid:
            # We don't set a cookie for the new session here (as
            # `cookie_on_exception` is `False` and an exception was raised), but we
            # still need to delete the existing cookie for the session that the
            # request started with (as the session has now been invalidated).
            delete_cookie_func(response=response)
    else:
        if please_recookie:
            if request.exception is None or cookie_on_exception is True:
                _set_cookie_and_response()
