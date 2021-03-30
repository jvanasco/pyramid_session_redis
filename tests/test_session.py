# -*- coding: utf-8 -*-
from __future__ import print_function

# stdlib
import itertools
import pdb
import pprint
import time
import unittest

# local
from pyramid_session_redis.compat import pickle
from pyramid_session_redis.exceptions import (
    InvalidSession,
    InvalidSession_PayloadTimeout,
    InvalidSession_PayloadLegacy,
)
from pyramid_session_redis.session import RedisSession
from pyramid_session_redis.util import (
    encode_session_payload,
    int_time,
    LAZYCREATE_SESSION,
)

# local test suite
from . import DummyRedis


# ==============================================================================


class TestRedisSession(unittest.TestCase):
    def _makeOne(
        self,
        redis,
        session_id,
        new,
        func_new_session,
        serialize=pickle.dumps,
        deserialize=pickle.loads,
        detect_changes=True,
        set_redis_ttl=True,
        deserialized_fails_new=None,
        timeout_trigger=None,
        timeout=1200,
        python_expires=True,
        set_redis_ttl_readheavy=None,
    ):
        _set_redis_ttl_onexit = False
        if (timeout and set_redis_ttl) and (
            not timeout_trigger and not python_expires and not set_redis_ttl_readheavy
        ):
            _set_redis_ttl_onexit = True
        return RedisSession(
            redis=redis,
            session_id=session_id,
            new=new,
            new_session=func_new_session,
            serialize=serialize,
            deserialize=deserialize,
            detect_changes=detect_changes,
            set_redis_ttl=set_redis_ttl,
            set_redis_ttl_readheavy=set_redis_ttl_readheavy,
            _set_redis_ttl_onexit=_set_redis_ttl_onexit,
            deserialized_fails_new=deserialized_fails_new,
            timeout_trigger=timeout_trigger,
            timeout=timeout,
            python_expires=python_expires,
        )

    def _set_up_session_in_redis(
        self, redis, session_id, timeout, session_dict=None, serialize=pickle.dumps
    ):
        """
        Note: this will call `encode_session_payload` with the initial session
        data. On a typical test this will mean an extra initial call to
        `encode_session_payload``
        """
        if session_dict is None:
            session_dict = {}
        time_now = int_time()
        expires = time_now + timeout if timeout else None
        payload = encode_session_payload(session_dict, time_now, timeout, expires)
        redis.set(session_id, serialize(payload))
        return session_id

    def _make_id_generator(self):
        ids = itertools.count(start=0, step=1)
        return lambda: str(next(ids))

    def _set_up_session_in_Redis_and_makeOne(
        self,
        session_id=None,
        session_dict=None,
        new=True,
        timeout=300,
        detect_changes=True,
    ):
        redis = DummyRedis()
        id_generator = self._make_id_generator()
        if session_id is None:
            session_id = id_generator()
        self._set_up_session_in_redis(
            redis=redis,
            session_id=session_id,
            session_dict=session_dict,
            timeout=timeout,
        )
        func_new_session = lambda: self._set_up_session_in_redis(
            redis=redis,
            session_id=id_generator(),
            session_dict=session_dict,
            timeout=timeout,
        )
        return self._makeOne(
            redis=redis,
            session_id=session_id,
            new=new,
            func_new_session=func_new_session,
            detect_changes=detect_changes,
            timeout=timeout,
        )

    def test_init_new_session(self):
        session_id = "session_id"
        new = True
        timeout = 300
        inst = self._set_up_session_in_Redis_and_makeOne(
            session_id=session_id, new=new, timeout=timeout
        )
        self.assertEqual(inst.session_id, session_id)
        self.assertIs(inst.new, new)
        self.assertDictEqual(dict(inst), {})

    def test_init_existing_session(self):
        session_id = "session_id"
        session_dict = {"key": "value"}
        new = False
        timeout = 300
        inst = self._set_up_session_in_Redis_and_makeOne(
            session_id=session_id, session_dict=session_dict, new=new, timeout=timeout
        )
        self.assertEqual(inst.session_id, session_id)
        self.assertIs(inst.new, new)
        self.assertDictEqual(dict(inst), session_dict)

    def test_delitem(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        inst["key"] = "val"
        del inst["key"]
        inst.do_persist()
        session_dict_in_redis = inst.from_redis()["m"]
        self.assertNotIn("key", inst)
        self.assertNotIn("key", session_dict_in_redis)

    def test_setitem(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        inst["key"] = "val"
        inst.do_persist()
        session_dict_in_redis = inst.from_redis()["m"]
        self.assertIn("key", inst)
        self.assertIn("key", session_dict_in_redis)

    def test_getitem(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        inst["key"] = "val"
        inst.do_persist()
        session_dict_in_redis = inst.from_redis()["m"]
        self.assertEqual(inst["key"], session_dict_in_redis["key"])

    def test_contains(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        inst["key"] = "val"
        inst.do_persist()
        session_dict_in_redis = inst.from_redis()["m"]
        self.assertTrue("key" in inst)
        self.assertTrue("key" in session_dict_in_redis)

    def test_setdefault(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        result = inst.setdefault("key", "val")
        self.assertEqual(result, inst["key"])

    def test_keys(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        inst["key1"] = ""
        inst["key2"] = ""
        inst_keys = inst.keys()
        inst.do_persist()
        session_dict_in_redis = inst.from_redis()["m"]
        persisted_keys = session_dict_in_redis.keys()
        self.assertEqual(inst_keys, persisted_keys)

    def test_items(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        inst["a"] = 1
        inst["b"] = 2
        inst_items = inst.items()
        inst.do_persist()
        session_dict_in_redis = inst.from_redis()["m"]
        persisted_items = session_dict_in_redis.items()
        self.assertEqual(inst_items, persisted_items)

    def test_clear(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        inst["a"] = 1
        inst.clear()
        session_dict_in_redis = inst.from_redis()["m"]
        self.assertNotIn("a", inst)
        self.assertNotIn("a", session_dict_in_redis)

    def test_get(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        inst["key"] = "val"
        get_from_inst = inst.get("key")
        self.assertEqual(get_from_inst, "val")
        inst.do_persist()
        session_dict_in_redis = inst.from_redis()["m"]
        get_from_redis = session_dict_in_redis.get("key")
        self.assertEqual(get_from_inst, get_from_redis)

    def test_get_default(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        get_from_inst = inst.get("key", "val")
        self.assertEqual(get_from_inst, "val")
        session_dict_in_redis = inst.from_redis()["m"]
        get_from_redis = session_dict_in_redis.get("key", "val")
        self.assertEqual(get_from_inst, get_from_redis)

    def test_pop(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        inst["key"] = "val"
        popped = inst.pop("key")
        self.assertEqual(popped, "val")
        session_dict_in_redis = inst.from_redis()["m"]
        self.assertNotIn("key", session_dict_in_redis)

    def test_pop_default(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        popped = inst.pop("key", "val")
        self.assertEqual(popped, "val")

    def test_update(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        inst["a"] = 1
        to_be_updated = {"a": "overriden", "b": 2}
        inst.update(to_be_updated)
        self.assertEqual(inst["a"], "overriden")
        self.assertEqual(inst["b"], 2)
        inst.do_persist()
        session_dict_in_redis = inst.from_redis()["m"]
        self.assertEqual(session_dict_in_redis["a"], "overriden")
        self.assertEqual(session_dict_in_redis["b"], 2)

    def test_iter(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        keys = ["a", "b", "c"]
        for k in keys:
            inst[k] = k
        itered = list(inst.__iter__())
        itered.sort()
        self.assertEqual(keys, itered)

    def test_has_key(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        inst["actual_key"] = ""
        self.assertIn("actual_key", inst)
        self.assertNotIn("not_a_key", inst)

    def test_values(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        inst["a"] = 1
        inst["b"] = 2
        expected_values = [1, 2]
        actual_values = sorted(inst.values())
        self.assertEqual(actual_values, expected_values)

    def test_itervalues(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        inst["a"] = 1
        inst["b"] = 2
        itered = list(inst.itervalues())
        itered.sort()
        expected = [1, 2]
        self.assertEqual(expected, itered)

    def test_iteritems(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        inst["a"] = 1
        inst["b"] = 2
        itered = list(inst.iteritems())
        itered.sort()
        expected = [("a", 1), ("b", 2)]
        self.assertEqual(expected, itered)

    def test_iterkeys(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        inst["a"] = 1
        inst["b"] = 2
        itered = list(inst.iterkeys())
        itered.sort()
        expected = ["a", "b"]
        self.assertEqual(expected, itered)

    def test_popitem(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        inst["a"] = 1
        inst["b"] = 2
        popped = inst.popitem()
        options = [("a", 1), ("b", 2)]
        self.assertIn(popped, options)
        session_dict_in_redis = inst.from_redis()["m"]
        self.assertNotIn(popped, session_dict_in_redis)

    def test_IDict_instance_conforms(self):
        from pyramid.interfaces import IDict
        from zope.interface.verify import verifyObject

        inst = self._set_up_session_in_Redis_and_makeOne()
        verifyObject(IDict, inst)

    def test_created(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        created = inst.from_redis()["c"]
        self.assertEqual(inst.created, created)

    def test_timeout(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        timeout = inst.from_redis()["t"]
        self.assertEqual(inst.timeout, timeout)

    def test_invalidate(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        first_session_id = inst.session_id
        inst.invalidate()
        self.assertNotIn(first_session_id, inst.redis.store)
        self.assertIs(inst._invalidated, True)

    def test_dict_multilevel(self):
        inst = self._set_up_session_in_Redis_and_makeOne(session_id="test1")
        inst["dict"] = {"foo": {"bar": 1}}
        inst.do_persist()
        get_from_inst = inst["dict"]["foo"]["bar"]
        self.assertEqual(get_from_inst, 1)
        session_dict_in_redis = inst.from_redis()["m"]
        get_from_redis = session_dict_in_redis["dict"]["foo"]["bar"]
        self.assertEqual(get_from_redis, 1)
        inst["dict"]["foo"]["bar"] = 2
        inst.do_persist()
        session_dict_in_redis2 = inst.from_redis()["m"]
        get_from_redis2 = session_dict_in_redis2["dict"]["foo"]["bar"]
        self.assertEqual(get_from_redis2, 2)

    def test_dict_multilevel_detect_changes_on(self):
        inst = self._set_up_session_in_Redis_and_makeOne(
            session_id="test1", detect_changes=True
        )
        # set a base dict and ensure it worked
        inst["dict"] = {"foo": {"bar": 1}}
        inst.do_persist()
        get_from_inst = inst["dict"]["foo"]["bar"]
        self.assertEqual(get_from_inst, 1)
        # grab the dict and edit it
        session_dict_in_redis = inst.from_redis()["m"]
        get_from_redis = session_dict_in_redis["dict"]["foo"]["bar"]
        self.assertEqual(get_from_redis, 1)
        inst["dict"]["foo"]["bar"] = 2
        # ensure the change was detected
        should_persist = inst._session_state.should_persist(inst)
        self.assertTrue(should_persist)

    def test_dict_multilevel_detect_changes_off(self):
        inst = self._set_up_session_in_Redis_and_makeOne(
            session_id="test1", detect_changes=False
        )
        # set a base dict and ensure it worked
        inst["dict"] = {"foo": {"bar": 1}}
        inst.do_persist()
        get_from_inst = inst["dict"]["foo"]["bar"]
        self.assertEqual(get_from_inst, 1)
        # grab the dict and edit it
        session_dict_in_redis = inst.from_redis()["m"]
        get_from_redis = session_dict_in_redis["dict"]["foo"]["bar"]
        self.assertEqual(get_from_redis, 1)
        inst["dict"]["foo"]["bar"] = 2
        # ensure the change was NOT detected
        should_persist = inst._session_state.should_persist(inst)
        self.assertFalse(should_persist)

    def test_new_session_after_invalidate(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        first_session_id = inst.session_id
        inst["key"] = "value"
        inst.invalidate()
        inst.ensure_id()  # ensure we have an id in redis, which creates a null payload
        second_session_id = inst.session_id
        self.assertSetEqual(set(inst.redis.store.keys()), {second_session_id})
        self.assertNotEqual(second_session_id, first_session_id)
        self.assertIs(bool(second_session_id), True)
        self.assertDictEqual(dict(inst), {})
        self.assertIs(inst.new, True)
        self.assertIs(inst._invalidated, False)

    def test_session_id_access_after_invalidate_creates_new_session(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        first_session_id = inst.session_id
        inst.invalidate()

        # 1.4.x+| session_id defaults to a LAZYCREATE
        self.assertIs(inst.session_id_safecheck, None)
        self.assertIs(inst.session_id, LAZYCREATE_SESSION)

        second_session_id = inst.session_id
        self.assertNotEqual(second_session_id, first_session_id)
        self.assertIs(bool(second_session_id), True)

    def test_managed_dict_access_after_invalidate_creates_new_session(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        first_session_id = inst.session_id
        inst.invalidate()
        inst.managed_dict  # access

        # 1.4.x+| session_id defaults to a LAZYCREATE
        # 1.4.x+| session_id is only created via ensure_id()
        self.assertIs(inst.session_id_safecheck, None)
        self.assertIs(inst.session_id, LAZYCREATE_SESSION)
        inst.ensure_id()

        # ORIGINALLY
        # .session_id attribute access also creates a new session after
        # invalidate, so just asserting .session_id is not enough to prove that
        # a new session was created after .managed_dict access. Here we note
        # down the session_ids in Redis right after .managed_dict access for an
        # additional check.
        session_ids_in_redis = inst.redis.store.keys()
        second_session_id = inst.session_id
        self.assertSetEqual(set(session_ids_in_redis), {second_session_id})
        self.assertNotEqual(second_session_id, first_session_id)
        self.assertIs(bool(second_session_id), True)

    def test_created_access_after_invalidate_creates_new_session(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        first_session_id = inst.session_id
        inst.invalidate()
        inst.created  # access

        # 1.4.x+| session_id defaults to a LAZYCREATE
        # 1.4.x+| session_id is only created via ensure_id()
        self.assertIs(inst.session_id_safecheck, None)
        self.assertIs(inst.session_id, LAZYCREATE_SESSION)
        inst.ensure_id()

        # ORIGINALLY
        # .session_id attribute access also creates a new session after
        # invalidate, so just asserting .session_id was not enough to prove that
        # a new session was created after .created access. Here we noted down
        # the session_ids in Redis right after .created access for an
        # additional check.
        session_ids_in_redis = inst.redis.store.keys()
        second_session_id = inst.session_id
        self.assertSetEqual(set(session_ids_in_redis), {second_session_id})
        self.assertNotEqual(second_session_id, first_session_id)
        self.assertIs(bool(second_session_id), True)

    def test_timeout_access_after_invalidate_creates_new_session(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        first_session_id = inst.session_id
        inst.invalidate()
        inst.timeout  # access

        # 1.4.x+| session_id defaults to a LAZYCREATE
        # 1.4.x+| session_id is only created via ensure_id()
        self.assertIs(inst.session_id_safecheck, None)
        self.assertIs(inst.session_id, LAZYCREATE_SESSION)
        inst.ensure_id()

        # ORIGINALLY:
        # .session_id attribute access also creates a new session after
        # invalidate, so just asserting .session_id is not enough to prove that
        # a new session was created after .timeout access. Here we note down
        # the session_ids in Redis right after .timeout access for an
        # additional check.
        session_ids_in_redis = inst.redis.store.keys()
        second_session_id = inst.session_id
        self.assertSetEqual(set(session_ids_in_redis), {second_session_id})
        self.assertNotEqual(second_session_id, first_session_id)
        self.assertIs(bool(second_session_id), True)

    def test_new_attribute_access_after_invalidate_creates_new_session(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        first_session_id = inst.session_id
        inst.invalidate()
        inst.new  # access

        # 1.4.x+| session_id defaults to a LAZYCREATE
        # 1.4.x+| session_id is only created via ensure_id()
        self.assertIs(inst.session_id_safecheck, None)
        self.assertIs(inst.session_id, LAZYCREATE_SESSION)
        inst.ensure_id()

        # ORIGINALLY
        # .session_id attribute access also creates a new session after
        # invalidate, so just asserting .session_id is not enough to prove that
        # a new session was created after .created access. Here we note down
        # session_ids in Redis right after .new access for an additional check.
        session_ids_in_redis = inst.redis.store.keys()
        second_session_id = inst.session_id
        self.assertSetEqual(set(session_ids_in_redis), {second_session_id})
        self.assertNotEqual(second_session_id, first_session_id)
        self.assertIs(bool(second_session_id), True)

    def test_repeated_invalidates_without_new_session_created_in_between(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        first_session_id = inst.session_id
        inst.invalidate()
        inst.invalidate()
        self.assertNotIn(first_session_id, inst.redis.store)
        self.assertIs(inst._invalidated, True)
        second_session_id = inst.session_id
        self.assertNotEqual(second_session_id, first_session_id)
        self.assertIs(bool(second_session_id), True)

    def test_invalidate_new_session_invalidate(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        inst.invalidate()
        second_session_id = inst.session_id
        inst.invalidate()
        session_ids_in_redis = inst.redis.store.keys()
        self.assertNotIn(second_session_id, session_ids_in_redis)
        self.assertIs(inst._invalidated, True)

    def test_invalidate_new_session_invalidate_new_session(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        inst.ensure_id()  # ensure we have an id in redis, which creates a null payload

        inst.invalidate()
        inst.ensure_id()  # ensure we have an id in redis, which creates a null payload
        second_session_id = inst.session_id

        inst.invalidate()
        inst.ensure_id()  # ensure we have an id in redis, which creates a null payload
        third_session_id = inst.session_id

        session_ids_in_redis = inst.redis.store.keys()
        self.assertSetEqual(set(session_ids_in_redis), {third_session_id})
        self.assertNotEqual(third_session_id, second_session_id)
        self.assertIs(bool(third_session_id), True)
        self.assertDictEqual(dict(inst), {})
        self.assertIs(inst.new, True)
        self.assertIs(inst._invalidated, False)

    def test_mutablevalue_changed(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        inst["a"] = {"1": 1, "2": 2}
        tmp = inst["a"]
        tmp["3"] = 3
        inst.changed()
        inst.do_persist()
        session_dict_in_redis = inst.from_redis()["m"]
        self.assertEqual(session_dict_in_redis["a"], {"1": 1, "2": 2, "3": 3})

    def test_csrf_token(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        new_token = inst.new_csrf_token()
        got_token = inst.get_csrf_token()
        self.assertEqual(new_token, got_token)

    def test_get_new_csrf_token(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        self.assertNotIn("_csrft_", inst)
        token = inst.get_csrf_token()
        self.assertEqual(inst["_csrft_"], token)

    def test_flash(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        inst.flash("message")
        msgs = inst.peek_flash()
        self.assertIn("message", msgs)

    def test_flash_alternate_queue(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        inst.flash("message", "queue")
        default_queue = inst.peek_flash()
        self.assertNotIn("message", default_queue)
        other_queue = inst.peek_flash("queue")
        self.assertIn("message", other_queue)

    def test_pop_flash(self):
        inst = self._set_up_session_in_Redis_and_makeOne()
        inst.flash("message")
        popped = inst.pop_flash()
        self.assertIn("message", popped)
        msgs = inst.peek_flash()
        self.assertEqual(msgs, [])

    def test_ISession_instance_conforms(self):
        from pyramid.interfaces import ISession
        from zope.interface.verify import verifyObject

        inst = self._set_up_session_in_Redis_and_makeOne()
        verifyObject(ISession, inst)

    def _test_adjust_session_timeout(self, variant=None):
        inst = self._set_up_session_in_Redis_and_makeOne(timeout=100)
        adjusted_timeout = 200
        if not variant:
            inst.adjust_session_timeout(adjusted_timeout)
        else:
            getattr(inst, variant)(adjusted_timeout)
        inst.do_persist()
        self.assertEqual(inst.timeout, adjusted_timeout)
        self.assertEqual(inst.from_redis()["t"], adjusted_timeout)

    def test_adjust_session_timeout(self):
        self._test_adjust_session_timeout()

    def test_adjust_session_timeout__legacy(self):
        self._test_adjust_session_timeout(variant="adjust_timeout_for_session")


class _TestRedisSessionNew_CORE(object):
    """
    Support functions for 1.2.x+ tests
    see
    """

    session_id = "session_id"

    def _makeOne(
        self,
        redis,
        session_id,
        new,
        func_new_session,
        serialize=pickle.dumps,
        deserialize=pickle.loads,
        detect_changes=True,
        set_redis_ttl=True,
        deserialized_fails_new=None,
        timeout_trigger=None,
        timeout=1200,
        python_expires=True,
        set_redis_ttl_readheavy=None,
    ):

        _set_redis_ttl_onexit = False
        if (timeout and set_redis_ttl) and (
            not timeout_trigger and not python_expires and not set_redis_ttl_readheavy
        ):
            _set_redis_ttl_onexit = True

        return RedisSession(
            redis=redis,
            session_id=session_id,
            new=new,
            new_session=func_new_session,
            serialize=serialize,
            deserialize=deserialize,
            detect_changes=detect_changes,
            set_redis_ttl=set_redis_ttl,
            set_redis_ttl_readheavy=set_redis_ttl_readheavy,
            _set_redis_ttl_onexit=_set_redis_ttl_onexit,
            deserialized_fails_new=deserialized_fails_new,
            timeout_trigger=timeout_trigger,
            timeout=timeout,
            python_expires=python_expires,
        )

    def _set_up_session_in_redis(
        self,
        redis,
        session_id,
        timeout,
        session_dict=None,
        serialize=pickle.dumps,
        session_version=None,
        expires=None,
        python_expires=True,
        reset_history=True,
    ):
        """
        Note: this will call `encode_session_payload` with the initial session
        data. On a typical test this will mean an extra initial call to
        `encode_session_payload`.
        the `expires` kwarg is to fake an expiry date.
        """
        if session_dict is None:
            session_dict = {}
        time_now = int_time()
        payload = encode_session_payload(
            session_dict, time_now, timeout, expires, python_expires=python_expires
        )
        if session_version is not None:
            payload["v"] = session_version
        # code an expires if needed
        if expires:
            # `encode_session_payload` will update the expires if we passed it,
            # so we must insert an expired value manually
            if python_expires:
                payload["x"] = expires
        elif not expires:
            if python_expires:
                expires = time_now + timeout
                payload["x"] = expires
        redis.set(session_id, serialize(payload))
        if reset_history:
            redis._history_reset()
        return session_id

    def _make_id_generator(self):
        ids = itertools.count(start=0, step=1)
        return lambda: str(next(ids))

    def _set_up_session_in_Redis_and_makeOne(
        self,
        session_id=None,
        session_dict=None,
        new=True,
        timeout=60,
        timeout_trigger=30,
        detect_changes=True,
        set_redis_ttl=True,
        session_version=None,
        expires=None,
        python_expires=True,
        set_redis_ttl_readheavy=None,
    ):
        redis = DummyRedis()
        id_generator = self._make_id_generator()
        if session_id is None:
            session_id = id_generator()
        self._set_up_session_in_redis(
            redis=redis,
            session_id=session_id,
            session_dict=session_dict,
            timeout=timeout,
            session_version=session_version,
            expires=expires,
            python_expires=python_expires,
        )
        func_new_session = lambda: self._set_up_session_in_redis(
            redis=redis,
            session_id=id_generator(),
            session_dict=session_dict,
            timeout=timeout,
            python_expires=python_expires,
        )
        return self._makeOne(
            redis=redis,
            session_id=session_id,
            new=new,
            func_new_session=func_new_session,
            detect_changes=detect_changes,
            timeout=timeout,
            set_redis_ttl=set_redis_ttl,
            set_redis_ttl_readheavy=set_redis_ttl_readheavy,
            python_expires=python_expires,
        )

    def _deserialize_session(self, session, deserialize=pickle.loads):
        _session_id = session.session_id
        _session_data = session.redis.store[_session_id]
        _session_serialized = deserialize(_session_data)
        return _session_serialized


class _TestRedisSessionNew__MIXIN_A(object):
    PYTHON_EXPIRES = None
    set_redis_ttl = None
    set_redis_ttl_readheavy = None
    session_id = "session_id"
    timeout = 3
    timeout_trigger = 6
    adjusted_timeout = 6

    def _session_new(self):
        session = self._set_up_session_in_Redis_and_makeOne(
            session_id=self.session_id,
            new=True,
            timeout=self.timeout,
            set_redis_ttl=self.set_redis_ttl,
            set_redis_ttl_readheavy=self.set_redis_ttl_readheavy,
            python_expires=self.PYTHON_EXPIRES,
        )
        session._deferred_callback(None)  # trigger the real session's set/setex
        self.assertEqual(session.session_id, self.session_id)
        self.assertIs(session.new, True)
        self.assertDictEqual(dict(session), {})
        return session

    def _factory_new_session(self, session):
        id_generator = self._make_id_generator()
        func_new_session = lambda: self._set_up_session_in_redis(
            redis=session.redis,
            session_id=id_generator(),
            session_dict={},
            timeout=self.timeout,
            python_expires=self.PYTHON_EXPIRES,
            set_redis_ttl=self.set_redis_ttl,
            set_redis_ttl_readheavy=self.set_redis_ttl_readheavy,
        )
        return func_new_session

    def _session_get(self, session, func_new_session):
        session2 = self._makeOne(
            session.redis,
            self.session_id,
            True,
            func_new_session,
            set_redis_ttl=self.set_redis_ttl,
            set_redis_ttl_readheavy=self.set_redis_ttl_readheavy,
            timeout=self.timeout,
            python_expires=self.PYTHON_EXPIRES,
        )
        return session2


class TestRedisSessionNew(unittest.TestCase, _TestRedisSessionNew_CORE):
    """these are 1.2x+ tests"""

    def test_init_new_session_notimeout(self):
        new = True
        timeout = 0
        set_redis_ttl = True
        session = self._set_up_session_in_Redis_and_makeOne(
            session_id=self.session_id,
            new=new,
            timeout=timeout,
            set_redis_ttl=set_redis_ttl,
        )
        session.do_persist()  # trigger the real session's set/setex
        self.assertEqual(session.session_id, self.session_id)
        self.assertIs(session.new, new)
        self.assertDictEqual(dict(session), {})

        self.assertEqual(session.timeout, None)

        _deserialized = self._deserialize_session(session)
        self.assertNotIn("t", _deserialized)

        # get, set
        self.assertEqual(len(session.redis._history), 2)
        _redis_op = session.redis._history[1]
        self.assertEqual(_redis_op[0], "set")

        # clear the history, `do_refresh` should do nothing (timeout=0)
        session.redis._history_reset()
        session.do_refresh()  # trigger the real session's set/setex
        self.assertEqual(
            len(session.redis._history), 0
        )  # we shouldn't have any timeout at all

        # clear the history, `do_refresh+force_redis_ttl` ensures an "expire"
        session.redis._history_reset()
        session.do_refresh(force_redis_ttl=47)  # trigger the real session's set/setex
        self.assertEqual(len(session.redis._history), 1)
        _redis_op = session.redis._history[0]
        self.assertEqual(_redis_op[0], "expire")
        self.assertEqual(_redis_op[2], 47)

    def test_init_new_session_notimeout_lru(self):
        """
        check that a no timeout will trigger a SET if LRU enabled
        """
        new = True
        timeout = 0
        set_redis_ttl = False
        session = self._set_up_session_in_Redis_and_makeOne(
            session_id=self.session_id,
            new=new,
            timeout=timeout,
            set_redis_ttl=set_redis_ttl,
        )
        session.do_persist()  # trigger the real session's set/setex
        self.assertEqual(session.session_id, self.session_id)
        self.assertIs(session.new, new)
        self.assertDictEqual(dict(session), {})

        _deserialized = self._deserialize_session(session)
        self.assertNotIn("t", _deserialized)

        # get, set
        self.assertEqual(len(session.redis._history), 2)
        _redis_op = session.redis._history[1]
        self.assertEqual(_redis_op[0], "set")

        # clear the history, `do_refresh` should do nothing (timeout=0)
        session.redis._history_reset()
        session.do_refresh()  # trigger the real session's set/setex
        self.assertEqual(
            len(session.redis._history), 0
        )  # we shouldn't have any timeout at all

        # clear the history, `do_refresh+force_redis_ttl` ensures an "expire"
        session.redis._history_reset()
        session.do_refresh(force_redis_ttl=47)  # trigger the real session's set/setex
        self.assertEqual(len(session.redis._history), 1)
        _redis_op = session.redis._history[0]
        self.assertEqual(_redis_op[0], "expire")
        self.assertEqual(_redis_op[2], 47)

    def test_init_new_session_timeout(self):
        """
        check that a timeout will trigger a SETEX
        """
        new = True
        timeout = 60
        set_redis_ttl = True
        session = self._set_up_session_in_Redis_and_makeOne(
            session_id=self.session_id,
            new=new,
            timeout=timeout,
            set_redis_ttl=set_redis_ttl,
        )
        session.do_persist()  # trigger the real session's set/setex
        self.assertEqual(session.session_id, self.session_id)
        self.assertIs(session.new, new)
        self.assertDictEqual(dict(session), {})

        _deserialized = self._deserialize_session(session)
        self.assertIn("t", _deserialized)
        # get, set
        self.assertEqual(len(session.redis._history), 2)
        _redis_op = session.redis._history[1]
        self.assertEqual(_redis_op[0], "setex")

        # clear the history, `do_refresh` should issue an "expire" (timeout=60)
        session.redis._history_reset()
        session.do_refresh()  # trigger the real session's set/setex
        # we shouldn't have set a timeout
        self.assertEqual(len(session.redis._history), 1)
        _redis_op = session.redis._history[0]
        self.assertEqual(_redis_op[0], "expire")

        # clear the history, `do_refresh+force_redis_ttl` ensures an "expire"
        session.redis._history_reset()
        session.do_refresh(force_redis_ttl=47)  # trigger the real session's set/setex
        self.assertEqual(len(session.redis._history), 1)
        _redis_op = session.redis._history[0]
        self.assertEqual(_redis_op[0], "expire")
        self.assertEqual(_redis_op[2], 47)

    def test_init_new_session_timeout_lru(self):
        """
        check that a timeout will trigger a SET if LRU enabled
        """
        new = True
        timeout = 60
        set_redis_ttl = False
        session = self._set_up_session_in_Redis_and_makeOne(
            session_id=self.session_id,
            new=new,
            timeout=timeout,
            set_redis_ttl=set_redis_ttl,
        )
        session.do_persist()  # trigger the real session's set/setex
        self.assertEqual(session.session_id, self.session_id)
        self.assertIs(session.new, new)
        self.assertDictEqual(dict(session), {})
        _deserialized = self._deserialize_session(session)
        self.assertIn("t", _deserialized)
        self.assertEqual(len(session.redis._history), 2)
        _redis_op = session.redis._history[1]
        self.assertEqual(_redis_op[0], "set")

        # clear the history, `do_refresh` should do nothing (timeout=60, set_redis_ttl=False)
        session.redis._history_reset()
        session.do_refresh()  # trigger the real session's set/setex
        self.assertEqual(len(session.redis._history), 0)

        # clear the history, `do_refresh` should issue an "expire" (force_redis_ttl=60)
        session.redis._history_reset()
        session.do_refresh(force_redis_ttl=47)  # trigger the real session's set/setex
        self.assertEqual(len(session.redis._history), 1)
        _redis_op = session.redis._history[0]
        self.assertEqual(_redis_op[0], "expire")
        self.assertEqual(_redis_op[2], 47)

    def test_session_invalid_legacy(self):
        """
        check that ``exceptions.InvalidSession_PayloadLegacy`` is raised if a previous version is detected
        """
        new = True
        timeout = 60
        set_redis_ttl = False
        session_version = -1
        with self.assertRaises(InvalidSession_PayloadLegacy):
            session = self._set_up_session_in_Redis_and_makeOne(
                session_id=self.session_id,
                new=new,
                timeout=timeout,
                set_redis_ttl=set_redis_ttl,
                session_version=session_version,
            )
        return

    def test_session_invalid_expires(self):
        """
        check that ``exceptions.InvalidSession_PayloadTimeout`` is raised if we timed out
        """
        new = True
        timeout = 60
        set_redis_ttl = False
        expires = int_time() - timeout - 1
        with self.assertRaises(InvalidSession_PayloadTimeout):
            session = self._set_up_session_in_Redis_and_makeOne(
                session_id=self.session_id,
                new=new,
                timeout=timeout,
                set_redis_ttl=set_redis_ttl,
                expires=expires,
            )


class TestRedisSessionNew_TimeoutAdjustments_A(
    _TestRedisSessionNew__MIXIN_A, _TestRedisSessionNew_CORE, unittest.TestCase
):
    """these are 1.4x+ tests"""

    PYTHON_EXPIRES = True
    set_redis_ttl = True
    timeout = 6
    timeout_trigger = 3
    adjusted_timeout = 86400  # 31536000

    def test_adjust_timeout(self):
        """
        check that a timeout will trigger a SETEX

        python -munittest pyramid_session_redis.tests.test_session.TestRedisSessionNew_TimeoutAdjustments_A.test_adjust_timeout
        """
        self._test_adjust_timeout()

    def test_adjust_timeout__legacy(self):
        self._test_adjust_timeout(variant="adjust_timeout_for_session")

    def _test_adjust_timeout(self, variant=None):
        session = self._session_new()
        serialized_1 = (
            session.from_redis()
        )  # this executes a second get, the session doesn't save the raw value

        timeout_1 = serialized_1["t"]
        self.assertEqual(timeout_1, self.timeout)
        timestamp_created = serialized_1["c"]
        timestamp_expiry_initial = serialized_1["x"]
        if not variant:
            session.adjust_session_timeout(self.adjusted_timeout)
        else:
            getattr(session, variant)(self.adjusted_timeout)
        session._deferred_callback(None)  # trigger the real session's set/setex
        self.assertEqual(len(session.redis._history), 3)
        self.assertEqual(session.redis._history[0][0], "get")
        self.assertEqual(session.redis._history[1][0], "get")
        self.assertEqual(session.redis._history[2][0], "setex")

        serialized_2 = (
            session.from_redis()
        )  # this executes a second get, the session doesn't save the raw value
        self.assertEqual(len(session.redis._history), 4)
        self.assertEqual(session.redis._history[3][0], "get")

        timestamp_expiry_new = serialized_2["x"]
        timeout_2 = serialized_2["t"]
        self.assertEqual(timeout_2, self.adjusted_timeout)

        timestamp_expiry_expected = timestamp_created + self.adjusted_timeout
        self.assertEqual(timestamp_expiry_new, timestamp_expiry_expected)

        # okay now check that redis got the correct commands
        # get, [get], setex, [get] || [] are our test commands, not part of the flow
        self.assertEqual(len(session.redis._history), 4)


class TestRedisSessionNew_TimeoutAdjustments_B(
    _TestRedisSessionNew__MIXIN_A, _TestRedisSessionNew_CORE, unittest.TestCase
):
    """these are 1.4x+ tests"""

    PYTHON_EXPIRES = True
    set_redis_ttl = True
    timeout = 3
    timeout_trigger = 1
    adjusted_timeout = 4

    def test_timeout_trigger(self):
        self._test_timeout_trigger()

    def test_timeout_trigger__legacy(self):
        self._test_timeout_trigger(variant="adjust_timeout_for_session")

    def _test_timeout_trigger(self, variant=None):
        """
        python -munittest pyramid_session_redis.tests.test_session.TestRedisSessionNew_TimeoutAdjustments_B.test_timeout_trigger
        """
        session = self._session_new()

        # this should set:
        # session.managed_dict = {'FOO': '1'}
        session["FOO"] = "1"
        session._deferred_callback(None)  # trigger the real session's set/setex

        serialized_1 = session.from_redis()
        timeout_1 = serialized_1["t"]
        self.assertEqual(timeout_1, self.timeout)
        timestamp_created = serialized_1["c"]
        timestamp_expiry_initial = serialized_1["x"]
        if not variant:
            session.adjust_session_timeout(self.adjusted_timeout)
        else:
            getattr(session, variant)(self.adjusted_timeout)
        session._deferred_callback(None)  # trigger the real session's set/setex

        serialized_2 = session.from_redis()
        timestamp_expiry_new = serialized_2["x"]
        timeout_2 = serialized_2["t"]
        self.assertEqual(timeout_2, self.adjusted_timeout)

        timestamp_expiry_expected = timestamp_created + self.adjusted_timeout
        self.assertEqual(timestamp_expiry_new, timestamp_expiry_expected)

        # okay now check that redis got the correct commands
        # 0 - GET
        # 1 - SETEX
        # 2 - GET
        # 3 - SETEX
        # 4 - GET
        self.assertEqual(len(session.redis._history), 5)
        self.assertEqual(session.redis._history[1][0], "setex")  # this is our foo
        self.assertEqual(session.redis._history[1][2], self.timeout)
        self.assertEqual(session.redis._history[3][0], "setex")
        self.assertEqual(session.redis._history[3][2], self.adjusted_timeout)

        # sleep post-trigger and pre-expire
        # this should create a new trigger, because we wake up within 1 second...
        time.sleep(3)

        func_new_session = self._factory_new_session(session)
        session2 = self._session_get(session, func_new_session)
        self.assertEqual(session2.managed_dict["FOO"], "1")
        session2._deferred_callback(None)  # trigger the real session's set/setex

        # okay now check that redis got the correct commands
        # 0 - GET
        # 1 - SETEX
        # 2 - GET
        # 3 - SETEX
        # 4 - GET
        # 5 - GET
        # 6 - SETEX -- this is triggered by the _deferred_callback beine within the timeout
        self.assertEqual(len(session.redis._history), 7)

        # now check that the timeout is in the payload...
        session2_redis = session2.from_redis()
        self.assertEqual(
            session2_redis["x"], (session2.timestamp + self.adjusted_timeout)
        )

        sleeptime = session2_redis["x"] - int(time.time()) + 1
        print("sleeping for ", sleeptime)
        time.sleep(sleeptime)

        with self.assertRaises(InvalidSession_PayloadTimeout):
            session3 = self._makeOne(
                session.redis,
                self.session_id,
                True,  # new
                func_new_session,
                set_redis_ttl=self.set_redis_ttl,
                timeout_trigger=self.timeout_trigger,
                timeout=self.timeout,
                python_expires=self.PYTHON_EXPIRES,
            )

        # okay now check that redis got the correct commands
        # 0 - GET
        # 1 - SETEX
        # 2 - GET
        # 3 - SETEX
        # 4 - GET
        # 5 - GET
        # 6 - SETEX -- this is triggered by the _deferred_callback beine within the timeout
        # 7 - GET
        # 8 - GET
        self.assertEqual(len(session.redis._history), 9)


class TestRedisSessionNew_RedisTTL_Classic(
    _TestRedisSessionNew__MIXIN_A, _TestRedisSessionNew_CORE, unittest.TestCase
):
    """these are 1.4x+ tests"""

    PYTHON_EXPIRES = False
    set_redis_ttl = True
    set_redis_ttl_readheavy = False
    timeout = 1
    timeout_trigger = None

    def test_refresh(self):
        """
        python -munittest pyramid_session_redis.tests.test_session.TestRedisSessionNew_RedisTTL_Classic.test_refresh
        """
        session = self._session_new()

        # okay now check that redis got the correct commands
        # 0 - GET
        # no setex, because the session is empty
        self.assertEqual(len(session.redis._history), 1)
        self.assertEqual(session.redis._history[0][0], "get")  # this is our foo

        # but if we store something it would have been different...
        session["FOO"] = "1"
        session._deferred_callback(None)  # trigger the real session's set/setex

        # 0 - GET
        # 1 - SETEX
        self.assertEqual(len(session.redis._history), 2)
        self.assertEqual(session.redis._history[1][0], "setex")  # this is our foo
        self.assertEqual(session.redis._history[1][2], self.timeout)

        func_new_session = self._factory_new_session(session)
        session2 = self._session_get(session, func_new_session)
        self.assertEqual(session2.managed_dict["FOO"], "1")
        session2._deferred_callback(None)  # trigger the real session's expire

        # 0 - GET
        # 1 - SETEX
        # 2 - GET
        # 3 - EXPIRE
        self.assertEqual(len(session.redis._history), 4)
        self.assertEqual(session.redis._history[2][0], "get")
        self.assertEqual(session.redis._history[3][0], "expire")

        # will sleep for a moment...
        sleepy = self.timeout - 1
        print("will sleep for:", sleepy)
        time.sleep(sleepy)

        session3 = self._session_get(session, func_new_session)
        self.assertEqual(session3.managed_dict["FOO"], "1")
        session3._deferred_callback(
            None
        )  # trigger the real session's set/setex (but don't)

        # 0 - GET
        # 1 - SETEX
        # 2 - GET
        # 3 - EXPIRE
        # 4 - GET
        # 5 - EXPIRE
        self.assertEqual(len(session.redis._history), 6)
        self.assertEqual(session.redis._history[4][0], "get")
        self.assertEqual(session.redis._history[5][0], "expire")


class TestRedisSessionNew_RedisTTL_ReadHeavy(
    _TestRedisSessionNew__MIXIN_A, _TestRedisSessionNew_CORE, unittest.TestCase
):
    """these are 1.4x+ tests"""

    PYTHON_EXPIRES = False
    set_redis_ttl = True
    set_redis_ttl_readheavy = True
    timeout = 4

    def test_refresh(self):
        """
        python -munittest pyramid_session_redis.tests.test_session.TestRedisSessionNew_RedisTTL_ReadHeavy.test_refresh
        """
        session = self._session_new()

        # okay now check that redis got the correct commands
        # 0 - pipline.GET
        # 1 - pipline.EXPIRE
        # no setex, because the session is empty
        self.assertEqual(len(session.redis._history), 2)

        # but if we store something it would have been different...
        session["FOO"] = "1"
        session._deferred_callback(None)  # trigger the real session's set/setex

        # 0 - pipline.GET
        # 1 - pipline.EXPIRE
        # 2 - SETEX
        self.assertEqual(len(session.redis._history), 3)
        self.assertEqual(session.redis._history[0][0], "pipeline.get")
        self.assertEqual(session.redis._history[1][0], "pipeline.expire")
        self.assertEqual(session.redis._history[2][0], "setex")  # this is our foo
        self.assertEqual(session.redis._history[2][2], self.timeout)

        func_new_session = self._factory_new_session(session)
        session2 = self._session_get(session, func_new_session)
        self.assertEqual(session2.managed_dict["FOO"], "1")
        session2._deferred_callback(
            None
        )  # trigger the real session's set/setex (but don't)

        # 0 - pipline.GET
        # 1 - pipline.EXPIRE
        # 2 - SETEX
        # 3 - pipline.GET
        # 4 - pipline.EXPIRE
        self.assertEqual(len(session.redis._history), 5)
        self.assertEqual(session.redis._history[3][0], "pipeline.get")
        self.assertEqual(session.redis._history[4][0], "pipeline.expire")

        # will sleep for a moment...
        sleepy = self.timeout - 1
        print("will sleep for:", sleepy)
        time.sleep(sleepy)

        session3 = self._session_get(session, func_new_session)
        self.assertEqual(session3.managed_dict["FOO"], "1")
        session3._deferred_callback(
            None
        )  # trigger the real session's set/setex (but don't)

        # 0 - pipline.GET
        # 1 - pipline.EXPIRE
        # 2 - SETEX
        # 3 - pipline.GET
        # 4 - pipline.EXPIRE
        # 5 - pipline.GET
        # 6 - pipline.EXPIRE
        self.assertEqual(len(session.redis._history), 7)
        self.assertEqual(session.redis._history[5][0], "pipeline.get")
        self.assertEqual(session.redis._history[6][0], "pipeline.expire")
