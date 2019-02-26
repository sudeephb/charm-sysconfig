from charmhelpers.core import hookenv, host
from charmhelpers.core.templating import render
from charmhelpers.contrib.openstack.utils import config_flags_parser

CPUFREQUTILS_TMPL = 'cpufrequtils.j2'
GRUB_CONF_TMPL = 'grub.j2'
SYSTEMD_SYSTEM_TMPL = 'etc.systemd.system.conf.j2'

CPUFREQUTILS = '/etc/default/cpufrequtils'
# GRUB_CONF = '/etc/default/grub'
GRUB_CONF = '/etc/default/grub.d/90-sysconfig.cfg'
SYSTEMD_SYSTEM = '/etc/systemd/system.conf'


class SysconfigHelper():
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

    def update_cpufreq(self):
        if self._governor not in ('performance', 'powersave'):
            return
        context = {'governor': self._governor}
        render(source=CPUFREQUTILS_TMPL, templates_dir='templates',
               target=CPUFREQUTILS, context=context)
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

    def update_grub_file(self, isolcpus):
        if isolcpus:
            isolcpus = self.cpu_range
        extra_flags = self.extra_flags.get('grub', {})
        context = {'cpu_range': isolcpus,
                   'hugepagesz': self._hugepagesz,
                   'hugepages': self._hugepages,
                   'grub_config_flags': config_flags_parser(extra_flags)}
        render(source=GRUB_CONF_TMPL, templates_dir='templates',
               target=GRUB_CONF, context=context)
        hookenv.log('grub file update: isolcpus={cpu_range}, '
                    'hugepagesz={hugepagesz}, '
                    'hugepages={hugepages}, '
                    'config-flags={grub_config_flags}'.format(**context),
                    'DEBUG')

    def update_systemd_system_file(self, cpuaffinity):
        if cpuaffinity:
            cpuaffinity = self.cpu_range
        extra_flags = self.extra_flags.get('systemd', {})
        context = {'cpuaffinity': cpuaffinity,
                   'systemd_config_flags': config_flags_parser(extra_flags)}
        render(source=SYSTEMD_SYSTEM_TMPL, templates_dir='templates',
               target=SYSTEMD_SYSTEM, context=context)
        hookenv.log('systemd-system.conf update: '
                    'CPUAffinity={cpuaffinity}, '
                    'config-flags={systemd_config_flags}'.format(**context),
                    'DEBUG')

    def update_config_flags(self):
        for k in self.extra_flags:
            if k == 'grub':
                self.update_grub_file(self.reservation == 'isolcpus')
            elif k == 'systemd':
                self.update_systemd_system_file(self.reservation == 'affinity')
