pyramid_session_redis
=====================

``pyramid_session_redis`` stores Pyramid session data in Redis or Valkey. The
browser receives a signed session ID; application data remains in the backend.
Writes and TTL refreshes are normally deferred until the request finishes.

Start with :doc:`getting_started`, then choose expiry and persistence behavior
using :doc:`configuration` and :doc:`performance`. These pages describe the
current checkout, including changes awaiting release.

.. toctree::
   :maxdepth: 2

   getting_started
   configuration
   sessions
   performance
   backends
   api
   contributing

Project information
-------------------

* `Source and issue tracker <https://github.com/jvanasco/pyramid_session_redis>`_
* `Changelog <https://github.com/jvanasco/pyramid_session_redis/blob/main/CHANGES.md>`_
* `Contributors <https://github.com/jvanasco/pyramid_session_redis/blob/main/CONTRIBUTORS.txt>`_
* `License <https://github.com/jvanasco/pyramid_session_redis/blob/main/LICENSE.txt>`_

The project began as a fork of Eric Rasmussen's ``pyramid_redis_sessions``.
Current configuration and payload formats differ from that original project.
