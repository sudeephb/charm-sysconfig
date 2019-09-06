# Copyright 2019 Canonical Ltd.
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

from lib_sysconfig import CPUFREQUTILS, GRUB_CONF, SYSTEMD_SYSTEM, KERNEL, SysConfigHelper

from charms.reactive import (
    helpers,
    hook,
    set_flag,
    when,
    when_none,
    when_not,
    is_flag_set,
    clear_flag,
)
from charmhelpers.core import host, hookenv


helper = SysConfigHelper()


@when_none('sysconfig.installed', 'sysconfig.unsupported')
@when('juju-info.connected')
def install_sysconfig():
    syshelper = SysConfigHelper()

    # container not supported unless enable-container=true for testing purpose
    if host.is_container() and not syshelper.enable_container:
        hookenv.status_set('blocked', 'containers are not supported')
        set_flag('sysconfig.unsupported')
        return

    if not syshelper.is_config_valid():
        hookenv.status_set('blocked', 'configuration parameters not valid.')
        return

    syshelper.install_configured_kernel()
    syshelper.update_cpufreq()
    syshelper.update_grub_file()
    syshelper.update_systemd_system_file()
    set_flag('sysconfig.installed')
    update_status()


@when('sysconfig.installed')
@when_not('sysconfig.unsupported')
@when('config.changed')
def config_changed():
    syshelper = SysConfigHelper()
    hookenv.status_set('maintenance', 'applying changes')

    if not syshelper.is_config_valid():
        hookenv.status_set('blocked', 'configuration parameters not valid.')
        return

    # Kernel
    if syshelper.charm_config.changed('kernel-version'):
        syshelper.install_configured_kernel()

    # cpufreq
    if syshelper.charm_config.changed('governor') or helpers.any_file_changed([CPUFREQUTILS]):
        syshelper.update_cpufreq()

    # GRUB
    if syshelper.charm_config.changed('reservation') or \
            syshelper.charm_config.changed('hugepages') or \
            syshelper.charm_config.changed('hugepagesz') or \
            syshelper.charm_config.changed('raid-autodetection') or \
            syshelper.charm_config.changed('enable-pti') or \
            syshelper.charm_config.changed('enable-iommu') or \
            syshelper.charm_config.changed('grub-config-flags') or \
            syshelper.charm_config.changed('kernel-version') or \
            syshelper.charm_config.changed('update-grub') or \
            helpers.any_file_changed([GRUB_CONF]):

        syshelper.update_grub_file()

    # systemd
    if syshelper.charm_config.changed('reservation') or \
            syshelper.charm_config.changed('systemd-config-flags') or \
            helpers.any_file_changed([SYSTEMD_SYSTEM]):
        syshelper.update_systemd_system_file()

    update_status()


@hook('update-status')
@when_not('sysconfig.unsupported')
def update_status():
    resources = [KERNEL, SYSTEMD_SYSTEM, GRUB_CONF]
    boot_changes = SysConfigHelper.boot_resources.resources_changed_since_boot(resources)

    if boot_changes:
        hookenv.status_set('active', 'reboot required. Changes in: {}'.format(', '.join(boot_changes)))
    else:
        hookenv.status_set('active', 'ready')


@when('config.changed.enable-container')
@when_not('sysconfig.installed')
def enable_container_changed():
    if not is_flag_set('sysconfig.installed'):
        # Note: useful for testing purpose
        clear_flag('sysconfig.unsupported')
        return

    hookenv.status_set('maintenance', 'installation in progress')


@when('sysconfig.installed')
@when_not('juju-info.available')
def remove_configuration():
    hookenv.status_set('maintenance', 'removing sysconfig configurations')
    syshelper = SysConfigHelper()
    syshelper.remove_cpufreq_configuration()
    syshelper.remove_grub_configuration()
    syshelper.remove_systemd_configuration()
    clear_flag('sysconfig.installed')
    clear_flag('sysconfig.unsupported')
