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

from lib_sysconfig import CPUFREQUTILS, GRUB_CONF, SYSTEMD_SYSTEM, KERNEL, SysconfigHelper

from charms.layer import status
from charms.reactive import (
    helpers,
    hook,
    set_flag,
    when,
    when_none,
    when_not,
)
from charmhelpers.core import host


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
    status.maintenance('Applying changes')

    # cpufreq
    if syshelper.charm_config.changed('governor') or helpers.any_file_changed([CPUFREQUTILS]):
        syshelper.update_cpufreq()

    # GRUB or systemd reconfiguration
    updated = False
    if (syshelper.charm_config.changed('reservation') or
        syshelper.charm_config.changed('cpu-range')) and \
            syshelper.reservation in ('isolcpus', 'affinity', 'off'):
        syshelper.update_grub_file(syshelper.reservation == 'isolcpus')
        syshelper.update_systemd_system_file(syshelper.reservation == 'affinity')
        updated = True

    # GRUB reconfig (if not already done)
    if (syshelper.charm_config.changed('hugepagesz') or syshelper.charm_config.changed('hugepages')) and not updated:
        syshelper.update_grub_file(syshelper.reservation == 'isolcpus')

    if syshelper.charm_config.changed('config-flags') and not updated:
        syshelper.update_config_flags()

    # Update kernel version
    if syshelper.charm_config.changed('kernel-version'):
        syshelper.install_configured_kernel()

    update_status()


@hook('update-status')
def update_status():
    resources = [KERNEL, CPUFREQUTILS, SYSTEMD_SYSTEM, GRUB_CONF]
    boot_changes = SysconfigHelper.boot_resources.resources_changed_since_boot(resources)
    if boot_changes:
        status.active("Reboot required. Changes in: {}".format(", ".join(boot_changes)))
    else:
        status.active("Ready")
