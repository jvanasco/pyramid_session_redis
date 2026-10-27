Getting started
===============

Install
-------

The current package supports Python 3.7+, Pyramid 2+, and redis-py 4+.
Install it in your application's environment::

    python -m pip install pyramid_session_redis

Run a Redis or Valkey server that the application can reach. See :doc:`backends`
for connection options and Valkey examples.

Configure Pyramid
-----------------

Add settings to your application's INI file:

.. code-block:: ini

   redis.sessions.secret = replace-with-a-private-random-secret
   redis.sessions.redis_url = redis://localhost:6379/0
   redis.sessions.timeout = 1200

Include the package before creating the WSGI application:

.. code-block:: python

   from pyramid.config import Configurator

   def main(global_config, **settings):
       config = Configurator(settings=settings)
       config.include("pyramid_session_redis")
       # Register the application's routes and views here.
       return config.make_wsgi_app()

The include resolves supported dotted paths, parses the ``redis.sessions.*``
settings, and registers the session factory. Use a private signing secret shared
by all application workers that read the same sessions. Changing it invalidates
the cookies those workers can accept.

You can also construct and register the factory directly:

.. code-block:: python

   from pyramid.config import Configurator
   from pyramid_session_redis import RedisSessionFactory

   session_factory = RedisSessionFactory(
       secret=signing_secret,  # supplied by your application's configuration
       redis_url="redis://localhost:6379/0",
       timeout=1200,
   )
   config = Configurator(session_factory=session_factory)

Use the session
---------------

.. code-block:: python

   def remember_preference(request):
       request.session["theme"] = "dark"
       request.session.flash("Preference saved")
       return {"theme": request.session["theme"]}

Simply accessing an empty, new session does not normally create a backend key
or send a cookie. Adding data causes an ID to be reserved when needed, a cookie
to be set during response processing, and the payload to be written by a
finished callback. Existing sessions load from the backend when Pyramid first
constructs ``request.session``.

The default cookie is named ``session``. It is HTTP-only, scoped to ``/``, and
lasts for the browser session. For an HTTPS application, configure cookie flags
according to its deployment, for example:

.. code-block:: ini

   redis.sessions.cookie_secure = true
   redis.sessions.cookie_httponly = true
   redis.sessions.cookie_samesite = lax

Cookie lifetime and backend inactivity timeout are separate controls. See
:doc:`configuration` for all defaults and :doc:`sessions` for invalidation.
