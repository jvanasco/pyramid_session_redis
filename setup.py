# -*- coding: utf-8 -*-
import os
import re

from setuptools import find_packages
from setuptools import setup

# ==============================================================================

HERE = os.path.abspath(os.path.dirname(__file__))

# manage package version
# store version in the init.py
with open(os.path.join(HERE, "src", "pyramid_session_redis", "__init__.py")) as v_file:
    package_version = (
        re.compile(r'.*__VERSION__ = "(.*?)"', re.S).match(v_file.read()).group(1)  # type: ignore[union-attr]
    )

long_description = description = (
    "High performance and actively maintained server-side session framework for Pyramid and Redis."
)
with open(os.path.join(HERE, "README.md")) as f:
    long_description = f.read()


# set up requires
install_requires = [
    "redis>=4.0.0",
    "pyramid>=2",
    "zope.interface",  # in Pyramid
    "typing_extensions",  # for 3.7 `Literal`; Protocol
]
testing_requires = [
    "mypy",
    "nose",
    "pytest",
    "types-webob",  # stubs
    "webob",  # in Pyramid
    "webtest",
    "waitress",
]
testing_extras = install_requires + testing_requires + ["coverage"]
docs_extras = [
    "sphinx",
]

setup(
    name="pyramid_session_redis",
    version=package_version,
    description=description,
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=[
        "Intended Audience :: Developers",
        "Framework :: Pyramid",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
    keywords="pyramid session redis",
    author="Jonathan Vanasco",
    author_email="jonathan@findmeon.com",
    url="https://github.com/jvanasco/pyramid_session_redis",
    license="BSD",
    test_suite="nose.collector",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    package_data={
        "": [
            "py.typed",
            "docs/*",
        ],
    },
    zip_safe=False,
    entry_points="",
    install_requires=install_requires,
    tests_require=testing_requires,
    extras_require={
        "testing": testing_extras,
        "docs": docs_extras,
    },
)
