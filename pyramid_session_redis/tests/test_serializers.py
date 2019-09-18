# -*- coding: utf-8 -*-
from __future__ import print_function


import unittest

from webob.cookies import SignedSerializer
from ..util import _NullSerializer
from ..legacy import LegacyCookieSerializer
from ..legacy import GracefulCookieSerializer


class TestNullSerializer(unittest.TestCase):
    def test_roundtrip_string(self):
        serializer = _NullSerializer()
        data = "foo"
        _serialized = serializer.dumps(data)
        self.assertEqual(_serialized, serializer.loads(_serialized))

    def test_roundtrip_int(self):
        serializer = _NullSerializer()
        data = 100
        _serialized = serializer.dumps(data)
        self.assertEqual(_serialized, serializer.loads(_serialized))


class TestCookieSerialization(unittest.TestCase):
    def _makeOne_default(self, secret):
        signed_serializer = SignedSerializer(
            secret, "pyramid_session_redis.", "sha512", serializer=_NullSerializer()
        )
        return signed_serializer

    def _makeOne_legacy(self, secret):
        signed_serializer = LegacyCookieSerializer(secret)
        return signed_serializer

    def _makeOne_graceful(self, secret, logging_hook=None):
        signed_serializer = GracefulCookieSerializer(secret, logging_hook=logging_hook)
        return signed_serializer

    def test_roundtrip_default(self):
        secret = "foo"
        session_id = "123"
        signed_serializer = self._makeOne_default(secret)
        _serialized = signed_serializer.dumps(session_id)
        self.assertEqual(session_id, signed_serializer.loads(_serialized))

    def test_roundtrip_legacy(self):
        secret = "foo"
        session_id = "123"
        signed_serializer = self._makeOne_legacy(secret)
        _serialized = signed_serializer.dumps(session_id)
        self.assertEqual(session_id, signed_serializer.loads(_serialized))

    def test_incompatible(self):
        secret = "foo"
        session_id = "123"
        signed_serializer_current = self._makeOne_default(secret)
        signed_serializer_legacy = self._makeOne_legacy(secret)
        _serialized_current = signed_serializer_current.dumps(session_id)
        _serialized_legacy = signed_serializer_legacy.dumps(session_id)
        self.assertNotEqual(_serialized_current, _serialized_legacy)
        self.assertRaises(
            ValueError, signed_serializer_legacy.loads, _serialized_current
        )
        self.assertRaises(
            ValueError, signed_serializer_current.loads, _serialized_legacy
        )

    def test_graceful(self):
        secret = "foo"
        session_id = "123"
        signed_serializer_current = self._makeOne_default(secret)
        signed_serializer_legacy = self._makeOne_legacy(secret)
        signed_serializer_graceful = self._makeOne_graceful(secret)

        _serialized_current = signed_serializer_current.dumps(session_id)
        _serialized_legacy = signed_serializer_legacy.dumps(session_id)
        _serialized_graceful = signed_serializer_graceful.dumps(session_id)

        self.assertEqual(_serialized_current, _serialized_graceful)
        self.assertNotEqual(_serialized_legacy, _serialized_graceful)

        self.assertEqual(
            session_id, signed_serializer_graceful.loads(_serialized_current)
        )
        self.assertEqual(
            session_id, signed_serializer_graceful.loads(_serialized_graceful)
        )
        self.assertEqual(
            session_id, signed_serializer_graceful.loads(_serialized_legacy)
        )

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

        signed_serializer_legacy = self._makeOne_legacy(secret)
        signed_serializer_graceful = self._makeOne_graceful(secret, logging_hook)
        _serialized_graceful = signed_serializer_graceful.dumps(session_id)
        _serialized_legacy = signed_serializer_legacy.dumps(session_id)

        self.assertEqual(len(logging_hook._attempts), 0)
        self.assertEqual(len(logging_hook._successes), 0)

        signed_serializer_graceful.loads(_serialized_graceful)

        self.assertEqual(len(logging_hook._attempts_global), 1)
        self.assertEqual(len(logging_hook._attempts), 1)
        self.assertEqual(len(logging_hook._successes), 1)

        signed_serializer_graceful.loads(_serialized_legacy)
        self.assertEqual(len(logging_hook._attempts_global), 2)
        self.assertEqual(len(logging_hook._attempts), 3)
        self.assertEqual(len(logging_hook._successes), 2)

        signed_serializer_graceful.loads(_serialized_graceful)
        self.assertEqual(len(logging_hook._attempts_global), 3)
        self.assertEqual(len(logging_hook._attempts), 4)
        self.assertEqual(len(logging_hook._successes), 3)

        self.assertRaises(ValueError, signed_serializer_graceful.loads, "foo")
        self.assertEqual(len(logging_hook._attempts_global), 4)
        self.assertEqual(len(logging_hook._attempts), 6)
        self.assertEqual(len(logging_hook._successes), 3)
