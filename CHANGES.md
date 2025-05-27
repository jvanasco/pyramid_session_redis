Changelog
=========


* v1.8.0dev
  * remove deprecations:
    * `pyramid_session_redis.legacy` namespace
    * `util.SerializerInterface`
    * `util._NullSerializer`
  * remove deprecated constructor kwargs; use `redis_` prefixes:
      client_callable -> redis_client_callable
      db -> redis_db
      host -> redis_host
      password -> redis_password
      port -> redis_port
      url -> redis_url
  * toggle behavior:
    `invalidate_empty_session` defaults to `True`
  * internal
    * connections were previously cached onto `Request.registry._redis_sessions`
      now cached onto `_pyramid_session_redis`
    * tests
      * tests were not invoking `_process_finished_callbacks` on mocked objects,
        which improperly tested several scenarios
     
* v1.7.0
  * released 2025.05.27
  * no changes from v1.7.0rc3  

* v1.7.0rc3
  * 2025.05.22
  * hashlib.md5() specifies `usedforsecurity=False` in Py39 and above

* v1.7.0rc2
  * 2025.05.22
  * more typing
  * testing on py313
  * drop testing/support for python3.6 due to github removing ubuntu20.04
  * update pre-commit to use flake8 and a CI version of black
  * minimum redis Python API is now 4.0.0 (November 15 2021)
  * removed deprecated redis kwargs:
      ``socket_timeout``
          replaced by  ``redis_socket_timeout``.
      ``connection_pool``
          replaced by ``redis_connection_pool``.
      ``charset``
          replaced by ``redis_encoding``.
      ``errors``
          replaced by ``redis_encoding_errors``.
      ``unix_socket_path``
          replaced by ``redis_unix_socket_path``.
  * util.SerializerInterface is deprecated and replaced with util.SignedSerializerInterface
     - this will be removed in the next minor release (1.8)
  * the entire `pyramid_session_redis.legacy` namespace has been deprecated.
    this namespace existed to migrate off the `pyramid_redis_session` package
    that package has not been updated in 9 years, and last supported python 3.4
     - this will be removed in the next minor release (1.8)
  * _NullSerializer has been deprecated and renamed to _StringSerializer
  * introduce `invalidate_empty_session` to automatically clear sessions
  * deprecate additional redis kwargs, in favor of variants with a `redis_` prefix:
      url -> redis_url
      host -> redis_host
      port -> redis_port
      db -> redis_db
      password -> redis_password
      client_callable -> redis_client_callable
     - this will be removed in the next minor release (1.8)

* v1.7.0rc1
  * 2023.06.13
  * Breaking Changes:
    * The `session_id` will now always be serialized into a string.
      * If a custom `id_generator` is used, it MUST return a string.
      * Default usage of this package should not be affected at all.      
  * code style changes
  * dropping PY2
  * initial typing support
  * remove some webob dependencies

* 2021.11.16
	* version 1.6.3
	* detect Redis version to better handle deprecated kwargs
	* drop testing/support for python3.5
	* minimum six requirement. thank you, @Wim-De-Clercq 
	* cleanup changelog
	* matrix testing

* 2021.08.10
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

* 2021.04.01
	* version 1.6.1
	* fix invalid `expires` default. thank you, @olemoign
	* doc fixes

* 2021.03.30
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


* 2020.10.20
    * version 1.5.3
    * upgraded black; 20.8b1
    * integrated with pre-commit
    * replaced travis with github actions
    * packaging fixes


