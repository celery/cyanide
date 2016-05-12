=====================================================================
 Cyanide - Celery stress testing and integration test support.
=====================================================================

|build-status| |coverage|

:Version: 1.1.0
:Web: http://cyanide.readthedocs.org/
:Download: http://pypi.python.org/pypi/cyanide/
:Source: http://github.com/celery/cyanide/
:Keywords: celery, stress, integration, functional, testing

.. contents::
    :local:

Introduction
============

This stress test suite will attempt to break the Celery worker in different
ways, and can also be used to write new stress test suites for projects
depending on Celery infrastructure.

The worker must currently be started separately, and it's encouraged
to repeat the suite using workers started with different configuration values.

Ideas include:

#. Default, single process:
    ::

        $ celery -A cyanide worker -c 1

#. Default, multiple processes:
    ::

        $ celery -A cyanide worker -c 8

#.  Frequent ``maxtasksperchild`` recycling, single child process:
    ::

        $ celery -A cyanide worker -c 1 --maxtasksperchild=1

#. Frequent autoscale scale down & ``maxtasksperchild``, single child process:
    ::

        $ AUTOSCALE_KEEPALIVE=0.01 celery -A cyanide worker \
        >   --autoscale=1,0 --maxtasksperchild=1

#. Frequent ``maxtasksperchild``, multiple child processes:
    ::

        $ celery -A cyanide worker -c 8 --maxtasksperchild=1

#. Processes terminated by time limits:
    ::

        $ celery -A cyanide worker --time-limit=1

#. Frequent ``maxtasksperchild``, single child process with late ack:
    ::

        $ celery -A cyanide worker -c1 --maxtasksperchild=1 -Z acks_late

#. Worker using the ``eventlet`` pool:

    Start the worker, here having a thousand green-threads:
    ::

            $ celery -A cyanide worker -c1000 -P eventlet

    You must activate the `green` test group when starting the test suite:
    ::

        $ celery cyanide -g green

#. Worker using the ``gevent`` pool:

    Start the worker, here having a thousand green-threads:
    ::

            $ celery -A cyanide worker -c1000 -P gevent

    You must activate the `green` test group when starting the test suite:
    ::

        $ celery cyanide -g green

Tips
====

It's a good idea to include the ``--purge <celery worker --purge>``
argument to clear out tasks from previous runs.

Note that the stress client will probably hang if the test fails, so this
test suite is currently not suited for automatic runs.

Configuration Templates
=======================

You can select a configuration template using the `-Z` command-line argument
to any ``celery -A cyanide`` command or the ``celery cyanide``
command used to execute the test suite.

The templates available are:

* ``default``

    Using AMQP as a broker, RPC as a result backend,
    and using JSON serialization for task and result messages.

    Both broker and result store is expected to run at localhost.

* ``vagrant1``

    Use the VM started by ``celery vagrant up`` as the broker
    and result backend (RabbitMQ).

* ``vagrant1_redis``

    Use the VM started by ``celery vagrant up`` as the broker
    and result backend (Redis).

* ``redis``

    Using Redis as a broker and result backend.

* ``redistore``

    Using Redis as a result backend only.

* ``acks_late``

    Enables late ack globally.

* ``pickle``

    Using pickle as the serializer for tasks and results
    (also allowing the worker to receive and process pickled messages)

* ``confirms``

    Enables RabbitMQ publisher confirmations.

* ``events``

    Configure workers to send task events.

* ``proto1``

    Use version 1 of the task message protocol (pre 4.0)

You can see the resulting configuration from any template by running
the command:
::

    $ celery -A cyanide report -Z redis

Examples
--------

Example running the stress test using the ``redis`` configuration template:
::

    $ cyanide -Z redis

Example running the worker using the ``redis`` configuration template:
::

    $ celery -A cyanide worker -Z redis

You can also mix several templates by providing a comma-separated list:
::

    $ celery -A cyanide worker -Z redis,acks_late

In this example (``redis,acks_late``) the ``redis`` template will be used
as main configuration, and then the additional keys from the ``acks_late`` template
will be merged as changes.

Test Suite Options
==================

After one or more worker instances are running, you can start executing the
tests.

By default the complete test suite will be executed:
::

    $ celery cyanide

You can also specify what test cases to run by providing one or more names
as arguments:
::

    $ celery cyanide revoketermfast revoketermslow

A full list of test case names can be retrieved with the
``-l <celery cyanide -l>`` switch:
::

    $ celery cyanide -l
    .> 1) chain,
    .> 2) chaincomplex,
    .> 3) parentids_chain,
    .> 4) parentids_group,
    .> 5) manyshort,
    .> 6) unicodetask,
    .> 7) always_timeout,
    .> 8) termbysig,
    .> 9) timelimits,
    .> 10) timelimits_soft,
    .> 11) alwayskilled,
    .> 12) alwaysexits,
    .> 13) bigtasksbigvalue,
    .> 14) bigtasks,
    .> 15) smalltasks,
    .> 16) revoketermfast,
    .> 17) revoketermslow

