# -*- coding: utf-8 -*-

# stdlib
from typing import Dict
from typing import Optional
from typing import TYPE_CHECKING
import unittest

# pypi
from pyramid import testing
from pyramid.request import Request
from pyramid.router import Router
import pyramid.scripting
from webtest import TestApp

# local
import pyramid_session_redis
from pyramid_session_redis.session import RedisSession
from ._util import is_cookie_setter
from ._util import is_cookie_unsetter
from ._util import LIVE_PSR_CONFIG
from .web_app import main

# ==============================================================================

INVALIDATE_CONFIG_TRUE = LIVE_PSR_CONFIG.copy()
INVALIDATE_CONFIG_TRUE.update({"redis.sessions.invalidate_empty_session": True})

INVALIDATE_CONFIG_FALSE = LIVE_PSR_CONFIG.copy()
INVALIDATE_CONFIG_FALSE.update({"redis.sessions.invalidate_empty_session": False})


class AppTest(unittest.TestCase):
    _testapp: Optional[TestApp] = None
    _pyramid_app: Router
    _settings: Dict = LIVE_PSR_CONFIG

    def assertCookieIsSetter(self, cookie: str) -> None:
        assert is_cookie_setter(cookie)

    def assertCookieIsUnsetter(self, cookie: str) -> None:
        assert is_cookie_unsetter(cookie)

    def setUp(self) -> None:
        self._pyramid_app = app = main(None, **self._settings)
        self._testapp = TestApp(app)

    def tearDown(self):
        testing.tearDown()


class Test_BasicSessionUsage(AppTest):

    def test_session_access__none(self):
        if TYPE_CHECKING:
            assert self._testapp is not None
        request = Request.blank("/session_access__none")
        with pyramid.scripting.prepare(
            registry=self._pyramid_app.registry,
            request=request,
        ) as env:
            assert request == env["request"]
            assert isinstance(request.session, RedisSession)
            assert not request.session.keys()  # request not invoked
            res = self._testapp.app.invoke_request(request)
            assert res.text == "<body><h1>session_access__none</h1></body>"
            assert "Set-Cookie" not in res.headers
            """
            request.response
            request.response.headers
            request.response.text
            """

    def test_session_access__set_and_unset(self):
        """
        Edge A-
            calling set and unset within a single request
            SHOULD NOT persist the empty session
        """
        if TYPE_CHECKING:
            assert self._testapp is not None
        request = Request.blank("/session_access__set_and_unset")
        with pyramid.scripting.prepare(
            registry=self._pyramid_app.registry,
            request=request,
        ) as env:
            assert request == env["request"]
            assert isinstance(request.session, RedisSession)
            assert not request.session.keys()  # request not invoked
            res = self._testapp.app.invoke_request(request)
            assert res.text == "<body><h1>session_access__set_and_unset</h1></body>"
            assert "Set-Cookie" not in res.headers


class _Test_InvalidateEmptySession(AppTest):

    def _test_session_access__set__then__unset(self, invalidates: bool) -> None:
        """
        Edge B
            calling:
            * set on request 1;
            * unset on request 2

            SHOULD persist the empty session if:
                v1.7 - default
                redis.sessions.invalidate_empty_session = False

            SHOULD delete the empty session if:
                v1.8 - default
                redis.sessions.invalidate_empty_session = True
        """
        if TYPE_CHECKING:
            assert self._testapp is not None
        session_id: str
        session_cookie: str
        request = Request.blank("/session_access__set")
        with pyramid.scripting.prepare(
            registry=self._pyramid_app.registry,
            request=request,
        ) as env:
            assert request == env["request"]
            assert isinstance(request.session, RedisSession)
            assert not request.session.keys()  # request not invoked
            res = self._testapp.app.invoke_request(request)
            assert res.text == "<body><h1>session_access__set</h1></body>"
            assert "Set-Cookie" in res.headers
            session_id = request.session.session_id  # noqa: F841
            session_cookie = res.headers["Set-Cookie"]
            # this will look like `session=X'; Path=/; HttpOnly"
            session_cookie = (session_cookie.split(";")[0]).strip()
        headers_in = {"Cookie": session_cookie}
        request2 = Request.blank("/session_access__unset", headers=headers_in)
        with pyramid.scripting.prepare(
            registry=self._pyramid_app.registry,
            request=request2,
        ) as env:
            assert request2 == env["request"]
            assert isinstance(request2.session, RedisSession)
            assert (
                "a" in request2.session.keys()
            )  # request not invoked, but we can load it
            res2 = self._testapp.app.invoke_request(request2)
            assert (
                "a" not in request2.session.keys()
            )  # request invoked, session cleared
            assert not request2.session.keys()  # request invoked, cleared in view
            assert res2.text == "<body><h1>session_access__unset</h1></body>"

            if invalidates:
                assert "Set-Cookie" in res2.headers
                self.assertCookieIsUnsetter(res2.headers["Set-Cookie"])
            else:
                assert "Set-Cookie" not in res2.headers


class Test_InvalidateEmptySession_Unconfigured(_Test_InvalidateEmptySession):

    def test_not_configured(self) -> None:
        # 1.7 = False
        # 1.8 = True
        assert pyramid_session_redis.INVALIDATE_EMPTY_SESSION is False
        self._test_session_access__set__then__unset(invalidates=False)


class Test_InvalidateEmptySession_True(_Test_InvalidateEmptySession):

    _settings = INVALIDATE_CONFIG_TRUE

    def test_configured_true(self) -> None:
        self._test_session_access__set__then__unset(invalidates=True)


class Test_InvalidateEmptySession_False(_Test_InvalidateEmptySession):

    _settings = INVALIDATE_CONFIG_FALSE

    def test_configured_false(self) -> None:
        self._test_session_access__set__then__unset(invalidates=False)
