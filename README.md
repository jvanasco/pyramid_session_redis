IMPORTANT
=========

`pyramid_session_redis` is an actively maintained fork of `pyramid_redis_sessions` (ericrasmussen/pyramid_redis_sessions), with many improvements and API changes designed for high performance (particularly with servers under load) and a slightly different API for developer convenience.

This package is now following a multi-version release process.  

The 1.2.x branch is in maintenance mode as of 1.2.2, and will culminate in a final 1.3.0 release.  

The 1.4.x branch is under active development and subject to change.  It will culminate in a stable 1.5.0 API release.

----

The 1.2.x branch and earlier are largely compatible with `pyramid_redis_sessions` as-is.  If you are using this, you should pin your installs to `<=1.3.0` or `<1.3`.

The 1.4.x branch and later have several design changes and are not a drop-in replacement.  Some kwargs may have changed.  The structure of the package has changed as well, and advanced users who leverage the internals will need to upgrade.  The package remains a plug-and-play pyramid sessions interface.


Key Differences:
================

Depending on your needs, this package is probably more desirable than the original project.  This package significantly cuts down on the communication between Redis and Pyramid vs the original implementation.  Some options are offered to minimize the size of payloads as well.

This package contains a lot of hooks and features to aid developers who are using this in high-traffic situations.  This package does not recommend a "best deployment", but offers different strategies for creating a best deployment under different circumstances.


Through 1.2.x
---------------

