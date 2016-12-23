# -*- coding: utf-8 -*-

from functools import partial
import time

from pyramid.exceptions import ConfigurationError
from pyramid.settings import asbool
from redis.exceptions import WatchError
from .compat import PY3, token_urlsafe


def to_binary(value, enc="UTF-8"):  # pragma: no cover
    if PY3 and isinstance(value, str):
        value = value.encode(enc)
    return value


def to_unicode(value):  # pragma: no cover
    if not PY3:
        value = unicode(value)
    return value


def _generate_session_id():
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
    encode to a 64 character url-safe string, while 32 bits will only be encoded
    to a 40 character string.
    """
    return token_urlsafe(48)


def prefixed_id(prefix='session:'):
    """
    Adds a prefix to the unique session id, for cases where you want to
    visually distinguish keys in redis.
    """
    session_id = _generate_session_id()
    prefixed_id = prefix + session_id
    return prefixed_id


def _insert_session_id_if_unique(
    redis,
    timeout,
    session_id,
    serialize,
):
    """ Attempt to insert a given ``session_id`` and return the successful id
    or ``None``."""
    _payload = serialize({'managed_dict': {},
                          'created': time.time(),
                          'timeout': timeout,
                          })
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
            pipe.setex(session_id, timeout, _payload)
            pipe.execute()
            # if a WatchError wasn't raised during execution, everything
            # we just did happened atomically
            return session_id
        except WatchError:
            return None


def get_unique_session_id(
    redis,
    timeout,
    serialize,
    generator=_generate_session_id,
):
    """
    Returns a unique session id after inserting it successfully in Redis.
    """
    while 1:
        session_id = generator()
        attempt = _insert_session_id_if_unique(
            redis,
            timeout,
            session_id,
            serialize,
            )
        if attempt is not None:
            return attempt


def _parse_settings(settings):
    """
    Convenience function to collect settings prefixed by 'redis.sessions' and
    coerce settings to ``int``, ``float``, and ``bool`` as needed.
    """
    keys = [s for s in settings if s.startswith('redis.sessions.')]

    options = {}

    for k in keys:
        param = k.split('.')[-1]
        value = settings[k]
        options[param] = value

    # only required setting
    if 'secret' not in options:
        raise ConfigurationError('redis.sessions.secret is a required setting')

    # coerce bools
    for b in ('cookie_secure', 'cookie_httponly', 'cookie_on_exception'):
        if b in options:
            options[b] = asbool(options[b])

    # coerce ints
    for i in ('timeout', 'port', 'db', 'cookie_max_age'):
        if i in options:
            options[i] = int(options[i])

    # coerce float
    if 'socket_timeout' in options:
        options['socket_timeout'] = float(options['socket_timeout'])

    # check for settings conflict
    if 'prefix' in options and 'id_generator' in options:
        err = 'cannot specify custom id_generator and a key prefix'
        raise ConfigurationError(err)

    # convenience setting for overriding key prefixes
    if 'prefix' in options:
        prefix = options.pop('prefix')
        options['id_generator'] = partial(prefixed_id, prefix=prefix)

    return options


def refresh(wrapped):
    """
    Decorator to reset the expire time for this session's key in Redis.
    This will mark the `_session_state.please_refresh` as True, to be
    handled in a callback.
    To immediately persist a session, call `session.do_refresh`.
    """
    def wrapped_refresh(session, *arg, **kw):
        result = wrapped(session, *arg, **kw)
        if not session._assume_redis_lru:
            session._session_state.please_refresh = True
        return result

    return wrapped_refresh


def persist(wrapped):
    """
    Decorator to persist in Redis all the data that needs to be persisted for
    this session and reset the expire time.
    This will mark the `_session_state.please_persist` as True, to be
    handled in a callback.
    To immediately persist a session, call `session.do_persist`.
    """
    def wrapped_persist(session, *arg, **kw):
        result = wrapped(session, *arg, **kw)
        session._session_state.please_persist = True
        return result

    return wrapped_persist
