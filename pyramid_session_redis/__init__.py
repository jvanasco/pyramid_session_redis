# -*- coding: utf-8 -*-

import functools

from pyramid.session import (
    signed_deserialize,
    signed_serialize,
    )

from .compat import cPickle
from .connection import get_default_connection
from .exceptions import InvalidSession
from .session import RedisSession
from .util import (
    _generate_session_id,
    _parse_settings,
    get_unique_session_id,
    )


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
    cookieless_headers = ["expires", "cache-control", ]
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
    for option in ('client_callable', 'serialize', 'deserialize',
                   'id_generator'):
        key = 'redis.sessions.%s' % option
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
    cookie_name='session',
    cookie_max_age=None,
    cookie_path='/',
    cookie_domain=None,
    cookie_secure=False,
    cookie_httponly=True,
    cookie_on_exception=True,
    url=None,
    host='localhost',
    port=6379,
    db=0,
    password=None,
    socket_timeout=None,
    connection_pool=None,
    charset='utf-8',
    errors='strict',
    unix_socket_path=None,
    client_callable=None,
    serialize=cPickle.dumps,
    deserialize=cPickle.loads,
    id_generator=_generate_session_id,
    assume_redis_lru=None,
    detect_changes=True,
    deserialized_fails_new=None,
    func_check_response_allow_cookies=None,
):
    """
    Constructs and returns a session factory that will provide session data
    from a Redis server. The returned factory can be supplied as the
    ``session_factory`` argument of a :class:`pyramid.config.Configurator`
    constructor, or used as the ``session_factory`` argument of the
    :meth:`pyramid.config.Configurator.set_session_factory` method.

    Parameters:

    ``secret``
    A string which is used to sign the cookie.

    ``timeout``
    A number of seconds of inactivity before a session times out.

    ``cookie_name``
    The name of the cookie used for sessioning. Default: ``session``.

    ``cookie_max_age``
    The maximum age of the cookie used for sessioning (in seconds).
    Default: ``None`` (browser scope).

    ``cookie_path``
    The path used for the session cookie. Default: ``/``.

    ``cookie_domain``
    The domain used for the session cookie. Default: ``None`` (no domain).

    ``cookie_secure``
    The 'secure' flag of the session cookie. Default: ``False``.

    ``cookie_httponly``
    The 'httpOnly' flag of the session cookie. Default: ``True``.

    ``cookie_on_exception``
    If ``True``, set a session cookie even if an exception occurs
    while rendering a view. Default: ``True``.

    ``url``
    A connection string for a Redis server, in the format:
    redis://username:password@localhost:6379/0
    Default: ``None``.

    ``host``
    A string representing the IP of your Redis server. Default: ``localhost``.

    ``port``
    An integer representing the port of your Redis server. Default: ``6379``.

    ``db``
    An integer to select a specific database on your Redis server.
    Default: ``0``

    ``password``
    A string password to connect to your Redis server/database if
    required. Default: ``None``.

    ``client_callable``
    A python callable that accepts a Pyramid `request` and Redis config options
    and returns a Redis client such as redis-py's `StrictRedis`.
    Default: ``None``.

    ``serialize``
    A function to serialize the session dict for storage in Redis.
    Default: ``cPickle.dumps``.

    ``deserialize``
    A function to deserialize the stored session data in Redis.
    Default: ``cPickle.loads``.

    ``id_generator``
    A function to create a unique ID to be used as the session key when a
    session is first created.
    Default: private function that uses sha1 with the time and random elements
    to create a 40 character unique ID.

    ``assume_redis_lru``
    Boolean value. If set to ``True``, will assume that redis is configured as
    a least-recently-used cache [http://redis.io/topics/lru-cache] and will NOT
    sent EXPIRY data for sessions.
    Default: ``None``

    ``detect_changes``
    Boolean value. If set to ``True``, will calculate nested changes after
    serialization to ensure persistence of nested data.
    Default: ``True``

    ``deserialized_fails_new``
    If ``True`` will handle deserializtion errors by creating a new session.

    ``func_check_response_allow_cookies``
    A callable function that accepts a response, returning ``True`` if the
    cookie can be sent and ``False`` if it should not.  This defaults to
    ``None``.  An example callable is available in
    ``check_response_allow_cookies``, which checks for `expires` and
    `cache-control` cookies.


    The following arguments are also passed straight to the ``StrictRedis``
    constructor and allow you to further configure the Redis client::

      socket_timeout
      connection_pool
      charset
      errors
      unix_socket_path
    """
    def factory(request, new_session_id=get_unique_session_id):
        redis_options = dict(
            host=host,
            port=port,
            db=db,
            password=password,
            socket_timeout=socket_timeout,
            connection_pool=connection_pool,
            charset=charset,
            errors=errors,
            unix_socket_path=unix_socket_path,
            )

        # an explicit client callable gets priority over the default
        redis = client_callable(request, **redis_options) \
            if client_callable is not None \
            else get_default_connection(request, url=url, **redis_options)

        # attempt to retrieve a session_id from the cookie
        session_id_from_cookie = _get_session_id_from_cookie(
            request=request,
            cookie_name=cookie_name,
            secret=secret,
            )

        new_session = functools.partial(
            new_session_id,
            redis=redis,
            timeout=timeout,
            serialize=serialize,
            generator=id_generator,
            )

        try:
            if not session_id_from_cookie:
                raise InvalidSession('initial new session')
            session_id = session_id_from_cookie
            session_cookie_was_valid = True
            session = RedisSession(
                redis=redis,
                session_id=session_id,
                new=not session_cookie_was_valid,
                new_session=new_session,
                serialize=serialize,
                deserialize=deserialize,
                assume_redis_lru=assume_redis_lru,
                detect_changes=detect_changes,
                deserialized_fails_new=deserialized_fails_new,
                )
        except InvalidSession:
            session_id = new_session()
            session_cookie_was_valid = False
            session = RedisSession(
                redis=redis,
                session_id=session_id,
                new=not session_cookie_was_valid,
                new_session=new_session,
                serialize=serialize,
                deserialize=deserialize,
                assume_redis_lru=assume_redis_lru,
                detect_changes=detect_changes,
                )

        set_cookie = functools.partial(
            _set_cookie,
            session,
            cookie_name=cookie_name,
            cookie_max_age=cookie_max_age,
            cookie_path=cookie_path,
            cookie_domain=cookie_domain,
            cookie_secure=cookie_secure,
            cookie_httponly=cookie_httponly,
            secret=secret,
            )
        delete_cookie = functools.partial(
            _delete_cookie,
            cookie_name=cookie_name,
            cookie_path=cookie_path,
            cookie_domain=cookie_domain,
            )
        cookie_callback = functools.partial(
            _cookie_callback,
            session,
            session_cookie_was_valid=session_cookie_was_valid,
            cookie_on_exception=cookie_on_exception,
            set_cookie=set_cookie,
            delete_cookie=delete_cookie,
            func_check_response_allow_cookies=func_check_response_allow_cookies,
            )
        request.add_response_callback(cookie_callback)

        finished_callback = functools.partial(
            _finished_callback,
            session
            )
        request.add_finished_callback(finished_callback)

        return session

    return factory


