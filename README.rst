IMPORTANT
=========

`pyramid_session_redis` is an actively maintained fork of `pyramid_redis_sessions` (ericrasmussen/pyramid_redis_sessions), with many improvements and API changes designed for servers under load and developer convenience.

Key Differences:
================


* The original version communicated with Redis on every attribute access; `pyramid_session_redis` will queue a single `persist` or `refresh` task using Pyramid's `add_finished_callback` hook.
* The original version used `EXISTS` to check if a session existed or not, then proceeded to `GET` or create a new session.  `pyramid_session_redis` will immediately attempt a `GET`, and will create a new session on failure.  This cuts down a Redis traffic.
* Separate calls to `SET` and `EXPIRE` were replaced with a single `SETEX`
* A flag can be set to enable a LRU Cache (least recently used) mode. No expiry data will be sent to Redis, allowing the Redis server to handle the LRU logic itself
* The active `session` is decoupled from the request attribute (ie, this can handle a "session" set up on alternate attributes)
* The original library does not detect changes in nested dictionaries. This package uses `hashlib.md5` to fingerprint the serialized value on read; if no changes were detected a failsafe will serialize+md5 the data to decide if a write should occur. This can be disabled by setting `detect_changes` to False.
* The original raises a fatal error if a session can not be deserialized.  by passing in `deserialized_fails_new` to the constructor, you can create a new session on deserialization errors.

Other Updates:
==============

* support for disabling sessions on CDN generated content via `func_check_response_allow_cookies`
* thankts to github/hongyuan1306, token generation has been consolidated to use python3's stdlib (or reimplemented if not available).  tokens are also 32, not 20, chars.
* redis is supported in a LRU mode (see http://redis.io/topics/lru-cache) by setting the option `set_redis_ttl` to `False` (by default, it is `True`).  This will eliminate calls to EXPIRE and will use SET instead of SETEX.
* the payload timeout can be set to an integer via `use_int_time=True`.  This will cast the `created` time via "int(math.ceil(time.time()))".  This can reduce a payload by several characters.

Depending on your needs, this package may be more desirable.  It significantly cuts down on the communication between Redis and the pyramid app vs the original package.  Some options are offered to minimize the size of payloads as well.

Notes:
======

If ``set_redis_ttl`` is False, it does not imply there is no timeout at all -- only that Redis will not be sent timeout data via `SETEX` or `EXPIRE`.  Timeout data will still be stored in Python.

If Redis is functioning as an LRU Cache, abandoned sessions will never be seen by Python, but will eventually be cleared out to make room for new sessions by the inherent Redis LRU logic.

Timeout data stored in Python is relatively small when compared to the timeout data stored in Redis.

If you want to NEVER have sessions timeout, set the initial `timeout` to "0" or "None".

Examples:
---------

Timeout in Python, with Redis TTL via SETEX/EXPIRE:

	timeout = 60

Timeout in Python, no Redis TTL (only SET used)

	timeout = 60
	assume_redis_ttl = True
	
No Timeout in Python, no Redis TTL (only SET used)

	timeout = 0  # or None
	assume_redis_ttl = True


To Do:
================

The following features are under consideration. PRs are requested

[ ] A way to not create a session if the new session is empty.  Accessing the session or session-id will trigger the generation of a session_id, even if empty. In high load situations this may not be ideal, and no session/session_id should be created unless the session is populated.


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
