# -*- coding: utf-8 -*-
# stdlib
import pickle
from typing import Any
from typing import Dict
from typing import Optional
import warnings

# pypi
from redis.exceptions import WatchError

warnings.filterwarnings(
    "ignore", message=".*pkg_resources.declare_namespace.*", category=DeprecationWarning
)
warnings.filterwarnings(
    "ignore", message=".*pkg_resources is deprecated.*", category=DeprecationWarning
)


# ==============================================================================


class DummySessionState(object):
    please_persist = None
    please_refresh = None


class DummySession(object):
    def __init__(
        self,
        session_id,
        redis,
        timeout=300,
        serialize=pickle.dumps,
    ):
        self.session_id = session_id
        self.redis = redis
        self.timeout = timeout
        self.serialize = serialize
        self.managed_dict = {}
        self.created = float()
        self._set_redis_ttl = True
        self._session_state = DummySessionState()

    def to_redis(self):
        data = {"m": self.managed_dict, "c": self.created}
        if self.timeout:
            data["t"] = self.timeout
        return self.serialize(data)


class DummyRedis(object):
    url: Optional[str]
    timeouts: Dict[str, int]
    _store: Dict[str, Any]
    opts: Dict[str, Any]

    def __init__(self, raise_watcherror=False, **kw):
        self.url = None
        self.timeouts = {}
        self._store = {}
        self.__dict__.update(kw)
        self._history = []
        self.pipeline = lambda: DummyPipeline(
            self._store, self, raise_watcherror
        )  # noqa: E501

    def _history_reset(self):
        # test method. fake. used for tests against the actual redis operations
        self._history = []

    @classmethod
    def from_url(cls, url, **opts):
        redis = DummyRedis()
        redis.url = url
        redis.opts = opts
        return redis

    def get(self, key):
        self._history.append(("get", key))
        return self._store.get(key)

    def set(self, key, value, debug=None):
        self._store[key] = value
        self._history.append(("set", key, value, debug))

    def setex(self, key, timeout, value, debug=None):
        # Redis is `key, value, timeout`
        # StrictRedis is `key, timeout, value`
        # this package uses StrictRedis
        self._store[key] = value
        self.timeouts[key] = timeout
        self._history.append(("setex", key, timeout, value, debug))

    def delete(self, *keys):
        for key in keys:
            self._store.pop(key, None)

    def exists(self, key):
        return key in self._store

    def expire(self, key, timeout):
        self.timeouts[key] = timeout
        self._history.append(("expire", key, timeout))

    def ttl(self, key):
        return self.timeouts.get(key)

    def keys(self):
        return self._store.keys()


class DummyPipeline(object):
    def __init__(self, store, redis_con, raise_watcherror=False):
        self._store = store
        self.raise_watcherror = raise_watcherror
        self._redis_con = redis_con
        self._history = []
        self._commands = []
        self._watching = False
        self._in_multi = False

    def __enter__(self):
        return self

    def __exit__(self, *arg, **kwarg):
        pass

    def multi(self):
        self._in_multi = True

    def set(self, key, value, debug=None):
        self._commands.append(("set", key, value))
        self._history.append(("set", key, debug))
        self._redis_con._history.append(("pipeline.set", key, value, debug))

    def get(self, key):
        self._history.append(("get", key))
        self._redis_con._history.append(("pipeline.get", key))
        if self._watching and not self._in_multi:
            return self._store.get(key)
        self._commands.append(("get", key))
        return self

    def expire(self, key, timeout):
        self._commands.append(("expire", key, timeout))
        self._history.append(("expire", key, timeout))
        self._redis_con._history.append(("pipeline.expire", key, timeout))

    def setex(self, key, timeout, value, debug=None):
        self._commands.append(("setex", key, timeout, value))
        self._history.append(("setex", key, timeout, debug))
        self._redis_con._history.append(
            ("pipeline.setex", key, timeout, value, debug)
        )  # noqa: E501

    def watch(self, key):
        if self.raise_watcherror:
            raise WatchError
        self._watching = True

    def execute(self):
        results = []
        for command in self._commands:
            op, key = command[:2]
            if op == "get":
                results.append(self._store.get(key))
            elif op == "set":
                self._store[key] = command[2]
                results.append(True)
            elif op == "setex":
                self._store[key] = command[3]
                self._redis_con.timeouts[key] = command[2]
                results.append(True)
            elif op == "expire":
                self._redis_con.timeouts[key] = command[2]
                results.append(key in self._store)
        self._commands.clear()
        return results
