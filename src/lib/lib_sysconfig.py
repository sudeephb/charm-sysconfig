"""SysConfig helper module.

Manage grub, systemd, coufrequtils and kernel version configuration.
"""
import hashlib
import os
import subprocess
from datetime import datetime, timedelta, timezone

from charmhelpers.contrib.openstack.utils import config_flags_parser
from charmhelpers.core import hookenv, host, unitdata
from charmhelpers.core.templating import render
from charmhelpers.fetch import apt_install, apt_update

GRUB_DEFAULT = 'Advanced options for Ubuntu>Ubuntu, with Linux {}'
CPUFREQUTILS_TMPL = 'cpufrequtils.j2'
GRUB_CONF_TMPL = 'grub.j2'
SYSTEMD_SYSTEM_TMPL = 'etc.systemd.system.conf.j2'
SYSTEMD_RESOLVED_TMPL = 'etc.systemd.resolved.conf.j2'

CPUFREQUTILS = '/etc/default/cpufrequtils'
GRUB_CONF = '/etc/default/grub.d/90-sysconfig.cfg'
SYSTEMD_SYSTEM = '/etc/systemd/system.conf'
SYSTEMD_RESOLVED = '/etc/systemd/resolved.conf'
KERNEL = 'kernel'


def parse_config_flags(config_flags):
    """Parse config flags into a dict.

    :param config_flags: key pairs list. Format: key1=value1,key2=value2
    :return dict: format {'key1': 'value1', 'key2': 'value2'}
    """
    key_value_pairs = config_flags.split(",")
    parsed_config_flags = {}
    for index, pair in enumerate(key_value_pairs):
        if '=' in pair:
            key, value = map(str.strip, pair.split('=', 1))
            # Note(peppepetra): if value contains a comma that is also used as
            # delimiter, we need to reconstruct the value
            i = index + 1
            while i < len(key_value_pairs):
                if '=' in key_value_pairs[i]:
                    break
                value += ',' + key_value_pairs[i]
                i += 1
            parsed_config_flags[key] = value
    return parsed_config_flags


def running_kernel():
    """Return kernel version running in the principal unit."""
    return os.uname().release


def boot_time():
    """Return timestamp of last boot."""
    with open('/proc/uptime', 'r') as f:
        uptime_seconds = float(f.readline().split()[0])
        boot_time = datetime.now(timezone.utc) - timedelta(seconds=uptime_seconds)
        return boot_time


class BootResourceState:
    """A class to track resources changed since last reboot."""

    def __init__(self, db=None):
        """Initialize empty db used to track resources updates."""
        if db is None:
            db = unitdata.kv()
        self.db = db

    def key_for(self, resource_name):
        """Return db key for a given resource."""
        return "sysconfig.boot_resource.{}".format(resource_name)

    def set_resource(self, resource_name):
        """Update db entry for the resource_name with time.now."""
        timestamp = datetime.now(timezone.utc)
        self.db.set(self.key_for(resource_name), timestamp.timestamp())

    def get_resource_changed_timestamp(self, resource_name):
        """Retrieve timestamp of last resource change recorded.

        :param resource_name: resource to check
        :return: datetime of resource change, or datetime.min if resource not registered
        """
        tfloat = self.db.get(self.key_for(resource_name))
        if tfloat is not None:
            return datetime.fromtimestamp(tfloat, timezone.utc)
        return datetime.min.replace(tzinfo=timezone.utc)  # We don't have a ts -> changed at dawn of time

    def resources_changed_since_boot(self, resource_names):
        """Given a list of resource names return those that have changed since boot.

        :param resource_names: list of names
        :return: list of names
        """
        boot_ts = boot_time()
        changed = [name for name in resource_names if boot_ts < self.get_resource_changed_timestamp(name)]
        return changed


