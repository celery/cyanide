from __future__ import absolute_import, unicode_literals

import random

from time import sleep

from celery import group

from cyanide.tasks import (
    add, any_, exiting, kill, sleeping,
    sleeping_ignore_limits, any_returning,
)
from cyanide.data import BIG, SMALL
from cyanide.suite import Suite, testcase


class Default(Suite):

    @testcase('all', 'green')
    def manyshort(self):
        self.join(group(add.s(i, i) for i in range(1000))(),
                  timeout=10, propagate=True)

    @testcase('all')
    def always_timeout(self):
        self.join(
            group(sleeping.s(1).set(time_limit=0.1)
                  for _ in range(100))(),
            timeout=10, propagate=False,
        )

    @testcase('all')
    def termbysig(self):
        self._evil_groupmember(kill)

    @testcase('green')
    def group_with_exit(self):
        self._evil_groupmember(exiting)

    @testcase('all')
    def timelimits(self):
        self._evil_groupmember(sleeping, 2, time_limit=1)

    @testcase('all')
    def timelimits_soft(self):
        self._evil_groupmember(sleeping_ignore_limits, 2,
                               soft_time_limit=1, time_limit=1.1)

    @testcase('all')
    def alwayskilled(self):
        g = group(kill.s() for _ in range(10))
        self.join(g(), timeout=10)

    @testcase('all', 'green')
    def alwaysexits(self):
        g = group(exiting.s() for _ in range(10))
        self.join(g(), timeout=10)

    def _evil_groupmember(self, evil_t, *eargs, **opts):
        g1 = group(add.s(2, 2).set(**opts), evil_t.s(*eargs).set(**opts),
                   add.s(4, 4).set(**opts), add.s(8, 8).set(**opts))
        g2 = group(add.s(3, 3).set(**opts), add.s(5, 5).set(**opts),
                   evil_t.s(*eargs).set(**opts), add.s(7, 7).set(**opts))
        self.join(g1(), timeout=10)
        self.join(g2(), timeout=10)

    @testcase('all', 'green')
    def bigtasksbigvalue(self):
        g = group(any_returning.s(BIG, sleep=0.3) for i in range(8))
        r = g()
        try:
            self.join(r, timeout=10)
        finally:
            # very big values so remove results from backend
            try:
                r.forget()
            except NotImplementedError:
                pass

    @testcase('all', 'green')
    def bigtasks(self, wait=None):
        self._revoketerm(wait, False, False, BIG)

    @testcase('all', 'green')
    def smalltasks(self, wait=None):
        self._revoketerm(wait, False, False, SMALL)

    @testcase('all')
    def revoketermfast(self, wait=None):
        self._revoketerm(wait, True, False, SMALL)

    @testcase('all')
    def revoketermslow(self, wait=5):
        self._revoketerm(wait, True, True, BIG)

    def _revoketerm(self, wait=None, terminate=True,
                    joindelay=True, data=BIG):
        g = group(any_.s(data, sleep=wait) for i in range(8))
        r = g()
        if terminate:
            if joindelay:
                sleep(random.choice(range(4)))
            r.revoke(terminate=True)
        self.join(r, timeout=10)
