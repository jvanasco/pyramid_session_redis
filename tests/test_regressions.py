"""Session lifecycle regressions with deterministic clocks and command histories."""

import datetime
import pickle
from typing import Any
from typing import Dict
from unittest.mock import patch

from pyramid import testing
from pyramid.response import Response
import pytest

from pyramid_session_redis import RedisSessionFactory
from pyramid_session_redis.exceptions import InvalidSession_DeserializationError
from pyramid_session_redis.exceptions import InvalidSession_PayloadTimeout
from pyramid_session_redis.exceptions import RawDeserializationError
from pyramid_session_redis.exceptions import SessionConflict
from pyramid_session_redis.session import RedisSession
from pyramid_session_redis.util import _parse_settings
from pyramid_session_redis.util import LazyCreateSession
from . import as_redis_client
from . import DummyRedis


@pytest.fixture
def clock():
    with patch("pyramid_session_redis.session.int_time", return_value=1050), patch(
        "pyramid_session_redis.util.int_time", return_value=1050
    ):
        yield


@pytest.fixture
def redis():
    client = DummyRedis()
    client.set(
        "sid",
        pickle.dumps({"m": {"user": "alice"}, "c": 1000, "v": 1, "t": 100, "x": 1100}),
    )
    client._history_reset()
    return client


def make_session(redis, **kwargs):
    return RedisSession(
        redis=redis,
        session_id="sid",
        new=False,
        new_session=lambda: "new",
        timeout=100,
        **kwargs,
    )


@pytest.mark.parametrize(
    "value,expected",
    [("0.5", 0.5), (0.5, 0.5), ("None", None), (None, None), ("0", 0.0)],
)
def test_socket_timeout_parser(value, expected):
    options = _parse_settings(
        {
            "redis.sessions.secret": "secret",
            "redis.sessions.redis_socket_timeout": value,
        }
    )
    assert options["redis_socket_timeout"] == expected


def test_readheavy_executes_pipeline(redis, clock):
    payload = pickle.loads(redis.get("sid"))
    payload.pop("x")
    redis.set("sid", pickle.dumps(payload))
    redis._history_reset()
    session = make_session(redis, python_expires=False, set_redis_ttl_readheavy=True)
    assert session["user"] == "alice"
    session._deferred_callback(testing.DummyRequest())
    assert [entry[0] for entry in redis._history] == ["pipeline.get", "pipeline.expire"]


def test_expiry_refresh_does_not_depend_on_change_detection(redis, clock):
    session = make_session(redis, python_expires=True, detect_changes=False)
    assert session.get("user") == "alice"
    session._deferred_callback(testing.DummyRequest())
    assert pickle.loads(redis.get("sid"))["x"] == 1150
    with patch("pyramid_session_redis.session.int_time", return_value=1101):
        assert make_session(redis, python_expires=True)["user"] == "alice"


def test_explicit_expiry_is_preserved(redis, clock):
    session = make_session(redis, python_expires=True)
    session.adjust_session_expires(1060)
    session.do_persist()
    assert pickle.loads(redis.get("sid"))["x"] == 1060
    with patch("pyramid_session_redis.session.int_time", return_value=1061):
        with pytest.raises(InvalidSession_PayloadTimeout):
            make_session(redis, python_expires=True)


@pytest.mark.parametrize("timeout", [0, None])
def test_disabling_timeout_clears_python_and_redis_expiry(redis, clock, timeout):
    session = make_session(redis, python_expires=True)
    session.adjust_session_timeout(timeout)
    session.do_persist()
    assert "x" not in pickle.loads(redis.get("sid"))
    assert "t" not in pickle.loads(redis.get("sid"))
    assert redis._history[-3][0] == "set"


def test_negative_timeout_is_rejected(redis, clock):
    with pytest.raises(ValueError):
        RedisSessionFactory(secret="secret", timeout=-1)
    with pytest.raises(ValueError):
        make_session(redis).adjust_session_timeout(-1)
    with pytest.raises(ValueError):
        RedisSession(
            redis=as_redis_client(redis),
            session_id=LazyCreateSession,
            new=True,
            new_session=lambda: "new",
            timeout=-1,
        )


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"v": 1, "c": 1000},
        {"v": "bad", "m": {}, "c": 1000},
        {"v": 1, "m": {}, "c": 1000, "t": "bad"},
    ],
)
@pytest.mark.parametrize("recover", [True, False])
def test_malformed_envelope_has_consistent_error(redis, clock, payload, recover):
    redis.set("sid", pickle.dumps(payload))
    expected = (
        InvalidSession_DeserializationError if recover else RawDeserializationError
    )
    with pytest.raises(expected):
        make_session(redis, deserialized_fails_new=recover)


def test_decoded_responses_fail_clearly(redis):
    redis.set("sid", "text")
    with pytest.raises(RawDeserializationError, match="decode_responses=False"):
        make_session(redis)


def test_default_writes_keep_the_fast_path(redis, clock):
    session = make_session(redis)
    session["counter"] = 1
    session.do_persist()
    assert [entry[0] for entry in redis._history] == ["get", "setex"]