You can also start from an offset within this list, e.g. to skip the first two
tests use ``--offset=2 <celery cyanide --offset>``:
::

    $ celery cyanide --offset=2

See ``celery cyanide --help`` for a list of all available
command-line options.

Vagrant
=======

Starting
--------

Cyanide ships with a complete virtual machine solution to run your tests.
The image ships with Celery, Cyanide, RabbitMQ and Redis and can be deployed
simply by running the ``celery vagrant`` command:
::

    $ celery vagrant up


The IP address of the new virtual machine will be 192.168.33.123,
and you can easily tell both the worker and cyanide test suite to use
it by specifying the ``vagrant1`` (RabbitMQ) or ``vagrant1_redis`` templates:
::

    $ celery -A worker -Z vagrant1
    $ celery cyanide -Z vagrant1

SSH
---

To open an SSH session with the virtual machine after starting
with ``celery vagrant up`` do:
::

    $ ssh $(celery vagrant sshargs)

Stopping
--------

To shutdown the virtual machine run the command:
::

    $ celery vagrant halt

To destroy the instance run the command:

::

    $ celery vagrant destroy


.. note::

    To completely wipe your instance you need to remove the
    ``.vagrant`` directory.

    The location of this directory can be retrieved by executing
    the following:
    ::

        $ celery vagrant statedir
        /opt/devel/cyanide/cyanide/vagrant/.vagrant

    You can combine this with ``rm`` to force removal of this
    directory:
    ::

        $ rm -rf $(celery vagrant statedir)

Environment Variables
=====================

``CYANIDE_TRANS``
-----------------

If the ``CYANIDE_TRANS`` environment variable is set
the stress test suite will use transient task messages instead of persisting
messages to disk.

To avoid declaration collision the ``cstress.trans`` queue name will be used
when this option is enabled.

``CYANIDE_BROKER``
------------------

You can set the ``CYANIDE_BROKER`` environment variable
to change the default broker used:
::

    $ CYANIDE_BROKER='amqp://' celery -A cyanide worker # ...
    $ CYANIDE_BROKER='amqp://' celery cyanide

``CYANIDE_BACKEND``
-------------------

You can set the ``CYANIDE_BACKEND`` environment variable to change
the result backend used:
::

    $ CYANIDE_BACKEND='amqp://' celery -A cyanide worker # ...
    $ CYANIDE_BACKEND='amqp://' celery cyanide

``CYANIDE_QUEUE``
-----------------

A queue named ``c.stress`` is created and used by default for all task
communication.

You can change the name of this queue using the ``CYANIDE_QUEUE``
environment variable:
::

    $ CYANIDE_QUEUE='cyanide' celery -A cyanide worker # ...
    $ CYANIDE_QUEUE='cyanide' celery cyanide

``CYANIDE_PREFETCH``
--------------------

The ``CYANIDE_PREFETCH`` environment variable sets the default prefetch
multiplier (default value is 10).

``AWS_REGION``
--------------

The ``AWS_REGION`` environment variable changes the Amazon AWS region
to something other than the default ``us-east-1``, to be used with the
``sqs`` template.


Custom Suites
=============

You can define custom suites (look at source code of
``cyanide.suites.default`` for inspiration), and tell cyanide to use that
suite by specifying the ``celery cyanide -S`` option:
::

    $ celery cyanide -S proj.funtests:MySuite

.. _installation:

Installation
============

You can install cyanide either via the Python Package Index (PyPI)
or from source.

To install using `pip`:
::

    $ pip install -U cyanide

.. _installing-from-source:

Downloading and installing from source
--------------------------------------

Download the latest version of cyanide from
http://pypi.python.org/pypi/cyanide

You can install it by doing the following:
::

    $ tar xvfz cyanide-0.0.0.tar.gz
    $ cd cyanide-0.0.0
    $ python setup.py build
    # python setup.py install

The last command must be executed as a privileged user if
you are not currently using a virtualenv.

.. _installing-from-git:

Using the development version
-----------------------------

With pip
~~~~~~~~

You can install the latest snapshot of cyanide using the following
pip command:
::

    $ pip install https://github.com/celery/cyanide/zipball/master#egg=cyanide

.. |build-status| image:: https://secure.travis-ci.org/celery/cyanide.png?branch=master
    :alt: Build status
    :target: https://travis-ci.org/celery/cyanide

.. |coverage| image:: https://codecov.io/github/celery/cyanide/coverage.svg?branch=master
    :target: https://codecov.io/github/celery/cyanide?branch=master

