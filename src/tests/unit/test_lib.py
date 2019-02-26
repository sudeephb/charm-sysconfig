#!/usr/bin/python3

from collections import OrderedDict

# from pytest import mark
import unittest.mock as mock
import lib_sysconfig


class TestLib():
    def test_pytest(self):
        assert True

    def test_sysconfig(self, sysconfig):
        ''' See if the helper fixture works to load charm configs '''
        assert isinstance(sysconfig.charm_config, dict)
        assert isinstance(sysconfig.extra_flags, dict)

    @mock.patch('lib_sysconfig.hookenv.config')
    def test_config_flags(self, config):
        config.return_value = {
            'config-flags': (
                "{'grub': 'GRUB_DEFAULT=\"Advanced options for "
                "Ubuntu>Ubuntu, with Linux 4.15.0-38-generic\"'}"
                ),
        }
        sysh = lib_sysconfig.SysconfigHelper()
        assert sysh.config_flags() == OrderedDict([(
            'grub',
            ('GRUB_DEFAULT="Advanced options for Ubuntu>Ubuntu, with Linux'
             ' 4.15.0-38-generic"')
            )])

    @mock.patch('lib_sysconfig.hookenv.config')
    @mock.patch('lib_sysconfig.host.service_restart')
    @mock.patch('lib_sysconfig.render')
    def test_update_cpufreq(self, render, restart, config):
        expected = {'governor': 'performance'}
        config.return_value = expected
        # expected = (
        #     b'# Juju generated file - do not edit\n\n'
        #     b'GOVERNOR=performance'
        # )
        sysh = lib_sysconfig.SysconfigHelper()
        sysh.update_cpufreq()
        render.assert_called_with(
            source=lib_sysconfig.CPUFREQUTILS_TMPL,
            target=lib_sysconfig.CPUFREQUTILS,
            templates_dir='templates',
            context=expected)

    @mock.patch('lib_sysconfig.hookenv.config')
    @mock.patch('lib_sysconfig.hookenv.log')
    @mock.patch('lib_sysconfig.render')
    def test_update_grub_file_true(self, render, log, config):
        config.return_value = {
            'reservation': 'isolcpus',
            'cpu-range': '0-10',
            'hugepages': '400',
            'hugepagesz': '1G',
            'config-flags': (
                "{'grub': 'GRUB_DEFAULT=\"Advanced options for "
                "Ubuntu>Ubuntu, with Linux 4.15.0-38-generic\"'}"
                ),
        }
        expected = config.return_value.copy()
        expected['cpu_range'] = expected['cpu-range']
        expected['grub_config_flags'] = OrderedDict([
            ('GRUB_DEFAULT',
             ('"Advanced options for Ubuntu>Ubuntu, with Linux'
              ' 4.15.0-38-generic"'))
            ])
        del expected['config-flags']
        del expected['cpu-range']
        del expected['reservation']
        sysh = lib_sysconfig.SysconfigHelper()
        sysh.update_grub_file(True)
        render.assert_called_with(
            source=lib_sysconfig.GRUB_CONF_TMPL,
            target=lib_sysconfig.GRUB_CONF,
            templates_dir='templates',
            context=expected)

    @mock.patch('lib_sysconfig.hookenv.config')
    @mock.patch('lib_sysconfig.hookenv.log')
    @mock.patch('lib_sysconfig.render')
    def test_update_grub_file_false(self, render, log, config):
        config.return_value = {
            'hugepages': '400',
            'hugepagesz': '1G',
            'config-flags': (
                "{'grub': 'GRUB_DEFAULT=\"Advanced options for "
                "Ubuntu>Ubuntu, with Linux 4.15.0-38-generic\"'}"
                ),
        }
        expected = config.return_value.copy()
        expected['cpu_range'] = False
        expected['grub_config_flags'] = OrderedDict([
            ('GRUB_DEFAULT',
             ('"Advanced options for Ubuntu>Ubuntu, with Linux'
              ' 4.15.0-38-generic"'))
            ])
        del expected['config-flags']
        sysh = lib_sysconfig.SysconfigHelper()
        sysh.update_grub_file(False)
        render.assert_called_with(
            source=lib_sysconfig.GRUB_CONF_TMPL,
            target=lib_sysconfig.GRUB_CONF,
            templates_dir='templates',
            context=expected)

    @mock.patch('lib_sysconfig.hookenv.config')
    @mock.patch('lib_sysconfig.hookenv.log')
    @mock.patch('lib_sysconfig.render')
    def test_update_systemd_system_file_true(self, render, log, config):
        config.return_value = {
            'reservation': 'affinity',
            'cpu-range': '0-10',
            'hugepages': '400',
            'hugepagesz': '1G',
            'config-flags': "{'systemd': 'LogLevel=info'}",
        }
        expected = config.return_value.copy()
        expected['cpuaffinity'] = expected['cpu-range']
        expected['systemd_config_flags'] = OrderedDict([('LogLevel', 'info')])
        for key in ('config-flags cpu-range hugepages hugepagesz'
                    ' reservation').split():
            del expected[key]
        sysh = lib_sysconfig.SysconfigHelper()
        sysh.update_systemd_system_file(True)
        render.assert_called_with(
            source=lib_sysconfig.SYSTEMD_SYSTEM_TMPL,
            target=lib_sysconfig.SYSTEMD_SYSTEM,
            templates_dir='templates',
            context=expected)

    @mock.patch('lib_sysconfig.hookenv.config')
    @mock.patch('lib_sysconfig.hookenv.log')
    @mock.patch('lib_sysconfig.render')
    def test_update_systemd_system_file_false(self, render, log, config):
        config.return_value = {
            'reservation': 'affinity',
            'cpu-range': '0-10',
            'hugepages': '400',
            'hugepagesz': '1G',
            'config-flags': "{'systemd': 'LogLevel=info'}",
        }
        expected = config.return_value.copy()
        expected['cpuaffinity'] = False
        expected['systemd_config_flags'] = OrderedDict([('LogLevel', 'info')])
        for key in ('config-flags cpu-range hugepages hugepagesz'
                    ' reservation').split():
            del expected[key]
        sysh = lib_sysconfig.SysconfigHelper()
        sysh.update_systemd_system_file(False)
        render.assert_called_with(
            source=lib_sysconfig.SYSTEMD_SYSTEM_TMPL,
            target=lib_sysconfig.SYSTEMD_SYSTEM,
            templates_dir='templates',
            context=expected)
    # Include tests for functions in lib_sysconfig
