# -*- coding: utf-8 -*-

import os
import re

from setuptools import find_packages
from setuptools import setup

# manage package version
# store version in the init.py
with open(
    os.path.join(os.path.dirname(__file__), "pyramid_session_redis", "__init__.py")
) as v_file:
    package_version = (
        re.compile(r'.*__VERSION__ = "(.*?)"', re.S).match(v_file.read()).group(1)
    )


# set up requires
install_requires = [
    "redis>=2.4.11, != 2.9.1",
    "pyramid>=1.3,<2",
    "six",
    # 'zope.interface',  # in Pyramid
]
testing_requires = [
    "nose",
    # 'webob',  # in Pyramid
]
testing_extras = testing_requires + ["coverage"]
docs_extras = ["sphinx"]


def main():

    setup(
        name="pyramid_session_redis",
        version=package_version,
        description="Pyramid web framework session factory backed by Redis",
        long_description="""High performance and actively maintained server-side session framework for Pyramid and Redis.  https://github.com/jvanasco/pyramid_session_redis""",
        classifiers=[
            "Intended Audience :: Developers",
            "Framework :: Pyramid",
            "Programming Language :: Python :: 2.7",
            "Programming Language :: Python :: 3",
        ],
        keywords="pyramid session redis",
        author="Jonathan Vanasco",
        author_email="jonathan@findmeon.com",
        url="https://github.com/jvanasco/pyramid_session_redis",
        license="FreeBSD",
        packages=find_packages(),
        # test_suite='pyramid_session_redis.tests.test_factory.TestRedisSessionFactory_loggedExceptions',
        test_suite="nose.collector",
        include_package_data=True,
        zip_safe=False,
        tests_require=testing_requires,
        install_requires=install_requires,
        entry_points="",
        extras_require={"testing": testing_extras, "docs": docs_extras},
    )


if __name__ == "__main__":
    main()
