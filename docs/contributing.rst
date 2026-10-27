Development and documentation
=============================

Working from a checkout
-----------------------

Create a virtual environment with a supported Python version, then install:

.. code-block:: sh

   python -m pip install -e '.[testing,docs]'

The ``testing`` extra pins ``setuptools<82`` so older Pyramid releases can
still import ``pkg_resources`` during test collection. Pyramid 2.1 declares
this cap itself; keeping it in the test extra also covers older releases used
by the supported Python matrix. It is not a runtime or build dependency of this
package. See `Pyramid issue 3731 <https://github.com/Pylons/pyramid/issues/3731>`_.

Unit tests and static checks
----------------------------

Without a live backend, leave ``PSR_TEST_REDIS_URL`` unset and run::

    python -m pytest --ignore=tests/test_pyramid.py

The protocol tests in ``tests/test_backend.py`` skip when that environment
variable is unset. Existing application tests in ``tests/test_pyramid.py``
expect localhost database 9 when no URL is configured.

The configured tox environments also support::

    tox -e lint,mypy

Install tox separately if it is not already available. The mypy environment
checks source, the full test suite, and consumer-side typing contracts,
including preserved signatures of decorated session methods.

Coverage reports
----------------

The ``testing`` extra includes pytest-cov and coverage.py's TOML support. Run
line and branch coverage against a disposable Redis or Valkey backend::

    PSR_TEST_REDIS_URL=redis://localhost:6379/9 tox -e coverage

Without a backend, leave the URL unset and run the unit suite only::

    tox -e coverage -- --ignore=tests/test_pyramid.py

The terminal report lists missing lines and branch destinations. Open
``htmlcov/index.html`` to inspect them in context. ``coverage.xml`` and
``coverage.json`` contain machine-readable reports; ``.coverage`` contains the
raw measurements. Generated files are ignored by Git.

Coverage measures the library package, including modules not imported by the
tests. Ordinary pytest runs do not enable measurement. To use pytest directly::

    python -m pytest --cov --cov-config=pyproject.toml --cov-report=term-missing

The configured CI matrix runs coverage against each Python/backend combination
and saves HTML, XML, and JSON reports as artifacts, even when tests fail. There
is initially no minimum-percentage gate. Review uncovered behavior before
choosing a threshold; coverage is evidence of execution, not proof that an
assertion tests every relevant outcome. Interpreter-specific compatibility
branches can legitimately differ between matrix entries.

Configuration layout
--------------------

``setup.cfg`` contains package metadata, dependency extras, package discovery,
Flake8 settings, and tox environments. ``pyproject.toml`` selects the build
backend and holds the Black, mypy, pytest, and coverage configuration. Run
``python -m mypy`` to check the source and test paths configured there.

The version remains in ``pyramid_session_redis.__VERSION__``. Setuptools reads
its literal value through the ``attr:`` directive rather than importing the
application during a build. Modern builds and editable installs use the
declared PEP 517/660 backend; there is no ``setup.py`` entry point. Use
``python -m pip install -e '.[testing,docs]'`` for development and
``python -m build`` for distributions.

``MANIFEST.in`` controls source archive contents. Pre-commit and GitHub Actions
retain their native YAML files, and Sphinx retains ``docs/conf.py``.

Real Redis and Valkey backends
------------------------------

Point the same suite at either backend::

    PSR_TEST_REDIS_URL=redis://localhost:6379/9 python -m pytest

A Unix socket works too::

    PSR_TEST_REDIS_URL='unix:///path/to/backend.sock?db=9' python -m pytest

Use a disposable backend or database. The new protocol tests use unique key
prefixes and remove their keys after each test. Existing application tests can
leave session keys until their TTLs expire. Tests must not flush a shared
database. CI is configured to run the full suite against Redis 7.2, Valkey 7.2,
and Valkey 8.

Build the documentation
-----------------------

Run from the repository root::

    python -m sphinx -W --keep-going -b html docs docs/_build/html

Open ``docs/_build/html/index.html`` in a browser. The warnings-as-errors build
also runs in CI. Configuration reads the version from source without importing
the application or connecting to a backend.

Documentation sources live in the top-level ``docs/`` directory. They are
maintained in the repository and excluded from both wheels and source archives;
installed library packages contain the Python implementation and ``py.typed``.
Build the docs from a repository checkout. Generated HTML is ignored by Git.

Packaging checks
----------------

Install the separate ``build`` frontend, then run::

    python -m pip install build
    python -m build

Inspect the wheel and source archive under ``dist/``. Neither should contain a
``docs`` directory or generated documentation. The wheel should retain
``pyramid_session_redis/py.typed``. Avoid reusing stale ``build/`` output when
checking that files have been removed from a package.
