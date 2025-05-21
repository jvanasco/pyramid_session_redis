# -*- coding: utf-8 -*-

# stdlib
import os
from typing import Any
from typing import Dict
from typing import Optional
from typing import Tuple
from typing import TYPE_CHECKING
import unittest

# pypi
from webob.cookies import SignedSerializer

# local
from pyramid_session_redis import _get_session_id_from_cookie
from pyramid_session_redis.exceptions import InvalidSessionId_Serialization
from pyramid_session_redis.util import _StringSerializer

# ==============================================================================

# export GENERATE_COOKIE_DATA=1
GENERATE_COOKIE_DATA = bool(int(os.getenv("GENERATE_COOKIE_DATA", "0")))

TYPE_COOKIES = Optional[Dict[str, str]]

# ----


class _ExpectedFailure_Setup(Exception):
    pass


class _FakeRequest(object):
    response: Optional["_FakeResponse"] = None

    @property
    def cookies(self) -> TYPE_COOKIES:
        """proxy against response.set_cookie to loosely mimic interace"""
        if self.response:
            return self.response.cookies
        return None


class _FakeResponse(object):
    req: Optional[_FakeRequest] = None
    cookies: TYPE_COOKIES = None

    def __init__(self, req: Optional[_FakeRequest] = None) -> None:
        self.cookies: TYPE_COOKIES = {}
        self.req = req
        if self.req:
            self.req.response = self

    def set_cookie(self, name: str, value: str) -> None:
        # webob.set_cookie expects str
        assert isinstance(value, str)
        if self.cookies is not None:
            self.cookies[name] = value


class Test_GetSessionIdFromCookie(unittest.TestCase):
    """
    In production, we should NEVER use a _StringSerializer like this.
    Instead, we should always use a SignedSerializer.

    The _StringSerializer is only used in this context to test the function
    `_get_session_id_from_cookie`
    """

    def _makeOne(
        self,
        cookie_name: str,
        cookie_value: str,
    ) -> Tuple[_FakeRequest, _FakeResponse, _StringSerializer]:
        serializer = _StringSerializer()
        if isinstance(cookie_value, str):
            _cookie_signed = serializer.dumps(cookie_value)  # bytes
            _cookie_value = _cookie_signed.decode()  # set_cookie wants str
        else:
            self.assertRaises(
                InvalidSessionId_Serialization, serializer.dumps, cookie_value
            )
            raise _ExpectedFailure_Setup()
        req = _FakeRequest()
        res = _FakeResponse(req)
        res.set_cookie(cookie_name, _cookie_value)
        if TYPE_CHECKING:
            assert res.cookies is not None
        self.assertIn(cookie_name, res.cookies)
        _value_encoded = res.cookies[cookie_name]
        self.assertEqual(type(_value_encoded), str)
        return req, res, serializer

    def _test_setup(
        self,
        cookie_name: str,
        value_in: Any,  # raw value in
        value_encoded: Any,  # encoded into Response; must be bytes
        value_decoded: str,  # decoded from request
    ) -> None:
        req, res, serializer = self._makeOne(cookie_name, value_in)
        if TYPE_CHECKING:
            assert res.cookies is not None
        _decoded = _get_session_id_from_cookie(req, cookie_name, serializer)
        self.assertIn(cookie_name, res.cookies)
        self.assertEqual(res.cookies[cookie_name], value_encoded)
        self.assertEqual(value_decoded, _decoded)
        self.assertEqual(type(_decoded), str)

    def test_string(self):
        cookie_name = "test_string"
        cookie_value = "string"
        value_encoded = "string"
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


