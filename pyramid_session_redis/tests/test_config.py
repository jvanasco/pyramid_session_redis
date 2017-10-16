# -*- coding: utf-8 -*-

import unittest

from pyramid import testing
from pyramid.threadlocal import get_current_request

from ..exceptions import InvalidSession, InvalidSession_DeserializationError

# dotted paths to dummy callables
_id_path = 'pyramid_session_redis.tests.test_config.dummy_id_generator'
_client_path = 'pyramid_session_redis.tests.test_config.dummy_client_callable'
_invalid_logger = 'pyramid_session_redis.tests.test_config.dummy_invalid_logger'


class Test_includeme(unittest.TestCase):
    def setUp(self):
        request = testing.DummyRequest()
        self.config = testing.setUp(request=request)
        self.config.registry.settings = {
            'redis.sessions.secret': 'supersecret',
            'redis.sessions.db': 9,
            'redis.sessions.serialize': 'pickle.dumps',
            'redis.sessions.deserialize': 'pickle.loads',
            'redis.sessions.id_generator': _id_path,
            'redis.sessions.client_callable': _client_path,
            'redis.sessions.func_invalid_logger': _invalid_logger,
        }
        self.config.include('pyramid_session_redis')
        self.settings = self.config.registry.settings

    def tearDown(self):
        testing.tearDown()

    def test_includeme_serialize_deserialize(self):
        request = get_current_request()
        serialize = self.settings['redis.sessions.serialize']
        deserialize = self.settings['redis.sessions.deserialize']
        result = deserialize(serialize('test'))
        self.assertEqual(result, 'test')

    def test_includeme_id_generator(self):
        request = get_current_request()
        generator = self.settings['redis.sessions.id_generator']
        self.assertEqual(generator(), 42)

    def test_includeme_client_callable(self):
        request = get_current_request()
        get_client = self.settings['redis.sessions.client_callable']
        self.assertEqual(get_client(request), 'client')

    def test_includeme_invalid_logger(self):
        request = get_current_request()
        logging_func = self.settings['redis.sessions.func_invalid_logger']
        raised_error = InvalidSession_DeserializationError('foo')
        # check to ensure this is an InvalidSession instance
        self.assertTrue(logging_func(raised_error))


# used to ensure includeme can resolve a dotted path to an id generator
def dummy_id_generator():
    return 42


# used to ensure includeme can resolve a dotted path to a redis client callable
def dummy_client_callable(request, **opts):
    return 'client'


def dummy_invalid_logger(raised):
    assert isinstance(raised, InvalidSession)
    return True
