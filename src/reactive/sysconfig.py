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

import logging
import re

from lib_sysconfig import (
    CPUFREQUTILS,
    GRUB_CONF,
    SYSTEMD_SYSTEM,
    SysconfigHelper,
)

from charms.layer import status
from charms.reactive import (
    helpers,
    when,
    when_none,
    when_not,
    set_flag,
    clear_flag,
)
# from charms.reactive.bus import get_states

# from charmhelpers import context
from charmhelpers.core import (
    hookenv,
    host,
)


@when_none('sysconfig.installed', 'sysconfig.unsupported')
def install():
    if host.is_container():
        status.blocked('Containers are not supported')
        set_flag('hw-health.unsupported')
        return
    set_flag('sysconfig.installed')


@when('sysconfig.installed')
@when_not('sysconfig.unsupported')
@when('config.changed')
def config_changed():
    syshelper = SysconfigHelper()
    hookenv.status_set('maintenance', 'Applying changes')

    # cpufreq
    if syshelper.charm_config.changed('governor') \
            or helpers.any_file_changed([CPUFREQUTILS]):
        syshelper.update_cpufreq()

    # GRUB or systemd reconfiguration
    updated = False
    if (syshelper.charm_config.changed('reservation') or
            syshelper.charm_config.changed('cpu-range')) and \
            syshelper.reservation in ('isolcpus', 'affinity', 'off'):
        syshelper.update_grub_file(
            syshelper.reservation == 'isolcpus')
        syshelper.update_systemd_system_file(
            syshelper.reservation == 'cpuaffinity')
        updated = True

    # GRUB reconfig (if not already done)
    if (syshelper.charm_config.changed('hugepagesz') or
            syshelper.charm_config.changed('hugepages')) and \
            not updated:
        syshelper.update_grub_file(syshelper.reservation == 'isolcpus')

    if syshelper.charm_config.changed('config-flags') and not updated:
        syshelper.update_config_flags()

    # update-grub needed
    boot_changes = []
    for filename in (GRUB_CONF, SYSTEMD_SYSTEM):
        if helpers.any_file_changed([filename]):
            boot_changes.append(filename)

    if boot_changes:
        status.active('Reboot required. Changes in: ',
                      ', '.join(boot_changes))
    else:
        status.active('Ready')