class Test_CookieSigner_StringSerializer(unittest.TestCase):
    """
    to generate data for tests::

       export GENERATE_COOKIE_DATA=1
    """

    def _makeOne(
        self,
        cookie_name: str,
        cookie_value: str,
    ) -> Tuple[_FakeRequest, _FakeResponse, SignedSerializer]:
        # webob docs `SignedSerializer`:
        # An object with two methods: `loads`` and ``dumps``.  The ``loads`` method
        # should accept bytes and return a Python object.  The ``dumps`` method
        # should accept a Python object and return bytes.

        # SignedSerializer(secret, salt, hashalg="sha512", serializer=None)
        cookie_signer = SignedSerializer(
            "secret",
            "pyramid_session_redis.",
            "sha512",
            serializer=_StringSerializer(),
        )
        if isinstance(cookie_value, str):
            _cookie_signed = cookie_signer.dumps(cookie_value)  # bytes
            _cookie_value = _cookie_signed.decode()  # set_cookie( wants str
        else:
            self.assertRaises(
                InvalidSessionId_Serialization, cookie_signer.dumps, cookie_value
            )
            raise _ExpectedFailure_Setup()

        req = _FakeRequest()
        res = _FakeResponse(req)
        res.set_cookie(cookie_name, _cookie_value)
        if GENERATE_COOKIE_DATA:
            print("--------")
            print("%s.%s" % (self.__class__.__name__, self._testMethodName))
            print("  name:  ", cookie_name)
            print("  value: ", cookie_value)
            print("  signed:", _cookie_value)
        return req, res, cookie_signer

    def _test_setup(
        self,
        cookie_name: str,
        value_in: Any,
        value_expected: Any,
        value_signed: str,
    ) -> None:
        req, res, cookie_signer = self._makeOne(cookie_name, value_in)
        if TYPE_CHECKING:
            assert res.cookies is not None
        self.assertIn(cookie_name, res.cookies)
        self.assertEqual(res.cookies[cookie_name], value_signed)
        value_out = _get_session_id_from_cookie(req, cookie_name, cookie_signer)
        self.assertEqual(value_expected, value_out)

    def test_string(self):
        cookie_name = "test_string"
        cookie_value = "string"
        value_expected = "string"
        value_signed = "JW5R1E8zj18d1HHYi1v0bXsBrGgEPSG0BKQ4U1CjLkNbFM4WlTz1XzQEebEOv4k9F8RGuT3V_TizoDdRwz52sHN0cmluZw"
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

    def _makeOne(
        self,
        cookie_name: str,
        cookie_value: str,
    ) -> Tuple[_FakeRequest, _FakeResponse, SignedSerializer]:
        # webob docs `SignedSerializer`:
        # An object with two methods: `loads`` and ``dumps``.  The ``loads`` method
        # should accept bytes and return a Python object.  The ``dumps`` method
        # should accept a Python object and return bytes.

        # SignedSerializer(secret, salt, hashalg="sha512", serializer=None)
        cookie_signer = SignedSerializer(
            "secret",
            "pyramid_session_redis.",
            "sha512",
        )
        if isinstance(cookie_value, bytes):
            self.assertRaises(TypeError, cookie_signer.dumps, cookie_value)
            raise _ExpectedFailure_Setup()
        else:
            _cookie_signed = cookie_signer.dumps(cookie_value)  # bytes
            _cookie_value = _cookie_signed.decode()  # .set_cookie wants str
        req = _FakeRequest()
        res = _FakeResponse(req)
        res.set_cookie(cookie_name, _cookie_value)
        if GENERATE_COOKIE_DATA:
            print("--------")
            print("%s.%s" % (self.__class__.__name__, self._testMethodName))
            print("  name:  ", cookie_name)
            print("  value: ", cookie_value)
            print("  signed:", _cookie_value)
        return req, res, cookie_signer

    def _test_setup(
        self,
        cookie_name: str,
        value_in: Any,
        value_expected: Any,
        value_signed: str,
    ) -> None:
        req, res, cookie_signer = self._makeOne(cookie_name, value_in)
        if TYPE_CHECKING:
            assert res.cookies is not None
        self.assertIn(cookie_name, res.cookies)
        self.assertEqual(res.cookies[cookie_name], value_signed)
        value_out = _get_session_id_from_cookie(req, cookie_name, cookie_signer)
        self.assertEqual(value_expected, value_out)

    def test_string(self):
        cookie_name = "test_string"
        cookie_value = "string"
        value_expected = "string"
        value_signed = "r3pVu9XGVFfz1MZQYdVT9kWVrb94mZT1TdL8HNYnFVf5cDcXPaL4ULuQ_GZ7hNAZNQCwfSRSGuffr6eQTgoHBSJzdHJpbmci"
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
        value_signed = "5aK2BseK-h0dYZa18Pxv8PVdLrKJwlmYNyh2Ck_-febyiABrjgFx1bNrwf128CL0I7Ulpw3f9FpOwlU7sMe5xDE"
        self._test_setup(cookie_name, cookie_value, value_expected, value_signed)


