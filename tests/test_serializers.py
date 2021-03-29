# -*- coding: utf-8 -*-
from __future__ import print_function

# stdlib
import unittest

# pypi
from webob.cookies import SignedSerializer

# local
from pyramid_session_redis.util import _NullSerializer
from pyramid_session_redis.legacy import LegacyCookieSerializer
from pyramid_session_redis.legacy import GracefulCookieSerializer


# ==============================================================================


class TestNullSerializer(unittest.TestCase):
    def test_roundtrip_string(self):
        serializer = _NullSerializer()
        data = "foo"
        _serialized = serializer.dumps(data)
        self.assertEqual(data, serializer.loads(_serialized))

    def test_roundtrip_int(self):
        serializer = _NullSerializer()
        data = 100
        _serialized = serializer.dumps(data)
        self.assertEqual(data, serializer.loads(_serialized))


class TestCookieSerialization(unittest.TestCase):
    def _makeOne_default(self, secret):
        cookie_signer = SignedSerializer(
            secret, "pyramid_session_redis.", "sha512", serializer=_NullSerializer()
        )
        return cookie_signer

    def _makeOne_legacy(self, secret):
        cookie_signer = LegacyCookieSerializer(secret)
        return cookie_signer

    def _makeOne_graceful(self, secret, logging_hook=None):
        cookie_signer = GracefulCookieSerializer(secret, logging_hook=logging_hook)
        return cookie_signer

    def test_roundtrip_default(self):
        secret = "foo"
        session_id = "123"
        cookie_signer = self._makeOne_default(secret)
        _serialized = cookie_signer.dumps(session_id)
        self.assertEqual(session_id, cookie_signer.loads(_serialized))

    def test_roundtrip_legacy(self):
        secret = "foo"
        session_id = "123"
        cookie_signer = self._makeOne_legacy(secret)
        _serialized = cookie_signer.dumps(session_id)
        self.assertEqual(session_id, cookie_signer.loads(_serialized))

    def test_incompatible(self):
        secret = "foo"
        session_id = "123"
        cookie_signer_current = self._makeOne_default(secret)
        cookie_signer_legacy = self._makeOne_legacy(secret)
        _serialized_current = cookie_signer_current.dumps(session_id)
        _serialized_legacy = cookie_signer_legacy.dumps(session_id)
        self.assertNotEqual(_serialized_current, _serialized_legacy)
        self.assertRaises(ValueError, cookie_signer_legacy.loads, _serialized_current)
        self.assertRaises(ValueError, cookie_signer_current.loads, _serialized_legacy)

    def test_graceful(self):
        secret = "foo"
        session_id = "123"
        cookie_signer_current = self._makeOne_default(secret)
        cookie_signer_legacy = self._makeOne_legacy(secret)
        cookie_signer_graceful = self._makeOne_graceful(secret)

        _serialized_current = cookie_signer_current.dumps(session_id)
        _serialized_legacy = cookie_signer_legacy.dumps(session_id)
        _serialized_graceful = cookie_signer_graceful.dumps(session_id)

        self.assertEqual(_serialized_current, _serialized_graceful)
        self.assertNotEqual(_serialized_legacy, _serialized_graceful)

        self.assertEqual(session_id, cookie_signer_graceful.loads(_serialized_current))
        self.assertEqual(session_id, cookie_signer_graceful.loads(_serialized_graceful))
        self.assertEqual(session_id, cookie_signer_graceful.loads(_serialized_legacy))

    def test_graceful_hooks(self):
        secret = "foo"
        session_id = "123"

        class LoggingHook(object):
            def __init__(self):
                self._attempts_global = []
                self._attempts = []
                self._successes = []

            def attempt(self, serializer):
                if serializer == "global":
                    self._attempts_global.append(serializer)
                else:
                    self._attempts.append(serializer)

            def success(self, serializer):
                self._successes.append(serializer)

        logging_hook = LoggingHook()

        cookie_signer_legacy = self._makeOne_legacy(secret)
        cookie_signer_graceful = self._makeOne_graceful(secret, logging_hook)
        _serialized_graceful = cookie_signer_graceful.dumps(session_id)
        _serialized_legacy = cookie_signer_legacy.dumps(session_id)

        self.assertEqual(len(logging_hook._attempts), 0)
        self.assertEqual(len(logging_hook._successes), 0)

        cookie_signer_graceful.loads(_serialized_graceful)

        self.assertEqual(len(logging_hook._attempts_global), 1)
        self.assertEqual(len(logging_hook._attempts), 1)
        self.assertEqual(len(logging_hook._successes), 1)

        cookie_signer_graceful.loads(_serialized_legacy)
        self.assertEqual(len(logging_hook._attempts_global), 2)
        self.assertEqual(len(logging_hook._attempts), 3)
        self.assertEqual(len(logging_hook._successes), 2)

        cookie_signer_graceful.loads(_serialized_graceful)
        self.assertEqual(len(logging_hook._attempts_global), 3)
        self.assertEqual(len(logging_hook._attempts), 4)
        self.assertEqual(len(logging_hook._successes), 3)

        self.assertRaises(ValueError, cookie_signer_graceful.loads, "foo")
        self.assertEqual(len(logging_hook._attempts_global), 4)
        self.assertEqual(len(logging_hook._attempts), 6)
        self.assertEqual(len(logging_hook._successes), 3)
