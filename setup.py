# -*- coding: utf-8 -*-
import os
import re

from setuptools import find_packages
from setuptools import setup

HERE = os.path.abspath(os.path.dirname(__file__))

# manage package version
# store version in the init.py
with open(os.path.join(HERE, "src", "pyramid_session_redis", "__init__.py")) as v_file:
    package_version = (
        re.compile(r'.*__VERSION__ = "(.*?)"', re.S).match(v_file.read()).group(1)
    )

long_description = (
    description
) = "High performance and actively maintained server-side session framework for Pyramid and Redis."
with open(os.path.join(HERE, "README.md")) as f:
    long_description = f.read()


# set up requires
install_requires = [
    "redis>=2.4.11, != 2.9.1",
    "pyramid>=1.3",
    "six",
    "zope.interface",  # in Pyramid
]
testing_requires = [
    "nose",
    "pytest",
    "webob",  # in Pyramid
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
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
    ],
    keywords="pyramid session redis",
    author="Jonathan Vanasco",
    author_email="jonathan@findmeon.com",
    url="https://github.com/jvanasco/pyramid_session_redis",
    license="BSD",
    test_suite="nose.collector",
    packages=find_packages(
        where="src",
    ),
    package_dir={"": "src"},
    include_package_data=True,
    zip_safe=False,
    entry_points="",
    install_requires=install_requires,
    tests_require=testing_requires,
    extras_require={
        "testing": testing_extras,
        "docs": docs_extras,
    },
)
