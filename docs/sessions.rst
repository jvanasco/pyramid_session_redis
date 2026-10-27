Using sessions
==============

Data and mutations
------------------

Use ``request.session`` to read and write the managed dictionary:

.. code-block:: python

   session = request.session
   session["cart"] = {"items": []}
   session["cart"]["items"].append("book")
   theme = session.get("theme", "light")

Top-level mutations are marked for deferred persistence. By default,
``detect_changes=True`` also detects nested changes by comparing serialized
payload hashes. If you disable detection, call ``session.changed()`` after
mutating nested objects. ``changed()`` marks the session; it does not write to
the backend immediately.

The session supports dictionary operations such as indexing, membership,
iteration, ``get``, ``setdefault``, ``update``, ``pop``, ``popitem``, ``clear``,
``keys``, ``items``, and ``values``. ``keys`` and ``items`` return dict views;
``values`` returns a list. The compatibility methods ``iterkeys``, ``iteritems``,
and ``itervalues`` also return lists. ``pop(key)`` returns ``None`` for a missing
key rather than raising ``KeyError``.

Lifecycle and empty sessions
----------------------------

New sessions begin with an empty payload and a lazy-ID sentinel. Adding data
normally causes a backend ID and signed cookie to be created during response
processing. The finished callback writes the final payload. Reading an existing
session loads it from storage, and subsequent dictionary operations work on
the in-memory payload.

With ``invalidate_empty_session=True`` (the default), an empty existing session
is invalidated during response processing. Empty new sessions are not persisted
by that callback. Setting the option to false retains existing empty sessions
but does not automatically send cookies for untouched new sessions.

``session.ensure_id()`` reserves and returns a real string ID, even when the
session is empty. Reserving an ID alone does not guarantee that a cookie will
be sent. ``session.session_id_safecheck`` is a property that returns ``None``
for an empty session; for a nonempty session, it ensures and returns an ID.

Invalidation
------------

.. code-block:: python

   request.session.invalidate()

Invalidation immediately deletes the current backend key. Response processing
deletes an existing valid session cookie. Accessing session state after
invalidation creates a new lazy session; adding new data then creates a new ID.

Concurrent requests already holding the old payload can recreate a deleted key
under the default write policy. Applications that need to reject those writes
can enable :ref:`optimistic-concurrency`.

Flash messages and CSRF tokens
------------------------------

.. code-block:: python

   session.flash("Saved", queue="notice", allow_duplicate=False)
   pending = session.peek_flash("notice")  # leaves the queue in the session
   messages = session.pop_flash("notice")  # removes the queue
   token = session.get_csrf_token()        # creates a token when absent
   replacement = session.new_csrf_token()

Flash queues use keys beginning with ``_f_``. The CSRF token uses ``_csrft_``.
Avoid using those keys for unrelated application data. These methods manage
session state; request-side CSRF validation is still an application/framework
responsibility.

Properties and immediate actions
--------------------------------

``created`` is the integer creation timestamp. ``timeout`` and ``expires`` may
be ``None``. ``new`` indicates whether this session was created for the request.
``version`` is the stored envelope API version, not a concurrency revision.
``session_id`` may be the lazy sentinel until ``ensure_id()`` has been called.

``do_persist()`` writes immediately. ``do_refresh()`` refreshes the backend TTL
when one is configured; it does not update Python expiry. Normal views should
usually leave persistence to the finished callback. Explicit writes are useful
when handling optimistic conflicts before producing a response.

``adjust_cookie_max_age(seconds_or_timedelta_or_none)`` and
``adjust_cookie_expires(datetime_or_timedelta_or_none)`` request a replacement
cookie on the response. ``please_recookie()`` requests a replacement without
changing its attributes. These controls affect the response cookie only.

``adjust_session_timeout(seconds_or_none)`` changes the stored timeout when
persisted. Zero and ``None`` clear timeout and Python expiry; a normal write then
removes the backend TTL. ``adjust_session_expires(epoch)`` sets Python expiry for
writes during this request without altering the backend TTL. The next request
resumes normal sliding-expiry rules. See :doc:`performance` for timing details.
