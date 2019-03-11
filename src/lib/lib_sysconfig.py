from datetime import datetime, timedelta

from charmhelpers.core import hookenv, host, unitdata
from charmhelpers.core.templating import render
from charmhelpers.contrib.openstack.utils import config_flags_parser

CPUFREQUTILS_TMPL = 'cpufrequtils.j2'
GRUB_CONF_TMPL = 'grub.j2'
SYSTEMD_SYSTEM_TMPL = 'etc.systemd.system.conf.j2'

CPUFREQUTILS = '/etc/default/cpufrequtils'
# GRUB_CONF = '/etc/default/grub'
GRUB_CONF = '/etc/default/grub.d/90-sysconfig.cfg'
SYSTEMD_SYSTEM = '/etc/systemd/system.conf'
KERNEL = 'kernel'


def boot_time():
    with open('/proc/uptime', 'r') as f:
        uptime_seconds = float(f.readline().split()[0])
        boot_since = datetime.now() - timedelta(seconds=uptime_seconds)
        return boot_since


class BootResourceState:

    def __init__(self, db=None):
        if db is None:
            db = unitdata.kv()
        self.db = db

    def key_for(self, resource_name):
        return "sysconfig.boot_resource.{}".format(resource_name)

    def set_resource(self, resource_name):
        timestamp = datetime.now()  # Naive datetime, as we do not expect transfer across timezones
        tstr = timestamp.strftime('%Y-%m-%dT%H:%M:%S')
        self.db.set(self.key_for(resource_name), tstr)

    def get_resource_changed_timestamp(self, resource_name):
        """Retrieve timestamp of last resource change recorded

        :param resource_name: resource to check
        :return: datetime of resource change, or datetime.min if resource not registered
        """
        tstr = self.db.get(self.key_for(resource_name))
        if tstr is not None:
            return datetime.strptime(tstr, '%Y-%m-%dT%H:%M:%S')
        return datetime.min  # We don't have a ts -> changed at dawn of time

    def resources_changed_since_boot(self, resource_names):
        boot_ts = boot_time()
        changed = [name for name in resource_names if boot_ts < self.get_resource_changed_timestamp(name)]
        return changed


class SysconfigHelper():

    boot_resources = BootResourceState()

    def __init__(self):
        self.charm_config = hookenv.config()
        self.extra_flags = self.config_flags()

    def config_flags(self):
        if not self.charm_config.get('config-flags'):
            return {}
        flags = config_flags_parser(self.charm_config['config-flags'])
        return flags

    @property
    def _governor(self):
        return self.charm_config['governor']

    def _render_boot_resource(self, source, target, context):
        render(source=source, templates_dir='templates', target=target, context=context)
        self.boot_resources.set_resource(target)

    def update_cpufreq(self):
        if self._governor not in ('performance', 'powersave'):
            return
        context = {'governor': self._governor}
        self._render_boot_resource(CPUFREQUTILS_TMPL, CPUFREQUTILS, context)
        host.service_restart('cpufrequtils')

    @property
    def reservation(self):
        return self.charm_config['reservation']

    @property
    def cpu_range(self):
        return self.charm_config['cpu-range']

    @property
    def _hugepagesz(self):
        return self.charm_config['hugepagesz']

    @property
    def _hugepages(self):
        return self.charm_config['hugepages']

    def update_grub_file(self, isolcpus=False):
        """Renders a new grub configuration file which will be parsed last, at '/etc/default/grub.d'.

        The file will include hugepages reservation. Isolcpus is optional, since CPUAffinity is also supported.

        config-flags charm parameter can share values under a 'grub' key. Those values will be consequently parsed
        and included as extra key=value rows.
        """
        if isolcpus:
            isolcpus = self.cpu_range
        extra_flags = self.extra_flags.get('grub', '')
        context = {'cpu_range': isolcpus, 'hugepagesz': self._hugepagesz, 'hugepages': self._hugepages,
                   'grub_config_flags': config_flags_parser(extra_flags)}
        self._render_boot_resource(GRUB_CONF_TMPL, GRUB_CONF, context)
        hookenv.log('grub file update: isolcpus={cpu_range}, hugepagesz={hugepagesz}, hugepages={hugepages}, '
                    'config-flags={grub_config_flags}'.format(**context), 'DEBUG')

    def update_systemd_system_file(self, cpuaffinity):
        """Renders a new systemd configuration file which will overwrite '/etc/systemd/system.conf'.

        The file will optionally include CPUAffinity ranges, since Isolcpus is also supported supported.

        config-flags charm parameter can share values under a 'grub' key. Those values will be consequently
        parsed and included as extra key=value rows.
        """
        if cpuaffinity:
            cpuaffinity = self.cpu_range
        extra_flags = self.extra_flags.get('systemd', '')
        context = {'cpuaffinity': cpuaffinity, 'systemd_config_flags': config_flags_parser(extra_flags)}
        self._render_boot_resource(SYSTEMD_SYSTEM_TMPL, SYSTEMD_SYSTEM, context)
        hookenv.log('systemd-system.conf update: CPUAffinity={cpuaffinity}, '
                    'config-flags={systemd_config_flags}'.format(**context), 'DEBUG')

    def update_config_flags(self):
        if 'grub' in self.extra_flags:
            self.update_grub_file(self.reservation == 'isolcpus')
        if 'systemd' in self.extra_flags:
            self.update_systemd_system_file(self.reservation == 'affinity')
