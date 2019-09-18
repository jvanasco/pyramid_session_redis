=========
TODO
=========

# Tests for better integration of the cookie serializer

The existing tests on this concept are largely from pyramid_redis_session and may not test what we need


# Tests for `timeout_trigger`

The testsuite needs to test that timeout trigger is being correctly triggered 
via a short test with `sleep`.

The edgecase that we are trying to recreate:

https://github.com/jvanasco/pyramid_session_redis/issues/11

```
redis.sessions.secret = <removed>
redis.sessions.unix_socket_path = /run/redis/socket
redis.sessions.prefix = session:
redis.sessions.cookie_secure = true
redis.sessions.cookie_max_age = 31536000
redis.sessions.timeout = 3600
```

* A user comes to the site without a session, so they're not logged in and a new session is created for them in redis, with timeout 3600 seconds.
* They log in, and I use adjust_timeout_for_session() to set their timeout to either 1 day or 1 year, depending if they checked the "keep me logged in" box or not.
* If I examine the actual session data stored in redis at this point, the TTL on the redis key has been updated to the correct value (86400 or 31536000), but the x value stored inside the python dict is still 3600, and the t value is still the original 1-hour-later timestamp.

the internal payload should be updated along with the redis TTL.

`test_timeout_trigger` has been started, but should be refactored. it doesn't seem to work as expected regarding the number of redis hits.


