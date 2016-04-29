from __future__ import absolute_import, print_function, unicode_literals

import celery

from celery import signals
from celery.bin.base import Option

from .templates import use_template, template_names

IS_CELERY_4 = celery.VERSION[0] >= 4


class App(celery.Celery):
    cyanide_suite = 'cyanide.suites.default:Default'
    template_selected = False

    def __init__(self, *args, **kwargs):
        self.template = kwargs.pop('template', None)
        super(App, self).__init__(*args, **kwargs)
        self.user_options['preload'].add(
            Option(
                '-Z', '--template', default='default',
                help='Configuration template to use: {0}'.format(
                    template_names(),
                ),
            )
        )
        signals.user_preload_options.connect(self.on_preload_parsed)
        if IS_CELERY_4:
            self.on_configure.connect(self._maybe_use_default_template)

    def on_preload_parsed(self, options=None, **kwargs):
        self.use_template(options['template'])

    def use_template(self, name='default'):
        if self.template_selected:
            raise RuntimeError('App already configured')
        use_template(self, name)
        self.template_selected = True

    def _maybe_use_default_template(self, **kwargs):
        if not self.template_selected:
            self.use_template('default')

    if not IS_CELERY_4:
        after_configure = None

        def _get_config(self):
            ret = super(App, self)._get_config()
            if self.after_configure:
                self.after_configure(ret)
            return ret

        def on_configure(self):
            self._maybe_use_default_template()

app = App('cyanide', set_as_current=False)
