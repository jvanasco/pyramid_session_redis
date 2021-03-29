.. _front:

======================
pyramid_session_redis
======================
This package provides a fast and stable implementation of Pyramid's `ISession
interface <https://docs.pylonsproject.org/projects/pyramid/en/latest/api/interfaces.html#pyramid.interfaces.ISession>`_,
using Redis as its backend.

``pyramid_session_redis`` is a fork of the `pyramid_redis_sessions 
<https://github.com/ericrasmussen/pyramid_redis_sessions>`_ project by
Eric Rasmussen. The code and documentation have been changed significantly as the
API and feature set evolved.

Narrative Documentation
=======================

.. toctree::
   :maxdepth: 2

   gettingstarted
   advanced
   api
   redis
   contributing


Support and Documentation
=========================
The official documentation is available at:
https://github.com/jvanasco/pyramid_session_redis

You can report bugs or open support requests in the `github issue tracker
<https://github.com/jvanasco/pyramid_session_redis/issues>`_.


Authors
=======
`Jonathan Vanasco <https://github.com/jvanasco>` is the primary author. 
The original code was written by `Eric Rasmussen <https://github.com/ericrasmussen>`_.

A complete list of contributors is available in `CONTRIBUTORS.txt
<https://github.com/jvanasco/pyramid_session_redis/blob/main/CONTRIBUTORS.txt>`_.



License
=======
`pyramid_session_redis` is available under a FreeBSD-derived license. See
`LICENSE.txt <https://github.com/jvanasco/pyramid_session_redis/blob/main/LICENSE.txt>`_
for details.

It is hoped this project can be relicensed under the MIT license in the future.



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