@pytest.mark.parametrize("invalidate", [True, False])
@pytest.mark.parametrize("set_redis_ttl", [True, False])
def test_optimistic_writes_reject_removed_or_changed_payload(
    redis, clock, invalidate, set_redis_ttl
):
    first = make_session(
        redis, optimistic_concurrency=True, set_redis_ttl=set_redis_ttl
    )
    second = make_session(
        redis, optimistic_concurrency=True, set_redis_ttl=set_redis_ttl
    )
    if invalidate:
        first.invalidate()
    else:
        first["counter"] = 1
        first.do_persist()
    second["counter"] = 2
    with pytest.raises(SessionConflict):
        second.do_persist()
    if invalidate:
        assert not redis.exists("sid")
    else:
        assert pickle.loads(redis.get("sid"))["m"]["counter"] == 1


def test_optimistic_snapshot_updates_after_a_successful_write(redis, clock):
    session = make_session(redis, optimistic_concurrency=True)
    session["counter"] = 1
    session.do_persist()
    session["counter"] = 2
    session.do_persist()
    assert pickle.loads(redis.get("sid"))["m"]["counter"] == 2


def test_factory_passes_concurrency_option_to_new_and_existing_sessions(redis, clock):
    options = _parse_settings(
        {
            "redis.sessions.secret": "secret",
            "redis.sessions.optimistic_concurrency": "true",
        }
    )
    factory = RedisSessionFactory(
        redis_client_callable=lambda *a, **kw: redis, **options
    )
    request = testing.DummyRequest()
    new = factory(request)
    assert new.session_id is LazyCreateSession
    new["user"] = "alice"
    new.do_persist()
    new.do_persist()
    with patch(
        "pyramid_session_redis._get_session_id_from_cookie", return_value=new.session_id
    ):
        existing = factory(testing.DummyRequest())
    assert existing._optimistic_concurrency is True


def test_decorated_methods_keep_names():
    assert RedisSession.adjust_cookie_max_age.__name__ == "adjust_cookie_max_age"


@pytest.mark.parametrize(
    "options,message",
    [
        ({"timeout": None, "python_expires": False}, "requires"),
        ({"timeout": 0, "python_expires": False}, "requires"),
        ({"set_redis_ttl": False, "python_expires": False}, "requires"),
        ({"python_expires": True}, "not compatible"),
        ({"python_expires": False, "timeout_trigger": 20}, "not compatible"),
    ],
)
@pytest.mark.parametrize("factory_api", [True, False])
def test_invalid_readheavy_configuration_is_rejected(
    redis, options, message, factory_api
):
    session_options: Dict[str, Any] = {
        "timeout": 1200,
        "python_expires": True,
        "set_redis_ttl_readheavy": True,
    }
    session_options.update(options)
    with pytest.raises(ValueError, match=message):
        if factory_api:
            RedisSessionFactory(secret="secret", **session_options)
        else:
            RedisSession(
                redis=as_redis_client(redis),
                session_id="sid",
                new=False,
                new_session=lambda: "new",
                **session_options,
            )
    assert redis._history == []


def test_factory_zero_timeout_creates_a_session_without_expiry(redis, clock):
    factory = RedisSessionFactory(
        secret="secret", timeout=0, redis_client_callable=lambda *a, **kw: redis
    )
    session = factory(testing.DummyRequest())
    session["user"] = "alice"
    session.do_persist()
    payload = pickle.loads(redis.get(session.ensure_id()))
    assert "x" not in payload
    assert "t" not in payload
    assert session.timeout is None
    assert all(entry[0] != "setex" for entry in redis._history)


def test_refreshing_a_lazy_session_does_not_allocate_an_id(redis, clock):
    factory = RedisSessionFactory(
        secret="secret", redis_client_callable=lambda *a, **kw: redis
    )
    session = factory(testing.DummyRequest())
    session.do_refresh()
    assert session.session_id is LazyCreateSession
    assert redis._history == []


@pytest.mark.parametrize("timestamp,expected_expiry", [(1079, 1100), (1080, 1180)])
def test_read_only_expiry_refresh_respects_trigger_boundary(
    redis, timestamp, expected_expiry
):
    with patch("pyramid_session_redis.session.int_time", return_value=timestamp), patch(
        "pyramid_session_redis.util.int_time", return_value=timestamp
    ):
        session = make_session(
            redis, python_expires=True, detect_changes=False, timeout_trigger=20
        )
        assert session.get("user") == "alice"
        session._deferred_callback(testing.DummyRequest())
    assert pickle.loads(redis.get("sid"))["x"] == expected_expiry


def test_factory_cookie_policy_reaches_the_response(redis, clock):
    factory = RedisSessionFactory(
        secret="secret",
        redis_client_callable=lambda *a, **kw: redis,
        cookie_secure=True,
        cookie_httponly=True,
        cookie_samesite="lax",
        cookie_comment="session-policy",
        cookie_expires=datetime.timedelta(days=1),
    )
    request = testing.DummyRequest(exception=None)
    session = factory(request)
    session["user"] = "alice"
    response = Response()
    request._process_response_callbacks(response)
    request._process_finished_callbacks()
    cookie = response.headers["Set-Cookie"].lower()
    for attribute in (
        "; secure",
        "; httponly",
        "; samesite=lax",
        "comment=session-policy",
        "expires=",
    ):
        assert attribute in cookie
