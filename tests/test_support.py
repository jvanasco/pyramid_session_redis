# -*- coding: utf-8 -*-

# stdlib
import os
from typing import Optional
import unittest

# pypi
from webob.cookies import SignedSerializer

# local
from pyramid_session_redis import _get_session_id_from_cookie
from pyramid_session_redis.exceptions import InvalidSessionId_Serialization
from pyramid_session_redis.util import _NullSerializer

# ==============================================================================

# export GENERATE_COOKIE_DATA=1
GENERATE_COOKIE_DATA = bool(int(os.getenv("GENERATE_COOKIE_DATA", "0")))

# ----


class _ExpectedFailure_Setup(Exception):
    pass


class _FakeRequest(object):
    response: Optional["_FakeResponse"] = None

    @property
    def cookies(self):
        """proxy against response.set_cookie to loosely mimic interace"""
        if self.response:
            return self.response.cookies
        return None


class _FakeResponse(object):
    req: Optional[_FakeRequest] = None
    cookies: Optional[dict[str, bytes]] = None

    def __init__(self, req: Optional[_FakeRequest] = None):
        self.cookies = {}
        self.req = req
        if self.req:
            self.req.response = self

    def set_cookie(self, name: str, value: str):
        _value: bytes
        if isinstance(value, str):
            _value = value.encode()
        else:
            _value = value
        if self.cookies is not None:
            self.cookies[name] = _value


class Test_GetSessionIdFromCookie(unittest.TestCase):
    """
    In production, we should NEVER use a _NullSerializer like this.
    Instead, we should always use a SignedSerializer.

    The _NullSerializer is only used in this context to test the function
    `_get_session_id_from_cookie`
    """

    def _makeOne(self, cookie_name, cookie_value):
        serializer = _NullSerializer()
        if isinstance(cookie_value, str):
            _cookie_value = serializer.dumps(cookie_value)
        else:
            self.assertRaises(
                InvalidSessionId_Serialization, serializer.dumps, cookie_value
            )
            raise _ExpectedFailure_Setup()

        req = _FakeRequest()
        res = _FakeResponse(req)
        res.set_cookie(cookie_name, _cookie_value)
        self.assertIn(cookie_name, res.cookies)
        _value_encoded = res.cookies[cookie_name]
        self.assertEqual(type(_value_encoded), bytes)
        return res, serializer

    def _test_setup(
        self,
        cookie_name,
        value_in,  # raw value in
        value_encoded,  # encoded into Response; must be bytes
        value_decoded,  # decoded from request
    ):
        res, serializer = self._makeOne(cookie_name, value_in)
        _decoded = _get_session_id_from_cookie(res, cookie_name, serializer)
        self.assertIn(cookie_name, res.cookies)
        self.assertEqual(res.cookies[cookie_name], value_encoded)
        self.assertEqual(value_decoded, _decoded)
        self.assertEqual(type(_decoded), str)

    def test_string(self):
        cookie_name = "test_string"
        cookie_value = "string"
        value_encoded = b"string"
        value_decoded = "string"
        self._test_setup(cookie_name, cookie_value, value_encoded, value_decoded)

    def test_int(self):
        cookie_name = "test_int"
        cookie_value = 1
        # this should fail during setup
        value_encoded = None
        value_decoded = None
        self.assertRaises(
            _ExpectedFailure_Setup,
            self._test_setup,
            cookie_name,
            cookie_value,
            value_encoded,
            value_decoded,
        )

    def test_bytes(self):
        cookie_name = "test_bytes"
        cookie_value = b"bytes"
        # this should fail during setup
        value_encoded = None
        value_decoded = None
        self.assertRaises(
            _ExpectedFailure_Setup,
            self._test_setup,
            cookie_name,
            cookie_value,
            value_encoded,
            value_decoded,
        )


