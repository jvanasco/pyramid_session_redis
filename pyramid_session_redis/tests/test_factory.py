# -*- coding: utf-8 -*-

import itertools
import unittest
import pprint

from pyramid import testing
from ..compat import cPickle
from ..util import encode_session_payload, int_time, LAZYCREATE_SESSION



class _TestRedisSessionFactoryCore(unittest.TestCase):

    def _makeOne(self, request, secret='secret', **kw):
        from .. import RedisSessionFactory
        session = RedisSessionFactory(secret, **kw)(request)
        return session

    def _makeOneSession(self, redis, session_id, **kw):
        from ..session import RedisSession
        session = RedisSession(
            redis=redis,
            session_id=session_id,
            **kw
        )
        return session

    def _register_callback(self, request, session):
        import functools
        from .. import _finished_callback
        finished_callback = functools.partial(
            _finished_callback,
            session
        )
        request.add_finished_callback(finished_callback)

    def _assert_is_a_header_to_set_cookie(self, header_value):
        # The negative assertion below is the least complicated option for
        # asserting that a Set-Cookie header sets a cookie rather than deletes
        # a cookie. This helper method is to help make that intention clearer
        # in the tests.
        self.assertNotIn('Max-Age=0', header_value)

    def _get_session_id(self, request):
        from ..compat import cPickle
        from ..util import create_unique_session_id
        redis = request.registry._redis_sessions
        session_id = create_unique_session_id(redis, timeout=100,
                                              serialize=cPickle.dumps)
        return session_id

    def _serialize(self, session_id, secret='secret'):
        from pyramid.session import signed_serialize
        return signed_serialize(session_id, secret)

    def _set_session_cookie(self, request, session_id, cookie_name='session',
                            secret='secret'):
        cookieval = self._serialize(session_id, secret=secret)
        request.cookies[cookie_name] = cookieval

    def _make_request(self):
        from . import DummyRedis
        request = testing.DummyRequest()
        request.registry._redis_sessions = DummyRedis()
        request.exception = None
        return request


