TODO
=====

# more tests covering "please_recookie"

I am not sure the current logic will cover all edge cases


# Tests for better integration of the cookie serializer

The existing tests on this concept are largely from pyramid_redis_session and may not test what we need

* Creating a new session still takes 2 SET/SETEX calls -- one for a placeholder, the next to update.  This should be consolidated into one. (was this done already?)

