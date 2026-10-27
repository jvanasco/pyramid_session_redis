Redis, Valkey, and serialization
================================

Connecting
----------

The library uses redis-py's synchronous client for both Redis and Valkey:

.. code-block:: ini

   redis.sessions.secret = replace-with-your-secret
   redis.sessions.redis_url = redis://localhost:6379/0

Use ``rediss://`` for a TLS connection, or a Unix socket URL such as
``unix:///path/to/backend.sock?db=0``. Keep backend responses as bytes:
``decode_responses=False`` is redis-py's default and is required for serialized
payloads. URLs take precedence over individual connection settings when using
the default connection getter.

The default getter caches one client on the Pyramid application registry and
reuses its pool. If multiple session factories need different backend clients
in one registry, use ``redis_client_callable`` to control their connections.

Valkey
------

Existing Redis-protocol clients can connect to Valkey; see the
`Valkey client compatibility notes <https://valkey.io/clients/>`_. Keep the
``redis.sessions.*`` names and a ``redis://`` or ``rediss://`` URL. An additional
``valkey`` Python dependency and a ``valkey://`` URL are not needed.

For a local disposable instance::

    docker run --rm -p 6379:6379 valkey/valkey:8

The configured CI matrix runs the same suite against Redis 7.2, Valkey 7.2, and
Valkey 8. It covers signed-cookie round trips, nested changes, pipelines, TTL
refresh, timeout removal, invalidation, and optimistic conflicts. Instructions
for running the suite locally are in :doc:`contributing`.

Custom clients
--------------

The getter receives the current request and the factory's individual connection
options. It should return a shared synchronous redis-py-compatible client whose
responses are bytes. The factory does not forward ``redis_url`` to this hook.

.. code-block:: python

   from redis import StrictRedis
   from pyramid_session_redis import RedisSessionFactory

   client = StrictRedis.from_url(backend_url, decode_responses=False)

   def get_session_client(request, **connection_options):
       return client

   session_factory = RedisSessionFactory(
       secret=signing_secret,
       redis_client_callable=get_session_client,
   )

The application owns the lifetime and shutdown of a custom client and its pool.
Do not create and discard a new connection pool for each request.

Changing the payload serializer
-------------------------------

The default serializer is pickle. Access to the backend must therefore be
trusted: a cookie signature protects the session ID, not the stored pickle
payload. A custom serializer must encode the full envelope to bytes and decode
it back to a dict.

For sessions containing only JSON-compatible data:

.. code-block:: python

   import json
   from pyramid_session_redis import RedisSessionFactory

   def serialize_payload(payload):
       return json.dumps(payload, separators=(",", ":")).encode("utf-8")

   def deserialize_payload(raw):
       return json.loads(raw.decode("utf-8"))

   session_factory = RedisSessionFactory(
       secret=signing_secret,
       serialize=serialize_payload,
       deserialize=deserialize_payload,
   )

Migration must account for existing serialized sessions. A JSON decoder cannot
read old pickle payloads. ``deserialized_fails_new=True`` replaces unreadable
sessions with new ones, which loses their previous data; it is not a migration.

The current envelope contains ``m`` (managed dict), ``c`` (creation timestamp),
and ``v`` (envelope API version). ``t`` (timeout) and ``x`` (Python expiry) are
optional. Creation and expiry values are integer epoch seconds. The ``v`` field
is a schema version, not an optimistic write revision.