def _get_session_id_from_cookie(request, cookie_name, secret):
    """
    Attempts to retrieve and return a session ID from a session cookie in the
    current request. Returns None if the cookie isn't found or the value cannot
    be deserialized for any reason.
    """
    cookieval = request.cookies.get(cookie_name)

    if cookieval is not None:
        try:
            session_id = signed_deserialize(cookieval, secret)
            return session_id
        except ValueError:
            pass

    return None


def _set_cookie(
    session,
    request,
    response,
    cookie_name,
    cookie_max_age,
    cookie_path,
    cookie_domain,
    cookie_secure,
    cookie_httponly,
    secret,
):
    """
    `session` is via functools.partial
    `request` and `response` are appended by add_response_callback
    """
    cookieval = signed_serialize(session.session_id, secret)
    response.set_cookie(
        cookie_name,
        value=cookieval,
        max_age=cookie_max_age,
        path=cookie_path,
        domain=cookie_domain,
        secure=cookie_secure,
        httponly=cookie_httponly,
        )


def _delete_cookie(response, cookie_name, cookie_path, cookie_domain):
    response.delete_cookie(cookie_name, path=cookie_path, domain=cookie_domain)


def _cookie_callback(
    session,
    request,
    response,
    session_cookie_was_valid,
    cookie_on_exception,
    set_cookie,
    delete_cookie,
    func_check_response_allow_cookies,
):
    """
    Response callback to set the appropriate Set-Cookie header.
    `session` is via functools.partial
    `request` and `response` are appended by add_response_callback
    """
    if func_check_response_allow_cookies is not None:
        if not func_check_response_allow_cookies(response):
            # if we don't want to send cookies on this response,
            # we might not want to persist or refresh
            # session._session_state.dont_persist = True
            # session._session_state.dont_refresh = True
            return
    if session._invalidated:
        if session_cookie_was_valid:
            delete_cookie(response=response)
        return
    if session.new:
        if cookie_on_exception is True or request.exception is None:
            set_cookie(request=request, response=response)

            # If we set a cookie we need to make sure that downstream
            # web servicess do not serve this response from a cache
            # for requests coming in with a different session cookie.
            # Otherwise we might leak sessions between users.
            varies = ("Cookie", )
            vary = set(response.vary if response.vary is not None else [])
            vary |= set(varies)
            response.vary = vary

        elif session_cookie_was_valid:
            # We don't set a cookie for the new session here (as
            # cookie_on_exception is False and an exception was raised), but we
            # still need to delete the existing cookie for the session that the
            # request started with (as the session has now been invalidated).
            delete_cookie(response=response)


def _finished_callback(
    session,
    request,
):
    """Finished callback to persist a cookie if needed.
    `session` is via functools.partial
    `request` is appended by add_finished_callback
    """
    if not session._session_state.dont_persist:
        if session._session_state.please_persist:
            session.do_persist()
            session._session_state.please_refresh = False
        else:
            serialized_session = session._session_state.should_persist(session)
            if serialized_session:
                session.do_persist(serialized_session=serialized_session)
                session._session_state.please_refresh = False
    if not session._session_state.dont_refresh:
        if session._session_state.please_refresh:
            session.do_refresh()
