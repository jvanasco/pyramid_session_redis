# -*- coding: utf-8 -*-

# stdlib
import unittest

# pypi
from pyramid import testing
from pyramid.threadlocal import get_current_request
from pyramid.exceptions import ConfigurationError

# local
from pyramid_session_redis.exceptions import (
    InvalidSession,
    InvalidSession_DeserializationError,
)


# ==============================================================================


# dotted paths to dummy callables
_id_path = "tests.test_config.dummy_id_generator"
_client_path = "tests.test_config.dummy_client_callable"
_invalid_logger = "tests.test_config.dummy_invalid_logger"


# ------------------------------------------------------------------------------


# used to ensure includeme can resolve a dotted path to an id generator
def dummy_id_generator():
    return 42


# used to ensure includeme can resolve a dotted path to a redis client callable
def dummy_client_callable(request, **opts):
    return "client"


def dummy_invalid_logger(raised):
    assert isinstance(raised, InvalidSession)
    return True


class CustomCookieSigner(object):
    def loads(self, s):
        return s

    def dumps(self, s):
        return s


# ------------------------------------------------------------------------------


class Test_includeme_simple(unittest.TestCase):
    def setUp(self):
        request = testing.DummyRequest()
        self.config = testing.setUp(request=request)
        self.config.registry.settings = {
            "redis.sessions.secret": "supersecret",
            "redis.sessions.db": 9,
            "redis.sessions.serialize": "pickle.dumps",
            "redis.sessions.deserialize": "pickle.loads",
            "redis.sessions.id_generator": _id_path,
            "redis.sessions.client_callable": _client_path,
            "redis.sessions.func_invalid_logger": _invalid_logger,
        }
        self.config.include("pyramid_session_redis")
        self.settings = self.config.registry.settings

    def tearDown(self):
        testing.tearDown()

    def test_includeme_serialize_deserialize(self):
        request = get_current_request()
        serialize = self.settings["redis.sessions.serialize"]
        deserialize = self.settings["redis.sessions.deserialize"]
        result = deserialize(serialize("test"))
        self.assertEqual(result, "test")

    def test_includeme_id_generator(self):
        request = get_current_request()
        generator = self.settings["redis.sessions.id_generator"]
        self.assertEqual(generator(), 42)

    def test_includeme_client_callable(self):
        request = get_current_request()
        get_client = self.settings["redis.sessions.client_callable"]
        self.assertEqual(get_client(request), "client")

    def test_includeme_invalid_logger(self):
        request = get_current_request()
        logging_func = self.settings["redis.sessions.func_invalid_logger"]
        raised_error = InvalidSession_DeserializationError("foo")
        # check to ensure this is an InvalidSession instance
        self.assertTrue(logging_func(raised_error))


class Test_includeme_advanced(unittest.TestCase):
    def test_fails__no_cookiesigner__no_secret(self):
        request = testing.DummyRequest()
        self.config = testing.setUp(request=request)
        self.config.registry.settings = {
            "redis.sessions.db": 9,
            "redis.sessions.serialize": "pickle.dumps",
            "redis.sessions.deserialize": "pickle.loads",
            "redis.sessions.id_generator": _id_path,
            "redis.sessions.client_callable": _client_path,
            "redis.sessions.func_invalid_logger": _invalid_logger,
            # "redis.sessions.secret": "supersecret",  # don't include!
            # "redis.sessions.cookie_signer": "",  # don't include!
        }
        with self.assertRaises(ConfigurationError) as cm:
            self.config.include("pyramid_session_redis")
        self.assertEqual(
            cm.exception.args[0],
            "One, and only one, of `redis.sessions.secret` and `redis.sessions.cookie_signer` must be provided.",
        )

    def test_fails__cookiesigner__secret(self):
        request = testing.DummyRequest()
        self.config = testing.setUp(request=request)
        self.config.registry.settings = {
            "redis.sessions.db": 9,
            "redis.sessions.serialize": "pickle.dumps",
            "redis.sessions.deserialize": "pickle.loads",
            "redis.sessions.id_generator": _id_path,
            "redis.sessions.client_callable": _client_path,
            "redis.sessions.func_invalid_logger": _invalid_logger,
            "redis.sessions.secret": "supersecret",
            "redis.sessions.cookie_signer": CustomCookieSigner(),
        }
        with self.assertRaises(ConfigurationError) as cm:
            self.config.include("pyramid_session_redis")
        self.assertEqual(
            cm.exception.args[0],
            "One, and only one, of `redis.sessions.secret` and `redis.sessions.cookie_signer` must be provided.",
        )

    def test__cookiesigner__custom(self):
        request = testing.DummyRequest()
        self.config = testing.setUp(request=request)
        self.config.registry.settings = {
            "redis.sessions.db": 9,
            "redis.sessions.serialize": "pickle.dumps",
            "redis.sessions.deserialize": "pickle.loads",
            "redis.sessions.id_generator": _id_path,
            "redis.sessions.client_callable": _client_path,
            "redis.sessions.func_invalid_logger": _invalid_logger,
            "redis.sessions.cookie_signer": CustomCookieSigner(),
        }
