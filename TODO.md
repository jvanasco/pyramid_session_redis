TODO
=====

# more tests covering "please_recookie"

I am not sure the current logic will cover all edge cases


# Tests for better integration of the cookie serializer

The existing tests on this concept are largely from pyramid_redis_session and may not test what we need

* Creating a new session still takes 2 SET/SETEX calls -- one for a placeholder, the next to update.  This should be consolidated into one. (was this done already?)

# Tests should use mocks or protocols

There are some issues with typing, because tests use DummyRedis not Redis, etc.

* DummyClass args are invalid
* RealClasses don't have certain attributes

Examples::

*  tests/test_connection.py:36: error: Argument "client_class" to "get_default_connection" has incompatible type "type[DummyRedis]"; expected "type[Redis]"  [arg-type]
* tests/test_connection.py:38: error: "Redis" has no attribute "url"  [attr-defined]
