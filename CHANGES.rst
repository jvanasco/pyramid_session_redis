=========
Changelog
=========

-1/17/2017:
    * version 1.2.1
    * fixed bug with session.invalidate that caused placeholder sessions to be created( https://github.com/jvanasco/pyramid_session_redis/issues/2 )
    * added test to guard against above bug
    * fixed some whitespace issues (trailing spaces, tabs-not-spaces)
    * migrated pacakge version id from setup.py into __init__.py as "__VERSION__" variable.
    * migrated tests and code to handle webob 1.7's deprecation of cookie values

-12/23/2016:
    * version 1.2.0
    * merged PR1 from hongyuan1306 (https://github.com/jvanasco/pyramid_session_redis/pull/1)
        * Make the package Python3 compatible
        * Consolidate token/session generation
        * Leverage token/session generation from python3.6 stdlib; fallback otherwise.
    * updated the bits on token_urlsafe from 32 to 48; this encodes to a 64 character string

-11/10/2016:
    * version 1.1.2
    release error fix.

-11/10/2016:
    * version 1.1.1
    * integrated/rewrote pr from pyramid_redis_sessions for session leakage on cdns
        https://github.com/ericrasmussen/pyramid_redis_sessions/pull/74/files
    * response.vary will now ensure `Cookie`
    * Session factory now accepts `func_check_response_allow_cookies(response)` a callable which can disable setting the cookie.
    * streamlined some work in utils

-11/09/2016: renamed to pyramid_session_redis

-08/15/2016: Changes for jvanasco branch
    * added `deserialized_fails_new` to handle deserialization errors

-08/02/2016: Changes for jvanasco branch
    * made the detection of nested changes configurable. by default this is set to True.

-06/16/2016: Changes for jvanasco branch

    * changed `persist` from being "on demand" into a single callback via pyramid's `add_finished_callback`
    * changed `refresh` from being "on demand" into a single callback via pyramid's `add_finished_callback`
    * decoupled active `session` from being a particular named attribute on the "request".
    * removed an initial call to redis' `EXISTS`. Instead of "If EXISTS then GET", we simply GET the active session and create a new one if it does not exist.
    * replaced separate calls to "SET" and "EXPIRE" with single "SETEX"
    * added a feature to assume redis is operating as a LRU cache, therefore not sending expiry data
    * ensure nested session values trigger a persist by calculating an md5 hash of the serialized session data on load; then again in the finished callback

----------


-Initial Release

-09/24/2012: 0.9 beta release

-11/12/2012: raise ConfigurationError if required redis.sessions.secret setting
             is missing.

-02/17/2013: New API method: adjust_timeout_for_session. This method allows you
             to permanently alter the timeout setting for a given session for
             the duration of the session.

             Note: on a development branch this was known as
             "reset_timeout_for_session" but was renamed to avoid confusion
             with the internal act of resetting timeouts each time the session
             is accessed.

             Additional changes include:

                 1) Removing the unused "period" setting
                 2) Fixing an error with the cookie_on_exception setting
                 3) Using asbool for boolean settings
                 4) Adding documentation
                 5) Adding new configuration options (see the docs for details)


              Internal (non-API) changes include:

                 * renamed the new session flag from "_v_new" to "_rs_new"
                 * remove util module's dependency on cPickle
                 * always cast the timeout setting as an int
                 * removing unused imports
                 * many updates and additions to docstrings/comments
                 * moving the redis connection/client logic to a new module

-06/30/2013: New configuration options:

                * redis.sessions.client_callable (supply your own redis client)
                * redis.sessions.serialize (use your own pickling function)
                * redis.sessions.deserialize (use your own unpickling function)
                * redis.sessions.id_generator (callable to generate session IDs)
                * redis.sessions.prefix (add a prefix to session IDs in redis)

             BREAKING CHANGE: cookie_httponly now defaults to True. If you are
               currently relying on outside scripts being able to access the
               session cookie (a bad idea to begin with), you will need to
               explicitly set::

                   redis.sessions.cookie_httponly = False

               For most (likely all) users, you will not notice any difference.

               Reference: https://www.owasp.org/index.php/HttpOnly


             Session ID generation: session IDs are now generated with an
               initial value from os.urandom, which (according to the offical
               python docs) is "suitable for cryptographic use". The previous
               implementation was concerned primarily with integrity. This
               update improves on integrity but also adds a greater level of
               security.

