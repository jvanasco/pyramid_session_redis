# -*- coding: utf-8 -*-

# stdlib
import hashlib
import pickle
from secrets import token_hex
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import Dict
from typing import Iterator
from typing import List
from typing import Optional
from typing import overload
from typing import Tuple
from typing import TYPE_CHECKING
from typing import Union

# pypi
from pyramid.decorator import reify
from pyramid.interfaces import ISession
from typing_extensions import Literal
from zope.interface import implementer

# local
from .compat import _PY_3_9_OR_ABOVE
from .exceptions import InvalidSession_DeserializationError
from .exceptions import InvalidSession_Lazycreate
from .exceptions import InvalidSession_NotInBackend
from .exceptions import InvalidSession_PayloadLegacy
from .exceptions import InvalidSession_PayloadTimeout
from .exceptions import RawDeserializationError
from .util import decode_session_payload as decode_session_payload_func
from .util import empty_session_payload
from .util import encode_session_payload as encode_session_payload_func
from .util import int_time
from .util import LazyCreateSession
from .util import NotSpecified
from .util import persist
from .util import recookie
from .util import refresh
from .util import SESSION_API_VERSION
from .util import TYPING_COOKIE_EXPIRES
from .util import TYPING_COOKIE_EXPIRES__A
from .util import TYPING_COOKIE_MAX_AGE__A
from .util import TYPING_KEY
from .util import TYPING_SESSION_ID

if TYPE_CHECKING:
    from collections.abc import ItemsView
    from collections.abc import KeysView

    # from pyramid.request import Request  # webob has stubs; pyramid does not
    from redis.client import Redis as RedisClient
    from webob.request import Request

# ==============================================================================


def hashed_value(serialized: bytes) -> str:
    """
    quick hash of serialized data
    only used for comparison to detect changes

    :param serialized: string. serialized data to hash.
    :returns hash: string.
    """
    if _PY_3_9_OR_ABOVE:
        # TODO: this becomes the default when 3.9 is the minimum version
        return hashlib.md5(serialized, usedforsecurity=False).hexdigest()
    return hashlib.md5(serialized).hexdigest()


class _SessionState(object):
    session_id: TYPING_SESSION_ID
    managed_dict: Dict
    created: int
    timeout: Optional[int]
    expires: Optional[int]  # see `util.empty_session_payload`
    version: Optional[int]
    new: bool
    persisted_hash: Optional[str]

    # markers for update
    please_persist: Optional[bool] = None
    please_recookie: Optional[bool] = None
    please_refresh: Optional[bool] = None

    # these markers are consulted in cleanup routines
    dont_persist: Optional[bool] = None
    dont_refresh: Optional[bool] = None

    # optional attributes, not set by default
    cookie_expires: TYPING_COOKIE_EXPIRES__A = (
        NotSpecified  # TYPING_COOKIE_EXPIRES__A includes None
    )
    cookie_max_age: TYPING_COOKIE_MAX_AGE__A = (
        NotSpecified  # TYPING_COOKIE_MAX_AGE__A includes None
    )

    def __init__(
        self,
        session_id: TYPING_SESSION_ID,
        managed_dict: Dict,
        created: int,
        timeout: Optional[int],  # loaded off dict
        expires: Optional[int],  # loaded off dict
        version: Optional[int],  # loaded off dict
        new: bool,
        persisted_hash: Optional[str],
    ):
        """
        all these args are guaranteed to be submitted for the object;
        no need to create default object attributes
        """
        self.session_id = session_id
        self.managed_dict = managed_dict
        self.created = created
        self.timeout = timeout
        self.expires = expires
        self.version = version
        self.new = new
        self.persisted_hash = persisted_hash

    def should_persist(
        self,
        session: "RedisSession",
    ) -> Union[Literal[False], bytes]:
        """
        this is a backup routine
        compares the persisted hash with a hash of the current value
        returns `False` or `serialized_session`

        :param session:
        :returns serialized_session:
        """
        if self.dont_persist:
            return False
        if self.expires and session._timeout_trigger:
            if session.timestamp >= (self.expires - session._timeout_trigger):
                self.please_persist = True
        if self.please_persist:
            return session.to_redis()
        if not session._detect_changes:
            return False
        serialized_session = session.to_redis()
        serialized_hash = hashed_value(serialized_session)
        if serialized_hash == self.persisted_hash:
            return False
        return serialized_session


