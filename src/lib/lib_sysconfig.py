"""SysConfig helper module.

Manage grub, systemd, coufrequtils and kernel version configuration.
"""
import hashlib
import os
import subprocess
import base64
import binascii
import yaml
from datetime import datetime, timedelta, timezone

from charmhelpers.contrib.openstack.utils import config_flags_parser
from charmhelpers.core import hookenv, host, unitdata
from charmhelpers.core.templating import render
import charmhelpers.core.sysctl as sysctl
from charmhelpers.fetch import apt_install, apt_update

from charms.reactive.helpers import any_file_changed

GRUB_DEFAULT = 'Advanced options for Ubuntu>Ubuntu, with Linux {}'
CPUFREQUTILS_TMPL = 'cpufrequtils.j2'
GRUB_CONF_TMPL = 'grub.j2'
SYSTEMD_SYSTEM_TMPL = 'etc.systemd.system.conf.j2'
SYSTEMD_RESOLVED_TMPL = 'etc.systemd.resolved.conf.j2'

CPUFREQUTILS = '/etc/default/cpufrequtils'
GRUB_CONF = '/etc/default/grub.d/90-sysconfig.cfg'
SYSTEMD_SYSTEM = '/etc/systemd/system.conf'
SYSTEMD_RESOLVED = '/etc/systemd/resolved.conf'
SYSCTL_CONF = '/etc/sysctl.d/90-charm-sysconfig.conf'
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

    def calculate_resource_sha256sum(self, resource_name):
        """Calcucate sha256sum of contents of provided resource."""
        sha = hashlib.sha256()
        sha.update(open(resource_name, 'rb').read())
        return sha.hexdigest()

    def update_resource_checksums(self, resources):
        """Update db entry for the resource_name with sha256sum of its contents."""
        for resource in resources:
            if not os.path.exists(resource):
                continue

            self.db.set("{}.sha256sum".format(self.key_for(resource)),
                        self.calculate_resource_sha256sum(resource))

    def set_resource(self, resource_name):
        """Update db entry for the resource_name with time.now."""
        timestamp = datetime.now(timezone.utc)
        self.db.set(self.key_for(resource_name), timestamp.timestamp())
        # NOTE: don't set checksum here

    def get_resource_sha256sum(self, resource_name):
        """Get db record of sha256sum of contents of provided resource."""
        key = self.key_for(resource_name)
        return self.db.get("{}.sha256sum".format(key))

    def get_resource_changed_timestamp(self, resource_name):
        """Retrieve timestamp of last resource change recorded.

        :param resource_name: resource to check
        :return: datetime of resource change, or datetime.min if resource not registered
        """
        tfloat = self.db.get(self.key_for(resource_name))
        if tfloat is not None:
            return datetime.fromtimestamp(tfloat, timezone.utc)
        return datetime.min.replace(tzinfo=timezone.utc)  # We don't have a ts -> changed at dawn of time

    def checksum_changed(self, resource_name):
        """Return True if checksum has changed since last recorded."""
        # NOTE: we treat checksum == None as True because this is required for
        #       backwards compatibility (see bug 1864217) since new resources
        #       created since the charm was patched will always have a checksum.
        if not self.get_resource_sha256sum(resource_name):
            return True

        new_sum = self.calculate_resource_sha256sum(resource_name)
        if self.get_resource_sha256sum(resource_name) != new_sum:
            return True

        return False

    def resources_changed_since_boot(self, resource_names):
        """Given a list of resource names return those that have changed since boot.

        :param resource_names: list of names
        :return: list of names
        """
        boot_ts = boot_time()
        time_changed = [name for name in resource_names
                        if boot_ts < self.get_resource_changed_timestamp(name)]

        csum_changed = [name for name in resource_names
                        if self.checksum_changed(name)]

        a = set(time_changed)
        b = set(csum_changed)
        c = set(csum_changed).difference(set(time_changed))
        d = set(b).difference(c)
        # i.e. update resources that have csum mismatch but did not change
        # since boot (we only ever update csum here).
        self.update_resource_checksums(c)

        # i.e. resources that have changed since boot time that do have csum
        # mismatch.
        changed = a.intersection(d)

        return list(changed)


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
    def sysctl_config(self):
        raw_b64 = self.charm_config['sysctl']
        if not raw_b64:
            return None

        """Return sysctl config option."""
        try:
            raw_str = base64.b64decode(raw_b64)
        except binascii.Error:
            err_msg = "sysctl config isn't base64 encoded"
            hookenv.status_set('blocked', err_msg)
            hookenv.log("%s: %s" % (err_msg, raw_b64), level=hookenv.ERROR)
            raise

        try:
            parsed = yaml.safe_load(raw_str)
        except yaml.YAMLError:
            err_msg = "Error parsing sysctl YAML"
            hookenv.status_set('blocked', err_msg)
            hookenv.log(
                "%s: %s" % (err_msg, raw_str.decode('utf-8')),
                level=hookenv.ERROR
            )
            raise

        return parsed

    @property
    def sysctl_file(self):
        return SYSCTL_CONF

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

    @staticmethod
    def _render_resource(source, target, context):
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
        self._update_systemd_resolved(context)
        hookenv.log('systemd-resolved configuration updated')

    def update_sysctl(self):
        sysctl.create(self.sysctl_config or {}, self.sysctl_file)
        hookenv.log('sysctl updated')

    def install_configured_kernel(self):
        """Install kernel as given by the kernel-version config option.

        Will install kernel and matching modules-extra package
        """
        if not self.kernel_version or self._is_kernel_already_running():
            hookenv.log(
                'Kernel is already running the required version',
                hookenv.DEBUG
            )
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
        # Ensure the ondemand service is disabled if governor is set, lp#1822774, lp#1863659, lp#740127
        # Ondemand service is not updated during test if host is container.
        if not host.is_container():
            hookenv.log('disabling the ondemand services for lp#1822774, lp#1863659,'
                        ' and lp#740127 if a governor is specified', hookenv.DEBUG)
            if self.governor:
                subprocess.call(
                    ['/bin/systemctl', 'mask', 'ondemand'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            else:
                # Renable ondemand when governor is unset.
                subprocess.call(
                    ['/bin/systemctl', 'unmask', 'ondemand'],
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
        self._update_systemd_resolved({})
        hookenv.log('deleted resolved configuration at '.format(SYSTEMD_RESOLVED), hookenv.DEBUG)

    def _update_systemd_resolved(self, context):
        self._render_resource(SYSTEMD_RESOLVED_TMPL, SYSTEMD_RESOLVED, context)
        if any_file_changed([SYSTEMD_RESOLVED]):
            host.service_restart('systemd-resolved')

    def remove_cpufreq_configuration(self):
        """Remove cpufrequtils configuration.

        Will render cpufrequtils config with empty context.
        """
        context = {}
        if not host.is_container():
            hookenv.log('Enabling the ondemand initscript for lp#1822774'
                        ' and lp#740127', 'DEBUG')
            subprocess.call(
                ['/bin/systemctl', 'unmask', 'ondemand'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

        self._render_boot_resource(CPUFREQUTILS_TMPL, CPUFREQUTILS, context)
        hookenv.log(
            'deleted cpufreq configuration at '.format(CPUFREQUTILS),
            hookenv.DEBUG
        )
        host.service_restart('cpufrequtils')
