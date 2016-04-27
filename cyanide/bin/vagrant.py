from __future__ import absolute_import, print_function, unicode_literals

import json
import os

from collections import OrderedDict

from celery.bin.base import Command, Option

from cyanide.vagrant import Vagrant, path


def csv_list_option(option, opt, value, parser):
    setattr(parser.values, option.dest, value.split(','))


class vagrant(Command):
    Vagrant = Vagrant

    def __init__(self, *args, **kwargs):
        super(vagrant, self).__init__(*args, **kwargs)
        self.commands = OrderedDict([
            ('up', self.up),
            ('status', self.status),
            ('sshargs', self.sshargs),
            ('destroy', self.destroy),
            ('suspend', self.suspend),
            ('resume', self.resume),
            ('halt', self.halt),
            ('provision', self.provision),
            ('reload', self.reload),
            ('conf', self.conf),
            ('user', self.user),
            ('hostname', self.hostname),
            ('user_hostname', self.user_hostname),
            ('user_hostname_port', self.user_hostname_port),
            ('port', self.port),
            ('keyfile', self.keyfile),
            ('box_list', self.box_list),
            ('path', self.path),
            ('statedir', self.statedir),
            ('snapshot_push', self.snapshot_push),
            ('snapshot_pop', self.snapshot_pop),
            ('snapshot_save', self.snapshot_save),
            ('snapshot_restore', self.snapshot_restore),
            ('snapshot_delete', self.snapshot_delete),
            ('snapshot_list', self.snapshot_list),
            ('version', self.version),
        ])
        self.vagrant = None

    def run(self, *args, **options):
        if not args:
            raise self.Error('missing subcommand. Try --help?')
        try:
            self.vagrant = self.create_session(**options)
            return self.run_command(*args, **options)
        except KeyboardInterrupt:
            print('interrupted by user: exiting...', file=self.stdout)

    def create_session(self, root, quiet_stdout, quiet_stderr, **kwargs):
        # make sure ``rm -rf $(celery vagrant statedir)`` does not
        # do horrible things.
        if root == '/':
            raise RuntimeError('Vagrant dir cannot be root (/) !!!')
        if '*' in root:
            raise RuntimeError('Vagrant dir cannot contain the * character')
        return self.Vagrant(
            root=root,
            quiet_stdout=quiet_stdout,
            quiet_stderr=quiet_stderr,
        )

    def usage(self, command):
        return '%prog {command} [{commands}] [options] {0.args}'.format(
            self, command=command, commands='|'.join(self.commands))

    def up(self, name, provision_with, **kwargs):
        self.vagrant.up(vm_name=name, provision_with=provision_with)

    def status(self, name, **kwargs):
        print(self.vagrant.status(vm_name=name), file=self.stdout)

    def sshargs(self, name, **kwargs):
        config = self.vagrant.conf(vm_name=name)
        print('{0}@{1} -p {2} -i {3}'.format(
            config['User'],
            config['HostName'],
            config['Port'],
            config['IdentityFile'],
        ), file=self.stdout)

    def destroy(self, name, **kwargs):
        self.vagrant.destroy(vm_name=name)

    def provision(self, name, provision_with, **kwargs):
        self.vagrant.provision(vm_name=name, provision_with=provision_with)

    def reload(self, name, provision_with, **kwargs):
        self.vagrant.reload(vm_name=name, provision_with=provision_with)

    def suspend(self, name, **kwargs):
        self.vagrant.suspend(vm_name=name)

    def resume(self, name, **kwargs):
        self.vagrant.resume(vm_name=name)

    def halt(self, name, force, **kwargs):
        self.vagrant.halt(vm_name=name, force=force)

    def conf(self, name, arguments, **kwargs):
        self.pretty_json(self.vagrant.conf(
            vm_name=name,
            ssh_config=arguments and arguments[0] or None,
        ))

    def path(self, **kwargs):
        print(self.vagrant.root, file=self.stdout)

    def statedir(self, **kwargs):
        print(os.path.join(self.vagrant.root, '.vagrant'), file=self.stdout)

    def user(self, name, **kwargs):
        print(self.vagrant.user(vm_name=name), file=self.stdout)

    def hostname(self, name, **kwargs):
        print(self.vagrant.hostname(vm_name=name), file=self.stdout)

    def user_hostname(self, name, **kwargs):
        print(self.vagrant.user_hostname(vm_name=name), file=self.stdout)

    def port(self, name, **kwargs):
        print(self.vagrant.port(vm_name=name), file=self.stdout)

    def user_hostname_port(self, name, **kwargs):
        print(self.vagrant.user_hostname_port(vm_name=name), file=self.stdout)

    def keyfile(self, name, **kwargs):
        print(self.vagrant.keyfile(vm_name=name), file=self.stdout)

    def version(self, **kwargs):
        print(self.vagrant.version(), file=self.stdout)

    def box_list(self, **kwargs):
        print(self.vagrant.box_list(), file=self.stdout)

    def snapshot_push(self, **kwargs):
        self.vagrant.snapshot_push()

    def snapshot_pop(self, **kwargs):
        self.vagrant.snapshot_pop()

    def snapshot_save(self, arguments, **kwargs):
        self.vagrant.snapshot_save(name=arguments[0])

    def snapshot_restore(self, arguments, **kwargs):
        self.vagrant.snapshot_restore(name=arguments[0])

    def snapshot_delete(self, arguments, **kwargs):
        self.vagrant.snapshot_delete(name=arguments[0])

    def snapshot_list(self, **kwargs):
        print(self.vagrant.snapshot_list(), file=self.stdout)

    def run_command(self, command, *args, **options):
        try:
            handler = self.commands[command]
        except KeyError:
            raise self.Error(
                'Unknown command: {0}.  Try --help?'.format(command))
        else:
            return handler(arguments=args, **options)

    def pretty_json(self, obj):
        json.dump(
            obj, self.stdout,
            sort_keys=True, indent=4, separators=(',', ': '),
        )
        print(file=self.stdout)

    def get_options(self):
        return (
            Option('--root', default=path(),
                   help='Directory holding Vagrantfile.'),
            Option('--name', default=None,
                   help='Optional VM name.'),
            Option('--provision-with', default=None,
                   type='string', action='callback',
                   callback=csv_list_option,
                   help='Optional comma-separated list of provisioners.'),
            Option('--quiet-stdout', action='store_true',
                   help='Disable output to stdout.'),
            Option('--quiet-stderr', action='store_true',
                   help='Disable output to stderr.'),
            Option('--force', action='store_true',
                   help='Force action (applies to e.g. halt).'),
        )


def main(argv=None):
    return vagrant(app='cyanide.app:app').execute_from_commandline(argv=argv)


if __name__ == '__main__':
    main()