class Test_CookieSigner_Invalids(unittest.TestCase):
    """
    let's make sure we can handle completely invalid data correctly

    to generate the data for theses tests, just grab a signed value from elsewhere and change a character.
    below, we change the last character of a valid payload from 'i' to 'J'
    """

    def test_webob_default(self):
        # cookie_name = "test_string"
        # mess up a value from something else
        value_signed = b"r3pVu9XGVFfz1MZQYdVT9kWVrb94mZT1TdL8HNYnFVf5cDcXPaL4ULuQ_GZ7hNAZNQCwfSRSGuffr6eQTgoHBSJzdHJpbmcJ"

        # now, let's try to read it...
        # webob docs `SignedSerializer`:
        # An object with two methods: `loads`` and ``dumps``.  The ``loads`` method
        # should accept bytes and return a Python object.  The ``dumps`` method
        # should accept a Python object and return bytes.

        # SignedSerializer(secret, salt, hashalg="sha512", serializer=None)
        cookie_signer = SignedSerializer(
            "secret",
            "pyramid_session_redis.",
            "sha512",
        )
        with self.assertRaises(ValueError) as ctx:
            _cookie_value = cookie_signer.loads(value_signed)  # noqa: F841
        self.assertEqual(ctx.exception.args[0], "Invalid signature")

    def test_our_default(self):
        # cookie_name = "test_string"
        # mess up a value from something else
        value_signed = b"r3pVu9XGVFfz1MZQYdVT9kWVrb94mZT1TdL8HNYnFVf5cDcXPaL4ULuQ_GZ7hNAZNQCwfSRSGuffr6eQTgoHBSJzdHJpbmcJ"

        # now, let's try to read it...
        # webob docs `SignedSerializer`:
        # An object with two methods: `loads`` and ``dumps``.  The ``loads`` method
        # should accept bytes and return a Python object.  The ``dumps`` method
        # should accept a Python object and return bytes.

        # SignedSerializer(secret, salt, hashalg="sha512", serializer=None)
        cookie_signer = SignedSerializer(
            "secret",
            "pyramid_session_redis.",
            "sha512",
            serializer=_StringSerializer(),
        )
        with self.assertRaises(ValueError) as ctx:
            _cookie_value = cookie_signer.loads(value_signed)  # noqa: F841
        self.assertEqual(ctx.exception.args[0], "Invalid signature")

    def test_crafted_malicious_1(self):
        """
        WRITE w/json;
        READ w/str
        """
        # cookie_name = "test_int"
        cookie_value = {"a": False, "b": {"c": 1, "d": "e"}}

        # by default this will use a JSON serialization
        # webob docs `SignedSerializer`:
        # An object with two methods: `loads`` and ``dumps``.  The ``loads`` method
        # should accept bytes and return a Python object.  The ``dumps`` method
        # should accept a Python object and return bytes.

        # SignedSerializer(secret, salt, hashalg="sha512", serializer=None)
        cookie_signer_write = SignedSerializer(
            "secret",
            "pyramid_session_redis.",
            "sha512",
        )
        _cookie_value = cookie_signer_write.dumps(cookie_value)

        # decoding with the same signer should create an int
        decoded_native = cookie_signer_write.loads(_cookie_value)
        self.assertIsInstance(decoded_native, dict)

        self.assertEqual(cookie_value, decoded_native)

        # but this only handles strings...
        # webob docs `SignedSerializer`:
        # An object with two methods: `loads`` and ``dumps``.  The ``loads`` method
        # should accept bytes and return a Python object.  The ``dumps`` method
        # should accept a Python object and return bytes.

        # SignedSerializer(secret, salt, hashalg="sha512", serializer=None)
        cookie_signer_read = SignedSerializer(
            "secret",
            "pyramid_session_redis.",
            "sha512",
            serializer=_StringSerializer(),
        )

        # decoding with the alternate signer should force this as a string
        decoded_trans = cookie_signer_read.loads(_cookie_value)
        self.assertIsInstance(decoded_trans, str)
