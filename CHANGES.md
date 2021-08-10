Changelog
=========

- unreleased

-2021.08.10
	* version 1.6.2
	* support newer redis arguments and a `redis_` namespace. thank you, @natej:
		* Accept newer encoding and encoding_errors args
			Update RedisSessionFactory() so it accepts newer encoding and
			encoding_errors args while retaining backwards compatibility.
		* add redis_ prefix for redis passthrough kwargs
			Add redis_ prefix for redis passthrough kwargs to
			RedisSessionFactory().
		* add tests for old and new encoding kwargs
			Add tests for old and new encoding args for RedisSessionFactory()
	* add tests for incompatible kwargs (test_session_factory_incompatible_kwargs)


-2021.04.01
	* version 1.6.1
	* fix invalid `expires` default. thank you, @olemoign
	* doc fixes

-2021.03.30
    * version 1.6.0
    * doc fixes
    * supports Pyramid-2; backwards compatible to Pyramid-1.x and Python-2.
    * packaging reorganization;
      * no changes to API or usage
      * package source now in /src
      * package tests now in /tests
      * `.compat` now the source for various imports
      * anticipated support for pending webob2 changes
    * API now accepts "cookie_expires" on creation [Addresses: #30]
    * Session has new methods:
        * `Session.adjust_cookie_expires(expires)`
        * `Session.adjust_cookie_max_age(max_age)`
    * Session now attempts to be aware of "recookie" requests
    * renamed `adjust_expires_for_session` to `adjust_session_expires`
        * legacy function still works
    * renamed `adjust_timeout_for_session` to `adjust_session_timeout`
        * legacy function still works
    * Closes:
        * #30 - Support "Expires" on Creation and Adjust
        * #31 - Support "max-age" on adjust
        * #32 - Pyramid 2.0 support


-2020.10.20
    * version 1.5.3
    * upgraded black; 20.8b1
    * integrated with pre-commit
    * replaced travis with github actions
    * packaging fixes


-2019.12.17
    * version 1.5.2
    * updated docs to reflect "None" (string) as valid option for samesite.
      This is not yet supported in WebOb, but will be as it was recently added
      to the cookie spec.
    * fixed markup in CHANGES.md (PR #27; thank you @Deimos)

- 2019.09.20
    * version 1.5.1
    * !!!!! SECURITY FIX. **NOT BACKWARDS COMPATIBLE BY DEFAULT**
    * support for `same_site` cookies
    * inline docs improved
    * configs_bool moved to `utils`, still accessable for now.
    * black formatting
    * security fix: changed `session_id` signed serialization.
      this was provided by the deprecated functions `pyramid.session.signed_serialize`
      and `pyramid.session.signed_deserialize`, which are removed in Pyramid 1.10.0+ and
      are considered to be a security vulnerability. using these functions allows
      a malevolent actor to submit a malicious payload that could cause a security
      issue.  This functionality is now handled by constructing a
      `webob.cookies.SignedSerializer()` (which uses JSON (de)serializtion) based on the
      provided `secret`, and using a `_NullSerializer` to encode the session_id
      (only a string session_id is stored in the cookie, so we just need to let the inpu
      string pass through). If desired, a devloper can provide a `cookie_signer`
      object instance to customize this functionality.
    * new `pyramid_session_redis.legacy` - tools to deal with upcoming Pyramid API
      changes (see issue #19)
    * new `pyramid_session_redis.legacy.LegacyCookieSerializer` - implementation
      of Pyramid `1.x > 1.10` signed cookie via the deprecated `signed_serialize`
      and `signed_deserialize` functions. these functions have been copied from
      pyramid and made available through an interface that is compatable with
      the Pyramid 1.10/2.x decision to use `webob.cookies.SignedSerializer`. this
      is only provided for migration and should not be used as it risks security
      issues.
    * new `pyramid_session_redis.legacy.GracefulCookieSerializer` - a serialzer
      that can temporarily replace the new usage of `SignedSerializer` by allowing
      a fallback to the legacy signed_serialize/signed_deserialize functions.
      This serializer allows for logging of serialization attempts and tracking
      the progress of migrating your userbase.  this
      is only provided for migration and should not be used as it risks security
      issues.

- 2019.06.27
    * version 1.5.0
    * new requirements to prepare for Pyramid 2.0 deprecations
    * version 1.4.3, originally scheduled for -2019/04/27
    * using six to handle python3 instead of some homegrown things

- 10/17/2017
    * version 1.4.2
    * set default timeout trigger to `None` (issue #12, forked from #11)
    * migrated `pyramid_session_redis._finished_callback` into `RedisSession._deferred_callback`
    * introduced new `set_redis_ttl_readheavy` option for read-intensive deployments

- 10/17/2017
    * version 1.4.1
    * fixed a deployment error on 1.4.0 that had a non-ascii character in the readme
    * forgot to run Python3 tests

- 10/17/2017
    * version 1.4.0
    * updated deprecation warnings
    * prepping for ability to not create sessions on every access.  getting spidered by bots who don't use sessions hurts Redis.
    * renamed `util.get_unique_session_id` to `util.create_unique_session_id`
    * added `util.empty_session_payload`
    * migrated some RedisSessionFactory functions into a more global (not per-request) block
    * added `func_invalid_logger` to session factory, also renamed internal exceptions. they were not a public api so there is no deprecation issue.
    * this seems fine in our production usage, so pushing live.

- Unreleased
    * skipped 1.3 release.  not enough usage to warrant backwards compat right now
    * a bunch of api changes to support lazy-created sessions.  the original structure would immediately create sessions, which can cause issues with bots and spidering.

- 1/24/2017:
    * version 1.2.2
    * merged most of pull request https://github.com/jvanasco/pyramid_session_redis/pull/3 from Chad Birch (@Deimos)
    * clarified assume_redis_lru in docs, added tests
    * added `force_redis_ttl` kwarg to `RedisSession.do_refresh`
    * added `set_redis_ttl` deprecating it's inverse: `assume_redis_lru`.  the `assume_redis_lru` kwarg will be supported until the 1.4.0 release.
    * added `use_int_time` as session factory arg. this will cast the `created` time to int(math.ceil(time)), saving some space

- 1/17/2017:
    * version 1.2.1
    * fixed bug with session.invalidate that caused placeholder sessions to be created( https://github.com/jvanasco/pyramid_session_redis/issues/2 )
    * added test to guard against above bug
    * fixed some whitespace issues (trailing spaces, tabs-not-spaces)
    * migrated pacakge version id from setup.py into __init__.py as "__VERSION__" variable.
    * migrated tests and code to handle webob 1.7's deprecation of cookie values

- 12/23/2016:
    * version 1.2.0
    * merged PR1 from hongyuan1306 (https://github.com/jvanasco/pyramid_session_redis/pull/1)
        * Make the package Python3 compatible
        * Consolidate token/session generation
        * Leverage token/session generation from python3.6 stdlib; fallback otherwise.
    * updated the bits on token_urlsafe from 32 to 48; this encodes to a 64 character string

- 11/10/2016:
    * version 1.1.2
    release error fix.

- 11/10/2016:
    * version 1.1.1
    * integrated/rewrote pr from pyramid_redis_sessions for session leakage on cdns
        https://github.com/ericrasmussen/pyramid_redis_sessions/pull/74/files
    * response.vary will now ensure `Cookie`
    * Session factory now accepts `func_check_response_allow_cookies(response)` a callable which can disable setting the cookie.
    * streamlined some work in utils

- 11/09/2016: renamed to pyramid_session_redis

- 08/15/2016: Changes for jvanasco branch
    * added `deserialized_fails_new` to handle deserialization errors

- 08/02/2016: Changes for jvanasco branch
    * made the detection of nested changes configurable. by default this is set to True.

- 06/16/2016: Changes for jvanasco branch

    * changed `persist` from being "on demand" into a single callback via pyramid's `add_finished_callback`
    * changed `refresh` from being "on demand" into a single callback via pyramid's `add_finished_callback`
    * decoupled active `session` from being a particular named attribute on the "request".
    * removed an initial call to redis' `EXISTS`. Instead of "If EXISTS then GET", we simply GET the active session and create a new one if it does not exist.
    * replaced separate calls to "SET" and "EXPIRE" with single "SETEX"
    * added a feature to assume redis is operating as a LRU cache, therefore not sending expiry data
    * ensure nested session values trigger a persist by calculating an md5 hash of the serialized session data on load; then again in the finished callback

----------


- Initial Release

- 09/24/2012: 0.9 beta release

- 11/12/2012: raise ConfigurationError if required redis.sessions.secret setting
             is missing.

- 02/17/2013: New API method: adjust_timeout_for_session. This method allows you
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

- 06/30/2013: New configuration options:

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

- 10/13/2013: Many documentation improvements, and some minor refactoring (better
    comments, removing unused functions, etc).

    This update has been in the works on the github main for months
    with no releases to pypi. It marks another major version bump,
    this time to 1.0a. Releases will follow a more typical versioning
    model from now on (similar to Pyramid's).


- 06/15/2014: Changes for 1.0a2

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

- 02/20/2015: Changes for 1.0.1

    * Removed redis-py upper bound to support new versions of redis-py

    * No longer pass unused settings to `StrictRedis.from_url` (no
    behavior changes since if you were passing in those settings
    before they were being ignored)

    * Updated to official/stable release version after successful
    alpha period and in order to support pip installs

