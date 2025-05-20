# stdlib

# pypi
from pyramid.config import Configurator
from pyramid.request import Request
from pyramid.response import Response
from waitress import serve

# local
from .test_config import LIVE_PSR_CONFIG

# ==============================================================================


def session_access__none(request: Request):
    return Response("<body><h1>session_access__none</h1></body>")


def session_access__set(request: Request):
    request.session["a"] = 1
    return Response("<body><h1>session_access__set</h1></body>")


def session_access__set_unset(request: Request):
    request.session["a"] = 1
    del request.session["a"]
    return Response("<body><h1>session_access__set_unset</h1></body>")


def session_access__unset(request: Request):
    try:
        del request.session["a"]
    except Exception:
        pass
    return Response("<body><h1>session_access__unset</h1></body>")


def main(global_config, **settings):
    """This function returns a Pyramid WSGI application."""
    config = Configurator(settings=settings)
    config.include("pyramid_session_redis")

    # --------------------------------------------------------------------------

    # session_access__none
    config.add_route("session_access__none", "/session_access__none")
    config.add_view(session_access__none, route_name="session_access__none")

    # session_access__set
    config.add_route("session_access__set", "/session_access__set")
    config.add_view(session_access__set, route_name="session_access__set")

    # session_access__set_unset
    config.add_route("session_access__set_unset", "/session_access__set_unset")
    config.add_view(session_access__set_unset, route_name="session_access__set_unset")

    # session_access__unset
    config.add_route("session_access__unset", "/session_access__unset")
    config.add_view(session_access__unset, route_name="session_access__unset")

    # --------------------------------------------------------------------------

    app = config.make_wsgi_app()
    return app


if __name__ == "__main__":
    app = main(None, **LIVE_PSR_CONFIG)
    serve(app, host="0.0.0.0", port=6543)
