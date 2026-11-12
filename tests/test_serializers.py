# -*- coding: utf-8 -*-

# stdlib
import unittest
from unittest.mock import patch

# pypi
from webob.cookies import SignedSerializer
from webob.request import Request

# local
from pyramid_session_redis import _get_session_id_from_cookie
from pyramid_session_redis.exceptions import InvalidSessionId_Deserialization
from pyramid_session_redis.exceptions import InvalidSessionId_Serialization
from pyramid_session_redis.util import _StringSerializer

# ==============================================================================


class TestStringSerializer(unittest.TestCase):
    def test_string(self):
        "this should be a roundtrip"
        serializer = _StringSerializer()
        data_in = "foo"
        data_out = data_in
        _serialized = serializer.dumps(data_in)
        self.assertEqual(data_out, serializer.loads(_serialized))

    def test_int(self):
        "this should fail; _StringSerializer requires a str"
        serializer = _StringSerializer()
        data_in = 100
        self.assertRaises(InvalidSessionId_Serialization, serializer.dumps, data_in)

    def test_bytes(self):
        "this should fail; _StringSerializer requires a str"
        serializer = _StringSerializer()
        data_in = b"foo"
        self.assertRaises(InvalidSessionId_Serialization, serializer.dumps, data_in)

    def test_invalid_utf8_preserves_specific_error_and_cause(self):
        with self.assertRaises(InvalidSessionId_Deserialization) as raised:
            _StringSerializer().loads(b"\xff")
        self.assertIsInstance(raised.exception, ValueError)
        self.assertIsInstance(raised.exception.__cause__, UnicodeDecodeError)
        self.assertIs(raised.exception.args[0], raised.exception.__cause__)

    def test_invalid_unicode_preserves_specific_error_and_cause(self):
        with self.assertRaises(InvalidSessionId_Serialization) as raised:
            _StringSerializer().dumps("\ud800")
        self.assertIsInstance(raised.exception, ValueError)
        self.assertIsInstance(raised.exception.__cause__, UnicodeEncodeError)
        self.assertIs(raised.exception.args[0], raised.exception.__cause__)


class TestCookieSerialization(unittest.TestCase):
    def _makeOne_default(self, secret: str) -> SignedSerializer:
        # webob docs `SignedSerializer`:
        # An object with two methods: `loads`` and ``dumps``.  The ``loads`` method
        # should accept bytes and return a Python object.  The ``dumps`` method
        # should accept a Python object and return bytes.

        # SignedSerializer(secret, salt, hashalg="sha512", serializer=None)
        cookie_signer = SignedSerializer(
            secret,
            "pyramid_session_redis.",
            "sha512",
            serializer=_StringSerializer(),
        )
        return cookie_signer

    def test_roundtrip_default(self):
        secret = "foo"
        session_id = "session_id:123"
        cookie_signer = self._makeOne_default(secret)
        _serialized = cookie_signer.dumps(session_id)
        self.assertEqual(session_id, cookie_signer.loads(_serialized))

    def test_signed_cookie_with_invalid_utf8_is_rejected(self):
        signer = self._makeOne_default("secret")
        # Produce a valid signature over bytes that cannot be a UTF-8 ID.
        with patch.object(signer.serializer, "dumps", return_value=b"\xff"):
            signed = signer.dumps("session-id")
        request = Request.blank(
            "/", headers={"Cookie": "session=" + signed.decode("ascii")}
        )
        self.assertIsNone(_get_session_id_from_cookie(request, "session", signer))