class Test_CookieSigner_NullSerializer(unittest.TestCase):
    """
    to generate data for tests::

       export GENERATE_COOKIE_DATA=1
    """

    def _makeOne(self, cookie_name, cookie_value):
        cookie_signer = SignedSerializer(
            "secret",
            "pyramid_session_redis.",
            "sha512",
            serializer=_NullSerializer(),
        )
        if isinstance(cookie_value, str):
            _cookie_value = cookie_signer.dumps(cookie_value)
        else:
            self.assertRaises(
                InvalidSessionId_Serialization, cookie_signer.dumps, cookie_value
            )
            raise _ExpectedFailure_Setup()

        res = _FakeResponse()
        res.set_cookie(cookie_name, _cookie_value)
        if GENERATE_COOKIE_DATA:
            print("--------")
            print("%s.%s" % (self.__class__.__name__, self._testMethodName))
            print("  name:  ", cookie_name)
            print("  value: ", cookie_value)
            print("  signed:", _cookie_value)
        return res, cookie_signer

    def _test_setup(self, cookie_name, value_in, value_expected, value_signed):
        res, cookie_signer = self._makeOne(cookie_name, value_in)
        self.assertIn(cookie_name, res.cookies)
        self.assertEqual(res.cookies[cookie_name], value_signed)
        value_out = _get_session_id_from_cookie(res, cookie_name, cookie_signer)
        self.assertEqual(value_expected, value_out)

    def test_string(self):
        cookie_name = "test_string"
        cookie_value = "string"
        value_expected = "string"
        value_signed = b"JW5R1E8zj18d1HHYi1v0bXsBrGgEPSG0BKQ4U1CjLkNbFM4WlTz1XzQEebEOv4k9F8RGuT3V_TizoDdRwz52sHN0cmluZw"
        self._test_setup(cookie_name, cookie_value, value_expected, value_signed)

    def test_bytes(self):
        cookie_name = "test_bytes"
        cookie_value = b"string"
        value_expected = None
        value_signed = None
        self.assertRaises(
            _ExpectedFailure_Setup,
            self._test_setup,
            cookie_name,
            cookie_value,
            value_expected,
            value_signed,
        )

    def test_int(self):
        cookie_name = "test_int"
        cookie_value = 1
        value_expected = None
        value_signed = None
        self.assertRaises(
            _ExpectedFailure_Setup,
            self._test_setup,
            cookie_name,
            cookie_value,
            value_expected,
            value_signed,
        )


class Test_CookieSigner_DefaultSerializer(unittest.TestCase):
    """
    to generate data for tests::

       export GENERATE_COOKIE_DATA=1
    """

    def _makeOne(self, cookie_name, cookie_value):
        cookie_signer = SignedSerializer(
            "secret",
            "pyramid_session_redis.",
            "sha512",
        )
        if isinstance(cookie_value, bytes):
            self.assertRaises(TypeError, cookie_signer.dumps, cookie_value)
            raise _ExpectedFailure_Setup()
        else:
            _cookie_value = cookie_signer.dumps(cookie_value)
        res = _FakeResponse()
        res.cookies[cookie_name] = _cookie_value
        if GENERATE_COOKIE_DATA:
            print("--------")
            print("%s.%s" % (self.__class__.__name__, self._testMethodName))
            print("  name:  ", cookie_name)
            print("  value: ", cookie_value)
            print("  signed:", _cookie_value)
        return res, cookie_signer

    def _test_setup(self, cookie_name, value_in, value_expected, value_signed):
        res, cookie_signer = self._makeOne(cookie_name, value_in)
        self.assertIn(cookie_name, res.cookies)
        self.assertEqual(res.cookies[cookie_name], value_signed)
        value_out = _get_session_id_from_cookie(res, cookie_name, cookie_signer)
        self.assertEqual(value_expected, value_out)

    def test_string(self):
        cookie_name = "test_string"
        cookie_value = "string"
        value_expected = "string"
        value_signed = b"r3pVu9XGVFfz1MZQYdVT9kWVrb94mZT1TdL8HNYnFVf5cDcXPaL4ULuQ_GZ7hNAZNQCwfSRSGuffr6eQTgoHBSJzdHJpbmci"
        self._test_setup(cookie_name, cookie_value, value_expected, value_signed)

    def test_bytes(self):
        cookie_name = "test_bytes"
        cookie_value = b"bytes"
        value_expected = None
        value_signed = None
        self.assertRaises(
            _ExpectedFailure_Setup,
            self._test_setup,
            cookie_name,
            cookie_value,
            value_expected,
            value_signed,
        )

    def test_int(self):
        cookie_name = "test_int"
        cookie_value = 1
        value_expected = 1
        value_signed = b"5aK2BseK-h0dYZa18Pxv8PVdLrKJwlmYNyh2Ck_-febyiABrjgFx1bNrwf128CL0I7Ulpw3f9FpOwlU7sMe5xDE"
        self._test_setup(cookie_name, cookie_value, value_expected, value_signed)
