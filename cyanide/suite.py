from __future__ import absolute_import, print_function, unicode_literals

import celery
import cyanide

import inspect
import platform
import socket
import sys
import traceback

from collections import OrderedDict, defaultdict, namedtuple
from itertools import count, cycle

from celery.exceptions import TimeoutError
from celery.five import items, monotonic, range, values
from celery.utils import timeutils
from celery.utils import isatty
from celery.utils.debug import blockdetection
from celery.utils.imports import qualname
from celery.utils.text import pluralize, truncate
from celery.utils.term import colored
from kombu.utils import retry_over_time

from .fbi import FBI
from .tasks import marker, _marker


BANNER = """\
Cyanide v{version} [celery {celery_version}]

{platform}

[config]
.> app:    {app}
.> broker: {conninfo}
.> suite: {suite}

[toc: {total} {TESTS} total]
{toc}
"""

F_PROGRESS = """\
{0.index:2d}: {0.test.__name__:<36} {status} \
({0.iteration}/{0.total_iterations}) rep#{0.repeats} runtime: \
{runtime}/{elapsed}\
"""

E_STILL_WAITING = """\
Still waiting for {0}. Trying again {when}: {exc!r}\
"""

Progress = namedtuple('Progress', (
    'test', 'iteration', 'total_iterations',
    'index', 'repeats', 'runtime', 'elapsed', 'completed',
))


Inf = float('Inf')


def assert_equal(a, b):
    assert a == b, '{0!r} != {1!r}'.format(a, b)


class StopSuite(Exception):
    pass


def humanize_seconds(secs, prefix='', sep='', now='now', **kwargs):
    s = timeutils.humanize_seconds(secs, prefix, sep, now, **kwargs)
    if s == now and secs > 0:
        return '{prefix}{sep}{0:.2f} seconds'.format(
            float(secs), prefix=prefix, sep=sep)
    return s


def pstatus(p, status=None):
    runtime = format(monotonic() - p.runtime, '.4f')
    elapsed = format(monotonic() - p.elapsed, '.4f')
    return F_PROGRESS.format(
        p,
        status=status or '',
        runtime=humanize_seconds(runtime, now=runtime),
        elapsed=humanize_seconds(elapsed, now=elapsed),
    )


class Speaker(object):

    def __init__(self, gap=5.0, file=None):
        self.gap = gap
        self.file = sys.stdout if file is None else file
        self.last_noise = monotonic() - self.gap * 2

    def beep(self):
        now = monotonic()
        if now - self.last_noise >= self.gap:
            self.emit()
            self.last_noise = now

    def emit(self):
        print('\a', file=self.file, end='')


class Meter(object):

    def __init__(self, s='.', end='', cursor='/-\\', file=None):
        self.s = s
        self.end = end
        self.file = sys.stdout if file is None else file
        self.counter = 0
        self.cursor = cycle(cursor)

    def emit(self, *args, **kwargs):
        self.counter += len(self.s)
        print(self.s * (self.counter - 1) + next(self.cursor),
              end='\r', file=self.file)
        self.file.flush()

    def revert(self):
        self.counter = 0


def testgroup(*funs):
    return OrderedDict((fun.__name__, fun) for fun in funs)


