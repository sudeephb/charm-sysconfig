# Copyright 2018 Canonical Ltd.
#
# This file is part of the CPUConfig Charm for Juju.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3, as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import re
# import base64
# import binascii
# import io
# import json
# import os
# import socket
# import time
# import yaml

from charms.reactive import (
    helpers,
    # hook,
    when,
    # when_not,
    set_state,
    remove_state,
)
from charms.reactive.bus import get_states

# from charmhelpers import context
from charmhelpers.core import (
    hookenv,
    host,
)
from charmhelpers.core.templating import render

CPUFREQUTILS_TMPL = 'cpufrequtils.j2'
GRUB_CONF_TMPL = 'grub.j2'
SYSTEMD_SYSTEM_TMPL = 'etc.systemd.system.conf.j2'

CPUFREQUTILS = '/etc/default/cpufrequtils'
GRUB_CONF = '/etc/default/grub'
SYSTEMD_SYSTEM = '/etc/systemd/system.conf'


def update_grub_file(isolcpus):
    config = hookenv.config()
    context = {'cpu_range': isolcpus,
               'hugepagesz': config['hugepagesz'],
               'hugepages': config['hugepages']}
    render(source=GRUB_CONF_TMPL, templates_dir='templates',
           target=GRUB_CONF, context=context)
    hookenv.log('[*] DEBUG: grub file update: isolcpus={cpu_range}, '
                'hugepagesz={hugepagesz}, '
                'hugepages={hugepages}'.format(**context))


def update_systemd_system_file(cpuaffinity):
    context = {'cpuaffinity': cpuaffinity}
    render(source=SYSTEMD_SYSTEM_TMPL, templates_dir='templates',
           target=SYSTEMD_SYSTEM, context=context)
    hookenv.log('[*] DEBUG: systemd-system.conf update: '
                'CPUAffinity={}'.format(cpuaffinity))


@when('config.changed')
def config_changed():
    try:
        # expect: systemd (1, #threads: 1)
        with open('/proc/1/sched') as fd:
            line = fd.readline()
            m = re.search('\d+', line)
            if not m or m.group() != '1':
                return
    except Exception as e:
        # No check => noop
        hookenv.log('cannot check if running on a container: {}'.format(e))
        return

    hookenv.status_set('maintenance', 'Applying changes')
    config = hookenv.config()

    # config-changed or data in the file has changed
    if (config.changed('governor') or
       helpers.any_file_changed([CPUFREQUTILS])) and \
       config['governor'] in ('performance', 'powersave'):
        context = {'governor': config['governor']}
        render(source=CPUFREQUTILS_TMPL, templates_dir='templates',
               target=CPUFREQUTILS, context=context)
        host.service_restart('cpufrequtils')

    # reservation or cpu-range have changed?
    # clear config.previous leftovers if needed
    grubfile_updated = False
    if (config.changed('reservation') or config.changed('cpu-range')) and \
       config['reservation'] in ('isolcpus', 'affinity', 'off'):
        res = config['reservation']
        if res == 'off':
            if config.previous('reservation') == 'isolcpus':
                update_grub_file('')
                grubfile_updated = True
            elif config.previous('reservation') == 'affinity':
                update_systemd_system_file('')
        elif res == 'isolcpus':
            isolcpus = config['cpu-range']
            # (aluria): cpu-range is not empty
            if isolcpus:
                update_grub_file(isolcpus)
                grubfile_updated = True
            if config.previous('reservation') == 'affinity':
                update_systemd_system_file('')
        elif res == 'affinity':
            # (aluria): systemd-system needs a list of pcpus,
            # not a (set of) range
            str_affinity = config['cpu-range']
            affinity = ''
            for cpu_block in str_affinity.split(','):
                if cpu_block.find('-') > -1 and \
                   len(cpu_block.split('-')) == 2:
                    c = cpu_block.split('-')
                    affinity += " " + " ".join(map(str,
                                                   range(int(c[0]),
                                                         int(c[1]) + 1)))
                else:
                    affinity += " " + str(cpu_block)
            affinity = affinity.strip()
            if config.previous('reservation') == 'isolcpus':
                update_grub_file('')
                grubfile_updated = True
            update_systemd_system_file(affinity)

    if not grubfile_updated and (config.changed('hugepagesz') or
                                 config.changed('hugepages')):
        if config['reservation'] == 'isolcpus':
            isolcpus = config['cpu-range']
        else:
            isolcpus = ''
        update_grub_file(isolcpus)

    # update-grub if /etc/default/grub changed
    # (or notify it is needed)
    current_states = get_states()
    if 'sysconfig.needs-update-grub' in current_states:
        hookenv.status_set('blocked', 'update-grub needs to be run')
    elif helpers.any_file_changed([GRUB_CONF]) and \
            config['update-grub'] == 'false':
        hookenv.status_set('blocked', 'update-grub needs to be run')
        set_state('sysconfig.needs-update-grub')
    else:
        # FIXME: if "update-grub" is true, this will mislead
        remove_state('sysconfig.needs-update-grub')
        hookenv.status_set('active', 'Ready')