@implementer(ISession)
class RedisSession(object):
    """
    Implements the Pyramid ISession and IDict interfaces and is returned by
    the ``RedisSessionFactory``.

    Methods that modify the ``dict`` (get, set, update, etc.) are decorated
    with ``@persist`` to update the persisted copy in Redis and reset the
    timeout.

    Methods that are read-only (items, keys, values, etc.) are decorated
    with ``@refresh`` to reset the session's expire time in Redis.

    Methods that request the SetCookie headers are updated are decorated
    with ``@recookie``.

    Session methods make use of the dict methods that already communicate with
    Redis, so they are not decorated.

    Parameters:

    ``redis``
    A Redis connection object.

    ``session_id``
    A unique string associated with the session. Used as a prefix for keys
    and hashes associated with the session.

    ``new``
    Boolean. Whether this session is new (whether it was created in this
    request).

    ``new_session``
    A function that takes no arguments. It should insert a new session into
    Redis under a new session_id, and return that session_id.

    ``new_session_payload``
    UNDER DEVELOPMENT
    A function that takes no arguments.  It is used to to generate a new
    session payload without creating the id (as new_session might)

    ``serialize``
    A function to serialize pickleable Python objects. Default:
    ``cPickle.dumps``.

    ``deserialize``
    The dual of ``serialize``, to convert serialized strings back to Python
    objects. Default: ``cPickle.loads``.

    ``set_redis_ttl``
     If ``True`` sets TTL data in Redis.  If ``False`` assumes Redis is
     configured as a LRU and does not update the expiry data via SETEX.
     Default: ``True``

    ``set_redis_ttl_readheavy``
     If ``True``, sets TTL data in Redis within a PIPELINE via GET+EXPIRE and
     supresses automatic TTL refresh during the deferred cleanup phase. If not
     ``True``, an EXPIRE is sent as a separate action during the deferred
     cleanup phase.  The optimized behavior improves performance on read-heavy
     operations, but may degrade performance on write-heavy operations.  This
     requires a ``timeout`` and ``set_redis_ttl`` to be True; it is not
     compatible with ``timeout_trigger`` or ``python_expires``.
     Default: ``None``

    ``_set_redis_ttl_onexit`` If ``True``, automatically queues a TTL Redis set
    during the cleanup phase. This should be calculated  based on the following
    criteria:
        * self._timeout
        * self._set_redis_ttl
        * not self._timeout_trigger
        * not self._python_expires
        * not self._set_redis_ttl_readheavy
    This is handled as a config option and not a realtime calcluation to save
    some processing. Unit Tests will want to pre-calculate this, otherwise the
    main factory API of this package handles it.
    Default: ``None``

    ``detect_changes``
    If ``True``, supports change detection Default: ``True``

    ``deserialized_fails_new``
    If ``True`` will handle deserializtion errors by creating a new session.

    ``new_payload_func``
    Default ``None``.  Function used to create a new session.

    ``timeout_trigger``
    Default ``None``.  If an int, used to trigger timeouts.

    ``python_expires``
    Default ``None``.  If True, Python is used to manage timeout data.  setting
    ``timeout_trigger`` will enable this.

    """

    redis: "RedisClient"
    _set_redis_ttl: bool
    _set_redis_ttl_readheavy: Optional[bool]
    _detect_changes: bool
    _deserialized_fails_new: Optional[bool]
    _timeout: Optional[int]
    _timeout_trigger: Optional[int]
    _python_expires: Optional[bool]
    _new: bool  # only used for testing/resync

    def __init__(
        self,
        redis: "RedisClient",
        session_id: TYPING_SESSION_ID,
        new: bool,
        new_session: Callable[[], TYPING_SESSION_ID],
        new_payload_func: Optional[Callable[..., Dict]] = None,
        serialize: Callable[
            [
                Dict,
            ],
            bytes,
        ] = pickle.dumps,  # dict->bytes
        deserialize: Callable[[bytes], Dict] = pickle.loads,  # bytes->dict
        set_redis_ttl: bool = True,
        detect_changes: bool = True,
        deserialized_fails_new: Optional[bool] = None,
        encode_session_payload_func: Optional[Callable[..., Dict]] = None,
        decode_session_payload_func: Optional[Callable[[Dict], Dict]] = None,
        timeout: Optional[int] = None,
        timeout_trigger: Optional[int] = None,
        python_expires: Optional[bool] = None,
        set_redis_ttl_readheavy: Optional[bool] = None,
        _set_redis_ttl_onexit: Optional[bool] = None,
    ):
        if timeout_trigger and not python_expires:  # fix this
            python_expires = True
        if not timeout:
            if set_redis_ttl_readheavy:
                raise ValueError("`set_redis_ttl_readheavy` requires `timeout`")
        self.redis = redis
        self.serialize = serialize  # type: ignore[method-assign, assignment]
        self.deserialize = deserialize  # type: ignore[method-assign, assignment]
        self.new_session = new_session  # type: ignore[method-assign]
        if new_payload_func is not None:
            self.new_payload = new_payload_func  # type: ignore[method-assign]
        if encode_session_payload_func is not None:
            self.encode_session_payload = encode_session_payload_func  # type: ignore[method-assign]
        if decode_session_payload_func is not None:
            self.decode_session_payload = decode_session_payload_func  # type: ignore[method-assign, assignment]
        self._set_redis_ttl = set_redis_ttl
        self._set_redis_ttl_readheavy = set_redis_ttl_readheavy
        self._detect_changes = detect_changes
        self._deserialized_fails_new = deserialized_fails_new
        self._timeout = timeout
        self._timeout_trigger = timeout_trigger
        self._python_expires = python_expires
        self._new = new  # only used for testing/resync
        self._session_state = self._make_session_state(
            session_id=session_id,
            new=new,
        )
        if _set_redis_ttl_onexit:
            self._session_state.please_refresh = True

    def _resync(self) -> None:
        """resyncs the session. this is really only needed for testing."""
        self._session_state = self._make_session_state(
            session_id=self.session_id, new=self._new
        )

    def new_session(self) -> TYPING_SESSION_ID:
        # this should be set via __init__
        raise NotImplementedError()

    def new_payload(self) -> Dict:
        # this should be set via __init__
        return empty_session_payload()

    def encode_session_payload(self, *args, **kwargs):
        """
        used to recode for serialization
        this can be overridden via __init__
        """
        return encode_session_payload_func(*args, **kwargs)

    def decode_session_payload(self, payload: Dict) -> Dict:
        """
        used to recode for serialization
        this can be overridden via __init__

        :param payload:
        :type payload: dict
        :returns decoded payload:
        """
        return decode_session_payload_func(payload)

    def serialize(self, data: Dict) -> bytes:
        # this should be set via __init__
        raise NotImplementedError()

    def deserialize(self, serialized: bytes) -> Dict:
        # this should be set via __init__
        raise NotImplementedError()

    @reify
    def _session_state(self) -> _SessionState:
        """this should only be executed after an `invalidate()`
        The `invalidate()` will "del self._session_state", which will remove
        the '_session_state' entry from the object dict (as created by __init__
        or by this function which reify's the return value). Removing that
        function allows this method to execute, and `reify` puts the new result
        in the object's dict.
        """
        return self._make_session_state(
            session_id=LazyCreateSession,
            new=True,
        )

    @reify
    def timestamp(self) -> int:
        return int_time()

    def _make_session_state(
        self,
        session_id: TYPING_SESSION_ID,
        new: bool,
    ) -> _SessionState:
        """
        This will try to load the session_id in Redis via ``from_redis``.
        If this fails, it will raise ``InvalidSession`` variants

        :param session_id:
        :param new:
        :returns `_SessionState``:
        """
        if session_id is LazyCreateSession:
            persisted_hash = None
            persisted = self.new_payload()
        else:
            # self.from_redis needs to take a session_id here, because
            # otherwise it would look up self.session_id, which is not ready
            # yet as session_state has not been created yet.
            (persisted, persisted_hash) = self.from_redis(
                session_id=session_id,
                persisted_hash=(True if self._detect_changes else False),
            )
            expires = persisted.get("x")
            if expires:
                if self.timestamp > expires:
                    raise InvalidSession_PayloadTimeout(
                        "`session_id` (%s) timed out in python" % session_id
                    )
            version = persisted.get("v")
            if not version or (version < SESSION_API_VERSION):
                raise InvalidSession_PayloadLegacy(
                    "`session_id` (%s) is a legacy format" % session_id
                )
        return _SessionState(
            session_id=session_id,
            managed_dict=persisted["m"],  # managed_dict
            created=persisted["c"],  # created
            timeout=persisted.get("t"),  # timeout
            expires=persisted.get("x"),  # expires
            version=persisted.get("v"),  # session api version
            new=new,
            persisted_hash=persisted_hash,
        )

    @property
    def session_id(self) -> str:
        """
        note:
        accessing this will create a new `_session_state` and `session_id`
        if there is no `_session_state`, such as in the case of an invalidation
        """
        return self._session_state.session_id

    @property
    def managed_dict(self) -> Dict:
        return self._session_state.managed_dict

    @property
    def created(self) -> int:
        return self._session_state.created

    @property
    def timeout(self) -> int:
        return self._session_state.timeout

    @property
    def expires(self) -> int:
        return self._session_state.expires

    @property
    def version(self) -> int:
        return self._session_state.version

    @property
    def new(self) -> bool:
        return self._session_state.new

    def to_redis(self) -> bytes:
        """Serialize a dict of the data that needs to be persisted for this
        session, for storage in Redis.

        Primarily used by the ``@persist`` decorator to save the current
        session state to Redis.
        """
        data = self.encode_session_payload(
            self.managed_dict,
            self.created,
            self.timeout,
            self.expires,
            timeout_trigger=self._timeout_trigger,
            python_expires=self._python_expires,
        )
        return self.serialize(data)

    @overload
    def from_redis(  # noqa: E704
        self,
        session_id: Optional[TYPING_SESSION_ID] = None,
        persisted_hash: Optional[None] = None,
    ) -> Dict: ...

    @overload
    def from_redis(  # noqa: E704
        self,
        session_id: Optional[TYPING_SESSION_ID] = None,
        persisted_hash: Literal[False] = False,
    ) -> Tuple[Dict, None]: ...

    @overload
    def from_redis(  # noqa: E704
        self,
        session_id: Optional[TYPING_SESSION_ID] = None,
        persisted_hash: Literal[True] = True,
    ) -> Tuple[Dict, str]: ...

    def from_redis(
        self,
        session_id: Optional[TYPING_SESSION_ID] = None,
        persisted_hash: Optional[Literal[True, False]] = None,
    ):
        """
        Get and deserialize the persisted data for this session from Redis.
        If ``persisted_hash`` is ``None`` (default), returns a single
        variable `deserialized`.
        If set to ``True`` or ``False``, returns a tuple.
        """
        _session_id = session_id or self.session_id
        if _session_id is LazyCreateSession:
            raise InvalidSession_Lazycreate(  # noaq: E501
                "`session_id` is LazyCreateSession"
            )
        if TYPE_CHECKING:
            assert isinstance(_session_id, str)

        # optimize a `TTL refresh` under certain conditions
        persisted: Union[Awaitable, bytes, None] = None
        if self._set_redis_ttl_readheavy:
            if TYPE_CHECKING:
                assert self._timeout is not None
            with self.redis.pipeline() as pipe:
                persisted = pipe.get(_session_id)  # type: ignore[assignment]
                _updated = pipe.expire(  # noqa: F841
                    _session_id,
                    self._timeout,
                )
            # mark that we shouldn't refresh
            self._session_state.dont_refresh = True
        else:
            persisted = self.redis.get(_session_id)

        if TYPE_CHECKING:
            assert not isinstance(persisted, Awaitable)

        if persisted is None:
            raise InvalidSession_NotInBackend(
                "`session_id` (%s) not in Redis" % _session_id
            )

        if TYPE_CHECKING:
            assert isinstance(persisted, bytes)

        try:
            deserialized = self.deserialize(persisted)
        except Exception as e:
            if self._deserialized_fails_new:
                raise InvalidSession_DeserializationError(
                    "`session_id` (%s) did not deserialize correctly"
                    % _session_id  # noaq: E501
                )
            raise RawDeserializationError(e)
        # TODO: typing on return can be better?
        if persisted_hash is True:
            # -> tuple[dict, str]
            return (deserialized, hashed_value(persisted))
        elif persisted_hash is False:
            # -> tuple[dict, None]
            return (deserialized, None)
        # -> dict
        return deserialized

    def invalidate(self) -> None:
        """Invalidate the session."""
        if self.session_id != LazyCreateSession:
            self.redis.delete(self.session_id)
        # Delete the self._session_state attribute so that direct access to or
        # indirect access via other methods and properties to .session_id,
        # .managed_dict, .created, .timeout and .new (i.e. anything stored in
        # self._session_state) after this will trigger the creation of a new
        # session with a new session_id via the `_session_state()` reified
        # property.
        del self._session_state

    def ensure_id(self) -> str:
        # this ensures we have a session_id
        if self._session_state.session_id is LazyCreateSession:
            self._session_state.session_id = self.new_session()
        return self._session_state.session_id

    @property
    def session_id_safecheck(self) -> Optional[str]:
        """if we don't have a managed_dict, return None"""
        if not self.managed_dict:
            return None
        return self.ensure_id()

    def do_persist(self, serialized_session=None) -> None:
        """
        Actually and immediately persist to Redis backend
        Only set a timeout in Redis timeout if we have timeouts AND are not
        in LRU mode.
        Note: this package uses StrictRedis(`key, timeout, value`)
              not Redis(`key, value, timeout`)
        """
        self.ensure_id()
        if serialized_session is None:
            serialized_session = self.to_redis()
        serverside_timeout = (
            True
            if ((self.timeout is not None) and (self._set_redis_ttl))
            else False  # noaq: E501
        )
        if serverside_timeout:
            self.redis.setex(self.session_id, self.timeout, serialized_session)
        else:
            self.redis.set(self.session_id, serialized_session)
        self._session_state.please_persist = False
        self._session_state.dont_refresh = True

    def do_refresh(self, force_redis_ttl=None) -> None:
        """
        Actually and immediately refresh the TTL to Redis backend.
        Does nothing if no timeout set (in LRU mode).
        Optional kwarg for developers ``force_redis_ttl`` (default None)
        can be provided to force a new Redis TTL.
        """
        if force_redis_ttl is not None:
            self.redis.expire(self.session_id, force_redis_ttl)
        else:
            if self.timeout is not None:
                if self._set_redis_ttl:
                    # set a TTL if unless we're in LRU mode
                    self.redis.expire(self.session_id, self.timeout)
        self._session_state.please_refresh = False

    # dict modifying methods decorated with @persist
    @persist
    def __delitem__(self, key: TYPING_KEY) -> None:
        del self.managed_dict[key]

    @persist
    def __setitem__(self, key: TYPING_KEY, value: Any) -> None:
        self.managed_dict[key] = value

    @persist
    def setdefault(self, key: TYPING_KEY, default: Optional[Any] = None):
        # TODO: typing
        # this should always return `None`, but mypy doesn't like that
        # unless this should somehow not return `None`
        return self.managed_dict.setdefault(key, default)

    @persist
    def clear(self) -> None:
        return self.managed_dict.clear()

    @persist
    def pop(self, key: TYPING_KEY, default: Optional[Any] = None) -> Any:
        return self.managed_dict.pop(key, default)

    @persist
    def update(self, other) -> None:
        # TODO: typing
        return self.managed_dict.update(other)

    @persist
    def popitem(self) -> tuple:
        # TODO: Deprecate? I can't imagine a usecase for this
        return self.managed_dict.popitem()

    # dict read-only methods decorated with @refresh
    @refresh
    def __getitem__(self, key: str) -> Any:
        return self.managed_dict[key]

    @refresh
    def __contains__(self, key: str) -> bool:
        return key in self.managed_dict

    @refresh
    def keys(self) -> "KeysView":
        # TODO: typing
        return self.managed_dict.keys()

    @refresh
    def items(self) -> "ItemsView":
        # TODO: typing
        return self.managed_dict.items()

    @refresh
    def get(self, key: TYPING_KEY, default: Optional[Any] = None):
        return self.managed_dict.get(key, default)

    @refresh
    def __iter__(self) -> Iterator:
        return self.managed_dict.__iter__()

    @refresh
    def has_key(self, key: TYPING_KEY) -> bool:
        return key in self.managed_dict

    @refresh
    def values(self) -> List:
        return list(self.managed_dict.values())

    @refresh
    def itervalues(self) -> List:
        return list(self.managed_dict.values())

    @refresh
    def iteritems(self) -> List:
        return list(self.managed_dict.items())

    @refresh
    def iterkeys(self) -> List:
        return list(self.managed_dict.keys())

    @persist
    def changed(self) -> None:
        """Persist all the data that needs to be persisted for this session
        immediately with ``@persist``.
        """
        pass

    # session methods persist or refresh using above dict methods
    def new_csrf_token(self) -> str:
        token = token_hex(32)
        self["_csrft_"] = token
        return token

    def get_csrf_token(self) -> str:
        token = self.get("_csrft_", None)
        if token is None:
            token = self.new_csrf_token()
        return token

    def flash(
        self,
        msg: str,
        queue: str = "",
        allow_duplicate: bool = True,
    ) -> None:
        storage = self.setdefault("_f_" + queue, [])
        if allow_duplicate or (msg not in storage):
            storage.append(msg)
            self.changed()  # notify Redis of change to ``storage`` mutable

    def peek_flash(self, queue: str = ""):
        storage = self.get("_f_" + queue, [])
        return storage

    def pop_flash(self, queue: str = ""):
        storage = self.pop("_f_" + queue, [])
        return storage

    # RedisSession extra methods

    @recookie
    def please_recookie(self) -> None:
        """
        this does nothing, other than invoking `@recookie` to ensure the cookie
        is sent with the Response.
        """
        return None

    @recookie
    def adjust_cookie_expires(self, expires: TYPING_COOKIE_EXPIRES) -> None:
        """
        Adjust the `expires` value on the cookie.
        The underlying functionality may be removed in WebOb 1.9.

        This method ONLY affects the SetCookie Headers.
        This method does not affect the session logic or any values.

        A datetime.timedelta object representing an amount of time,
        datetime.datetime or None.

        Expires and Max-Age have a somewhat convoluted relationship;
        Max-Age always takes precedence. You should be using Max-Age instead
        """
        self._session_state.cookie_expires = expires

    @recookie
    def adjust_cookie_max_age(self, max_age: int) -> None:
        """
        Permanently adjusts the max-age for this cookie to ``max_age``
        This value is used as the Max-Age of the generated cookie

        This method ONLY affects the SetCookie Headers.
        This method does not affect the session logic or any values.

        An integer representing a number of seconds, datetime.timedelta,
        or None.

        Expires and Max-Age have a somewhat convoluted relationship;
        Max-Age always takes precedence. You should be using Max-Age.
        """
        self._session_state.cookie_max_age = max_age

    @persist
    def adjust_session_expires(self, expires_epoch: int) -> None:
        """
        Updates the epoch used for Python timeout on expiry logic.
        """
        self._session_state.expires = expires_epoch

    @persist
    def adjust_session_timeout(self, timeout_seconds: int) -> None:
        """
        Permanently adjusts the `timeout` for this Session to
        ``timeout_seconds`` for as long as this Session is active.
        Useful in situations where you want to change the expiry time for
        a Session dynamically.
        """
        self._session_state.timeout = timeout_seconds

    # rename these
    adjust_expires_for_session = adjust_session_expires
    adjust_timeout_for_session = adjust_session_timeout

    @property
    def _invalidated(self) -> bool:
        """
        Boolean property indicating whether the session is in the state where
        it has been invalidated but a new session has not been created in its
        place.
        """
        return "_session_state" not in self.__dict__

    def _deferred_callback(self, request: "Request") -> None:
        """
        Finished callback to persist the data if needed.
        `request` is supplied by pyramid's `add_finished_callback` which should
        invoke this.
        """
        if "_session_state" not in self.__dict__:
            # _session_state is a reified property, which is saved into the
            # dict. if we call `session.invalidate()` the session is immediately
            # deleted however, accessing it here will trigger a new
            # _session_state creation and insert a placeholder for the
            # session_id into Redis.  this would be ok in certain situations,
            # however since we don't access any actual data in the session,
            # it won't have the cookie callback triggered -- which means the
            # cookie will never get sent to the user, and a phantom
            # session_id+placeholder will be in Redis until it times out.
            return
        if not self._session_state.dont_persist:
            if self._session_state.please_persist:
                self.do_persist()
                self._session_state.please_refresh = False
            else:
                if not self.session_id_safecheck:
                    return
                serialized_session = self._session_state.should_persist(self)
                if serialized_session:
                    self.do_persist(serialized_session=serialized_session)
                    self._session_state.please_refresh = False
        if not self._session_state.dont_refresh:
            if self._session_state.please_refresh:
                self.do_refresh()
