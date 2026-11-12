Configuration reference
=======================

Each factory option below is also an INI setting prefixed with
``redis.sessions.`` unless explicitly marked Python-only. For example,
``timeout=600`` becomes ``redis.sessions.timeout = 600``.

``config.include("pyramid_session_redis")`` converts boolean and numeric strings
and resolves dotted Python paths for supported hooks. When calling
``RedisSessionFactory`` directly, pass Python objects and values instead.
``session_factory_from_settings`` parses settings but does not itself resolve
dotted paths; the include performs that step first.

Signing and serialization
-------------------------

``secret`` (default ``None``)
    Secret used by WebOb's signed serializer for the session-ID cookie. Supply
    exactly one of a nonempty secret or ``cookie_signer``.

``cookie_signer`` (default ``None``)
    Alternative signer object with ``dumps(str) -> bytes`` and
    ``loads(bytes) -> str``. Invalid input should raise ``ValueError``. For INI
    configuration, the dotted path must resolve to the signer object, not a
    factory that still needs to be called.

``serialize`` / ``deserialize`` (defaults ``pickle.dumps`` / ``pickle.loads``)
    Paired callables converting the complete session envelope from a dict to
    bytes and back. The default pickle format requires trusted backend storage.
    Changing serializers requires a migration or invalidation of stored data.
    See :doc:`backends` for a JSON example.

``id_generator`` (default a cryptographically random URL-safe string generator)
    No-argument callable returning a string. IDs are checked for uniqueness
    when reserved in the backend. A generator that repeatedly returns an
    existing ID will keep retrying.

``prefix`` (INI convenience option only)
    Prefix for generated backend keys. Cannot be combined with ``id_generator``.
    For direct factory construction, use a partial of
    ``pyramid_session_redis.util.prefixed_id`` instead.

Expiry and persistence
----------------------

``timeout`` (default ``1200``)
    Inactivity timeout in seconds. ``0`` and ``None`` disable timeout tracking
    for newly created sessions. Negative values are rejected. Existing sessions
    retain their stored timeout until explicitly adjusted.

``python_expires`` (default ``True``)
    Track an expiry timestamp in the serialized payload and reject expired
    payloads on load. Payload expiry already present in stored data is checked
    even if this option is subsequently disabled.

``set_redis_ttl`` (default ``True``)
    Apply the session timeout as a backend TTL. Disabling this option does not
    disable Python expiry. Use an appropriate backend eviction policy if keys
    are intentionally stored without TTLs.

``timeout_trigger`` (default ``None``)
    Refresh Python expiry only once the request is within this many seconds of
    the stored expiry. ``0`` disables the threshold. Setting a nonzero trigger
    enables ``python_expires``. See the timing example in :doc:`performance`.

``set_redis_ttl_readheavy`` (default ``None``, disabled)
    Fetch the payload and refresh its TTL in one pipeline. Requires a timeout,
    ``set_redis_ttl=True``, ``python_expires=False``, and no timeout trigger.

``detect_changes`` (default ``True``)
    Serialize and compare the payload to detect nested mutations. Disabling
    this check requires calling ``session.changed()`` after nested mutations;
    it does not disable Python expiry maintenance.

``invalidate_empty_session`` (default ``True``)
    During response processing, invalidate an existing session whose managed
    dict is empty, and suppress persistence of an empty new session. Setting
    this to ``False`` retains existing empty sessions; it does not by itself
    allocate an ID or send a cookie for an untouched empty new session.

``optimistic_concurrency`` (default ``False``)
    Reject writes if the loaded payload changed or disappeared. Adds backend
    round trips only when enabled. See :doc:`performance` for conflict handling
    and the exact guarantees.

``deserialized_fails_new`` (default ``None``, disabled)
    Start a new session if payload deserialization or envelope validation fails.
    Otherwise raise ``RawDeserializationError``. Backend connection failures
    are not converted into new sessions.

Cookie options
--------------

The options are passed to WebOb when setting a session cookie. ``None`` means
no explicit value unless described otherwise.

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Option
     - Default
     - Purpose
   * - ``cookie_name``
     - ``"session"``
     - Cookie name.
   * - ``cookie_max_age``
     - ``None``
     - Browser lifetime in seconds, independent of backend expiry.
   * - ``cookie_path``
     - ``"/"``
     - Cookie path.
   * - ``cookie_domain``
     - ``None``
     - Optional cookie domain.
   * - ``cookie_secure``
     - ``False``
     - Restrict cookie transmission to HTTPS.
   * - ``cookie_httponly``
     - ``True``
     - HTTP-only flag.
   * - ``cookie_samesite``
     - ``None``
     - ``"lax"``, ``"strict"``, or ``"none"`` as supported by WebOb.
   * - ``cookie_on_exception``
     - ``True``
     - Allow session cookies on a response when the request has an exception.
   * - ``cookie_expires``
     - ``None``
     - Python-only datetime/timedelta option; prefer ``cookie_max_age``.
   * - ``cookie_comment``
     - ``None``
     - Legacy comment attribute, passed only when set.

Connection options
------------------

``redis_url`` (default ``None``)
    Connection URL. Accepts redis-py's ``redis://``, ``rediss://``, and
    ``unix://`` forms. Takes precedence over individual host, port, database,
    password, Unix socket, and connection-pool settings in the default getter.

``redis_host`` / ``redis_port`` / ``redis_db``
    Defaults: ``"localhost"``, ``6379``, and ``0``.

``redis_password`` / ``redis_unix_socket_path``
    Defaults: ``None``. Passed to the client when not using a URL.

``redis_socket_timeout`` (default ``None``)
    Optional floating-point seconds. INI values such as ``0.5`` and ``None``
    are accepted. A numeric zero is passed through to redis-py as ``0.0``;
    it is not converted into an unlimited timeout.

``redis_encoding`` / ``redis_encoding_errors``
    Defaults: ``None`` at the factory boundary, leaving redis-py's defaults in
    place. These do not enable response decoding: stored payloads must remain
    bytes.

``redis_connection_pool`` (default ``None``)
    Python-only connection pool. Not accepted by the INI settings parser.

``redis_client_callable`` (default ``None``)
    Callable accepting ``request`` and keyword connection options, returning a
    synchronous redis-py-compatible client. Takes precedence over the default
    getter. The factory does not pass ``redis_url`` into this hook; a custom
    getter should obtain its own URL if it needs one. See :doc:`backends`.

Response and logging hooks
--------------------------

``func_check_response_allow_cookies`` (default ``None``)
    Callable accepting the response and returning a boolean. Returning false
    skips cookie processing, including deletion; it does not cancel deferred
    backend persistence. The supplied ``check_response_allow_cookies`` helper
    returns false when either ``Cache-Control`` or ``Expires`` is present.

``func_invalid_logger`` (default ``None``)
    Callable invoked as ``logger(request, exception)`` when the factory replaces
    an invalid or missing session. Missing cookies are included. It does not
    receive ``SessionConflict`` or backend connection errors.
