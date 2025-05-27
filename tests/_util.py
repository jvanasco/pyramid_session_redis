# stdlib
from typing import Dict
from typing import Union

# local
from pyramid_session_redis.util import SignedSerializerInterface

# ------------------------------------------------------------------------------


# dotted paths to dummy callables
_id_path = "tests.test_config.dummy_id_generator"
_client_path = "tests.test_config.dummy_client_callable"
_invalid_logger = "tests.test_config.dummy_invalid_logger"

TEST_PSR_CONFIG: Dict[str, Union[str, int]] = {
    "redis.sessions.secret": "supersecret",
    "redis.sessions.serialize": "pickle.dumps",
    "redis.sessions.deserialize": "pickle.loads",
    "redis.sessions.id_generator": _id_path,
    "redis.sessions.redis_client_callable": _client_path,
    "redis.sessions.redis_db": 9,
    "redis.sessions.func_invalid_logger": _invalid_logger,
}

LIVE_PSR_CONFIG = TEST_PSR_CONFIG.copy()
del LIVE_PSR_CONFIG["redis.sessions.id_generator"]
del LIVE_PSR_CONFIG["redis.sessions.redis_client_callable"]


class CustomCookieSigner(SignedSerializerInterface):

    def dumps(self, s: str) -> bytes:
        return s.encode()

    def loads(self, s: bytes) -> str:
        return s.decode()


def _parse_cookie(header: str) -> Dict:
    morsels = {}
    # ('Set-Cookie', 'session=; Max-Age=0; Path=/; expires=Wed, 31-Dec-97 23:59:59 GMT')])
    _items = [i.strip() for i in header.split(";")]
    for _it in _items:
        (k, v) = [i.strip() for i in _it.split("=", 1)]  # max 2 items
        morsels[k.lower()] = v
    return morsels


def is_cookie_setter(cookie: str) -> bool:
    assert cookie != "session=; Max-Age=0; Path=/; expires=Wed, 31-Dec-97 23:59:59 GMT"
    morsels = _parse_cookie(cookie)
    assert morsels["session"] != ""  # not empty string
    if "max-age" in morsels:
        assert int(morsels["max-age"]) >= 1
    # expires=Wed, 31-Dec-97 23:59:59 GMT
    return True


def is_cookie_unsetter(cookie: str) -> bool:
    assert cookie == "session=; Max-Age=0; Path=/; expires=Wed, 31-Dec-97 23:59:59 GMT"
    # morsels = _parse_cookie(cookie)
    # assert morsels["session"] == ""  # empty string
    # if "max-age" in morsels:
    #    assert int(morsels["max-age"]) <= 0
    # # expires=Wed, 31-Dec-97 23:59:59 GMT
    return True
