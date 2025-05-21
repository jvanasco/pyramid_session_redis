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
    "redis.sessions.db": 9,
    "redis.sessions.serialize": "pickle.dumps",
    "redis.sessions.deserialize": "pickle.loads",
    "redis.sessions.id_generator": _id_path,
    "redis.sessions.client_callable": _client_path,
    "redis.sessions.func_invalid_logger": _invalid_logger,
}

LIVE_PSR_CONFIG = TEST_PSR_CONFIG.copy()
del LIVE_PSR_CONFIG["redis.sessions.id_generator"]
del LIVE_PSR_CONFIG["redis.sessions.client_callable"]


class CustomCookieSigner(SignedSerializerInterface):

    def dumps(self, s: str) -> bytes:
        return s.encode()

    def loads(self, s: bytes) -> str:
        return s.decode()
