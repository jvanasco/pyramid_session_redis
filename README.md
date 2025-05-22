[![Build Status](https://travis-ci.org/jvanasco/pyramid_session_redis.png)](https://travis-ci.org/jvanasco/pyramid_session_redis)


Overview
========

`pyramid_session_redis` is a mature, stable and actively maintained Server-Side
Sessions plugin for the Pyramid web framework.

Originally, this library was a fork of
[`pyramid_redis_sessions`](https://github.com/ericrasmussen/pyramid_redis_sessions), focused on
improvements and API changes designed for high performance (particularly with
servers under load), and a slightly different API designed for developer
convenience.

Compatibility
-------------

`main` and `1.7` branches require:

* Python 3.7+
* Pyramid 2.0


The `1.6` branch is designed to support both:

* Python 2
* Python 3

and

* Pyramid 1.x
* Pyramid 2.0


Breaking Changes
----------------

In the `1.7` branch, there are several breaking changes:
    * Drop Python 3.6
    * removed deprecated redis commands
    * minimum redis library is now 4.0
    * util._NullSerializer will ensure data is serialized into a string.
    * util._NullSerializer is deprecated; renamed to _util._StringSerializer
    * util.SerializerInterface is deprecated and replaced with util.SignedSerializerInterface
    * the entire `pyramid_session_redis.legacy` namespace has been deprecated;
    * there were serveral (de)serialization issues tied to issues with upstream typing

Planned changes for `1.8` branch:
    * remove the pyramid_session_redis.legacy namespace
    * set `invalidate_empty_session` to True



Prior Branches
--------------

The 1.6.x branch is in maintenance mode. This is the last branch to support
Python2 and Pyramid1.

The 1.5.x branch is EOL. No updates are expected, as 1.6 is backwards compatible.

The 1.4.x branch is EOL. It led to the stable 1.5.0 API release.

The 1.2.x branch is EOL as of 1.2.2. Previous plans were to support a final
1.3.0 release.

Prior Branch Details
____________________

The 1.2.x branch and earlier are largely a "drop-in-replacement" compatible with
Eric Rasmussen's `pyramid_redis_sessions` as-is.  If you are migrating from that
project and do not want to upgrade code, you should pin your install of this
library to `pyramid_session_redis<=1.3.0` or `pyramid_session_redis<1.3`

**Please be aware that you will be limited to using outdated versions of Pyramid 
1.x if using the 1.2.x branch.**

Starting with the 1.4.x branch, several design changes were made and this library
is not a drop-in replacement, **HOWEVER** upgrading will only require minimal
editing of your code: some editing for migration; some kwargs have changed;
the structure of the package changed (imports); and advanced users who leverage
the internal systems may need to upgrade. It should not take more than 5 minutes
to convert.  The package is still a plug-and-play Pyramid ISessions interface, so
there are very small changes.

Prior Branch Incompatibilities
______________________________

IMPORTANT: The internal payload structure changed in the 1.4 branch, and is no
longer compatible with sessions created under 1.2 - they will be invalid.

PRs that can handle a graceful fallback are welcome.

The 1.2 format guaranteed internal sessions to be in this format:

    {'managed_dict': {},
     'created': INT,
     'timeout': INT,
     }

The 1.4 version streamlines the keys for a lighter footprint and generally
looks like this:

    {'m': {},  # managed_dict
     'c': INT,  # created
     'v': SESSION_API_VERSION,  # api version INT
     # the following are optional and not guaranteed to be in a session
     't': INT,  # timeout
     'x': INT,  # expiry
     }

Key Takeaways:

* Keys were shortened to 1 letter
* An API Version is now used, to handle graceful changes in the future
* The Timeout is no longer guaranteed to be present.
  The library now supports the entire Timeout to be handled in Redis
* An "Expiry Timeout" may also exist

Key Concepts
============================================


Timeout vs Expires/MaxAge
-------------------------

This package allows you to set both *Timeout* and *Expiry* values.  The two
concepts are closely related, but very different.

A *Timeout* is an internal value and a moving target. It specifies how long a
Session should last before it times out due to inactivity. The timeout is
constantly refreshed when the session is accessed.

For example, consider these settings:

    timeout = 1800
    timeout_trigger = 900

The `timeout` setting is specifying the Session should remain active for 1800
seconds since it's last activity.  The `timeout_trigger` setting is an
optimization that defers modifying the Session's timeout on READ operations until
at least 900 seconds have passed since the last modification. Modifications will
always occur on WRITE operations.  Depending on your configuration, the timeout
may be stored in Redis, as part of the Python Payload, or both.

To illustrate how the above settings work, consider a timeline in which a User
visits a website and then visits it again 2000 seconds later:

> Visit 1 | 0s    | Session A (new)
> Visit N | 2000s | Session B (new)

When the User makes the last visit, the Session would have timed out, because it
exceeded the 1800 second mark in the timeout.

Now assume the User makes 3 visits in this timeline, and a second visit happens
at the 899 mark:

> Visit 1 | 0s    | Session A (new)
> Visit 2 | 899s  | Session A
> Visit N | 2000s | Session B (new)

When the User makes the last visit, the Session would still
have timed out, because the second visit did not meet the timeout_trigger
threshold.

But, if the second visit happens just 2 seconds later, at the 901 mark, the
timeout_trigger is reached and the session's timeout will be extended:

> Visit 1 | 0s    | Session A (new)
> Visit 2 | 901s  | Session A (update timeout trigger)
> Visit N | 2000s | Session A (update timeout trigger)

When the User makes the last visit, it would still happen within the context of
the original Session and the timeout will be extended even further.

*Expires* and *Max-Age* are generally values that related to Cookie settings.

*Expires* is created on a Cookie as either a specified Date, or a null value; if
the value is null (explicit or unspecified), the Cookie will be set as a
"Session" cookie and only last for the duration of the web browser application
being open.

*Max-Age* is created on a Cookie as the number of seconds until the Cookie
expires.  A zero or negative value will expire (delete) the cookie immediately.
If both Expires and Max-Age are set, Max-Age has precedence.


The Confusion?
--------------

If Redis stores our Timeout info, it stores it in an "expiry" value via `SETEX`
or similar calls.  


Key Differences From pyramid_redis_sessions
============================================

Depending on your needs, this package is probably more desirable than the
original project. This package was designed to significantly cut down on the
communication between Redis and Pyramid. Some options are offered to minimize
the size of Redis payloads as well.

This package contains additional hooks and features to aid developers who are
using Redis-based sessions in high-traffic situations.

This package does not recommend any "best deployment" strategies, but supports a
wide range of strategies to implement the "best deployment" under any given
circumstance.

Through 1.2.x
-------------

* The original package communicates with Redis on most attribute accesses and
  writes within a given request. The traffic can be burdensome in some
  implementations. `pyramid_session_redis` will queue a single `persist` or
  `refresh` task per-request using Pyramid's `add_finished_callback` hook.
* The original version used `EXISTS` to check if a Session existed or not, then
  proceeded to `GET` or `SET` a new Session.  `pyramid_session_redis` will
  immediately attempt a `GET`, and will `SET` a new Session on failure.
  This approach eliminates a call.
* Separate calls to `SET` and `EXPIRE` were replaced with a single `SETEX`.
* A flag can be set to enable a LRU Cache (least recently used) mode. No expiry
  data will be sent to Redis, allowing the Redis server to handle the LRU logic
  itself.
* The active Session is decoupled from the `request.session` attributs; this
  allows for the Session to be set up on alternate attributes and supports
  integration with
  [pyramid_session_multi](https://github.com/jvanasco/pyramid_session_multi).
* The original library does not detect changes in nested dictionaries. This
  package uses `hashlib.md5` to fingerprint the serialized value on READ; if no
  changes were detected, a failsafe will `Serialize+md5` the data to decide if a
  WRITE should occur. This behavior can be disabled by setting `detect_changes`
  to `False`.
* The original library raises a fatal error if a Session can not be
  deserialized. By passing in `deserialized_fails_new` to the constructor,
  you can create a new Session on deserialization errors.
* Support for disabling Sessions on CDN generated content via
  `func_check_response_allow_cookies`
* Thanks to @ github/hongyuan1306, Token Generation has been consolidated to use
  Python3's stdlib (or reimplemented if not available). Tokens are also 32,
  not 20, characters.
* Redis is supported in a LRU mode (see http://redis.io/topics/lru-cache) by
  setting the option `set_redis_ttl` to `False` (by default, it is `True`).
  This will eliminate calls to `EXPIRE` and will use `SET` instead of `SETEX`.
* In the 1.2.x branch, the created time can be set to an integer via
  `use_int_time=True`. This will cast the `created` time via
  `int(math.ceil(time.time()))`. This reduces a payload by several bits.

Other Updates 1.4.x+
--------------------

* Only `int()` time is supported; Fractional time wastes bytes.
* Sessions now have version control to support future upgrades via a "version"
  `v` key.
* The format of the internal payload was rewritten, the encoded payload now
  uses 1-letter keys instead of words. This should offset the addition of an
  expires timestamp and version id.
* There was no logic for Python timeout control (whoops!) this has been fixed.
  An "expires" `x` key now tracks the expiration.
* Added a `timeout_trigger` option.  This will defer expiry data updates to
  lower usage on Redis.  This is explained below in more detail.
* In high load situations, Redis can have performance and storage issues because
  in the original package Session IDs are created on every request (such as a
  getting spidered by a botnet that does not respect Sessions). In this package,
  a 'lazycreate' method is used: a session_id/cookie will not be generated
  unless a session is needed in the callback routine. In order to generate
  session_id/cookie beforehand, one can use the `RedisSession.ensure_id`
  function.  To safely check if a session id exists, one can use the
  `RedisSession.session_id_safecheck` method as well.
* Added `func_invalid_logger` to the constructor. This can be used to log
  invalid Sessions. It is incredibly useful when integrated with a statsd
  system. (see below)
* Added `set_redis_ttl_readheavy` to the factory and session constructors.
  This option will optimize Sessions which have Redis-maintained TTLs by
  executing a GET+EXPIRE together within a pipeline.



Installation
============

Install via pypi:

    pip install pyramid_session_redis


Configuration
=============

Configure `pyramid_session_redis` via your Paste config file or however you
prefer to configure Pyramid. Only `redis.sessions.secret` is required.
All other settings are optional.

For complete documentation on the `RedisSessionFactory` that uses these
settings, see :doc:`api`. Otherwise, keep reading for the quick list:


    # session settings
    redis.sessions.secret = your_cookie_signing_secret
    redis.sessions.timeout = 1200

    # session cookie settings
    redis.sessions.cookie_name = session
    redis.sessions.cookie_max_age = max_age_in_seconds
    redis.sessions.cookie_path = /
    redis.sessions.cookie_domain =
    redis.sessions.cookie_secure = False
    redis.sessions.cookie_httponly = False
    redis.sessions.cookie_on_exception = True

    # you can supply a redis connection string as a URL
    redis.sessions.url = redis://username:password@localhost:6379/0

    # or as individual settings (note: the URL gets preference if you do both)
    redis.sessions.host = localhost
    redis.sessions.port = 6379
    redis.sessions.db = 0
    redis.sessions.password = None

    # additional options can be supplied to redis-py's StrictRedis
    redis.sessions.redis_socket_timeout =
    redis.sessions.redis_connection_pool =
    redis.sessions.redis_encoding = utf-8
    redis.sessions.redis_errors = strict
    redis.sessions.redis_unix_socket_path =

    # in the advanced section we'll cover how to instantiate your own client
    redis.sessions.client_callable = my.dotted.python.callable

    # along with defining your own serialize and deserialize methods
    redis.sessions.serialize = cPickle.dumps
    redis.sessions.deserialize = cPickle.loads

    # you can specify a prefix to be used with session keys in redis
    redis.sessions.prefix = mycoolprefix

    # or you can supply your own UID generator callable for session keys
    redis.sessions.id_generator = niftyuid


Initialization
==============

Lastly, you need to tell Pyramid to use `pyramid_session_redis` as your
Session factory. The preferred way is adding it with `config.include`,
like this:

    def main(global_config, **settings):
        config = Configurator(settings=settings)
        config.include('pyramid_session_redis')

Alternately, instead of using the Configurator's include method, you can
activate Pyramid by changing your application's ".ini" file, use the following
line:

    pyramid.includes = pyramid_session_redis

The above method is recommended because it's simpler, idiomatic, and still fully
configurable. It even has the added benefit of automatically resolving dotted
python paths used in the advanced options.

However, you can also explicitly pass a settings dict to the
`session_factory_from_settings` function. This can be helpful if you configure
or modify your settings in code:

    from pyramid_session_redis import session_factory_from_settings

    def main(global_config, **settings):
        config = Configurator(settings=settings)
        session_factory = session_factory_from_settings(settings)
        config.set_session_factory(session_factory)


Timeout Notes
=============

If ``set_redis_ttl`` is False, it does not imply there is no timeout at all --
only that Redis will not be sent timeout data via `SETEX` or `EXPIRE`.
Timeout data will still be stored in Python.

If Redis is functioning as an LRU Cache, abandoned sessions will never be seen
by Python, but will eventually be cleared out to make room for new sessions by
the inherent Redis LRU logic.

Timeout data stored in Python is relatively small when compared to the timeout
data stored in Redis.

If you want to NEVER have sessions timeout, set the initial `timeout`
to "0" or "None".

Setting a `timeout_trigger` will require Python to track the expiry.

Enabling `set_redis_ttl_readheavy` requires a `timeout` and `set_redis_ttl`;
it also requires not enabling `timeout_trigger` or `python_expires`.


Timeout Examples
----------------

Timeout in Python, with Redis TTL via `SETEX`/`EXPIRE`:

    timeout = 60

Timeout in Python, no Redis TTL (only `SET` used)

    timeout = 60
    assume_redis_ttl = True

No Timeout in Python, no Redis TTL (only `SET` used)

    timeout = 0  # or None
    assume_redis_ttl = True


Warning: Session Locking and Race Conditions
============================================

This package does not incorporate any sort of locking for session updating or
handling of race conditions.

This should not be a problem for the vast majority of users, and is a feature
not present on any known Pyramid Session providers.

For more information, please see:

* https://github.com/jvanasco/pyramid_session_redis/issues/9
* https://github.com/Pylons/pyramid/issues/3041


Feature - Timeout Triggers
==========================

A timeout trigger can be used to limit the amount of updates/writes.
It may be more beneficial to your usage pattern.

For the sake of clarity, I'll use an oversimplification that Redis essentially
has two different internal data stores that are used independently: one for a
Key's payload and another for the Key's expiry.

In the 'classic' behavior (project this was forked from): every time you access
an existing session, the GET is followed by sending Redis a new EXPIRE time;
essentially every "read" has a corresponding "write" for the Redis-tracked
expiry record.

In order to minimize the writes via SETEX, I introduced the timeout trigger.
The trigger works by storing some timeout information in the Redis data payload,
and using that information to determine when to send a write. Instead of having
a GET+EXPIRE for every read, we only have a single GET and eliminate the write
caused by the EXPIRE. This has a maintenance cost though - once we hit the
timeout trigger, instead of just the GET we need to update the internal timeout
payload and issue a SET.

Going back to your situation: when the user stops activity at 40 minutes in, if
the timeout trigger is enabled then there has never been an update to the
internal payload or Redis about the user activity since the session was first
created. The purpose of the trigger is to defer that "write" operation.

In order to make a session valid for "reading" for around an hour, you should
do something like:

* a two-hour session with a 10 minute trigger, or
* a one-hour session with a 50 minute trigger

You can also disable the functionality by setting the trigger to 0. Up to a few
thousand daily users, you shouldn't have any issues with the overhead of the
"classic" mode. When you hit 10k users and/or start to have clustered web
servers communicating with dedicated Redis instances, setting a new EXPIRE after
every read operation becomes something you want to avoid.


Scenario 1 - Classic Redis
--------------------------

In the typical "classic" Redis usage pattern, the session usage is refreshed via
an `EXPIRE` call on every session view.

This is useful, but means many session operations will trigger two Redis calls
(`GET` + `EXPIRE`).  On a high performance system, this can be a lot.

This is a typical scenario with refreshing:

    timeout = 200

The following timeline would occur:

| time | Redis calls    | timeout |
| ---- | -------------- | ------- |
| 0    | `GET`+`SETEX`  | 200     |
| 100  | `GET`+`EXPIRE` | 300     |
| 200  | `GET`+`EXPIRE` | 400     |
| 300  | `GET`+`EXPIRE` | 500     |
| 400  | `GET`+`EXPIRE` | 600     |
| 500  | `GET`+`EXPIRE` | 700     |


Scenario 2 - Timeout Trigger
--------------------------

The 1.4.x branch introduces a `timeout_trigger` to augment the Session's
`timeout`.

Whereas a `timeout` states how long a session is good for, a `timeout_trigger`
defers how long a Session's refresh should be deferred for:

Given the following example, the package will use a 1200s timeout for requests,
but only trigger an update of the expiry time when the current time is within
600s of the expiry:

    timeout = 1200
    timeout_trigger = 600

The following timeline would occur:

| time | Redis calls  | timeout | next threshold |
| ---- | ------------ | ------- | -------------- |
| 0    | `GET`+`SET`* | 1200    | 600            |
| 1    | `GET`        | 1200    | 600            |
| ...  |              |         |                |
| 599  | `GET`        | 1200    | 600            |
| 600  | `GET`+`SET`* | 1800    | 1200           |
| 601  | `GET`        | 1800    | 1200           |
| ...  |              |         |                |
| 1199 | `GET`        | 1800    | 1200           |
| 1200 | `GET`+`SET`* | 2400    | 1800           |

* This method is compatible with setting a TTL in redis via `SETEX` or doing
everything within Python if Redis is in a LRU mode

The removes all calls to `EXPIRE` before the threshold is reached, which can be
 a considerable savings in read-heavy situations.

The caveat to this method: an expiry timestamp must be stored within the payload
AND updating the timeout requires a `SET` operation.


Feature - set_redis_ttl_readheavy
=================================

This is a new option in `1.4.2` which should improve performance on readheavy
installations BUT may degrade performance on writeheavy installations.  This
option will aggregate a GET+EXPIRE on every read.

`set_redis_ttl_readheavy` requires the following:

* a `timeout` value is set
* `set_redis_ttl` is `True`
* `timeout_trigger` is NOT set
* `python_expires` is NOT True

The default behavior of this library during a read-only request is this:

* On session access, query Redis via `redis.GET {session_id}`
* In a Pyramid callback, update Redis via `redis.EXPIRE {session_id} {expiry}`

During a read-write:

* On session access, query Redis via `redis.GET {session_id}`
* In a Pyramid callback, update Redis via
  `redis.SETEX {session_id} {payload} {expiry}`

The new `set_redis_ttl_readheavy` changes this. If enabled during a read-only
request, the behavior will be lighter on the Redis instance:

* On session access, open a pipeline with two Redis commands:
  `pipeline.GET {session_id}`,
  `pipeline.EXPIRE {session_id} {expiry}`.
* In a Pyramid callback, the duplicate expire is suppressed.

However during a read-write, the activity will be:

* On session access, open a pipeline with two Redis commands:
  `pipeline.GET {session_id}`,
  `pipeline.EXPIRE {session_id} {expiry}`.
* In a Pyramid callback, update Redis via
  `redis.SETEX {session_id} {payload} {expiry}`

Read-heavy applications should see a slight performance bump via the pipeined
GET+EXPIRE, however write-heavy applications are likely to see a performance
degradation as it adds an extra EXPIRE to every request.


Invalid Logging
================

The default behavior of this library is to silently create new session when bad
session data is encountered, such as a cookie with an invalid id or corrupted
datastore.  A graceful "new session" is the ideal situation for end-users.

The problem with that strategy is that problems in code or your application
stack can be hidden, and you might not know about a bad datastore.

The 1.4 release introduces `func_invalid_logger` to the factory constructor.
This can be used to track the invalid sessions that are safely caught and
silently upgraded.

How?  The package tracks why a session is invalid with variant classes of
`pyramid_session_redis.exceptions.InvalidSession`.

Specifically there are the following classes:

* ``InvalidSession(Exception)``
  Catchall base class
* ``InvalidSession_NoSessionCookie(InvalidSession)``
  The Session is invalid because there is no cookie.
  This is the same as "new session".
* ``InvalidSession_NotInBackend(InvalidSession)``
  The Session id was not in the backend.
* ``InvalidSession_DeserializationError(InvalidSession)``
    Error deserializing.
    This is raised if ``deserialized_fails_new`` is True. Otherwise the
    exception is wrapped in a ``RawDeserializationError`` and raised without
    being caught.
* ``InvalidSession_PayloadTimeout(InvalidSession)``
    The inner Python payload timed out.
* ``InvalidSession_PayloadLegacy(InvalidSession)``
    The Session is running on an earlier version.

The factory accepts a `func_invalid_logger` callable argument. The input is the
raised exception BEFORE a new cookie is generated, and will be the request and
an instance of `InvalidSession`.

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

The `func_invalid_logger` argument may be provided as a dotted-notation string
in a configuration file.


Uncaught Errors
================

The exception `pyramid_session_redis.exceptions.RawDeserializationError` will be
raised if deserialization of a payload fails and `deserialized_fails_new` is not
`True`. The first arg will be the caught exception. This allows for a standard
error across multiple deserialization options.


FAQ:
=====

Q. What serialization is used?
------------------------------

A. Serialization is used at two points

* Serializing the Session data.
  The server-side data serialization is handled by `pickle`. This Session data is
  created on the server by your application and remains on the server. `pickle`
  is safe to use in this context, as user-generated payloads can not be introduced
  to these (de)serialization routines. If you wish to avoid `pickle`, or your
  prefer to use another encoder, you can easily specify a different (de)serialization
  routine such as a custom JSON, msgpack or pretty much anything else.

* Serializing the `session_id` to encode into a signed cookie.
  This library uses `WebOb.cookies.SignedSerializer` to securely manage a HMAC
  signature of the `session_id` combined with a site-secret. The library allows
  for a custom replacement to be provided as well.
  
  In the original library, the session id and signature were turned into a
  cookie-safe value via `pickle` (de)serialization - a detail that remained in
  this library through `<=v1.5.0`. This approach was identified as a security
  risk, and was removed from this library starting in `v1.5.1`.  


Examples
========

There is an example of using this package in `pyramid_session_multi`
[examples/single_file_app.py](https://github.com/jvanasco/pyramid_session_multi/blob/main/examples/single_file_app.py).


Further Reading:
================

For more information about Redis performance under Python please see an
associated project:

* https://github.com/jvanasco/dogpile_backend_redis_advanced

To suport multiple Sessions under Pyramid

* https://github.com/jvanasco/pyramid_session_multi

Until Nov 2016 this was maintained as `jvanasco/pyramid_redis_sessions`

* The main branch for `jvanasco/pyramid_redis_sessions` was "custom_deployment"
* The branched named "main" is the upstream source from ericrasmussen

As of Nov 2016, this was forked into it's own project to allow for distribution
under PyPi.

All support is handled via GitHub : https://github.com/jvanasco/pyramid_session_redis


ToDo
=====

see `TODO.md`


Changelog
==========

see `CHANGES.md`


Support
=======

You can report bugs or open feature/support requests via GitHub

* https://github.com/jvanasco/pyramid_session_redis


License
=======

`pyramid_session_redis` is available under a FreeBSD-derived license. See
`LICENSE.txt <https://github.com/jvanasco/pyramid_session_redis/blob/main/LICENSE.txt>`_
for details.
