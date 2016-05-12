# -*- coding: utf-8 -*-
"""Celery stress testing and integration test support."""
# :copyright: (c) 2013-2016, Ask Solem.
#             All rights reserved.
# :license:   BSD (3 Clause), see LICENSE for more details.

from __future__ import absolute_import, unicode_literals

from collections import namedtuple

# data must be imported first to install json serializer
from . import data                  # noqa
from .app import app as celery_app  # noqa

version_info_t = namedtuple(
    'version_info_t', ('major', 'minor', 'micro', 'releaselevel', 'serial'),
)

VERSION = version_info = version_info_t(1, 1, 0, '', '')

__version__ = '{0.major}.{0.minor}.{0.micro}{0.releaselevel}'.format(VERSION)
__author__ = 'Ask Solem'
__contact__ = 'ask@celeryproject.org'
__homepage__ = 'https://github.com/celery/cyanide'
__docformat__ = 'restructuredtext'

# -eof meta-

__all__ = []
