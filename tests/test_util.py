# -*- coding: utf-8 -*-

# stdlib
import itertools
from typing import Any
from typing import Dict
import unittest

# local
from pyramid_session_redis.util import _generate_session_id
from pyramid_session_redis.util import _insert_session_id_if_unique
from pyramid_session_redis.util import _parse_settings
from pyramid_session_redis.util import create_unique_session_id
from pyramid_session_redis.util import int_time
from pyramid_session_redis.util import persist
from pyramid_session_redis.util import prefixed_id
from pyramid_session_redis.util import refresh
from . import DummyRedis
from . import DummySession


# ==============================================================================


class Test_parse_settings(unittest.TestCase):
    def _makeOne(self, settings):
        return _parse_settings(settings)

    def _makeSettings(self):
        settings = {
            "ignore.this.setting": "",
            "redis.sessions.cookie_secure": "false",
            "redis.sessions.redis_host": "localhost",
            "redis.sessions.redis_port": "1234",
            "redis.sessions.redis_socket_timeout": "1234",
            "redis.sessions.secret": "mysecret",
        }
        return settings

    def test_it(self):
        settings = self._makeSettings()
        inst = self._makeOne(settings)
        self.assertEqual(False, inst["cookie_secure"])
        self.assertEqual("localhost", inst["redis_host"])
        self.assertEqual(1234, inst["redis_port"])
        self.assertEqual(1234.0, inst["redis_socket_timeout"])
        self.assertNotIn("ignore.this.setting", inst)

    def test_minimal_configuration(self):
        settings = {"redis.sessions.secret": "mysecret"}
        inst = self._makeOne(settings)
        self.assertEqual("mysecret", inst["secret"])

    def test_no_secret_raises_error(self):
        from pyramid.exceptions import ConfigurationError

        settings: Dict[str, Any] = {}
        self.assertRaises(ConfigurationError, self._makeOne, settings)

    def test_prefix_and_generator_raises_error(self):
        from pyramid.exceptions import ConfigurationError

        settings = {
            "redis.sessions.id_generator": "test",
            "redis.sessions.prefix": "test",
            "redis.sessions.secret": "test",
        }
        self.assertRaises(ConfigurationError, self._makeOne, settings)

    def test_prefix_in_options(self):
        settings = {
            "redis.sessions.prefix": "testprefix",
            "redis.sessions.secret": "test",
        }
        inst = self._makeOne(settings)
        implicit_generator = inst["id_generator"]
        self.assertIn("testprefix", implicit_generator())


class Test__insert_session_id_if_unique(unittest.TestCase):
    def _makeOne(
        self,
        redis,
        timeout=1,
        session_id="id",
        serialize=lambda x: x,
        set_redis_ttl=True,
    ):
        return _insert_session_id_if_unique(
            redis, timeout, session_id, serialize, set_redis_ttl
        )

    def test_id_is_unique(self):
        redis = DummyRedis()
        before = int_time() - 2
        result = self._makeOne(redis)
        after = int_time() + 2
        persisted = redis.get("id")
        managed_dict = persisted["m"]
        created = persisted["c"]
        timeout = persisted["t"]
        self.assertDictEqual(managed_dict, {})
        self.assertGreaterEqual(created, before)
        self.assertLessEqual(created, after)
        self.assertEqual(timeout, 1)
        self.assertEqual(result, "id")

    def test_id_not_unique(self):
        redis = DummyRedis()
        original_value = object()
        redis.set("id", original_value)
        result = self._makeOne(redis)
        # assert value under key has not been changed
        self.assertEqual(redis.get("id"), original_value)
        self.assertEqual(result, None)

    def test_watcherror_returns_none(self):
        redis = DummyRedis(raise_watcherror=True)
        result = self._makeOne(redis)
        self.assertIs(redis.get("id"), None)
        self.assertEqual(result, None)


class Test_create_unique_session_id(unittest.TestCase):
    def _makeOne(self, redis=DummyRedis(), timeout=300):
        serialize = lambda x: x
        ids = itertools.count(start=1, step=1)
        generator = lambda: str(next(ids))
        return create_unique_session_id(
            redis,
            timeout,
            serialize,
            generator=generator,
        )

    def test_id_is_unique(self):
        result = self._makeOne()
        self.assertEqual(result, "1")

    def test_id_not_unique(self):
        redis = DummyRedis()
        redis.set("1", "")
        result = self._makeOne(redis)
        self.assertEqual(result, "2")


class Test__generate_session_id(unittest.TestCase):
    def _makeOne(self):
        return _generate_session_id

    def test_it(self):
        inst = self._makeOne()
        result = inst()
        self.assertEqual(len(result), 64)


class Test_prefixed_id(unittest.TestCase):
    def _makeOne(self):
        return prefixed_id

    def test_it(self):
        inst = self._makeOne()
        result = inst("prefix")
        self.assertEqual(len(result), 70)
        self.assertEqual(result[:6], "prefix")


class Test_persist_decorator(unittest.TestCase):
    def _makeOne(self, wrapped):
        return persist(wrapped)

    def _makeSession(self, timeout):
        redis = DummyRedis()
        session_id = "session.session_id"
        redis.timeouts[session_id] = timeout
        session = DummySession(session_id, redis, timeout)
        return session

    def test_it(self):
        def wrapped(session, *arg, **kwarg):
            return "expected result"

        inst = self._makeOne(wrapped)
        timeout = 300
        session = self._makeSession(timeout)
        result = inst(session)
        ttl = session.redis.ttl(session.session_id)
        self.assertEqual(result, "expected result")
        self.assertEqual(timeout, ttl)


class Test_refresh_decorator(unittest.TestCase):
    def _makeOne(self, wrapped):
        return refresh(wrapped)

    def _makeSession(self, timeout):
        redis = DummyRedis()
        session_id = "session.session_id"
        redis.timeouts[session_id] = timeout
        session = DummySession(session_id, redis, timeout)
        return session

    def test_it(self):
        def wrapped(session, *arg, **kwarg):
            return "expected result"

        inst = self._makeOne(wrapped)
        timeout = 300
        session = self._makeSession(timeout)
        result = inst(session)
        ttl = session.redis.ttl(session.session_id)
        self.assertEqual(result, "expected result")
        self.assertEqual(timeout, ttl)
