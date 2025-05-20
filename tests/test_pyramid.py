# -*- coding: utf-8 -*-

# stdlib
from typing import Dict
from typing import Optional
import unittest

# pypi
from pyramid import testing
from pyramid.request import Request
from pyramid.router import Router
import pyramid.scripting
from webtest import TestApp

# from pyramid.paster import get_appsettings

# local
from .test_config import LIVE_PSR_CONFIG
from .web_app import main
from pyramid_session_redis.session import RedisSession

# ==============================================================================


class AppTest(unittest.TestCase):
    _testapp: Optional[TestApp] = None
    _pyramid_app: Router
    _settings: Dict = LIVE_PSR_CONFIG

    def setUp(self) -> None:
        self._pyramid_app = app = main(None, **self._settings)
        self._testapp = TestApp(app)

    def tearDown(self):
        testing.tearDown()

    def test_session_access__none(self):
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

    def test_session_access__set_unset(self):
        """
        Edge A-
            calling set and unset within a single request
            SHOULD NOT persist the empty session
        """
        request = Request.blank("/session_access__set_unset")
        with pyramid.scripting.prepare(
            registry=self._pyramid_app.registry,
            request=request,
        ) as env:
            assert request == env["request"]
            assert isinstance(request.session, RedisSession)
            assert not request.session.keys()  # request not invoked
            res = self._testapp.app.invoke_request(request)
            assert res.text == "<body><h1>session_access__set_unset</h1></body>"
            assert "Set-Cookie" not in res.headers

    def test_session_access__set(self):
        """
        Edge B
            calling:
            * set on request 1;
            * unset on request 2
            SHOULD persist the empty session
        """
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
            assert "Set-Cookie" in res.headers