* 2019.12.17
    * version 1.5.2
    * updated docs to reflect "None" (string) as valid option for samesite.
      This is not yet supported in WebOb, but will be as it was recently added
      to the cookie spec.
    * fixed markup in CHANGES.md (PR #27; thank you @Deimos)

* 2019.09.20
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

* 2019.06.27
    * version 1.5.0
    * new requirements to prepare for Pyramid 2.0 deprecations
    * version 1.4.3, originally scheduled for * 2019/04/27
    * using six to handle python3 instead of some homegrown things

* 2017.10.17
    * version 1.4.2
    * set default timeout trigger to `None` (issue #12, forked from #11)
    * migrated `pyramid_session_redis._finished_callback` into `RedisSession._deferred_callback`
    * introduced new `set_redis_ttl_readheavy` option for read-intensive deployments

* 2017.10.17
    * version 1.4.1
    * fixed a deployment error on 1.4.0 that had a non-ascii character in the readme
    * forgot to run Python3 tests

* 2017.10.17
    * version 1.4.0
    * updated deprecation warnings
    * prepping for ability to not create sessions on every access.  getting spidered by bots who don't use sessions hurts Redis.
    * renamed `util.get_unique_session_id` to `util.create_unique_session_id`
    * added `util.empty_session_payload`
    * migrated some RedisSessionFactory functions into a more global (not per-request) block
    * added `func_invalid_logger` to session factory, also renamed internal exceptions. they were not a public api so there is no deprecation issue.
    * this seems fine in our production usage, so pushing live.

* Unreleased
    * skipped 1.3 release.  not enough usage to warrant backwards compat right now
    * a bunch of api changes to support lazy-created sessions.  the original structure would immediately create sessions, which can cause issues with bots and spidering.

* 2017.01.24
    * version 1.2.2
    * merged most of pull request https://github.com/jvanasco/pyramid_session_redis/pull/3 from Chad Birch (@Deimos)
    * clarified assume_redis_lru in docs, added tests
    * added `force_redis_ttl` kwarg to `RedisSession.do_refresh`
    * added `set_redis_ttl` deprecating it's inverse: `assume_redis_lru`.  the `assume_redis_lru` kwarg will be supported until the 1.4.0 release.
    * added `use_int_time` as session factory arg. this will cast the `created` time to int(math.ceil(time)), saving some space

* 2017.01.17
    * version 1.2.1
    * fixed bug with session.invalidate that caused placeholder sessions to be created( https://github.com/jvanasco/pyramid_session_redis/issues/2 )
    * added test to guard against above bug
    * fixed some whitespace issues (trailing spaces, tabs-not-spaces)
    * migrated pacakge version id from setup.py into __init__.py as "__VERSION__" variable.
    * migrated tests and code to handle webob 1.7's deprecation of cookie values

* 2016.12.23
    * version 1.2.0
    * merged PR1 from hongyuan1306 (https://github.com/jvanasco/pyramid_session_redis/pull/1)
        * Make the package Python3 compatible
        * Consolidate token/session generation
        * Leverage token/session generation from python3.6 stdlib; fallback otherwise.
    * updated the bits on token_urlsafe from 32 to 48; this encodes to a 64 character string

* 2016.11.10
    * version 1.1.2
    release error fix.

* 2016.11.10
    * version 1.1.1
    * integrated/rewrote pr from pyramid_redis_sessions for session leakage on cdns
        https://github.com/ericrasmussen/pyramid_redis_sessions/pull/74/files
    * response.vary will now ensure `Cookie`
    * Session factory now accepts `func_check_response_allow_cookies(response)` a callable which can disable setting the cookie.
    * streamlined some work in utils

* 2016.11.09
	renamed to pyramid_session_redis

* 2016.08.15
	* Changes for jvanasco branch
	    * added `deserialized_fails_new` to handle deserialization errors

* 2016.08.12
	* Changes for jvanasco branch
    	* made the detection of nested changes configurable. by default this is set to True.

* 2016.06.16
	* Changes for jvanasco branch
		* changed `persist` from being "on demand" into a single callback via pyramid's `add_finished_callback`
		* changed `refresh` from being "on demand" into a single callback via pyramid's `add_finished_callback`
		* decoupled active `session` from being a particular named attribute on the "request".
		* removed an initial call to redis' `EXISTS`. Instead of "If EXISTS then GET", we simply GET the active session and create a new one if it does not exist.
		* replaced separate calls to "SET" and "EXPIRE" with single "SETEX"
		* added a feature to assume redis is operating as a LRU cache, therefore not sending expiry data
		* ensure nested session values trigger a persist by calculating an md5 hash of the serialized session data on load; then again in the finished callback


* LEGACY CHANGELOG
	* see https://github.com/ericrasmussen/pyramid_redis_sessions/blob/master/CHANGES.rst
	