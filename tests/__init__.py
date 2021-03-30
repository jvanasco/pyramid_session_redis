# -*- coding: utf-8 -*-

# pypi
from redis.exceptions import WatchError

# local
from pyramid_session_redis.compat import pickle


# ==============================================================================


class DummySessionState(object):
    please_persist = None
    please_refresh = None


class DummySession(object):
    def __init__(self, session_id, redis, timeout=300, serialize=pickle.dumps):
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
    def __init__(self, raise_watcherror=False, **kw):
        self.url = None
        self.timeouts = {}
        self.store = {}
        self.__dict__.update(kw)
        self._history = []
        self.pipeline = lambda: DummyPipeline(self.store, self, raise_watcherror)

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
        return self.store.get(key)

    def set(self, key, value, debug=None):
        self.store[key] = value
        self._history.append(("set", key, value, debug))

    def setex(self, key, timeout, value, debug=None):
        # Redis is `key, value, timeout`
        # StrictRedis is `key, timeout, value`
        # this package uses StrictRedis
        self.store[key] = value
        self.timeouts[key] = timeout
        self._history.append(("setex", key, timeout, value, debug))

    def delete(self, *keys):
        for key in keys:
            del self.store[key]

    def exists(self, key):
        return key in self.store

    def expire(self, key, timeout):
        self.timeouts[key] = timeout
        self._history.append(("expire", key, timeout))

    def ttl(self, key):
        return self.timeouts.get(key)

    def keys(self):
        return self.store.keys()


class DummyPipeline(object):
    def __init__(self, store, redis_con, raise_watcherror=False):
        self.store = store
        self.raise_watcherror = raise_watcherror
        self._redis_con = redis_con
        self._history = []

    def __enter__(self):
        return self

    def __exit__(self, *arg, **kwarg):
        pass

    def multi(self):
        pass

    def set(self, key, value, debug=None):
        self.store[key] = value
        self._history.append(("set", key, debug))
        self._redis_con._history.append(("pipeline.set", key, value, debug))

    def get(self, key):
        self._history.append(("get", key))
        self._redis_con._history.append(("pipeline.get", key))
        return self.store.get(key)

    def expire(self, key, timeout):
        self._history.append(("expire", key, timeout))
        self._redis_con._history.append(("pipeline.expire", key, timeout))

    def setex(self, key, timeout, value, debug=None):
        self.store[key] = value
        self._history.append(("setex", key, timeout, debug))
        self._redis_con._history.append(("pipeline.setex", key, timeout, value, debug))

    def watch(self, key):
        if self.raise_watcherror:
            raise WatchError

    def execute(self):
        pass
