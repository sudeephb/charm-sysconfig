#!/usr/bin/python3

# from pytest import mark
# import unittest.mock as mock
import lib_sysconfig


class TestLib():
    def test_pytest(self):
        assert True

    def test_sysconfig(self, sysconfig):
        ''' See if the helper fixture works to load charm configs '''
        assert isinstance(sysconfig.charm_config, dict)
        assert isinstance(sysconfig.extra_flags, dict)

    def test_config_flags(self):
        sysh = lib_sysconfig.SysconfigHelper()
        opts = {'reservation': 'isolcpus',
                'cpu-range': '0-10',
                'hugepages': '400',
                'hugepagesz': '1G',
                'config-flags': (
                    "{'grub': 'GRUB_DEFAULT=\"Advanced options for "
                    "Ubuntu>Ubuntu, with Linux 4.15.0-38-generic\"'}"
                    ),
                'governor': 'performance'
                }
        sysh.charm_config.update(opts)

        assert (sysh.config_flags == {
            'grub': {
                'GRUB_DEFAULT': (
                    '"Advanced options for Ubuntu>Ubuntu, with Linux'
                    ' 4.15.0-38-generic\"'
                    )
                }
            }
        )

    # Include tests for functions in lib_sysconfig