class TestRedisSessionFactory(_TestRedisSessionFactoryCore):

    def test_ctor_no_cookie(self):
        """
        # original test
        request = self._make_request()
        session = self._makeOne(request)
        session_dict = session.from_redis()['m']
        self.assertDictEqual(session_dict, {})
        self.assertIs(session.new, True)
        
        # calling from_redis should not happen in 1.4.x+
        """
        request = self._make_request()
        session = self._makeOne(request)
        session_dict = session.managed_dict
        self.assertDictEqual(session_dict, {})
        self.assertIs(session.new, True)

    def test_ctor_with_cookie_still_valid(self):
        request = self._make_request()
        session_id_in_cookie = self._get_session_id(request)
        self._set_session_cookie(request=request,
                                 session_id=session_id_in_cookie)
        session = self._makeOne(request)
        self.assertEqual(session.session_id, session_id_in_cookie)
        self.assertIs(session.new, False)

    def test_ctor_with_bad_cookie(self):
        request = self._make_request()
        session_id_in_cookie = self._get_session_id(request)
        invalid_secret = 'aaaaaa'
        self._set_session_cookie(request=request,
                                 session_id=session_id_in_cookie,
                                 secret=invalid_secret)
        session = self._makeOne(request)
        self.assertNotEqual(session.session_id, session_id_in_cookie)
        self.assertIs(session.new, True)

    def test_session_id_not_in_redis(self):
        request = self._make_request()
        session_id_in_cookie = self._get_session_id(request)
        self._set_session_cookie(request=request,
                                 session_id=session_id_in_cookie)
        redis = request.registry._redis_sessions
        redis.store = {}  # clears keys in DummyRedis
        session = self._makeOne(request)
        self.assertNotEqual(session.session_id, session_id_in_cookie)
        self.assertIs(session.new, True)

    def test_factory_parameters_used_to_set_cookie(self):
        import re
        import webob
        cookie_name = 'testcookie'
        cookie_max_age = 300
        cookie_path = '/path'
        cookie_domain = 'example.com'
        cookie_secure = True
        cookie_httponly = False
        secret = 'test secret'

        request = self._make_request()
        session = request.session = self._makeOne(
            request,
            cookie_name=cookie_name,
            cookie_max_age=cookie_max_age,
            cookie_path=cookie_path,
            cookie_domain=cookie_domain,
            cookie_secure=cookie_secure,
            cookie_httponly=cookie_httponly,
            secret=secret,
        )
        session['key'] = 'value'
        response = webob.Response()
        request.response_callbacks[0](request, response)
        set_cookie_headers = response.headers.getall('Set-Cookie')
        self.assertEqual(len(set_cookie_headers), 1)

        # Make another response and .set_cookie() using the same values and
        # settings to get the expected header to compare against

        # note - webob 1.7 no longer supports name+value kwargs
        response_to_check_against = webob.Response()
        response_to_check_against.set_cookie(
            cookie_name,
            self._serialize(session_id=request.session.session_id,
                            secret=secret),
            max_age=cookie_max_age,
            path=cookie_path,
            domain=cookie_domain,
            secure=cookie_secure,
            httponly=cookie_httponly,
        )
        expected_header = response_to_check_against.headers.getall(
            'Set-Cookie')[0]
        remove_expires_attribute = lambda s: re.sub('Expires ?=[^;]*;', '', s,
                                                    flags=re.IGNORECASE)
        self.assertEqual(remove_expires_attribute(set_cookie_headers[0]),
                         remove_expires_attribute(expected_header))
        # We have to remove the Expires attributes from each header before the
        # assert comparison, as we cannot rely on their values to be the same
        # (one is generated after the other, and may have a slightly later
        # Expires time). The Expires value does not matter to us as it is
        # calculated from Max-Age.

    def test_factory_parameters_used_to_delete_cookie(self):
        import webob
        cookie_name = 'testcookie'
        cookie_path = '/path'
        cookie_domain = 'example.com'

        request = self._make_request()
        self._set_session_cookie(request=request,
                                 cookie_name=cookie_name,
                                 session_id=self._get_session_id(request))
        session = request.session = self._makeOne(
            request,
            cookie_name=cookie_name,
            cookie_path=cookie_path,
            cookie_domain=cookie_domain,
        )
        session.invalidate()
        response = webob.Response()
        request.response_callbacks[0](request, response)
        set_cookie_headers = response.headers.getall('Set-Cookie')
        self.assertEqual(len(set_cookie_headers), 1)

        # Make another response and .delete_cookie() using the same values and
        # settings to get the expected header to compare against
        response_to_check_against = webob.Response()
        response_to_check_against.delete_cookie(
            cookie_name,
            path=cookie_path,
            domain=cookie_domain,
        )
        expected_header = response.headers.getall('Set-Cookie')[0]
        self.assertEqual(set_cookie_headers[0], expected_header)

    # The tests below with names beginning with test_new_session_ test cases
    # where first access to request.session creates a new session, as in
    # test_ctor_no_cookie, test_ctor_with_bad_cookie and
    # test_session_id_not_in_redis.

    def test_new_session_cookie_on_exception_true_no_exception(self):
        # cookie_on_exception is True by default, no exception raised
        import webob
        request = self._make_request()
        request.session = self._makeOne(request)
        request.session['a'] = 1  # ensure a lazycreate is triggered
        response = webob.Response()
        request.response_callbacks[0](request, response)
        set_cookie_headers = response.headers.getall('Set-Cookie')
        self.assertEqual(len(set_cookie_headers), 1)
        self._assert_is_a_header_to_set_cookie(set_cookie_headers[0])

    def test_new_session_cookie_on_exception_true_exception(self):
        # cookie_on_exception is True by default, exception raised
        import webob
        request = self._make_request()
        request.session = self._makeOne(request)
        request.session['a'] = 1  # ensure a lazycreate is triggered
        request.exception = Exception()
        response = webob.Response()
        request.response_callbacks[0](request, response)
        set_cookie_headers = response.headers.getall('Set-Cookie')
        self.assertEqual(len(set_cookie_headers), 1)
        self._assert_is_a_header_to_set_cookie(set_cookie_headers[0])

    def test_new_session_cookie_on_exception_false_no_exception(self):
        # cookie_on_exception is False, no exception raised
        import webob
        request = self._make_request()
        request.session = self._makeOne(request, cookie_on_exception=False)
        request.session['a'] = 1  # ensure a lazycreate is triggered
        response = webob.Response()
        request.response_callbacks[0](request, response)
        set_cookie_headers = response.headers.getall('Set-Cookie')
        self.assertEqual(len(set_cookie_headers), 1)
        self._assert_is_a_header_to_set_cookie(set_cookie_headers[0])

    def test_new_session_cookie_on_exception_false_exception(self):
        # cookie_on_exception is False, exception raised
        import webob
        request = self._make_request()
        request.session = self._makeOne(request, cookie_on_exception=False)
        request.session['a'] = 1  # ensure a lazycreate is triggered
        request.exception = Exception()
        response = webob.Response()
        request.response_callbacks[0](request, response)
        self.assertNotIn('Set-Cookie', response.headers)

    def test_new_session_invalidate(self):
        # new session -> invalidate()
        import webob
        request = self._make_request()
        request.session = self._makeOne(request)
        request.session['a'] = 1  # ensure a lazycreate is triggered
        request.session.invalidate()
        response = webob.Response()
        request.response_callbacks[0](request, response)
        self.assertNotIn('Set-Cookie', response.headers)

    def test_new_session_session_after_invalidate_coe_True_no_exception(self):
        # new session -> invalidate() -> new session
        # cookie_on_exception is True by default, no exception raised
        import webob
        request = self._make_request()
        session = request.session = self._makeOne(request)
        session['a'] = 1  # ensure a lazycreate is triggered
        session.invalidate()
        session['key'] = 'value'
        response = webob.Response()
        request.response_callbacks[0](request, response)
        set_cookie_headers = response.headers.getall('Set-Cookie')
        self.assertEqual(len(set_cookie_headers), 1)
        self._assert_is_a_header_to_set_cookie(set_cookie_headers[0])

    def test_new_session_session_after_invalidate_coe_True_exception(self):
        # new session -> invalidate() -> new session
        # cookie_on_exception is True by default, exception raised
        import webob
        request = self._make_request()
        session = request.session = self._makeOne(request)
        session['a'] = 1  # ensure a lazycreate is triggered
        session.invalidate()
        session['key'] = 'value'
        request.exception = Exception()
        response = webob.Response()
        request.response_callbacks[0](request, response)
        set_cookie_headers = response.headers.getall('Set-Cookie')
        self.assertEqual(len(set_cookie_headers), 1)
        self._assert_is_a_header_to_set_cookie(set_cookie_headers[0])

    def test_new_session_session_after_invalidate_coe_False_no_exception(self):
        # new session -> invalidate() -> new session
        # cookie_on_exception is False, no exception raised
        import webob
        request = self._make_request()
        session = request.session = self._makeOne(request,
                                                  cookie_on_exception=False)
        session.invalidate()
        session['key'] = 'value'
        response = webob.Response()
        request.response_callbacks[0](request, response)
        set_cookie_headers = response.headers.getall('Set-Cookie')
        self.assertEqual(len(set_cookie_headers), 1)
        self._assert_is_a_header_to_set_cookie(set_cookie_headers[0])

    def test_new_session_session_after_invalidate_coe_False_exception(self):
        # new session -> invalidate() -> new session
        # cookie_on_exception is False, exception raised
        import webob
        request = self._make_request()
        session = request.session = self._makeOne(request,
                                                  cookie_on_exception=False)
        session.invalidate()
        session['key'] = 'value'
        request.exception = Exception()
        response = webob.Response()
        request.response_callbacks[0](request, response)
        self.assertNotIn('Set-Cookie', response.headers)

    def test_new_session_multiple_invalidates(self):
        # new session -> invalidate() -> new session -> invalidate()
        # Invalidate more than once, no new session after last invalidate()
        import webob
        request = self._make_request()
        session = request.session = self._makeOne(request)
        session['a'] = 1  # ensure a lazycreate is triggered
        session.invalidate()
        session['key'] = 'value'
        session.invalidate()
        response = webob.Response()
        request.response_callbacks[0](request, response)
        self.assertNotIn('Set-Cookie', response.headers)

    def test_new_session_multiple_invalidates_with_no_new_session_in_between(
        self
    ):
        # new session -> invalidate() -> invalidate()
        # Invalidate more than once, no new session in between invalidate()s,
        # no new session after last invalidate()
        import webob
        request = self._make_request()
        session = request.session = self._makeOne(request)
        session['a'] = 1  # ensure a lazycreate is triggered
        session.invalidate()
        session.invalidate()
        response = webob.Response()
        request.response_callbacks[0](request, response)
        self.assertNotIn('Set-Cookie', response.headers)

    def test_new_session_int_time(self):
        # new request
        request = self._make_request()

        # default behavior: we use int
        session = request.session = self._makeOne(request)
        session['a'] = 1  # ensure a lazycreate is triggered
        self.assertEquals(session.created, int(session.created))

    # The tests below with names beginning with test_existing_session_ test
    # cases where first access to request.session returns an existing session,
    # as in test_ctor_with_cookie_still_valid.

    def test_existing_session(self):
        import webob
        request = self._make_request()
        self._set_session_cookie(
            request=request,
            session_id=self._get_session_id(request),
        )
        request.session = self._makeOne(request)
        response = webob.Response()
        request.response_callbacks[0](request, response)
        self.assertNotIn('Set-Cookie', response.headers)

    def test_existing_session_invalidate(self):
        # existing session -> invalidate()
        import webob
        request = self._make_request()
        self._set_session_cookie(request=request,
                                 session_id=self._get_session_id(request))
        request.session = self._makeOne(request)
        request.session.invalidate()
        response = webob.Response()
        request.response_callbacks[0](request, response)
        set_cookie_headers = response.headers.getall('Set-Cookie')
        self.assertEqual(len(set_cookie_headers), 1)
        self.assertIn('Max-Age=0', set_cookie_headers[0])

    def test_existing_session_invalidate_nodupe(self):
        """
        This tests against an edge-case caused when a session is invalidated,
        but no new session interaction takes place. in this situation, the
        callback function introduced by `pyramid_session_redis` can create an
        unwanted placeholder value in redis.

        python -m unittest pyramid_session_redis.tests.test_factory.TestRedisSessionFactory.test_existing_session_invalidate_nodupe
        """
        # existing session -> invalidate()
        import webob
        request = self._make_request()
        session_id = self._get_session_id(request)
        self._set_session_cookie(request=request,
                                 session_id=session_id)
        request.session = self._makeOne(request)
        self._register_callback(request, request.session)
        persisted = request.session.redis.get(session_id)
        self.assertIsNotNone(persisted)

        # invalidate
        request.session.invalidate()
        response = webob.Response()
        request.response_callbacks[0](request, response)
        set_cookie_headers = response.headers.getall('Set-Cookie')
        self.assertEqual(len(set_cookie_headers), 1)
        self.assertIn('Max-Age=0', set_cookie_headers[0])

        # manually execute the callbacks
        request._process_finished_callbacks()

        # make sure this isn't in redis
        persisted = request.session.redis.get(session_id)
        self.assertIsNone(persisted)

        # make sure we don't have any keys in redis
        keys = request.session.redis.keys()
        self.assertEqual(len(keys), 0)

    def test_existing_session_session_after_invalidate_coe_True_no_exception(
        self
    ):
        # existing session -> invalidate() -> new session
        # cookie_on_exception is True by default, no exception raised
        import webob
        request = self._make_request()
        self._set_session_cookie(request=request,
                                 session_id=self._get_session_id(request))
        session = request.session = self._makeOne(request)
        session.invalidate()
        session['key'] = 'value'
        response = webob.Response()
        request.response_callbacks[0](request, response)
        set_cookie_headers = response.headers.getall('Set-Cookie')
        self.assertEqual(len(set_cookie_headers), 1)
        self._assert_is_a_header_to_set_cookie(set_cookie_headers[0])

    def test_existing_session_session_after_invalidate_coe_True_exception(
        self
    ):
        # existing session -> invalidate() -> new session
        # cookie_on_exception is True by default, exception raised
        import webob
        request = self._make_request()
        self._set_session_cookie(request=request,
                                 session_id=self._get_session_id(request))
        session = request.session = self._makeOne(request)
        session.invalidate()
        session['key'] = 'value'
        request.exception = Exception()
        response = webob.Response()
        request.response_callbacks[0](request, response)
        set_cookie_headers = response.headers.getall('Set-Cookie')
        self.assertEqual(len(set_cookie_headers), 1)
        self._assert_is_a_header_to_set_cookie(set_cookie_headers[0])

    def test_existing_session_session_after_invalidate_coe_False_no_exception(
        self
    ):
        # existing session -> invalidate() -> new session
        # cookie_on_exception is False, no exception raised
        import webob
        request = self._make_request()
        self._set_session_cookie(request=request,
                                 session_id=self._get_session_id(request))
        session = request.session = self._makeOne(request,
                                                  cookie_on_exception=False)
        session.invalidate()
        session['key'] = 'value'
        response = webob.Response()
        request.response_callbacks[0](request, response)
        set_cookie_headers = response.headers.getall('Set-Cookie')
        self.assertEqual(len(set_cookie_headers), 1)
        self._assert_is_a_header_to_set_cookie(set_cookie_headers[0])

    def test_existing_session_session_after_invalidate_coe_False_exception(
        self
    ):
        # existing session -> invalidate() -> new session
        # cookie_on_exception is False, exception raised
        import webob
        request = self._make_request()
        self._set_session_cookie(request=request,
                                 session_id=self._get_session_id(request))
        session = request.session = self._makeOne(request,
                                                  cookie_on_exception=False)
        session.invalidate()
        session['key'] = 'value'
        request.exception = Exception()
        response = webob.Response()
        request.response_callbacks[0](request, response)
        set_cookie_headers = response.headers.getall('Set-Cookie')
        self.assertEqual(len(set_cookie_headers), 1)
        self.assertIn('Max-Age=0', set_cookie_headers[0])
        # Cancel setting of cookie for new session, but still delete cookie for
        # the earlier invalidate().

    def test_existing_session_multiple_invalidates(self):
        # existing session -> invalidate() -> new session -> invalidate()
        # Invalidate more than once, no new session after last invalidate()
        import webob
        request = self._make_request()
        self._set_session_cookie(request=request,
                                 session_id=self._get_session_id(request))
        session = request.session = self._makeOne(request)
        session.invalidate()
        session['key'] = 'value'
        session.invalidate()
        response = webob.Response()
        request.response_callbacks[0](request, response)
        set_cookie_headers = response.headers.getall('Set-Cookie')
        self.assertEqual(len(set_cookie_headers), 1)
        self.assertIn('Max-Age=0', set_cookie_headers[0])

    def test_existing_session_multiple_invalidates_no_new_session_in_between(
        self
    ):
        # existing session -> invalidate() -> invalidate()
        # Invalidate more than once, no new session in between invalidate()s,
        # no new session after last invalidate()
        import webob
        request = self._make_request()
        self._set_session_cookie(request=request,
                                 session_id=self._get_session_id(request))
        session = request.session = self._makeOne(request)
        session.invalidate()
        session.invalidate()
        response = webob.Response()
        request.response_callbacks[0](request, response)
        set_cookie_headers = response.headers.getall('Set-Cookie')
        self.assertEqual(len(set_cookie_headers), 1)
        self.assertIn('Max-Age=0', set_cookie_headers[0])

    def test_instance_conforms(self):
        from pyramid.interfaces import ISession
        from zope.interface.verify import verifyObject
        request = self._make_request()
        inst = self._makeOne(request)
        verifyObject(ISession, inst)

    def test_adjusted_session_timeout_persists(self):
        request = self._make_request()
        inst = self._makeOne(request)
        inst.adjust_timeout_for_session(555)
        inst.do_persist()
        session_id = inst.session_id
        cookieval = self._serialize(session_id)
        request.cookies['session'] = cookieval
        new_session = self._makeOne(request)
        self.assertEqual(new_session.timeout, 555)

    def test_client_callable(self):
        from . import DummyRedis
        request = self._make_request()
        redis = DummyRedis()
        client_callable = lambda req, **kw: redis
        inst = self._makeOne(request, client_callable=client_callable)
        self.assertEqual(inst.redis, redis)

    def test_session_factory_from_settings(self):
        from .. import session_factory_from_settings
        request = self._make_request()
        settings = {'redis.sessions.secret': 'secret',
                    'redis.sessions.timeout': '999'}
        inst = session_factory_from_settings(settings)(request)
        self.assertEqual(inst.timeout, 999)

    def test_session_factory_from_settings_no_timeout(self):
        from .. import session_factory_from_settings
        """settings should allow `None` and `0`; both becoming `None`"""
        request_none = self._make_request()
        settings_none = {'redis.sessions.secret': 'secret',
                         'redis.sessions.timeout': 'None'}
        inst_none = session_factory_from_settings(settings_none)(request_none)
        self.assertEqual(inst_none.timeout, None)

        request_0 = self._make_request()
        settings_0 = {'redis.sessions.secret': 'secret',
                      'redis.sessions.timeout': '0'}
        inst_0 = session_factory_from_settings(settings_0)(request_0)
        self.assertEqual(inst_0.timeout, None)

    def test_check_response(self):
        from .. import check_response_allow_cookies
        from .. import RedisSessionFactory
        import webob

        factory = RedisSessionFactory(
            'secret',
            func_check_response_allow_cookies=check_response_allow_cookies,
        )

        # first check we can create a cookie
        request = self._make_request()
        session = factory(request)
        session['a'] = 1  # we only create a cookie on edit
        response = webob.Response()
        request.response_callbacks[0](request, response)
        hdrs_sc = response.headers.getall('Set-Cookie')
        self.assertEqual(len(hdrs_sc), 1)
        self.assertEqual(response.vary, ('Cookie', ))

        # then check we can't set a cookie
        for hdr_exclude in ('expires', 'cache-control'):
            request = self._make_request()
            session = factory(request)
            session['a'] = 1  # we only create a cookie on edit
            response = webob.Response()
            response.headers.add(hdr_exclude, '1')
            request.response_callbacks[0](request, response)
            hdrs_sc = response.headers.getall('Set-Cookie')
            self.assertEqual(len(hdrs_sc), 0)
            self.assertEqual(response.vary, None)

        # just to be safe
        for hdr_dontcare in ('foo', 'bar', ):
            request = self._make_request()
            session = factory(request)
            session['a'] = 1  # we only create a cookie on edit
            response = webob.Response()
            response.headers.add(hdr_dontcare, '1')
            request.response_callbacks[0](request, response)
            hdrs_sc = response.headers.getall('Set-Cookie')
            self.assertEqual(len(hdrs_sc), 1)
            self.assertEqual(response.vary, ('Cookie', ))

    def test_check_response_custom(self):
        from .. import RedisSessionFactory
        import webob

        def check_response_allow_cookies(response):
            """
            private response
            """
            # The view signals this is cacheable response
            # and we should not stamp a session cookie on it
            cookieless_headers = ["foo", ]
            for header in cookieless_headers:
                if header in response.headers:
                    return False
            return True

        factory = RedisSessionFactory(
            'secret',
            func_check_response_allow_cookies=check_response_allow_cookies,
        )

        # first check we can create a cookie
        request = self._make_request()
        session = factory(request)
        session['a'] = 1  # we only create a cookie on edit
        response = webob.Response()
        request.response_callbacks[0](request, response)
        hdrs_sc = response.headers.getall('Set-Cookie')
        self.assertEqual(len(hdrs_sc), 1)
        self.assertEqual(response.vary, ('Cookie', ))

        # then check we can't set a cookie
        for hdr_exclude in ('foo', ):
            request = self._make_request()
            session = factory(request)
            session['a'] = 1  # we only create a cookie on edit
            response = webob.Response()
            response.headers.add(hdr_exclude, '1')
            request.response_callbacks[0](request, response)
            hdrs_sc = response.headers.getall('Set-Cookie')
            self.assertEqual(len(hdrs_sc), 0)
            self.assertEqual(response.vary, None)

        # just to be safe
        for hdr_dontcare in ('bar', ):
            request = self._make_request()
            session = factory(request)
            session['a'] = 1  # we only create a cookie on edit
            response = webob.Response()
            response.headers.add(hdr_dontcare, '1')
            request.response_callbacks[0](request, response)
            hdrs_sc = response.headers.getall('Set-Cookie')
            self.assertEqual(len(hdrs_sc), 1)
            self.assertEqual(response.vary, ('Cookie', ))


