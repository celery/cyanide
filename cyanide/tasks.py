# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import os
import signal
import sys

from time import sleep

from celery.exceptions import SoftTimeLimitExceeded
from celery.utils.log import get_task_logger

from .app import app

E_MARKER_DELAY_ERROR = """\
Retrying marker.delay().  It failed to start: {0}\
"""

logger = get_task_logger(__name__)


def marker(s, sep='-'):
    """Marker is a task that logs something to the worker logs.

    :param s: Text to log.

    """
    print('{0}{1}'.format(sep, s))
    while True:
        try:
            return _marker.delay(s, sep)
        except Exception as exc:
            print(E_MARKER_DELAY_ERROR.format(exc))


@app.task
def _marker(s, sep='---'):
    print('{sep} {0} {sep}'.format(s, sep=sep))


@app.task
def add(x, y):
    """Add two numbers."""
    return x + y


@app.task(bind=True)
def ids(self, i):
    """Returns a tuple of ``root_id``, ``parent_id`` and
    the argument passed as ``i``."""
    return self.request.root_id, self.request.parent_id, i


@app.task(bind=True)
def collect_ids(self, res, i):
    """Used as a callback in a chain or group where the previous tasks
    are :task:`ids`: returns a tuple of::

        (previous_result, (root_id, parent_id, i))

    """
    return res, ids(i)


@app.task
def xsum(x):
    """Takes a list of numbers and returns the total."""
    return sum(x)


@app.task
def any_(*args, **kwargs):
    """Task taking any argument, returning nothing.

    This is useful for testing related to large arguments: big values,
    an insane number of positional arguments, etc.

    :keyword sleep: Optional number of seconds to sleep for before returning.

    """
    wait = kwargs.get('sleep')
    if wait:
        sleep(wait)


@app.task
def any_returning(*args, **kwargs):
    """The same as :task:`any` except it returns the arguments given
    as a tuple of ``(args, kwargs)``."""
    any_(*args, **kwargs)
    return args, kwargs


@app.task
def exiting(status=0):
    """Task calling ``sys.exit(status)`` to terminate its own worker
    process."""
    sys.exit(status)


@app.task
def kill(sig=getattr(signal, 'SIGKILL', None) or signal.SIGTERM):
    """Task sending signal to process currently executing itself.

    :keyword sig: Signal to send as signal number, default is :sig:`KILL`
      on platforms that supports that signal, for other platforms (i.e Windows)
      it will be :sig:`TERM`.

    """
    os.kill(os.getpid(), sig)


@app.task
def sleeping(i, **_):
    """Task sleeping for ``i`` seconds, and returning nothing."""
    sleep(i)


@app.task
def sleeping_ignore_limits(i, **_):
    """Task sleeping for ``i`` seconds, while ignoring soft time limits.

    If the task is signalled with
    :exc:`~celery.exceptions.SoftTimeLimitExceeded` the signal is ignored
    and the task will sleep for ``i`` seconds again, which will trigger
    the hard time limit (if enabled).

    """
    try:
        sleep(i)
    except SoftTimeLimitExceeded:
        sleep(i)


@app.task(bind=True)
def retries(self, n=1, countdown=1, return_value=10):
    """Task that retries itself ``n`` times.

    :param n: Number of times to retry.
    :param n: Seconds to wait (``int``/``float``) between each retry (default
      is one second).
    :param return_value: Value to return when task finally succeeds.
        Default is 10 (don't ask, I guess it's a random true value).

    """
    if not self.request.retries or self.request.retries < n:
        raise self.retry(countdown=countdown)
    return return_value


@app.task
def print_unicode(log_message='håå®ƒ valmuefrø', print_message='hiöäüß'):
    """Task that both logs and print strings containing funny characters."""
    logger.warning(log_message)
    print(print_message)


@app.task
def segfault():
    """Task causing a segfault, abruptly terminating the process
    executing the task."""
    import ctypes
    ctypes.memset(0, 0, 1)
    assert False, 'should not get here'


@app.task(bind=True)
def chord_adds(self, x):
    """Task that adds a new task to the current chord in a workflow."""
    self.add_to_chord(add.s(x, x))
    return 42


@app.task(bind=True)
def chord_replace(self, x):
    """Task that replaces itself in the current chord."""
    return self.replace_in_chord(add.s(x, x))


@app.task
def raising(exc=KeyError()):
    """Task raising exception.

    :param exc: Exception to raise.

    """
    raise exc


@app.task
def errback(request, exc, traceback):
    print('Task id {0!r} raised exception: {1!r}\n{2}'.format(
        request.id, exc, traceback,
    ))


@app.task
def old_errback(task_id):
    print('Task id %r raised exception' % (task_id,))


@app.task
def logs(msg, p=False):
    """Log a message to the worker logs.

    :keyword p: If set to :const:`True` the message will be printed instead
      of logged, thus being redirected to the stdout logger.

    """
    print(msg) if p else logger.info(msg)