-10/13/2013: Many documentation improvements, and some minor refactoring (better
             comments, removing unused functions, etc).

             This update has been in the works on the github master for months
             with no releases to pypi. It marks another major version bump,
             this time to 1.0a. Releases will follow a more typical versioning
             model from now on (similar to Pyramid's).


-06/15/2014: Changes for 1.0a2

             * **BREAKING CHANGE**: The ``.created`` and ``.timeout`` attributes
               of the session are now serialized and stored in Redis alongside
               the session dict in another dict. This and the other changes to
               ``.created`` and ``.timeout`` means pyramid_redis_sessions>=1.0a2
               will not be able to deserialize sessions created with
               pyramid_redis_sessions<1.0a2. No code changes are required, but
               please be prepared to clear out existing session data prior to
               upgrading.

             * Bug fix: ``RedisSession.created`` was storing and returning the
               time when the ``RedisSession`` instance was initialised, rather
               than the time the actual session was first created. This has now
               been fixed.

             * Bug fix: The ``timeout`` value has been moved out of the session
               dict, as it is not part of the session (previously it was stored
               in the session dict under the key ``_rs_timeout``, and would be
               lost for example when we cleared the session.)

             * Bug fix: The session now supports starting a new session (with a
               new session_id) within the same request after ``.invalidate()``.
               (Previously this was not possible, as ``.invalidate()`` cleared
               the session dict but did not change the session_id, and set a
               header to delete the cookie that meant any changes to the
               session after ``.invalidate()`` were lost.)

               The way ``.invalidate()`` previously handled deleting the cookie
               also meant that there would be more than one Set-Cookie headers
               for the same cookie name, which should not happen according to
               RFC 6265.  This has been fixed to set the one correct Set-Cookie
               header, and only when it is necessary (for example, a new
               session that is invalidated in the same request without further
               access to the session would not need to set any cookie).

               ``.invalidate()`` also now deletes the session from Redis rather
               than just relying on it to expire.


             * Bug fix: The ``cookie_path`` setting had no effect, as it was
               not being used to set and delete cookie. This has been fixed, we
               now set and delete cookie with the specified ``cookie_path`` as
               expected.

             * Bug fix: The ``cookie_domain`` setting value was not being used
               when setting a header to delete cookie, meaning any cookie with
               a domain different from the default was not being deleted (as a
               cookie only gets deleted if the path and domain match the ones
               used when the cookie was set). This is now fixed.

             * Fixed the default value of the ``cookie_httponly`` setting in
               the docstring, where the default had previously been changed
               from False to True but the docstring had not been updated with
               it.

             * pyramid_redis_sessions has dropped support for Python 2.6 and
               now requires Python >= 2.7.

             Internal (non-API) changes:

             * ``RedisSession``'s ``timeout`` parameter and
               ``.default_timeout`` attribute have been removed, as they are no
               longer needed now that the timeout is inserted into Redis by the
               factory at the beginning of a new session.
             * Added tests for cookie-related factory parameters.
             * Organised imports to PEP 8.

             Upstream package issue: redis-py introduced a breaking (and
             undocumented) API change in redis==2.10 (see
             https://github.com/andymccurdy/redis-py/issues/510 for
             details). Pinning to redis<=2.9.1 until getting confirmation on
             whether it's a bug that will be fixed, or if we'll need to
             accommodate two different APIs to use newer versions going forward.

-02/20/2015: Changes for 1.0.1

             * Removed redis-py upper bound to support new versions of redis-py

             * No longer pass unused settings to `StrictRedis.from_url` (no
               behavior changes since if you were passing in those settings
               before they were being ignored)

             * Updated to official/stable release version after successful
               alpha period and in order to support pip installs

