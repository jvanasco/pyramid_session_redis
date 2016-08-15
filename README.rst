IMPORTANT
=========

This is an actively maintained fork of `pyramid_redis_sessions`, with many improvements designed for servers under load and developer convenience.

Key Differences:

* The original version communicated with Redis on every attribute access; this version queues a persist or refresh using a finished callback mechanism
* The original version used `EXISTS` to check if a session exists or not.  This simply `GET`S and will create a new session on failure.
* Separate calls to SET and EXPIRE were replaced with a single SETEX
* A flag can be set to enable LRU mode. No expiry data will be sent to Redis, allowing it to handle the LRU logic itself
* The active `session` is decoupled from the request attribute (ie, this can handle a session set up on alternate attributes)
* The original does not detect changes in nested dictionaries. This package uses `hashlib.md5` to fingerprint the serialized value on read; if no changes were detected a failsafe will serialize+md5 the data to decide if a write should occur. This can be disabled by setting `detect_changes` to False.

Depending on your needs, this package may be more desirable.  It significantly cuts down on the communication between Redis and the pyramid app.

The master branch for `jvanasco/pyramid_redis_sessions` is "custom_deployment"

The branched named "master" is the upstream source from ericrasmussen


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