* The original package communicates with Redis on most attribute access and writes. The traffic can be too much on some implementations.  `pyramid_session_redis` will queue a single `persist` or `refresh` task using Pyramid's `add_finished_callback` hook.
* The original version used `EXISTS` to check if a session existed or not, then proceeded to `GET` or `SET` a new session.  `pyramid_session_redis` will immediately attempt a `GET`, and will `SET` a new session on failure.  This eliminates a call.
* Separate calls to `SET` and `EXPIRE` were replaced with a single `SETEX`
* A flag can be set to enable a LRU Cache (least recently used) mode. No expiry data will be sent to Redis, allowing the Redis server to handle the LRU logic itself
* The active `session` is decoupled from the request attribute (ie, this can handle a "session" set up on alternate attributes)
* The original library does not detect changes in nested dictionaries. This package uses `hashlib.md5` to fingerprint the serialized value on read; if no changes were detected a failsafe will serialize+md5 the data to decide if a write should occur. This can be disabled by setting `detect_changes` to False.
* The original raises a fatal error if a session can not be deserialized.  by passing in `deserialized_fails_new` to the constructor, you can create a new session on deserialization errors.
* Support for disabling sessions on CDN generated content via `func_check_response_allow_cookies`
* Thanks to @ github/hongyuan1306, token generation has been consolidated to use python3's stdlib (or reimplemented if not available).  tokens are also 32, not 20, chars.
* redis is supported in a LRU mode (see http://redis.io/topics/lru-cache) by setting the option `set_redis_ttl` to `False` (by default, it is `True`).  This will eliminate calls to `EXPIRE` and will use `SET` instead of `SETEX`.
* in the 1.2.x branch the created time can be set to an integer via `use_int_time=True`.  This will cast the `created` time via "int(math.ceil(time.time()))".  This can reduce a payload by several bits. 

Other Updates 1.4.x+
====================
* only int() time is supported.
* sessions now have version control to support future upgrades via a "version" `v` key.
* the format of the internal payload was rewritten, the encoded payload now uses 1-letter keys instead of words.  this should offset the addition of an expires timestamp and version id.
* there was no logic for python timeout control (whoops!) this has been fixed.  an "expires" `x` key now tracks the expiration.
* added a `timeout_trigger` option.  this will defer expiry data updates to lower usage on Redis.  This is explained below in more detail.
* In high load situations, Redis can have performance and storage issues because in the original package sessionIDs are created on every request (such as a getting spidered by a botnet that does not respect sessions). in this package, a 'lazycreate' method is used.  a session_id/cookie will not be generated unless a session is needed in the callback routine.  in order to generate session_id/cookie beforehand, one can use the `RedisSession.ensure_id` function.  To safely check if a session_id exists, one can use the `RedisSession.session_id_safecheck` method as well.
* added `func_invalid_logger` to constructor. this can be used to log invalid sessions. it is incredibly useful when integrated with a statsd system. (see below)



Notes:
======

If ``set_redis_ttl`` is False, it does not imply there is no timeout at all -- only that Redis will not be sent timeout data via `SETEX` or `EXPIRE`.  Timeout data will still be stored in Python.

If Redis is functioning as an LRU Cache, abandoned sessions will never be seen by Python, but will eventually be cleared out to make room for new sessions by the inherent Redis LRU logic.

Timeout data stored in Python is relatively small when compared to the timeout data stored in Redis.

If you want to NEVER have sessions timeout, set the initial `timeout` to "0" or "None".

Setting a timeout_trigger will require Python to track the expiry.

Examples:
---------

Timeout in Python, with Redis TTL via `SETEX`/`EXPIRE`:

	timeout = 60

Timeout in Python, no Redis TTL (only `SET` used)

	timeout = 60
	assume_redis_ttl = True
	
No Timeout in Python, no Redis TTL (only `SET` used)

	timeout = 0  # or None
	assume_redis_ttl = True


Timeout Triggers
=================

A timeout trigger can be used to limit the amount of updates/writes.  It may be more beneficial to your usage pattern.

Scenario 1 - Classic Redis
--------------------------

In the typical "classic" Redis usage pattern, the session usage is refreshed via an `EXPIRE` call on every session view

This is useful, but means many session operations will trigger two Redis calls (`GET` + `EXPIRE`).  On a high performance system, this can be a lot.

This is a typical scenario with refreshing:

```
timeout = 200

time 		Redis Calls		timeout
0			GET+SETEX		200
100			GET+EXPIRE		300
200			GET+EXPIRE		400
300			GET+EXPIRE		500
400			GET+EXPIRE		600
500			GET+EXPIRE		700
```

Scenario 2 - Timeout Trigger
--------------------------

The 1.4.x branch introduces a `timeout_trigger` to augment the session's `timeout`.

Whereas a `timeout` states how long a session is good for, a `timeout_trigger` defers how long a session's refresh should be deferred for:

Given the following example, the package will use a 1200s timeout for requests, but only trigger an update of the expiry time when the current time is within 600s of the expiry

```
timeout = 1200
timeout_trigger = 600
```

The following timeline would occur

```    
time    	Redis Calls		timeout		next threshold
0			GET+SET*  		1200		600
1			GET				1200		600
..
599			GET				1200		600
600			GET+SET* 		1800		1200
601			GET    			1800		1200
...
1199		GET    			1800		1200
1200		GET+SET*		2400		1800
```	

* This method is compatible with setting a TTL in redis via `SETEX` or doing everything within Python if redis is in a LRU mode

The removes all calls to `EXPIRE` before the threshold is reached, which can be a considerable savings in read-heavy situations

The caveat to this method: an expiry timestamp must be stored within the payload AND updating the timeout requires a `SET` operation.


Invalid Logging
================

The default behavior of this library is to silently create new session when bad session data is encountered, such as a cookie with an invalid id or corrupted datastore.  A graceful "new session" is the ideal situation for end-users.

The problem with that strategy is that problems in code or your application stack can be hidden, and you might not know about a bad datastore.

The 1.4 release introduces `func_invalid_logger` to the factory constructor. 
This can be used to track the invalid sessions that are safely caught and silently upgraded 

How?  The package tracks why a session is invalid with variant classes of `pyramid_session_redis.exceptions.InvalidSession`

Specifically there are the following classes:

* ``InvalidSession(Exception)`` Catchall base class
* ``InvalidSession_NoSessionCookie(InvalidSession)`` The session is invalid because there is no cookie.  This is the same as "new session".
* ``InvalidSession_NotInBackend(InvalidSession)`` The session id was not in the backend
* ``InvalidSession_DeserializationError(InvalidSession)`` Error deserializing.  This is raised if ``deserialized_fails_new`` is True. Otherwise the exception is wrapped in a ``RawDeserializationError`` and raised without being caught.
* ``InvalidSession_PayloadTimeout(InvalidSession)`` The inner python payload timed out
* ``InvalidSession_PayloadLegacy(InvalidSession)`` The session is running on an earlier version

The factory accepts a `func_invalid_logger` callable argument.  The input is the raised exception BEFORE a new cookie is generated, and will be the request and an instance of `InvalidSession`.

	from pyramid_session_redis.exceptions import *
	from my_statsd import new_statsd_client()
	
	statsd_client = new_statsd_client()

    def my_logger(request, raised_exception):
    	"""
    	raised_exception will be an instance of InvalidSession
    	log the exception to statsd for metrics
    	"""
    	if isinstance(raised_exception, InvalidSession_NoSessionCookie):
    		statsd_client.incr('invalid_session.NoSessionCookie')
    	elif isinstance(raised_exception, InvalidSession_NotInBackend):
    		statsd_client.incr('invalid_session.NotInBackend')
    	elif isinstance(raised_exception, InvalidSession_DeserializationError):
    		statsd_client.incr('invalid_session.DeserializationError')

	factory = RedisSessionFactory(...
								  func_invalid_logger=my_logger,
								  ...
								  )
		
The `func_invalid_logger` argument may be provided as a dotted-notation string in a settings file.

Uncaught Errors
================

The exception `pyramid_session_redis.exceptions.RawDeserializationError` will be raised if deserialization of a payload fails and `deserialized_fails_new` is not `True`.  The first arg will be the caught exception. This allows for a standard error across multiple deserialization options.


FAQ:
================

coming soon



To Do:
================

[ ] The API is a bit messy on the 1.4.x release. 
[ ] Creating a new session still takes 2 SET/SETEX calls -- one for a placeholder, the next to update.  This should be consolidated into one.


Further Reading:
================


For more information about Redis performance under python please see an associated project:

* https://github.com/jvanasco/dogpile_backend_redis_advanced

Until Nov 2016 this was maintained as `jvanasco/pyramid_redis_sessions`

* The master branch for `jvanasco/pyramid_redis_sessions` is "custom_deployment"
* The branched named "master" is the upstream source from ericrasmussen

As of Nov 2016, this was forked into it's own project to allow for distribution.

All support is handled via GitHub : https://github.com/jvanasco/pyramid_session_redis


ToDo
=====

pass


Overview
========

pyramid_redis_sessions is a server-side session library for the Pyramid Web
Application Development Framework, using Redis for storage. This library
implements the `Pyramid ISession interface <http://docs.pylonsproject.org/projects/pyramid/en/latest/api/interfaces.html#pyramid.interfaces.ISession>`_.


Why Use Redis for Your Sessions
===============================
Redis is fast, widely deployed, and stable. It works best when your data can
fit in memory, but is configurable and still quite fast when you need to sync
to disk. There are plenty of existing benchmarks, opinion pieces, and articles
if you want to learn about its use cases. But for `pyramid_redis_sessions`, I'm
interested in it specifically for these reasons:

* it really is bleeping fast (choose your own expletive)
* it has a very handy built-in mechanism for setting expirations on keys
* the watch mechanism is a nice, lightweight alternative to full transactions
* session data tends to be important but not mission critical, but if it is...
* it has configurable `persistence <http://redis.io/topics/persistence>`_


Documentation
=============

To get up and running as fast as possible, check out the
`Getting Started <http://pyramid-redis-sessions.readthedocs.org/en/latest/gettingstarted.html>`_
guide.

You can also read the
`full documentation <http://pyramid-redis-sessions.readthedocs.org/en/latest/index.html>`_
on Read the Docs.


Support
=======

You can report bugs or open feature/support requests in the
`GitHub issue tracker <https://github.com/ericrasmussen/pyramid_redis_sessions/issues>`_.

You can also get live help in #pyramid on irc.freenode.org. My nick is erasmas,
but if I'm not available you can still typically get support from the many other
knowledgeable regulars.


License
=======

pyramid_redis_sessions is available under a FreeBSD-derived license. See
`LICENSE.txt <https://github.com/ericrasmussen/pyramid_redis_sessions/blob/master/LICENSE.txt>`_
for details.
