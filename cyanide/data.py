# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import datetime
import decimal
import uuid

from .compat import bytes_if_py2

try:
    import simplejson as json
    from simplejson.decoder import JSONDecodeError as _DecodeError
    _json_extra_kwargs = {'use_decimal': False}
except ImportError:                 # pragma: no cover
    import json                     # noqa
    _json_extra_kwargs = {}           # noqa

    class _DecodeError(Exception):  # noqa
        pass


_encoder_cls = type(json._default_encoder)
type_registry = {}


class JSONEncoder(_encoder_cls):
    """Kombu custom json encoder."""

    def default(self, obj,
                dates=(datetime.datetime, datetime.date),
                times=(datetime.time,),
                textual=(decimal.Decimal, uuid.UUID),
                isinstance=isinstance,
                datetime=datetime.datetime):
        try:
            return super(JSONEncoder, self).default(obj)
        except TypeError:
            reducer = getattr(obj, '__to_json__', None)
            if reducer:
                return reducer()
            if isinstance(obj, dates):
                if not isinstance(obj, datetime):
                    obj = datetime(obj.year, obj.month, obj.day, 0, 0, 0, 0)
                r = obj.isoformat()
                if r.endswith("+00:00"):
                    r = r[:-6] + "Z"
                return r
            elif isinstance(obj, times):
                return obj.isoformat()
            elif isinstance(obj, textual):
                return text_t(obj)
            raise


def decode_hook(d):
    try:
        d = d['py/obj']
    except KeyError:
        return d
    type_registry[d['type']](**d['attrs'])


def install_json():
    json._default_encoder = JSONEncoder()
    json._default_decoder.object_hook = decode_hook
    try:
        from kombu.utils import json as kombujson
    except ImportError:
        pass
    else:
        kombujson._default_encoder = JSONEncoder
install_json()  # ugh, ugly but it's a test suite after all


# this imports kombu.utils.json, so can only import after install_json()
from celery.utils.debug import humanbytes  # noqa
from celery.utils.imports import qualname  # noqa


def json_reduce(obj, attrs):
    return {'py/obj': {'type': qualname(obj), 'attrs': attrs}}


def jsonable(cls):
    type_registry[qualname(cls)] = cls.__from_json__
    return cls


@jsonable
class Data(object):

    def __init__(self, label, data):
        self.label = label
        self.data = data

    def __str__(self):
        return bytes_if_py2('<Data: {0} ({1})>'.format(
            self.label, humanbytes(len(self.data)),
        ))

    def __repr__(self):
        return str(self)

    def __to_json__(self):
        return json_reduce(self, {'label': self.label, 'data': self.data})

    @classmethod
    def __from_json__(cls, label=None, data=None, **kwargs):
        return cls(label, data)

    def __reduce__(self):
        return Data, (self.label, self.data)

BIG = Data('BIG', 'x' * 2 ** 20 * 8)
SMALL = Data('SMALL', 'e' * 1024)