class Suite(object):

    def __init__(self, app,
                 block_timeout=30 * 60, no_color=False,
                 stdout=None, stderr=None):
        self.app = app
        self.stdout = sys.stdout if stdout is None else stdout
        self.stderr = sys.stderr if stderr is None else stderr
        if not isatty(self.stdout):
            no_color = True
        self.colored = colored(enabled=not no_color)
        self.connerrors = self.app.connection().recoverable_connection_errors
        self.block_timeout = block_timeout
        self.progress = None
        self.speaker = Speaker(file=self.stdout)
        self.fbi = FBI(app)
        self.init_groups()

    def setup(self):
        pass

    def teardown(self):
        pass

    def print(self, message, file=None):
        print(message, file=self.stdout if file is None else file)

    def error(self, message):
        print(self.colored.red(message), file=self.stderr)

    def warn(self, message):
        print(self.colored.cyan(message), file=self.stdout)

    def init_groups(self):
        acc = defaultdict(list)
        for attr in dir(self):
            if not _is_descriptor(self, attr):
                meth = getattr(self, attr)
                try:
                    groups = meth.__func__.__testgroup__
                except AttributeError:
                    pass
                else:
                    for g in groups:
                        acc[g].append(meth)
        # sort the tests by the order in which they are defined in the class
        for g in values(acc):
            g[:] = sorted(g, key=lambda m: m.__func__.__testsort__)
        self.groups = dict(
            (name, testgroup(*tests)) for name, tests in items(acc)
        )

    def run(self, names=None, iterations=50, offset=0,
            numtests=None, list_all=False, repeat=0, group='all',
            diag=False, no_join=False, **kw):
        self.no_join = no_join
        self.fbi.enable(diag)
        tests = self.filtertests(group, names)[offset:numtests or None]
        if list_all:
            return self.print(self.testlist(tests))
        self.print(self.banner(tests))
        self.print('+enable worker task events...')
        self.app.control.enable_events()
        it = count() if repeat == Inf else range(int(repeat) or 1)
        for i in it:
            marker(
                '{0} (repetition {1})'.format(
                    self.colored.bold('suite start'), i + 1),
                '+',
            )
            for j, test in enumerate(tests):
                self.runtest(test, iterations, j + 1, i + 1)
            marker(
                '{0} (repetition {1})'.format(
                    self.colored.bold('suite end'), i + 1),
                '+',
            )

    def assert_equal(self, a, b):
        return assert_equal(a, b)

    def filtertests(self, group, names):
        tests = self.groups[group]
        try:
            return ([tests[n] for n in names] if names
                    else list(values(tests)))
        except KeyError as exc:
            raise KeyError('Unknown test name: {0}'.format(exc))

    def testlist(self, tests):
        return ',\n'.join(
            '.> {0}) {1}'.format(i + 1, t.__name__)
            for i, t in enumerate(tests)
        )

    def banner(self, tests):
        app = self.app
        return BANNER.format(
            app='{0}:0x{1:x}'.format(app.main or '__main__', id(app)),
            version=cyanide.__version__,
            celery_version=celery.VERSION_BANNER,
            conninfo=app.connection().as_uri(),
            platform=platform.platform(),
            toc=self.testlist(tests),
            TESTS=pluralize(len(tests), 'test'),
            total=len(tests),
            suite=':'.join(qualname(self).rsplit('.', 1)),
        )

    def runtest(self, fun, n=50, index=0, repeats=1):
        n = getattr(fun, '__iterations__', None) or n
        header = '[[[{0}({1})]]]'.format(fun.__name__, n)
        if repeats > 1:
            header = '{0} #{1}'.format(header, repeats)
        self.print(header)
        with blockdetection(self.block_timeout):
            with self.fbi.investigation():
                runtime = elapsed = monotonic()
                i = 0
                failed = False
                self.progress = Progress(
                    fun, i, n, index, repeats, elapsed, runtime, 0,
                )
                _marker.delay(pstatus(self.progress))

                try:
                    for i in range(n):
                        runtime = monotonic()
                        self.progress = Progress(
                            fun, i + 1, n, index, repeats, runtime, elapsed, 0,
                        )
                        self.execute_test(fun)

                except Exception:
                    failed = True
                    self.speaker.beep()
                    raise
                finally:
                    if n > 1 or failed:
                        self.print('{0} {1} iterations in {2}'.format(
                            'failed after' if failed else 'completed',
                            i + 1, humanize_seconds(monotonic() - elapsed),
                        ), file=self.stderr if failed else self.stdout)
                    if not failed:
                        self.progress = Progress(
                            fun, i + 1, n, index, repeats, runtime, elapsed, 1,
                        )

    def execute_test(self, fun):
        self.setup()
        try:
            try:
                fun()
            except StopSuite:
                raise
            except AssertionError as exc:
                self.on_test_error(exc, 'FAILED')
            except Exception as exc:
                self.on_test_error(exc, 'ERROR')
            else:
                self.print(pstatus(self.progress, self.colored.green('OK')))
        finally:
            self.teardown()

    def on_test_error(self, exc, status):
        self.error('-> {0!r}'.format(exc))
        self.error(traceback.format_exc())
        self.error(pstatus(self.progress, self.colored.red(status)))

    def missing_results(self, r):
        return [res.id for res in r if res.id not in res.backend._cache]

    def wait_for(self, fun, catch,
                 desc='thing', args=(), kwargs={}, errback=None,
                 max_retries=10, interval_start=0.1, interval_step=0.5,
                 interval_max=5.0, emit_warning=False, **options):
        meter = Meter(file=self.stdout)

        def on_error(exc, intervals, retries):
            interval = next(intervals)
            if emit_warning:
                self.warn(E_STILL_WAITING.format(
                    desc, when=humanize_seconds(interval, 'in', ' '), exc=exc,
                ))
            else:
                meter.emit()
            if errback:
                errback(exc, interval, retries)
            return interval

        return self.retry_over_time(
            fun, catch,
            args=args, kwargs=kwargs,
            errback=on_error, max_retries=max_retries,
            interval_start=interval_start, interval_step=interval_step,
            **options
        )

    def ensure_not_for_a_while(self, fun, catch,
                               desc='thing', max_retries=20,
                               interval_start=0.1, interval_step=0.02,
                               interval_max=1.0, emit_warning=False,
                               **options):
        meter = Meter(file=self.stdout)
        try:
            return self.wait_for(
                fun, catch, desc=desc, max_retries=max_retries,
                interval_start=interval_start, interval_step=interval_step,
                interval_max=interval_max, emit_warning=emit_warning,
                errback=meter.emit,
            )
        except catch:
            pass
        else:
            raise AssertionError('Should not have happened: {0}'.format(desc))
        finally:
            meter.revert()

    def retry_over_time(self, *args, **kwargs):
        return retry_over_time(*args, **kwargs)

    def join(self, r, propagate=False, max_retries=10, **kwargs):
        if self.no_join:
            return
        received = []

        def on_result(task_id, value):
            received.append(task_id)

        for i in range(max_retries) if max_retries else count(0):
            received[:] = []
            try:
                return r.get(callback=on_result, propagate=propagate, **kwargs)
            except (socket.timeout, TimeoutError) as exc:
                waiting_for = self.missing_results(r)
                self.speaker.beep()
                marker(
                    'Still waiting for {0}/{1}: [{2}]: {3!r}'.format(
                        len(r) - len(received), len(r),
                        truncate(', '.join(waiting_for)), exc), '!',
                )
                self.fbi.diag(waiting_for)
            except self.connerrors as exc:
                self.speaker.beep()
                marker('join: connection lost: {0!r}'.format(exc), '!')
        raise StopSuite('Test failed: Missing task results')

    def dump_progress(self):
        return pstatus(self.progress) if self.progress else 'No test running'


_creation_counter = count(0)


def testcase(*groups, **kwargs):
    if not groups:
        raise ValueError('@testcase requires at least one group name')

    def _mark_as_case(fun):
        fun.__testgroup__ = groups
        fun.__testsort__ = next(_creation_counter)
        fun.__iterations__ = kwargs.get('iterations')
        return fun

    return _mark_as_case


def _is_descriptor(obj, attr):
    try:
        cattr = getattr(obj.__class__, attr)
    except AttributeError:
        pass
    else:
        return not inspect.ismethod(cattr) and hasattr(cattr, '__get__')
    return False
