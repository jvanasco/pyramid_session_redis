API guide
=========

Factory entry points
--------------------

``pyramid_session_redis.includeme(config)``
    Called by ``config.include("pyramid_session_redis")``. Resolves supported
    dotted paths, parses settings, and registers the session factory.

``pyramid_session_redis.session_factory_from_settings(settings)``
    Collects ``redis.sessions.*`` settings, coerces configured values, and
    returns a session factory. Callable settings must already be resolved.

``pyramid_session_redis.RedisSessionFactory(...)``
    Returns a callable accepting a Pyramid request and returning a
    ``RedisSession``. Pass Python values for the options listed in
    :doc:`configuration`. The returned factory registers response and finished
    callbacks on the request.

Sessions
--------

``pyramid_session_redis.session.RedisSession`` implements Pyramid's session
interface. Applications normally obtain it from ``request.session`` rather
than constructing it directly. See :doc:`sessions` for dictionary operations,
flash messages, CSRF tokens, and the deferred lifecycle.

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - Method or property
     - Behavior
   * - ``invalidate()``
     - Delete the current key immediately and mark the session invalidated.
   * - ``ensure_id() -> str``
     - Reserve an ID when still lazy; return a string.
   * - ``session_id_safecheck``
     - Property: ``None`` when empty; otherwise ensure and return an ID.
   * - ``changed()``
     - Mark the payload for deferred persistence.
   * - ``do_persist(serialized_session=None)``
     - Write immediately, optionally using pre-serialized bytes.
   * - ``do_refresh(force_redis_ttl=None)``
     - Refresh backend TTL only; optionally supply explicit seconds.
   * - ``please_recookie()``
     - Request a replacement cookie during response processing.
   * - ``adjust_cookie_max_age(max_age)``
     - Override response cookie max-age; seconds, timedelta, or ``None``.
   * - ``adjust_cookie_expires(expires)``
     - Override response cookie expiry; datetime, timedelta, or ``None``.
   * - ``adjust_session_timeout(timeout_seconds)``
     - Change timeout; zero and ``None`` disable it, negatives are rejected.
   * - ``adjust_session_expires(expires_epoch)``
     - Override Python expiry for this request's writes.
   * - ``flash(msg, queue="", allow_duplicate=True)``
     - Add a flash message, optionally suppressing duplicates.
   * - ``peek_flash(queue="")`` / ``pop_flash(queue="")``
     - Read a queue without removing it / read and remove it.
   * - ``get_csrf_token()`` / ``new_csrf_token()``
     - Obtain an existing token or create one / replace it.

``session_id`` can be a string or the ``LazyCreateSession`` class sentinel.
``created`` is an integer. ``timeout``, ``expires``, and ``version`` can be
``None``. ``new`` is a boolean; ``managed_dict`` exposes the internal dict.
Mutations made through ``managed_dict`` require normal nested-change detection
or an explicit ``changed()`` call.

The old ``adjust_timeout_for_session`` and ``adjust_expires_for_session`` names
remain aliases for the corresponding ``adjust_session_*`` methods.

Errors and monitoring
---------------------

Exceptions are defined in ``pyramid_session_redis.exceptions``.

``InvalidSession``
    Base class caught by the factory when replacing a missing or invalid
    session. Reasons include ``InvalidSession_NoSessionCookie``,
    ``InvalidSession_NotInBackend``, ``InvalidSession_PayloadTimeout``, and
    ``InvalidSession_PayloadLegacy``. The optional invalid-session logger
    receives the request and exception instance.

``InvalidSession_DeserializationError``
    Invalid-session reason used when deserialization recovery is enabled.
    It covers malformed envelopes as well as decoder failures.

``RawDeserializationError``
    Raised for decoder/validation failures when recovery is disabled. It is
    not automatically replaced with a fresh session.

``SessionConflict``
    Raised only by opt-in optimistic persistence when the original payload
    changed or disappeared, or when a watched key changed during the write.
    It is not an ``InvalidSession`` subtype and is not automatically retried.

Backend connection and command errors propagate from the client. They are not
handled by ``deserialized_fails_new`` or ``func_invalid_logger``.

Helpers
-------

``pyramid_session_redis.check_response_allow_cookies(response)``
    Return false if the response has ``Cache-Control`` or ``Expires``. This
    helper can be supplied as ``func_check_response_allow_cookies``.

``pyramid_session_redis.util.prefixed_id(prefix="session:")``
    Generate a random string ID with a prefix. Pass a partial as the factory's
    ``id_generator`` when configuring directly in Python.

``pyramid_session_redis.connection.get_default_connection(request, ...)``
    Obtain or cache the default synchronous client on the application registry.
    Custom multi-backend integrations should instead supply a client getter.
