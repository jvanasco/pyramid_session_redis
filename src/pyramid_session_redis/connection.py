# -*- coding: utf-8 -*-

"""
Defines common methods for obtaining a redis connection.

To use a custom connect function, create a callable with parameters:

  ``request``
  The current pyramid request object

  ``**redis_options``
  Additional keyword arguments accepted by redis-py's StrictRedis class


The callable must return an instance of StrictRedis or must implement the same
interface.

To use your custom connection function, you can pass it in directly as the
``client_callable`` argument to ``pyramid_session_redis.RedisSessionFactory``
or ``pyramid_session_redis.session_factory_from_settings``, or in your config
file you can specify a dotted python path as a string.


Example configuration in python::

    from my_cool_app import my_redis_connection_getter
    from pyramid_session_redis import session_factory_from_settings

    def main(global_config, **settings):
        config = Configurator(**settings)
        settings['client_callable'] = my_redis_connection_getter
        session_factory = session_factory_from_settings(settings)
        config.set_session_factory(session_factory)


Example configuration from an ini file::

    redis.sessions.secret = mysecret
    redis.sessions.client_callable = my_cool_app.my_redis_client_getter


This option is available so that developers can define their own Redis
instances as needed, but most users should not need to customize how they
connect.
"""
# stdlib
from typing import Optional
from typing import Type
from typing import TYPE_CHECKING

# pypi
from redis import StrictRedis

if TYPE_CHECKING:
    from webob.request import Request

    # from pyramid.request import Request  # webob has stubs; pyramid does not

# ==============================================================================


def get_default_connection(
    request: "Request",
    url: Optional[str] = None,
    client_class: Type[StrictRedis] = StrictRedis,
    **redis_options,
) -> StrictRedis:
    """
    Default Redis connection handler. Once a connection is established it is
    saved in `request.registry`.

    :param request: The current Pyramid ``Request`` object.
    :param url: string. An optional connection string that will be passed
        directly to `StrictRedis.from_url`. The connection string should be in
        the form `redis://username:password@localhost:6379/0`
    :param settings: dict. A dict of keyword args to be passed directly
        to `StrictRedis`.
    :returns: An instance of `StrictRedis`
    """
    # attempt to get an existing connection from the registry
    client = getattr(request.registry, "_pyramid_session_redis", None)

    # if we found an active connection, return it
    if client is not None:
        return client

    # otherwise create a new connection
    if url is not None:
        # remove defaults to avoid duplicating settings in the `url`
        redis_options.pop("password", None)
        redis_options.pop("host", None)
        redis_options.pop("port", None)
        redis_options.pop("db", None)
        # the StrictRedis.from_url option no longer takes a socket
        # argument. instead, sockets should be encoded in the URL if
        # used. example:
        #     unix://[:password]@/path/to/socket.sock?db=0
        redis_options.pop("unix_socket_path", None)
        # connection pools are also no longer a valid option for
        # loading via URL
        redis_options.pop("connection_pool", None)
        redis = client_class.from_url(url, **redis_options)
    else:
        redis = client_class(**redis_options)

    # save the new connection in the registry
    setattr(request.registry, "_pyramid_session_redis", redis)

    return redis
