"""Run the same protocol tests against Redis and Valkey in CI.

Set PSR_TEST_REDIS_URL to opt in locally. Only UUID-prefixed keys are removed.
"""

from functools import partial
import os
import pickle
from unittest.mock import patch
from uuid import uuid4

from pyramid import testing
from pyramid.response import Response
import pytest
from redis import StrictRedis

from pyramid_session_redis import RedisSessionFactory
from pyramid_session_redis.exceptions import SessionConflict
from pyramid_session_redis.util import prefixed_id


@pytest.fixture
def backend():
    url = os.environ.get("PSR_TEST_REDIS_URL")
    if not url:
        pytest.skip("Set PSR_TEST_REDIS_URL to run Redis/Valkey backend tests")
    client = StrictRedis.from_url(url, socket_timeout=2)
    client.ping()
    prefix = "psr-test-%s:" % uuid4().hex
    yield client, url, prefix
    keys = list(client.scan_iter(match=prefix + "*"))
    if keys:
        client.delete(*keys)
    client.connection_pool.disconnect()


def factory_for(backend, **kwargs):
    _, url, prefix = backend
    return RedisSessionFactory(
        secret="backend-test-secret",
        redis_url=url,
        id_generator=partial(prefixed_id, prefix=prefix),
        **kwargs,
    )


def finish(request):
    request.exception = None
    response = Response()
    request._process_response_callbacks(response)
    request._process_finished_callbacks()
    return response


def existing_request(factory, session_id):
    request = testing.DummyRequest()
    with patch(
        "pyramid_session_redis._get_session_id_from_cookie", return_value=session_id
    ):
        session = factory(request)
    assert session.new is False
    return request, session


@pytest.mark.parametrize("optimistic", [False, True])
def test_signed_cookie_roundtrip_nested_changes_and_invalidation(backend, optimistic):
    client, _, _ = backend
    factory = factory_for(backend, timeout=120, optimistic_concurrency=optimistic)
    request = testing.DummyRequest()
    session = factory(request)
    session["user"] = {"visits": 1}
    response = finish(request)
    session_id = session.ensure_id()
    assert 0 < client.ttl(session_id) <= 120
    assert "Set-Cookie" in response.headers

    # Use the actual signed cookie for the next request.
    cookie = response.headers["Set-Cookie"].split(";", 1)[0].split("=", 1)[1]
    second_request = testing.DummyRequest(cookies={"session": cookie})
    second = factory(second_request)
    assert second.new is False
    second["user"]["visits"] += 1
    finish(second_request)
    assert pickle.loads(client.get(session_id))["m"]["user"]["visits"] == 2
    second.invalidate()
    assert client.get(session_id) is None


def test_readheavy_pipeline_loads_data_and_refreshes_ttl(backend):
    client, _, _ = backend
    factory = factory_for(
        backend, timeout=120, python_expires=False, set_redis_ttl_readheavy=True
    )
    request = testing.DummyRequest()
    first = factory(request)
    first["value"] = 1
    finish(request)
    session_id = first.ensure_id()
    client.expire(session_id, 10)
    second_request, second = existing_request(factory, session_id)
    assert second["value"] == 1
    assert client.ttl(session_id) > 100
    finish(second_request)


@pytest.mark.parametrize("disable_with", [0, None])
def test_timeout_can_be_disabled_on_a_live_backend(backend, disable_with):
    client, _, _ = backend
    factory = factory_for(backend, timeout=120)
    request = testing.DummyRequest()
    session = factory(request)
    session["value"] = 1
    finish(request)
    _, second = existing_request(factory, session.ensure_id())
    second.adjust_session_timeout(disable_with)
    second.do_persist()
    assert client.ttl(second.ensure_id()) == -1
    assert "x" not in pickle.loads(client.get(second.ensure_id()))


@pytest.mark.parametrize("invalidate", [False, True])
def test_optimistic_concurrency_rejects_stale_writes(backend, invalidate):
    client, _, _ = backend
    factory = factory_for(backend, optimistic_concurrency=True)
    request = testing.DummyRequest()
    first = factory(request)
    first["user"] = "alice"
    finish(request)
    session_id = first.ensure_id()
    _, second = existing_request(factory, session_id)
    _, third = existing_request(factory, session_id)
    if invalidate:
        second.invalidate()
    else:
        second["user"] = "bob"
        second.do_persist()
    third["user"] = "stale"
    with pytest.raises(SessionConflict):
        third.do_persist()
    if invalidate:
        assert not client.exists(session_id)
    else:
        assert pickle.loads(client.get(session_id))["m"]["user"] == "bob"


def test_watch_detects_a_change_between_compare_and_exec(backend):
    client, _, _ = backend
    factory = factory_for(backend, optimistic_concurrency=True)
    request = testing.DummyRequest()
    session = factory(request)
    session["user"] = "alice"
    finish(request)
    _, session = existing_request(factory, session.ensure_id())
    session["user"] = "stale"
    original_pipeline = session.redis.pipeline

    def racing_pipeline():
        pipeline = original_pipeline()
        execute = pipeline.execute

        def concurrent_execute():
            client.delete(session.ensure_id())
            return execute()

        pipeline.execute = concurrent_execute
        return pipeline

    with patch.object(session.redis, "pipeline", side_effect=racing_pipeline):
        with pytest.raises(SessionConflict):
            session.do_persist()
    assert not client.exists(session.ensure_id())


def test_missing_readheavy_session_falls_back_to_lazy_creation(backend):
    factory = factory_for(
        backend, timeout=120, python_expires=False, set_redis_ttl_readheavy=True
    )
    request = testing.DummyRequest()
    with patch(
        "pyramid_session_redis._get_session_id_from_cookie",
        return_value=backend[2] + "missing",
    ):
        session = factory(request)
    assert session.new is True
    assert session.managed_dict == {}
