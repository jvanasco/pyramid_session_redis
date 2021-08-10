# -*- coding: utf-8 -*-
# stdlib
import functools
import time

# pypi
from pyramid.exceptions import ConfigurationError
from webob.cookies import SignedSerializer

# local
from .compat import pickle
from .connection import get_default_connection
from .exceptions import InvalidSession, InvalidSession_NoSessionCookie
from .session import RedisSession
from .util import (
    _generate_session_id,
    _NullSerializer,
    _parse_settings,
    configs_bool,  # not used here, but included for legacy
    configs_dotable,
    create_unique_session_id,
    empty_session_payload,
    LAZYCREATE_SESSION,
    NotSpecified,
    warn_future,
)


__VERSION__ = "1.6.2"


# ==============================================================================


def check_response_allow_cookies(response):
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


def includeme(config):
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


def session_factory_from_settings(settings):
    """
    Convenience method to construct a ``RedisSessionFactory`` from Paste config
    settings. Only settings prefixed with "redis.sessions" will be inspected
    and, if needed, coerced to their appropriate types (for example, casting
    the ``timeout`` value as an `int`).

    Parameters:

    ``settings``
    A dict of Pyramid application settings
    """
    options = _parse_settings(settings)
    return RedisSessionFactory(**options)


def RedisSessionFactory(
    secret,
    timeout=1200,
    cookie_name="session",
    cookie_max_age=None,
    cookie_path="/",
    cookie_domain=None,
    cookie_secure=False,
    cookie_httponly=True,
    cookie_expires=None,
    cookie_comment=None,
    cookie_samesite=None,
    cookie_on_exception=True,
    url=None,
    host="localhost",
    port=6379,
    db=0,
    password=None,
    client_callable=None,
    serialize=pickle.dumps,
    deserialize=pickle.loads,
    id_generator=_generate_session_id,
    set_redis_ttl=True,
    set_redis_ttl_readheavy=None,
    detect_changes=True,
    deserialized_fails_new=None,
    func_check_response_allow_cookies=None,
    func_invalid_logger=None,
    timeout_trigger=None,
    python_expires=True,
    cookie_signer=None,
    socket_timeout=None,  # redis, deprecated
    connection_pool=None,  # redis, deprecated
    charset=None,  # redis, deprecated
    errors=None,  # redis, deprecated
    unix_socket_path=None,  # redis, deprecated
    redis_socket_timeout=None,
    redis_connection_pool=None,
    redis_encoding=None,
    redis_encoding_errors=None,
    redis_unix_socket_path=None,
):
    """
    Constructs and returns a session factory that will provide session data
    from a Redis server. The returned factory can be supplied as the
    ``session_factory`` argument of a :class:`pyramid.config.Configurator`
    constructor, or used as the ``session_factory`` argument of the
    :meth:`pyramid.config.Configurator.set_session_factory` method.

    Parameters:

    ``secret``
    A string which is used to sign the cookie.  As an alternate, you can set this
    to ``None`` and provide a ``cookie_signer`` argument.

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
    Should only be ``"Strict"`` or ``"Lax"``.

    ``cookie_on_exception``
    Boolean value; Default: ``True``.
    If ``True``, set a session cookie even if an exception occurs
    while rendering a view.

    ``url``
    Default: ``None``.
    A connection string for a Redis server, in the format:
    redis://username:password@localhost:6379/0

    ``host``
    Default: ``localhost``.
    A string representing the IP of your Redis server.

    ``port``
    Default: ``6379``.
    An integer representing the port of your Redis server.

    ``db``
    Integer value; Default: ``0``
    An integer to select a specific database on your Redis server.

    ``password``
    Default: ``None``.
    A string password to connect to your Redis server/database if
    required.

    ``client_callable``
    Default: ``None``.
    A python callable that accepts a Pyramid `request` and Redis config options
    and returns a Redis client such as redis-py's `StrictRedis`.

    ``serialize``
    Default: ``pickle.dumps``. PY2=cPickle
    A function to serialize the session dict for storage in Redis.

    ``deserialize``
    Default: ``pickle.loads``. PY2=cPickle
    A function to deserialize the stored session data in Redis.

    ``id_generator``
    Default: private function that uses sha1 with the time and random elements
    to create a 40 character unique ID.
    A function to create a unique ID to be used as the session key when a
    session is first created.

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
     a PIPELINE via GET+EXPIRE and supresses automatic TTL refresh during the deferred
     cleanup phase. If not ``True``, an EXPIRE is sent as a separate action during
     the deferred cleanup phase.  The optimized behavior improves performance on
     read-heavy operations, but may degrade performance on write-heavy operations.
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
    If specified,  ``secret`` must be ``None``.
    An object with two methods, ``loads`` and ``dumps``.
    The ``loads`` method should accept bytes and return a Python object.
    The ``dumps`` method should accept a Python object and return bytes.
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

    ``socket_timeout``
    Default: ``None``.
    Deprecated passthrough argument to the `StrictRedis` constructor.
    Please upgrade to ``redis_socket_timeout``.

    ``connection_pool``
    Default: ``None``.
    Deprecated passthrough argument to the `StrictRedis` constructor.
    Please upgrade to ``redis_connection_pool``.

    ``charset``
    Default: ``utf-8``.
    Deprecated passthrough argument to the `StrictRedis` constructor.
    Please upgrade to ``redis_encoding``.

    ``errors``
    Default: ``strict``.
    Deprecated passthrough argument to the `StrictRedis` constructor.
    Please upgrade to ``redis_encoding_errors``.

    ``unix_socket_path``
    Default: ``None``.
    Deprecated passthrough argument to the `StrictRedis` constructor.
    Please upgrade to ``redis_unix_socket_path``.

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

    The following arguments are passed straight to the ``StrictRedis``
    constructor and allow you to further configure the Redis client::

        modern                 | deprecated
        -----------------------+--------------------
        redis_socket_timeout   | socket_timeout
        redis_connection_pool  | connection_pool
        redis_encoding         | charset
        redis_encoding_errors  | errors
        redis_unix_socket_path | unix_socket_path

    Users are encouraged to use the modern `redis_` namespace and not the
    deprecated legacy kwargs. Warnings will be emitted when deprecated kwargs
    are used. Submitting two equivalent kwargs will result in a ValueError being
    raised.
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
                "`set_redis_ttl_readheavy` is not compatible with `timeout_trigger` and `python_expires`"
            )
    optimize_redis_ttl = False

    _set_redis_ttl_onexit = False
    if (timeout and set_redis_ttl) and (
        not timeout_trigger and not python_expires and not set_redis_ttl_readheavy
    ):
        _set_redis_ttl_onexit = True

    # good for all factory() requests
    set_cookie_kwargs = {
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
    if socket_timeout is not None:
        if redis_socket_timeout:
            raise ValueError(
                "Submit only one of `redis_socket_timeout`, `socket_timeout`"
            )
        warn_future(
            "`socket_timeout` has been deprecated in favor of `redis_socket_timeout`"
        )
    if connection_pool is not None:
        if redis_connection_pool:
            raise ValueError(
                "Submit only one of `redis_connection_pool`, `connection_pool`"
            )
        warn_future(
            "`connection_pool` has been deprecated in favor of `redis_connection_pool`"
        )
    if charset is not None:
        if redis_encoding:
            raise ValueError("Submit only one of `redis_encoding`, `charset`")
        warn_future("`charset` has been deprecated in favor of `redis_encoding`")
    if errors is not None:
        if redis_encoding_errors:
            raise ValueError("Submit only one of `redis_encoding_errors`, `errors`")
        warn_future("`errors` has been deprecated in favor of `redis_encoding_errors`")
    if unix_socket_path is not None:
        if redis_unix_socket_path:
            raise ValueError(
                "Submit only one of `redis_unix_socket_path`, `unix_socket_path`"
            )
        warn_future(
            "`unix_socket_path` has been deprecated in favor of `redis_unix_socket_path`"
        )

    # favor the new terms to the old.
    # black formats this horribly within the dict, so calculate here for legibility
    redis_socket_timeout = (
        redis_socket_timeout if redis_socket_timeout is not None else socket_timeout
    )
    redis_connection_pool = (
        redis_connection_pool if redis_connection_pool is not None else connection_pool
    )
    redis_unix_socket_path = (
        redis_unix_socket_path
        if redis_unix_socket_path is not None
        else unix_socket_path
    )

    # good for all factory() requests
    redis_options = dict(
        host=host,
        port=port,
        db=db,
        password=password,
        socket_timeout=redis_socket_timeout,
        connection_pool=redis_connection_pool,
        unix_socket_path=redis_unix_socket_path,
    )

    # accept newer encoding and encoding_errors args while retaining backwards compatibility
    if redis_encoding is not None:
        redis_options["encoding"] = redis_encoding
    else:
        redis_options["charset"] = "utf-8" if charset is None else charset
    if redis_encoding_errors is not None:
        redis_options["encoding_errors"] = redis_encoding_errors
    else:
        redis_options["errors"] = "strict" if errors is None else errors

    # good for all factory() requests
    new_payload_func = functools.partial(
        empty_session_payload, timeout=timeout, python_expires=python_expires
    )

    # good for all factory() requests
    delete_cookie_func = functools.partial(
        _delete_cookie,
        cookie_name=cookie_name,
        cookie_path=cookie_path,
        cookie_domain=cookie_domain,
    )

    _secret_cookiesigner = (secret, cookie_signer)
    if all(_secret_cookiesigner) or not any(_secret_cookiesigner):
        raise ValueError(
            "One, and only one, of `secret` and `cookie_signer` must be provided."
        )
    if secret is not None:
        # the second argument is the salt. customizing this would needlessly complicate integration
        cookie_signer = SignedSerializer(
            secret, "pyramid_session_redis.", "sha512", serializer=_NullSerializer()
        )

    def factory(request, new_session_id_func=create_unique_session_id):

        # an explicit client callable gets priority over the default
        redis_conn = (
            client_callable(request, **redis_options)
            if client_callable is not None
            else get_default_connection(request, url=url, **redis_options)
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

        try:
            # attempt to retrieve a session_id from the cookie
            session_id = _get_session_id_from_cookie(
                request=request, cookie_name=cookie_name, cookie_signer=cookie_signer
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
            session_id = LAZYCREATE_SESSION
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
            cookie_signer=cookie_signer,
            cookie_name=cookie_name,
            **set_cookie_kwargs
        )
        cookie_callback = functools.partial(
            _cookie_callback,
            session,
            session_cookie_was_valid=session_cookie_was_valid,
            cookie_on_exception=cookie_on_exception,
            set_cookie_func=set_cookie_func,
            delete_cookie_func=delete_cookie_func,
            func_check_response_allow_cookies=func_check_response_allow_cookies,
        )
        request.add_response_callback(cookie_callback)
        request.add_finished_callback(session._deferred_callback)
        return session

    return factory


def _get_session_id_from_cookie(request, cookie_name, cookie_signer):
    """
    Attempts to retrieve and return a session ID from a session cookie in the
    current request. Returns None if the cookie isn't found or the value cannot
    be deserialized for any reason.
    """
    cookieval = request.cookies.get(cookie_name)
    if cookieval is not None:
        try:
            session_id = cookie_signer.loads(cookieval)
            return session_id
        except ValueError:
            pass

    return None


def _set_cookie(session, request, response, cookie_signer, cookie_name, **kwargs):
    """
    `session` is via functools.partial
    `request` and `response` are appended by add_response_callback
    """
    cookieval = cookie_signer.dumps(session.session_id)
    response.set_cookie(cookie_name, cookieval, **kwargs)


def _delete_cookie(response, cookie_name, cookie_path, cookie_domain):
    response.delete_cookie(cookie_name, path=cookie_path, domain=cookie_domain)


def _cookie_callback(
    session,
    request,
    response,
    session_cookie_was_valid,
    cookie_on_exception,
    set_cookie_func,
    delete_cookie_func,
    func_check_response_allow_cookies,
):
    """
    Response callback to set the appropriate Set-Cookie header.
    `session` is via functools.partial
    `request` and `response` are appended by add_response_callback
    """
    # `session._session_state` will not exist after `invalidate` and other methods
    # so we will sextract some info from it...
    please_recookie = None
    _override_args = {}
    if "_session_state" in session.__dict__:
        if session._session_state.please_recookie:
            please_recookie = True
            if session._session_state.cookie_expires != NotSpecified:
                _override_args["expires"] = session._session_state.cookie_expires
            if session._session_state.cookie_max_age != NotSpecified:
                _override_args["max_age"] = session._session_state.cookie_max_age
    if func_check_response_allow_cookies is not None:
        if not func_check_response_allow_cookies(response):
            # if we don't want to send cookies on this response,
            # we might not want to persist or refresh
            # session._session_state.dont_persist = True
            # session._session_state.dont_refresh = True
            return
    if session._invalidated:
        if session_cookie_was_valid:
            delete_cookie_func(response=response)
        return

    # helper function for multiple contexts
    def _set_cookie_and_response():
        set_cookie_func(request=request, response=response, **_override_args)

        # If we set a cookie we need to make sure that downstream
        # web servicess do not serve this response from a cache
        # for requests coming in with a different session cookie.
        # Otherwise we might leak sessions between users.
        varies = ("Cookie",)
        vary = set(response.vary if response.vary is not None else [])
        vary |= set(varies)
        response.vary = vary

    if session.new:
        if not session.session_id_safecheck:
            return
        if request.exception is None or cookie_on_exception is True:
            _set_cookie_and_response()
        elif session_cookie_was_valid:
            # We don't set a cookie for the new session here (as
            # cookie_on_exception is False and an exception was raised), but we
            # still need to delete the existing cookie for the session that the
            # request started with (as the session has now been invalidated).
            delete_cookie_func(response=response)
    else:
        if please_recookie:
            if request.exception is None or cookie_on_exception is True:
                _set_cookie_and_response()
