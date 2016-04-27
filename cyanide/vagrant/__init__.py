from __future__ import absolute_import, unicode_literals

import os
import vagrant


def path():
    return os.path.abspath(os.path.dirname(__file__))


class Vagrant(vagrant.Vagrant):

    def __init__(self, root=None, quiet_stdout=False, quiet_stderr=False,
                 *args, **kwargs):
        super(Vagrant, self).__init__(
            root or path(),
            quiet_stdout=quiet_stdout,
            quiet_stderr=quiet_stderr,
            *args, **kwargs)
