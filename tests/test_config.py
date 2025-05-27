# -*- coding: utf-8 -*-

# stdlib
import unittest

# pypi
from pyramid import testing
from pyramid.exceptions import ConfigurationError
from pyramid.request import Request
from pyramid.threadlocal import get_current_request
from typing_extensions import Literal

# local
from pyramid_session_redis.exceptions import InvalidSession
from pyramid_session_redis.exceptions import (
    InvalidSession_DeserializationError,
)  # noqa: E501
from ._util import _client_path
from ._util import _id_path
from ._util import _invalid_logger
from ._util import CustomCookieSigner

# ==============================================================================


# used to ensure includeme can resolve a dotted path to an id generator
def dummy_id_generator() -> str:
    return "42"


# used to ensure includeme can resolve a dotted path to a redis client callable
def dummy_client_callable(request: Request, **opts) -> str:
    return "client"


def dummy_invalid_logger(request: Request, raised: Exception) -> Literal[True]:
    assert isinstance(raised, InvalidSession)
    return True


# ------------------------------------------------------------------------------


class Test_includeme_simple(unittest.TestCase):
    def setUp(self):
        request = testing.DummyRequest()
        self.config = testing.setUp(request=request)
        self.config.registry.settings = {
            "redis.sessions.deserialize": "pickle.loads",
            "redis.sessions.func_invalid_logger": _invalid_logger,
            "redis.sessions.id_generator": _id_path,
            "redis.sessions.redis_client_callable": _client_path,
            "redis.sessions.redis_db": 9,
            "redis.sessions.secret": "supersecret",
            "redis.sessions.serialize": "pickle.dumps",
        }
        self.config.include("pyramid_session_redis")
        self.settings = self.config.registry.settings

    def tearDown(self):
        testing.tearDown()

    def test_includeme_serialize_deserialize(self):
        request = get_current_request()  # noqa: F841
        serialize = self.settings["redis.sessions.serialize"]
        deserialize = self.settings["redis.sessions.deserialize"]
        result = deserialize(serialize("test"))
        self.assertEqual(result, "test")

    def test_includeme_id_generator(self):
        request = get_current_request()  # noqa: F841
        generator = self.settings["redis.sessions.id_generator"]
        self.assertEqual(generator(), "42")

    def test_includeme_client_callable(self):
        request = get_current_request()
        get_client = self.settings["redis.sessions.redis_client_callable"]
        self.assertEqual(get_client(request), "client")

    def test_includeme_invalid_logger(self):
        request = get_current_request()  # noqa: F841
        logging_func = self.settings["redis.sessions.func_invalid_logger"]
        raised_error = InvalidSession_DeserializationError("foo")
        # check to ensure this is an InvalidSession instance
        self.assertTrue(logging_func(request, raised_error))


class Test_includeme_advanced(unittest.TestCase):
    def test_fails__no_cookiesigner__no_secret(self):
        request = testing.DummyRequest()
        self.config = testing.setUp(request=request)
        self.config.registry.settings = {
            "redis.sessions.deserialize": "pickle.loads",
            "redis.sessions.func_invalid_logger": _invalid_logger,
            "redis.sessions.id_generator": _id_path,
            "redis.sessions.redis_client_callable": _client_path,
            "redis.sessions.redis_db": 9,
            "redis.sessions.serialize": "pickle.dumps",
            # "redis.sessions.cookie_signer": "",  # don't include!
            # "redis.sessions.secret": "supersecret",  # don't include!
        }
        with self.assertRaises(ConfigurationError) as cm:
            self.config.include("pyramid_session_redis")
        self.assertEqual(
            cm.exception.args[0],
            "One, and only one, of `redis.sessions.secret` and "
            "`redis.sessions.cookie_signer` must be provided.",
        )

    def test_fails__cookiesigner__secret(self):
        request = testing.DummyRequest()
        self.config = testing.setUp(request=request)
        self.config.registry.settings = {
            "redis.sessions.cookie_signer": CustomCookieSigner(),
            "redis.sessions.deserialize": "pickle.loads",
            "redis.sessions.func_invalid_logger": _invalid_logger,
            "redis.sessions.id_generator": _id_path,
            "redis.sessions.redis_client_callable": _client_path,
            "redis.sessions.redis_db": 9,
            "redis.sessions.secret": "supersecret",
            "redis.sessions.serialize": "pickle.dumps",
        }
        with self.assertRaises(ConfigurationError) as cm:
            self.config.include("pyramid_session_redis")
        self.assertEqual(
            cm.exception.args[0],
            "One, and only one, of `redis.sessions.secret` and "
            "`redis.sessions.cookie_signer` must be provided.",
        )

    def test__cookiesigner__custom(self):
        request = testing.DummyRequest()
        self.config = testing.setUp(request=request)
        self.config.registry.settings = {
            "redis.sessions.cookie_signer": CustomCookieSigner(),
            "redis.sessions.deserialize": "pickle.loads",
            "redis.sessions.func_invalid_logger": _invalid_logger,
            "redis.sessions.id_generator": _id_path,
            "redis.sessions.redis_client_callable": _client_path,
            "redis.sessions.redis_db": 9,
            "redis.sessions.serialize": "pickle.dumps",
        }