class TestRedisSessionFactory_expiries_v1_4_x(_TestRedisSessionFactoryCore):

    # args are used 2x: for NEW and EXISTING session tests

    _args_timeout_trigger_pythonExpires_setRedisTtl = {'timeout': 1200,
                                                       'timeout_trigger': 600,
                                                       'python_expires': True,
                                                       'set_redis_ttl': True,
                                                       }

    _args_timeout_trigger_noPythonExpires_setRedisTtl = {'timeout': 1200,
                                                         'timeout_trigger': 600,
                                                         'python_expires': False,
                                                         'set_redis_ttl': True,
                                                         }

    _args_timeout_noTrigger_pythonExpires_setRedisTtl = {'timeout': 1200,
                                                         'timeout_trigger': None,
                                                         'python_expires': True,
                                                         'set_redis_ttl': True,
                                                          }

    _args_timeout_noTrigger_noPythonExpires_setRedisTtl = {'timeout': 1200,
                                                           'timeout_trigger': None,
                                                           'python_expires': False,
                                                           'set_redis_ttl': True,
                                                           }

    _args_noTimeout_trigger_pythonExpires_setRedisTtl = {'timeout': None,
                                                         'timeout_trigger': 600,
                                                         'python_expires': True,
                                                         'set_redis_ttl': True,
                                                         }

    _args_noTimeout_trigger_noPythonExpires_setRedisTtl = {'timeout': None,
                                                           'timeout_trigger': 600,
                                                           'python_expires': False,
                                                           'set_redis_ttl': True,
                                                           }

    _args_noTimeout_noTrigger_pythonExpires_setRedisTtl = {'timeout': None,
                                                           'timeout_trigger': None,
                                                           'python_expires': True,
                                                           'set_redis_ttl': True,
                                                           }

    _args_noTimeout_noTrigger_noPythonExpires_setRedisTtl = {'timeout': None,
                                                             'timeout_trigger': None,
                                                             'python_expires': False,
                                                             'set_redis_ttl': True,
                                                             }

    _args_timeout_trigger_pythonExpires_noRedisTtl = {'timeout': 1200,
                                                      'timeout_trigger': 600,
                                                      'python_expires': True,
                                                      'set_redis_ttl': False,
                                                      }

    _args_timeout_trigger_noPythonExpires_noRedisTtl = {'timeout': 1200,
                                                        'timeout_trigger': 600,
                                                        'python_expires': False,
                                                        'set_redis_ttl': False,
                                                        }

    _args_timeout_noTrigger_pythonExpires_noRedisTtl = {'timeout': 1200,
                                                        'timeout_trigger': None,
                                                        'python_expires': True,
                                                        'set_redis_ttl': False,
                                                         }

    _args_timeout_noTrigger_noPythonExpires_noRedisTtl = {'timeout': 1200,
                                                          'timeout_trigger': None,
                                                          'python_expires': False,
                                                          'set_redis_ttl': False,
                                                          }

    _args_noTimeout_trigger_pythonExpires_noRedisTtl = {'timeout': None,
                                                        'timeout_trigger': 600,
                                                        'python_expires': True,
                                                        'set_redis_ttl': False,
                                                        }

    _args_noTimeout_trigger_noPythonExpires_noRedisTtl = {'timeout': None,
                                                          'timeout_trigger': 600,
                                                          'python_expires': False,
                                                          'set_redis_ttl': False,
                                                          }

    _args_noTimeout_noTrigger_pythonExpires_noRedisTtl = {'timeout': None,
                                                          'timeout_trigger': None,
                                                          'python_expires': True,
                                                          'set_redis_ttl': False,
                                                          }

    _args_noTimeout_noTrigger_noPythonExpires_noRedisTtl = {'timeout': None,
                                                            'timeout_trigger': None,
                                                            'python_expires': False,
                                                            'set_redis_ttl': False,
                                                            }

    def _deserialize_session_stored(self, session, deserialize=cPickle.loads):
        """loads session from backend via id, deserializes"""
        _session_id = session.session_id
        _session_data = session.redis.store[_session_id]
        _session_deserialized = deserialize(_session_data)
        return _session_deserialized

    def _set_up_session_in_redis(self, redis, session_id,
                                 session_dict=None, timeout=None,
                                 timeout_trigger=None,
                                 serialize=cPickle.dumps,
                                 python_expires=None,
                                 set_redis_ttl=None,
                                 ):
        if timeout_trigger and not python_expires:  # fix this
            python_expires = True
        if session_dict is None:
            session_dict = {}
        time_now = int_time()
        expires = time_now + timeout if timeout else None
        payload = encode_session_payload(session_dict,
                                         time_now,
                                         timeout,
                                         expires,
                                         timeout_trigger=timeout_trigger,
                                         python_expires=python_expires,
                                         )
        if set_redis_ttl:
            redis.setex(session_id,
                        timeout,
                        serialize(payload),
                        )
        else:
            redis.set(session_id,
                      serialize(payload)
                      )
        return session_id

    def _set_up_session_in_Redis_and_makeOne(self, request, session_id,
                                             session_dict=None, new=True,
                                             timeout=300, timeout_trigger=150,
                                             python_expires=None,
                                             set_redis_ttl=None):
        redis = request.registry._redis_sessions
        self._set_up_session_in_redis(redis=redis, session_id=session_id,
                                      session_dict=session_dict,
                                      timeout=timeout,
                                      timeout_trigger=timeout_trigger,
                                      python_expires=python_expires,
                                      set_redis_ttl=set_redis_ttl,
                                      )
        new_session = lambda: self._set_up_session_in_redis(
            redis=redis,
            session_id=id_generator(),
            session_dict=session_dict,
            timeout=timeout,
            timeout_trigger=timeout_trigger,
            python_expires=python_expires,
            set_redis_ttl=set_redis_ttl,
        )
        return self._makeOneSession(
            redis,
            session_id,
            new=new,
            new_session=new_session,
            timeout=timeout,
            timeout_trigger=timeout_trigger,
            python_expires=python_expires,
            set_redis_ttl=set_redis_ttl,
        )

    def _prep_new_session(self, session_args):
        import webob
        request = self._make_request()

        request.session = self._makeOne(request, **session_args)
        request.session['a'] = 1  # ensure a lazycreate is triggered
        response = webob.Response()
        request.response_callbacks[0](request, response)  # sets the cookie
        set_cookie_headers = response.headers.getall('Set-Cookie')
        request.finished_callbacks[0](request)  # runs the persist
        self.assertEqual(len(set_cookie_headers), 1)
        self._assert_is_a_header_to_set_cookie(set_cookie_headers[0])
        # stored_session_data = self._deserialize_session_stored(request.session)
        return request

    def _prep_existing_session(self, session_args):
        import webob
        session_id = 'existing_session'

        request1 = self._make_request()
        # drop a session into our redis
        session_existing = self._set_up_session_in_Redis_and_makeOne(
            request1, 
            session_id,
            session_dict = {'key': 'value'},
            **session_args
        )

        # grab the registry data to persist, otherwise it gets discarded
        _redis_sessions = request1.registry._redis_sessions

        request = self._make_request()
        request.registry._redis_sessions = _redis_sessions

        self._set_session_cookie(
            request=request,
            session_id=session_id,
        )

        request.session = self._makeOne(request, **session_args)
        response = webob.Response()
        request.response_callbacks[0](request, response)
        request.finished_callbacks[0](request)  # runs any persist if needed
        self.assertNotIn('Set-Cookie', response.headers)
        # stored_session_data = self._deserialize_session_stored(request.session)
        return request
    
    def _adjust_request_session(self, request, serialize=cPickle.dumps, **kwargs):
        _session_deserialized = self._deserialize_session_stored(request.session)

        if 'created' in kwargs:
            created = kwargs.pop('created', 0)
            _session_deserialized['c'] += created
        if 'expires' in kwargs:
            expires = kwargs.pop('expires', 0)
            _session_deserialized['x'] += expires
        _session_deserialized['t'] += 1
        _session_deserialized['m']['foo'] = 'bar'
        _session_id = request.session.session_id
        _session_serialized = serialize(_session_deserialized)
        request.session.redis.store[_session_id] = _session_serialized
        
        _redis_sessions = request.registry._redis_sessions
        request2 = self._make_request()
        request2.registry._redis_sessions = _redis_sessions
        self._set_session_cookie(
            request=request2,
            session_id=_session_id,
        )
        request2.session = self._makeOne(request2, **kwargs)
        import webob
        response = webob.Response()
        request2.response_callbacks[0](request2, response)
        request2.finished_callbacks[0](request2)  # runs any persist if needed

        _session_deserialized2 = self._deserialize_session_stored(request2.session)

        return request2

    # --------------------------------------------------------------------------
    # new session - timeout
    # --------------------------------------------------------------------------

    def test_scenario_new__timeout_trigger_pythonExpires_setRedisTtl(self):
        session_args = self._args_timeout_trigger_pythonExpires_setRedisTtl
        request = self._prep_new_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertIn('x', stored_session_data)
        self.assertEqual(stored_session_data['x'], stored_session_data['c'] + stored_session_data['t'])

        # there should be two items in the history:
        # 0 = a pipeline.SETEX for the initial creation
        # 1 = a SETEX for the persist
        self.assertEqual(len(request.registry._redis_sessions._history), 2)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'pipeline.setex')
        self.assertEqual(request.registry._redis_sessions._history[0][2], session_args['timeout'])
        self.assertEqual(request.registry._redis_sessions._history[1][0], 'setex')
        self.assertEqual(request.registry._redis_sessions._history[1][2], session_args['timeout'])
        
    def test_scenario_new__timeout_trigger_pythonNoExpires_setRedisTtl(self):
        # note: timeout-trigger will force python_expires
        session_args = self._args_timeout_trigger_noPythonExpires_setRedisTtl
        request = self._prep_new_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertIn('x', stored_session_data)
        self.assertEqual(stored_session_data['x'], stored_session_data['c'] + stored_session_data['t'])

        # there should be two items in the history:
        # 0 = a pipeline.SETEX for the initial creation
        # 1 = a SETEX for the persist
        self.assertEqual(len(request.registry._redis_sessions._history), 2)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'pipeline.setex')
        self.assertEqual(request.registry._redis_sessions._history[0][2], session_args['timeout'])
        self.assertEqual(request.registry._redis_sessions._history[1][0], 'setex')
        self.assertEqual(request.registry._redis_sessions._history[1][2], session_args['timeout'])

    def test_scenario_new__timeout_noTrigger_pythonExpires_setRedisTtl(self):
        session_args = self._args_timeout_noTrigger_pythonExpires_setRedisTtl
        request = self._prep_new_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertIn('x', stored_session_data)
        self.assertEqual(stored_session_data['x'], stored_session_data['c'] + stored_session_data['t'])

        # there should be two items in the history:
        # 0 = a pipeline.SETEX for the initial creation
        # 1 = a SETEX for the persist
        self.assertEqual(len(request.registry._redis_sessions._history), 2)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'pipeline.setex')
        self.assertEqual(request.registry._redis_sessions._history[0][2], session_args['timeout'])
        self.assertEqual(request.registry._redis_sessions._history[1][0], 'setex')
        self.assertEqual(request.registry._redis_sessions._history[1][2], session_args['timeout'])
        
    def test_scenario_new__timeout_noTrigger_noPythonExpires_setRedisTtl(self):
        """
        a timeout entirely occurs via EXPIRY in redis
        """
        session_args = self._args_timeout_noTrigger_noPythonExpires_setRedisTtl
        request = self._prep_new_session(session_args)

        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertNotIn('x', stored_session_data)

        # there should be two items in the history:
        # 0 = a pipeline.SETEX for the initial creation
        # 1 = a SETEX for the persist
        self.assertEqual(len(request.registry._redis_sessions._history), 2)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'pipeline.setex')
        self.assertEqual(request.registry._redis_sessions._history[0][2], session_args['timeout'])
        self.assertEqual(request.registry._redis_sessions._history[1][0], 'setex')
        self.assertEqual(request.registry._redis_sessions._history[1][2], session_args['timeout'])

    # --------------------------------------------------------------------------
    # new session - no timeout
    # --------------------------------------------------------------------------

    def test_scenario_new__noTimeout_trigger_pythonExpires_setRedisTtl(self):
        """the ``timeout_trigger`` is irrelevant"""
        session_args = self._args_noTimeout_trigger_pythonExpires_setRedisTtl
        request = self._prep_new_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertNotIn('x', stored_session_data)

        # there should be two items in the history:
        # 0 = a pipeline.SET for the initial creation
        # 1 = a SET for the persist
        self.assertEqual(len(request.registry._redis_sessions._history), 2)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'pipeline.set')
        self.assertEqual(request.registry._redis_sessions._history[1][0], 'set')
        
    def test_scenario_new__noTimeout_trigger_pythonNoExpires_setRedisTtl(self):
        """the ``timeout_trigger`` is irrelevant"""
        session_args = self._args_noTimeout_trigger_noPythonExpires_setRedisTtl
        request = self._prep_new_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertNotIn('x', stored_session_data)

        # there should be two items in the history:
        # 0 = a pipeline.SET for the initial creation
        # 1 = a SET for the persist
        self.assertEqual(len(request.registry._redis_sessions._history), 2)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'pipeline.set')
        self.assertEqual(request.registry._redis_sessions._history[1][0], 'set')

    def test_scenario_new__noTimeout_noTrigger_pythonExpires_setRedisTtl(self):
        session_args = self._args_noTimeout_noTrigger_pythonExpires_setRedisTtl
        request = self._prep_new_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertNotIn('x', stored_session_data)

        # there should be two items in the history:
        # 0 = a pipeline.SET for the initial creation
        # 1 = a SET for the persist
        self.assertEqual(len(request.registry._redis_sessions._history), 2)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'pipeline.set')
        self.assertEqual(request.registry._redis_sessions._history[1][0], 'set')
        
    def test_scenario_new__noTimeout_noTrigger_noPythonExpires_setRedisTtl(self):
        session_args = self._args_noTimeout_noTrigger_noPythonExpires_setRedisTtl
        request = self._prep_new_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertNotIn('x', stored_session_data)

        # there should be two items in the history:
        # 0 = a pipeline.SET for the initial creation
        # 1 = a SET for the persist
        self.assertEqual(len(request.registry._redis_sessions._history), 2)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'pipeline.set')
        self.assertEqual(request.registry._redis_sessions._history[1][0], 'set')

    # --------------------------------------------------------------------------
    # existing session - timeout
    # --------------------------------------------------------------------------

    def test_scenario_existing__timeout_trigger_pythonExpires_setRedisTtl_noChange(self):
        session_args = self._args_timeout_trigger_pythonExpires_setRedisTtl
        request = self._prep_existing_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertIn('x', stored_session_data)
        self.assertEqual(stored_session_data['x'], stored_session_data['c'] + stored_session_data['t'])
        
        # there should be 1 items in the history:
        # 0 = a SETEX for the initial creation
        self.assertEqual(len(request.registry._redis_sessions._history), 1)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'setex')
        self.assertEqual(request.registry._redis_sessions._history[0][2], session_args['timeout'])
        
    def test_scenario_existing__timeout_trigger_pythonNoExpires_setRedisTtl_noChange(self):
        # note: timeout-trigger will force python_expires

        session_args = self._args_timeout_trigger_noPythonExpires_setRedisTtl
        request = self._prep_existing_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertIn('x', stored_session_data)
        
        # there should be 1 items in the history:
        # 0 = a SETEX for the initial creation
        self.assertEqual(len(request.registry._redis_sessions._history), 1)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'setex')
        self.assertEqual(request.registry._redis_sessions._history[0][2], session_args['timeout'])

    def test_scenario_existing__timeout_noTrigger_pythonExpires_setRedisTtl_noChange(self):
        session_args = self._args_timeout_noTrigger_pythonExpires_setRedisTtl
        request = self._prep_existing_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertIn('x', stored_session_data)
        self.assertEqual(stored_session_data['x'], stored_session_data['c'] + stored_session_data['t'])

        # there should be 1 items in the history:
        # 0 = a SETEX for the initial creation
        self.assertEqual(len(request.registry._redis_sessions._history), 1)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'setex')
        self.assertEqual(request.registry._redis_sessions._history[0][2], session_args['timeout'])
        
    def test_scenario_existing__timeout_noTrigger_noPythonExpires_setRedisTtl_noChange(self):
        """
        a timeout entirely occurs via EXPIRY in redis
        """
        session_args = self._args_timeout_noTrigger_noPythonExpires_setRedisTtl
        request = self._prep_existing_session(session_args)

        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertNotIn('x', stored_session_data)

        # there should be 1 items in the history:
        # 0 = a SETEX for the initial creation
        self.assertEqual(len(request.registry._redis_sessions._history), 1)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'setex')
        self.assertEqual(request.registry._redis_sessions._history[0][2], session_args['timeout'])

    # --------------------------------------------------------------------------
    # existing session - timeout
    # --------------------------------------------------------------------------
    
    def test_scenario_existing__noTimeout_trigger_pythonExpires_setRedisTtl(self):
        """the ``timeout_trigger`` is irrelevant"""
        session_args = self._args_noTimeout_trigger_pythonExpires_setRedisTtl
        request = self._prep_existing_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertNotIn('x', stored_session_data)

        # there should be 1 items in the history:
        # 0 = a SETEX for the initial creation
        self.assertEqual(len(request.registry._redis_sessions._history), 1)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'setex')
        self.assertEqual(request.registry._redis_sessions._history[0][2], session_args['timeout'])
        
    def test_scenario_existing__noTimeout_trigger_pythonNoExpires_setRedisTtl(self):
        """the ``timeout_trigger`` is irrelevant"""
        session_args = self._args_noTimeout_trigger_noPythonExpires_setRedisTtl
        request = self._prep_existing_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertNotIn('x', stored_session_data)

        # there should be 1 items in the history:
        # 0 = a SETEX for the initial creation
        self.assertEqual(len(request.registry._redis_sessions._history), 1)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'setex')
        self.assertEqual(request.registry._redis_sessions._history[0][2], session_args['timeout'])

    def test_scenario_existing__noTimeout_noTrigger_pythonExpires_setRedisTtl(self):
        session_args = self._args_noTimeout_noTrigger_pythonExpires_setRedisTtl
        request = self._prep_existing_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertNotIn('x', stored_session_data)

        # there should be 1 items in the history:
        # 0 = a SETEX for the initial creation
        self.assertEqual(len(request.registry._redis_sessions._history), 1)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'setex')
        self.assertEqual(request.registry._redis_sessions._history[0][2], session_args['timeout'])
        
    def test_scenario_existing__noTimeout_noTrigger_noPythonExpires_setRedisTtl(self):
        session_args = self._args_noTimeout_noTrigger_noPythonExpires_setRedisTtl
        request = self._prep_existing_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertNotIn('x', stored_session_data)

        # there should be 1 items in the history:
        # 0 = a SETEX for the initial creation
        self.assertEqual(len(request.registry._redis_sessions._history), 1)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'setex')
        self.assertEqual(request.registry._redis_sessions._history[0][2], session_args['timeout'])

    # ===========================
    # no ttl variants
    # ===========================

    def test_scenario_new__timeout_trigger_pythonExpires_noRedisTtl(self):
        session_args = self._args_timeout_trigger_pythonExpires_noRedisTtl
        request = self._prep_new_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertIn('x', stored_session_data)
        self.assertEqual(stored_session_data['x'], stored_session_data['c'] + stored_session_data['t'])

        # there should be two items in the history:
        # 0 = a pipeline.SETEX for the initial creation
        # 1 = a SETEX for the persist
        self.assertEqual(len(request.registry._redis_sessions._history), 2)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'pipeline.set')
        self.assertEqual(request.registry._redis_sessions._history[1][0], 'set')
        
    def test_scenario_new__timeout_trigger_pythonNoExpires_noRedisTtl(self):
        # note: timeout-trigger will force python_expires
        session_args = self._args_timeout_trigger_noPythonExpires_noRedisTtl
        request = self._prep_new_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertIn('x', stored_session_data)
        self.assertEqual(stored_session_data['x'], stored_session_data['c'] + stored_session_data['t'])

        # there should be two items in the history:
        # 0 = a pipeline.SETEX for the initial creation
        # 1 = a SETEX for the persist
        self.assertEqual(len(request.registry._redis_sessions._history), 2)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'pipeline.set')
        self.assertEqual(request.registry._redis_sessions._history[1][0], 'set')

    def test_scenario_new__timeout_noTrigger_pythonExpires_noRedisTtl(self):
        session_args = self._args_timeout_noTrigger_pythonExpires_noRedisTtl
        request = self._prep_new_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertIn('x', stored_session_data)
        self.assertEqual(stored_session_data['x'], stored_session_data['c'] + stored_session_data['t'])

        # there should be two items in the history:
        # 0 = a pipeline.SETEX for the initial creation
        # 1 = a SETEX for the persist
        self.assertEqual(len(request.registry._redis_sessions._history), 2)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'pipeline.set')
        self.assertEqual(request.registry._redis_sessions._history[1][0], 'set')
        
    def test_scenario_new__timeout_noTrigger_noPythonExpires_noRedisTtl(self):
        """
        a timeout entirely occurs via EXPIRY in redis
        """
        session_args = self._args_timeout_noTrigger_noPythonExpires_noRedisTtl
        request = self._prep_new_session(session_args)

        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertNotIn('x', stored_session_data)

        # there should be two items in the history:
        # 0 = a pipeline.SETEX for the initial creation
        # 1 = a SETEX for the persist
        self.assertEqual(len(request.registry._redis_sessions._history), 2)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'pipeline.set')
        self.assertEqual(request.registry._redis_sessions._history[1][0], 'set')

    # --------------------------------------------------------------------------
    # new session - no timeout
    # --------------------------------------------------------------------------

    def test_scenario_new__noTimeout_trigger_pythonExpires_noRedisTtl(self):
        """the ``timeout_trigger`` is irrelevant"""
        session_args = self._args_noTimeout_trigger_pythonExpires_noRedisTtl
        request = self._prep_new_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertNotIn('x', stored_session_data)

        # there should be two items in the history:
        # 0 = a pipeline.SET for the initial creation
        # 1 = a SET for the persist
        self.assertEqual(len(request.registry._redis_sessions._history), 2)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'pipeline.set')
        self.assertEqual(request.registry._redis_sessions._history[1][0], 'set')
        
    def test_scenario_new__noTimeout_trigger_pythonNoExpires_noRedisTtl(self):
        """the ``timeout_trigger`` is irrelevant"""
        session_args = self._args_noTimeout_trigger_noPythonExpires_noRedisTtl
        request = self._prep_new_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertNotIn('x', stored_session_data)

        # there should be two items in the history:
        # 0 = a pipeline.SET for the initial creation
        # 1 = a SET for the persist
        self.assertEqual(len(request.registry._redis_sessions._history), 2)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'pipeline.set')
        self.assertEqual(request.registry._redis_sessions._history[1][0], 'set')

    def test_scenario_new__noTimeout_noTrigger_pythonExpires_noRedisTtl(self):
        session_args = self._args_noTimeout_noTrigger_pythonExpires_noRedisTtl
        request = self._prep_new_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertNotIn('x', stored_session_data)

        # there should be two items in the history:
        # 0 = a pipeline.SET for the initial creation
        # 1 = a SET for the persist
        self.assertEqual(len(request.registry._redis_sessions._history), 2)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'pipeline.set')
        self.assertEqual(request.registry._redis_sessions._history[1][0], 'set')
        
    def test_scenario_new__noTimeout_noTrigger_noPythonExpires_noRedisTtl(self):
        session_args = self._args_noTimeout_noTrigger_noPythonExpires_noRedisTtl
        request = self._prep_new_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertNotIn('x', stored_session_data)

        # there should be two items in the history:
        # 0 = a pipeline.SET for the initial creation
        # 1 = a SET for the persist
        self.assertEqual(len(request.registry._redis_sessions._history), 2)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'pipeline.set')
        self.assertEqual(request.registry._redis_sessions._history[1][0], 'set')

    # --------------------------------------------------------------------------
    # existing session - timeout
    # --------------------------------------------------------------------------

    def test_scenario_existing__timeout_trigger_pythonExpires_noRedisTtl_noChange(self):
        session_args = self._args_timeout_trigger_pythonExpires_noRedisTtl
        request = self._prep_existing_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertIn('x', stored_session_data)
        self.assertEqual(stored_session_data['x'], stored_session_data['c'] + stored_session_data['t'])
        
        # there should be 1 items in the history:
        # 0 = a SETEX for the initial creation
        self.assertEqual(len(request.registry._redis_sessions._history), 1)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'set')
        
    def test_scenario_existing__timeout_trigger_pythonNoExpires_noRedisTtl_noChange(self):
        # note: timeout-trigger will force python_expires
        session_args = self._args_timeout_trigger_noPythonExpires_noRedisTtl
        request = self._prep_existing_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertIn('x', stored_session_data)
        
        # there should be 1 items in the history:
        # 0 = a SETEX for the initial creation
        self.assertEqual(len(request.registry._redis_sessions._history), 1)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'set')

    def test_scenario_existing__timeout_noTrigger_pythonExpires_noRedisTtl_noChange(self):
        session_args = self._args_timeout_noTrigger_pythonExpires_noRedisTtl
        request = self._prep_existing_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertIn('x', stored_session_data)
        self.assertEqual(stored_session_data['x'], stored_session_data['c'] + stored_session_data['t'])

        # there should be 1 items in the history:
        # 0 = a SETEX for the initial creation
        self.assertEqual(len(request.registry._redis_sessions._history), 1)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'set')
        
    def test_scenario_existing__timeout_noTrigger_noPythonExpires_noRedisTtl_noChange(self):
        """
        a timeout entirely occurs via EXPIRY in redis
        """
        session_args = self._args_timeout_noTrigger_noPythonExpires_noRedisTtl
        request = self._prep_existing_session(session_args)

        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertNotIn('x', stored_session_data)

        # there should be 1 items in the history:
        # 0 = a SETEX for the initial creation
        self.assertEqual(len(request.registry._redis_sessions._history), 1)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'set')

    # --------------------------------------------------------------------------
    # existing session - timeout
    # --------------------------------------------------------------------------
    
    def test_scenario_existing__noTimeout_trigger_pythonExpires_noRedisTtl(self):
        """the ``timeout_trigger`` is irrelevant"""
        session_args = self._args_noTimeout_trigger_pythonExpires_noRedisTtl
        request = self._prep_existing_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertNotIn('x', stored_session_data)

        # there should be 1 items in the history:
        # 0 = a SETEX for the initial creation
        self.assertEqual(len(request.registry._redis_sessions._history), 1)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'set')
        
    def test_scenario_existing__noTimeout_trigger_pythonNoExpires_noRedisTtl(self):
        """the ``timeout_trigger`` is irrelevant"""
        session_args = self._args_noTimeout_trigger_noPythonExpires_noRedisTtl
        request = self._prep_existing_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertNotIn('x', stored_session_data)

        # there should be 1 items in the history:
        # 0 = a SETEX for the initial creation
        self.assertEqual(len(request.registry._redis_sessions._history), 1)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'set')

    def test_scenario_existing__noTimeout_noTrigger_pythonExpires_noRedisTtl(self):
        session_args = self._args_noTimeout_noTrigger_pythonExpires_noRedisTtl
        request = self._prep_existing_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertNotIn('x', stored_session_data)

        # there should be 1 items in the history:
        # 0 = a SETEX for the initial creation
        self.assertEqual(len(request.registry._redis_sessions._history), 1)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'set')
        
    def test_scenario_existing__noTimeout_noTrigger_noPythonExpires_noRedisTtl(self):
        session_args = self._args_noTimeout_noTrigger_noPythonExpires_noRedisTtl
        request = self._prep_existing_session(session_args)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data = self._deserialize_session_stored(request.session)
        self.assertNotIn('x', stored_session_data)

        # there should be 1 items in the history:
        # 0 = a SETEX for the initial creation
        self.assertEqual(len(request.registry._redis_sessions._history), 1)
        self.assertEqual(request.registry._redis_sessions._history[0][0], 'set')


    # --------------------------------------------------------------------------
    # new session - timeout
    # --------------------------------------------------------------------------

    def test_scenario_flow__timeout_trigger_pythonExpires_noRedisTtl_noChange(self):
        session_args = self._args_timeout_trigger_pythonExpires_noRedisTtl
        request1 = self._prep_existing_session(session_args)

        stored_session_data_1 = self._deserialize_session_stored(request1.session)
        
        # timeout = 1200
        timeout_diff_1 = -9
        request2 = self._adjust_request_session(request1, expires=timeout_diff_1)
    
        # cookie_on_exception is True by default, no exception raised
        stored_session_data_2 = self._deserialize_session_stored(request2.session)
        
        self.assertIn('x', stored_session_data_2)
        self.assertEqual(stored_session_data_2['x'], stored_session_data_1['x'] + timeout_diff_1)
        
        # there should be 1 items in the history:
        # 0 = a SETEX for the initial creation
        self.assertEqual(len(request1.registry._redis_sessions._history), 1)
        self.assertEqual(request1.registry._redis_sessions._history[0][0], 'set')
