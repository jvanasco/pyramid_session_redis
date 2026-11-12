Expiry, performance, and concurrency
====================================

Default behavior
----------------

The defaults are a 1,200-second timeout, Python expiry enabled, backend TTLs
enabled, and nested-change detection enabled. The session is loaded once for a
request, and ordinary reads and mutations operate on its in-memory dictionary.
The finished callback persists changes or refreshes the backend TTL as needed.
Writes use ``SETEX`` when a backend timeout is enabled, otherwise ``SET``.

Python expiry is part of the serialized envelope. Updating its timestamp can
require a write even when application data did not change. Disabling nested
change detection does not suppress those expiry updates. New IDs are reserved
with an empty payload before the final payload is written; creation therefore
can involve more than one write.

Choosing an expiry mode
-----------------------

* Keep the defaults for both a backend TTL and a Python expiry check.
* Set ``python_expires=False`` to let the backend manage inactivity expiry.
  Existing payload expiry timestamps are still checked when loaded.
* Set ``set_redis_ttl=False`` to avoid backend TTL commands. Python expiry still
  applies unless separately disabled. Keys then require backend eviction or
  another cleanup policy.
* Set ``timeout=0`` or ``timeout=None`` to create sessions without inactivity
  expiry. This does not rewrite the timeout already stored in existing sessions.

Throttling expiry updates
-------------------------

``timeout_trigger`` defines a window before the stored Python expiry in which
it is refreshed. For example, with ``timeout=1200`` and ``timeout_trigger=600``:

.. list-table::
   :header-rows: 1

   * - Time since creation
     - Result on access
   * - 0 seconds
     - Initial expiry at 1,200 seconds.
   * - 599 seconds
     - No threshold-based refresh.
   * - 600 seconds
     - Refresh expiry to 1,800 seconds.
   * - 1,200 seconds
     - Refresh expiry to 2,400 seconds.

Application mutations can still cause writes between thresholds. A threshold
reduces expiry writes but permits sessions to expire sooner than one full
timeout after their last access. The trigger uses the stored expiry: for an
hour-long timeout and a ten-minute trigger, the first refresh window starts at
50 minutes. Choose a positive trigger smaller than the timeout.

Read-heavy backend expiry
-------------------------

.. code-block:: ini

   redis.sessions.timeout = 1200
   redis.sessions.set_redis_ttl = true
   redis.sessions.python_expires = false
   redis.sessions.set_redis_ttl_readheavy = true

This mode queues ``GET`` and ``EXPIRE`` together and executes the pipeline when
loading an existing session. It suppresses the redundant deferred TTL refresh.
It is incompatible with Python expiry and timeout triggers. TTL refresh happens
at load time in this mode, using the configured factory timeout; when per-session
timeouts differ, prefer the ordinary deferred refresh mode.

.. _optimistic-concurrency:

Optional optimistic concurrency
-------------------------------

The default is ``optimistic_concurrency=False``. It adds no backend calls to
the existing fast write path, which allows the last write to win.

Opt in with:

.. code-block:: ini

   redis.sessions.optimistic_concurrency = true

An optimistic write watches the session key, reads its current serialized
payload, compares it with the payload originally loaded, and writes inside a
``MULTI``/``EXEC`` transaction. A changed or missing payload raises
``pyramid_session_redis.exceptions.SessionConflict``. A change after comparison
but before execution also raises a conflict. Stale data is not retried.

This adds ``WATCH`` and ``GET`` round trips plus transaction execution to a
write. Reserving a new ID adds a read of its placeholder payload. No revision
field is added to the stored format. Identical serialized payloads compare
equal; expiration and eviction count as missing payloads. Writers that do not
opt in can still overwrite data, so enable the option consistently wherever
lost-update protection is required.

Persistence normally runs in Pyramid's finished callback, after response
processing. A conflict raised there cannot replace a response already produced.
Call ``request.session.do_persist()`` in a view if you need to detect a conflict
before producing its response. This is storage protection; it does not roll
back application side effects or provide transactions with another database.

Measuring changes
-----------------

Measure with the application's request pattern and serializer. Nested-change
detection spends CPU serializing and hashing payloads; read-heavy TTL mode can
save a round trip for reads but refreshes expiry before a later write. Optional
optimistic transactions intentionally spend more backend work to reject stale
writes. Cookie filtering suppresses cookies, not backend persistence.
