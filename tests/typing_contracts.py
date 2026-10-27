"""Consumer-side checks, run by mypy rather than pytest."""

from datetime import timedelta
from typing import Optional

from pyramid_session_redis.session import RedisSession
from pyramid_session_redis.util import TYPING_SESSION_ID


def public_contract(session: RedisSession) -> None:
    session_id: TYPING_SESSION_ID = session.session_id
    timeout: Optional[int] = session.timeout
    expires: Optional[int] = session.expires
    version: Optional[int] = session.version
    session.adjust_cookie_max_age(None)
    session.adjust_cookie_max_age(timedelta(seconds=60))
    session.adjust_session_timeout(None)
    session.adjust_cookie_max_age("invalid")  # type: ignore[arg-type]
    session.adjust_session_timeout("invalid")  # type: ignore[arg-type]
    session.__delitem__(None)  # type: ignore[arg-type]
    session.__getitem__(None)  # type: ignore[index]
    # Consume the annotations without imposing a concrete lazy-ID type.
    _ = session_id, timeout, expires, version