class SysConfigHelper:
    """Update sysconfig, grub, kernel and cpufrequtils config."""

    boot_resources = BootResourceState()

    def __init__(self):
        """Retrieve charm configuration."""
        self.charm_config = hookenv.config()

    @property
    def enable_container(self):
        """Return enable-container config."""
        return self.charm_config['enable-container']

    @property
    def reservation(self):
        """Return reservation config."""
        return self.charm_config['reservation']

    @property
    def cpu_range(self):
        """Return cpu-range config."""
        return self.charm_config['cpu-range']

    @property
    def hugepages(self):
        """Return hugepages config."""
        return self.charm_config['hugepages']

    @property
    def hugepagesz(self):
        """Return hugepagesz config."""
        return self.charm_config['hugepagesz']

    @property
    def raid_autodetection(self):
        """Return raid-autodetection config option."""
        return self.charm_config['raid-autodetection']

    @property
    def enable_pti(self):
        """Return raid-autodetection config option."""
        return self.charm_config['enable-pti']

    @property
    def enable_iommu(self):
        """Return enable-iommu config option."""
        return self.charm_config['enable-iommu']

    @property
    def grub_config_flags(self):
        """Return grub-config-flags config option."""
        return parse_config_flags(self.charm_config['grub-config-flags'])

    @property
    def systemd_config_flags(self):
        """Return systemd-config-flags config option."""
        return parse_config_flags(self.charm_config['systemd-config-flags'])

    @property
    def kernel_version(self):
        """Return kernel-version config option."""
        return self.charm_config['kernel-version']

    @property
    def update_grub(self):
        """Return update-grub config option."""
        return self.charm_config['update-grub']

    @property
    def governor(self):
        """Return governor config option."""
        return self.charm_config['governor']

    @property
    def resolved_cache_mode(self):
        """Return resolved-cache-mode config option."""
        return self.charm_config['resolved-cache-mode']

    @property
    def config_flags(self):
        """Return parsed config-flags into dict.

        [DEPRECATED]: this option should no longer be used.
        Instead grub-config-flags and systemd-config-flags should be used.
        """
        if not self.charm_config.get('config-flags'):
            return {}
        flags = config_flags_parser(self.charm_config['config-flags'])
        return flags

    def _render_boot_resource(self, source, target, context):
        """Render the template and set the resource as changed."""
        self._render_resource(source, target, context)
        self.boot_resources.set_resource(target)

    def _render_resource(self, source, target, context):
        """Render the template."""
        render(source=source, templates_dir='templates', target=target, context=context)

    def _is_kernel_already_running(self):
        """Check if the kernel version required by charm config is equal to kernel running."""
        configured = self.kernel_version
        if configured == running_kernel():
            hookenv.log("Already running kernel: {}".format(configured), hookenv.DEBUG)
            return True
        return False

    def _update_grub(self):
        """Call update-grub when update-grub config param is set to True."""
        if self.update_grub and not host.is_container():
            subprocess.check_call(['/usr/sbin/update-grub'])
            hookenv.log('Running update-grub to apply grub conf updates', hookenv.DEBUG)

    def is_config_valid(self):
        """Validate config parameters."""
        valid = True

        for config_key, value, valid_values in (
                ('reservation', self.reservation, ['off', 'isolcpus', 'affinity']),
                ('raid-autodetection', self.raid_autodetection, ['', 'noautodetect', 'partitionable']),
                ('governor', self.governor, ['', 'powersave', 'performance']),
                ('resolved-cache-mode', self.resolved_cache_mode, ['', 'yes', 'no', 'no-negative']),
        ):
            if value not in valid_values:
                hookenv.log('{} not valid. Possible values: {}'.format(config_key, repr(valid_values)), hookenv.DEBUG)
                valid = False

        return valid

    def update_grub_file(self):
        """Update /etc/default/grub.d/90-sysconfig.cfg according to charm configuration.

        Will call update-grub if update-grub config is set to True.
        """
        context = {}
        if self.reservation == 'isolcpus':
            context['cpu_range'] = self.cpu_range
        if self.hugepages:
            context['hugepages'] = self.hugepages
        if self.hugepagesz:
            context['hugepagesz'] = self.hugepagesz
        if self.raid_autodetection:
            context['raid'] = self.raid_autodetection
        if not self.enable_pti:
            context['pti_off'] = True
        if self.enable_iommu:
            context['iommu'] = True

        # Note(peppepetra): First check if new grub-config-flags is used
        # if not try to fallback into legacy config-flags
        if self.grub_config_flags:
            context['grub_config_flags'] = self.grub_config_flags
        else:
            context['grub_config_flags'] = parse_config_flags(self.config_flags.get('grub', ''))

        if self.kernel_version and not self._is_kernel_already_running():
            context['grub_default'] = GRUB_DEFAULT.format(self.kernel_version)

        self._render_boot_resource(GRUB_CONF_TMPL, GRUB_CONF, context)
        hookenv.log('grub configuration updated')
        self._update_grub()

    def update_systemd_system_file(self):
        """Update /etc/systemd/system.conf according to charm configuration."""
        context = {}
        if self.reservation == 'affinity':
            context['cpu_range'] = self.cpu_range

        # Note(peppepetra): First check if new systemd-config-flags is used
        # if not try to fallback into legacy config-flags
        if self.systemd_config_flags:
            context['systemd_config_flags'] = self.systemd_config_flags
        else:
            context['systemd_config_flags'] = parse_config_flags(self.config_flags.get('systemd', ''))

        self._render_boot_resource(SYSTEMD_SYSTEM_TMPL, SYSTEMD_SYSTEM, context)
        hookenv.log('systemd configuration updated')

    def update_systemd_resolved(self):
        """Update /etc/systemd/resolved.conf according to charm configuration."""
        context = {}
        if self.resolved_cache_mode:
            context['cache'] = self.resolved_cache_mode
        old_checksum = self.get_checksum(SYSTEMD_RESOLVED)
        self._render_resource(SYSTEMD_RESOLVED_TMPL, SYSTEMD_RESOLVED, context)
        new_checksum = self.get_checksum(SYSTEMD_RESOLVED)
        hookenv.log('systemd-resolved configuration updated')
        if new_checksum != old_checksum:
            host.service_restart('systemd-resolved')

    def install_configured_kernel(self):
        """Install kernel as given by the kernel-version config option.

        Will install kernel and matching modules-extra package
        """
        if not self.kernel_version or self._is_kernel_already_running():
            hookenv.log('kernel running already to the reuired version', hookenv.DEBUG)
            return

        configured = self.kernel_version
        pkgs = [tmpl.format(configured) for tmpl in ["linux-image-{}", "linux-modules-extra-{}"]]
        apt_update()
        apt_install(pkgs)
        hookenv.log("installing: {}".format(pkgs))
        self.boot_resources.set_resource(KERNEL)

    def update_cpufreq(self):
        """Update /etc/default/cpufrequtils and restart cpufrequtils service."""
        if self.governor not in ('', 'performance', 'powersave'):
            return
        context = {'governor': self.governor}
        self._render_boot_resource(CPUFREQUTILS_TMPL, CPUFREQUTILS, context)
        # Ensure the ondemand initscript is disabled if governor is set, lp#1822774 and lp#740127
        # Ondemand init script is not updated during test if host is container.
        if host.get_distrib_codename() == 'xenial' and not host.is_container():
            hookenv.log('disabling the ondemand initscript for lp#1822774'
                        ' and lp#740127 if a governor is specified', hookenv.DEBUG)
            if self.governor:
                subprocess.call(
                    ['/usr/sbin/update-rc.d', '-f', 'ondemand', 'remove'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            else:
                # Renable ondemand when governor is unset.
                subprocess.call(
                    ['/usr/sbin/update-rc.d', '-f', 'ondemand', 'defaults'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )

        host.service_restart('cpufrequtils')

    def remove_grub_configuration(self):
        """Remove /etc/default/grub.d/90-sysconfig.cfg if exists.

        Will call update-grub if update-grub config is set to True.
        """
        grub_configuration_path = GRUB_CONF
        if not os.path.exists(grub_configuration_path):
            return
        os.remove(grub_configuration_path)
        hookenv.log(
            'deleted grub configuration at '.format(grub_configuration_path),
            hookenv.DEBUG
        )
        self._update_grub()
        self.boot_resources.set_resource(GRUB_CONF)

    def remove_systemd_configuration(self):
        """Remove systemd configuration.

        Will render systemd config with empty context.
        """
        context = {}
        self._render_boot_resource(SYSTEMD_SYSTEM_TMPL, SYSTEMD_SYSTEM, context)
        hookenv.log(
            'deleted systemd configuration at '.format(SYSTEMD_SYSTEM),
            hookenv.DEBUG
        )

    def remove_resolved_configuration(self):
        """Remove systemd's resolved configuration.

        Will render resolved config with defaults.
        """
        context = {}
        old_checksum = self.get_checksum(SYSTEMD_RESOLVED)
        self._render_resource(SYSTEMD_RESOLVED_TMPL, SYSTEMD_RESOLVED, context)
        new_checksum = self.get_checksum(SYSTEMD_RESOLVED)
        hookenv.log('deleted resolved configuration at '.format(SYSTEMD_RESOLVED), hookenv.DEBUG)
        if new_checksum != old_checksum:
            host.service_restart('systemd-resolved')

    def remove_cpufreq_configuration(self):
        """Remove cpufrequtils configuration.

        Will render cpufrequtils config with empty context.
        """
        context = {}
        if host.get_distrib_codename() == 'xenial' and not host.is_container():
            hookenv.log('Enabling the ondemand initscript for lp#1822774'
                        ' and lp#740127', 'DEBUG')
            subprocess.call(
                ['/usr/sbin/update-rc.d', '-f', 'ondemand', 'defaults'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

        self._render_boot_resource(CPUFREQUTILS_TMPL, CPUFREQUTILS, context)
        hookenv.log(
            'deleted cpufreq configuration at '.format(CPUFREQUTILS),
            hookenv.DEBUG
        )
        host.service_restart('cpufrequtils')

    def get_checksum(self, filename):
        with open(filename, 'rb') as infile:
            return hashlib.sha256(infile.read()).hexdigest()
