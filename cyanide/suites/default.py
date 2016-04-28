from __future__ import absolute_import, unicode_literals

import random

from time import sleep

from celery import chain, group, uuid

from cyanide.tasks import (
    add, any_, collect_ids, exiting, ids, kill, sleeping,
    sleeping_ignore_limits, any_returning, print_unicode,
)
from cyanide.data import BIG, SMALL
from cyanide.suite import Suite, assert_equal, testcase


class Default(Suite):

    @testcase('all', 'green', 'redis', iterations=1)
    def chain(self):
        c = add.s(4, 4) | add.s(8) | add.s(16)
        assert_equal(self.join(c()), 32)

    @testcase('all', 'green', 'redis', iterations=1)
    def chaincomplex(self):
        c = (
            add.s(2, 2) | (
                add.s(4) | add.s(8) | add.s(16)
            ) |
            group(add.s(i) for i in range(4))
        )
        res = c()
        assert_equal(res.get(), [32, 33, 34, 35])

    @testcase('all', 'green', 'redis', iterations=1)
    def parentids_chain(self, num=248):
        c = chain(ids.si(i) for i in range(num))
        c.freeze()
        res = c()
        res.get(timeout=5)
        self.assert_ids(res, num - 1)

    @testcase('all', 'green', 'redis', iterations=1)
    def parentids_group(self):
        g = ids.si(1) | ids.si(2) | group(ids.si(i) for i in range(2, 50))
        res = g()
        expected_root_id = res.parent.parent.id
        expected_parent_id = res.parent.id
        values = res.get(timeout=5)

        for i, r in enumerate(values):
            root_id, parent_id, value = r
            assert_equal(root_id, expected_root_id)
            assert_equal(parent_id, expected_parent_id)
            assert_equal(value, i + 2)

    def assert_ids(self, res, size):
        i, root = size, res
        while root.parent:
            root = root.parent
        node = res
        while node:
            root_id, parent_id, value = node.get(timeout=5)
            assert_equal(value, i)
            assert_equal(root_id, root.id)
            if node.parent:
                assert_equal(parent_id, node.parent.id)
            node = node.parent
            i -= 1

    @testcase('redis', iterations=1)
    def parentids_chord(self):
        self.assert_parentids_chord()
        self.assert_parentids_chord(uuid(), uuid())

    def assert_parentids_chord(self, base_root=None, base_parent=None):
        g = (
            ids.si(1) |
            ids.si(2) |
            group(ids.si(i) for i in range(3, 50)) |
            collect_ids.s(i=50) |
            ids.si(51)
        )
        g.freeze(root_id=base_root, parent_id=base_parent)
        res = g.apply_async(root_id=base_root, parent_id=base_parent)
        expected_root_id = base_root or res.parent.parent.parent.id

        root_id, parent_id, value = res.get(timeout=5)
        assert_equal(value, 51)
        assert_equal(root_id, expected_root_id)
        assert_equal(parent_id, res.parent.id)

        prev, (root_id, parent_id, value) = res.parent.get(timeout=5)
        assert_equal(value, 50)
        assert_equal(root_id, expected_root_id)
        assert_equal(parent_id, res.parent.parent.id)

        for i, p in enumerate(prev):
            root_id, parent_id, value = p
            assert_equal(root_id, expected_root_id)
            assert_equal(parent_id, res.parent.parent.id)

        root_id, parent_id, value = res.parent.parent.get(timeout=5)
        assert_equal(value, 2)
        assert_equal(parent_id, res.parent.parent.parent.id)
        assert_equal(root_id, expected_root_id)

        root_id, parent_id, value = res.parent.parent.parent.get(timeout=5)
        assert_equal(value, 1)
        assert_equal(root_id, expected_root_id)
        assert_equal(parent_id, base_parent)

    @testcase('all', 'green')
    def manyshort(self):
        self.join(group(add.s(i, i) for i in range(1000))(),
                  timeout=10, propagate=True)

    @testcase('all', 'green', iterations=1)
    def unicodetask(self):
        self.join(group(print_unicode.s() for _ in range(5))(),
                  timeout=1, propagate=True)

    @testcase('all')
    def always_timeout(self):
        self.join(
            group(sleeping.s(1).set(time_limit=0.1)
                  for _ in range(100))(),
            timeout=10, propagate=True,
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
