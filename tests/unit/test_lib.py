#!/usr/bin/python3

import lib_sysconfig
import mock
from datetime import datetime, timezone


class TestBootResourceState:

    def boot_resource(self):
        db = mock.MagicMock()
        db.get.return_value = datetime(2019, 1, 1, tzinfo=timezone.utc).timestamp()
        return lib_sysconfig.BootResourceState(db=db)

    @mock.patch("lib_sysconfig.datetime")
    def test_set_resource(self, mock_datetime):
        test_time = datetime(2019, 1, 1, tzinfo=timezone.utc)
        mock_datetime.now.return_value = test_time
        boot_resource = self.boot_resource()
        boot_resource.set_resource("foofile")
        assert boot_resource.db.set.call_count == 1
        set_args = boot_resource.db.set.call_args[0]
        assert set_args[0] == "sysconfig.boot_resource.foofile"
        dt = datetime.fromtimestamp(set_args[1], timezone.utc)
        assert dt == test_time

    def test_get_resource(self):
        test_time = datetime(2019, 1, 1, tzinfo=timezone.utc)
        boot_resource = self.boot_resource()
        timestamp = boot_resource.get_resource_changed_timestamp("foofile")
        assert timestamp == test_time

    def test_get_unknown_resource(self):
        boot_resource = self.boot_resource()
        boot_resource.db = dict()  # plant empty dataset
        timestamp = boot_resource.get_resource_changed_timestamp("unregfile")
        assert timestamp == datetime.min.replace(tzinfo=timezone.utc)

    @mock.patch("lib_sysconfig.boot_time")
    def test_resources_changed_since_dawn_of_time(self, mock_boot_time):
        mock_boot_time.return_value = datetime.min.replace(tzinfo=timezone.utc)
        boot_resource = self.boot_resource()
        changed = boot_resource.resources_changed_since_boot(["foofile"])
        assert len(changed) == 1
        assert changed[0] == "foofile"

    @mock.patch("lib_sysconfig.boot_time")
    def test_resources_changed_future(self, mock_boot_time):
        mock_boot_time.return_value = datetime.max.replace(tzinfo=timezone.utc)
        boot_resource = self.boot_resource()
        changed = boot_resource.resources_changed_since_boot(["foofile"])
        assert not changed


class TestLib():
    def test_pytest(self):
        assert True

    def test_sysconfig(self, sysconfig):
        ''' See if the helper fixture works to load charm configs '''
        assert isinstance(sysconfig.charm_config, dict)

    @mock.patch("lib_sysconfig.subprocess.check_call")
    @mock.patch("lib_sysconfig.host.get_distrib_codename")
    @mock.patch("lib_sysconfig.hookenv.config")
    @mock.patch("lib_sysconfig.host.service_restart")
    @mock.patch("lib_sysconfig.render")
    def test_update_cpufreq(self, render, restart, config, codename, check_call):
        codename.return_value = "xenial"
        expected = {"governor": "performance"}
        config.return_value = expected
        sysh = lib_sysconfig.SysConfigHelper()
        sysh.update_cpufreq()
        render.assert_called_with(
            source=lib_sysconfig.CPUFREQUTILS_TMPL,
            target=lib_sysconfig.CPUFREQUTILS,
            templates_dir="templates",
            context=expected,
        )
        check_call.assert_called_with(['/usr/sbin/update-rc.d', '-f', 'ondemand', 'remove', '>', '/dev/null', '2>&1'])

    @mock.patch("lib_sysconfig.subprocess.check_call")
    @mock.patch("lib_sysconfig.host.get_distrib_codename")
    @mock.patch("lib_sysconfig.hookenv.config")
    @mock.patch("lib_sysconfig.host.service_restart")
    @mock.patch("lib_sysconfig.render")
    def test_update_cpufreq_governor_default(self, render, restart, config, codename, check_call):
        codename.return_value = "xenial"
        expected = {"governor": ""}
        config.return_value = expected
        sysh = lib_sysconfig.SysConfigHelper()
        sysh.update_cpufreq()
        render.assert_called_with(
            source=lib_sysconfig.CPUFREQUTILS_TMPL,
            target=lib_sysconfig.CPUFREQUTILS,
            templates_dir="templates",
            context=expected,
        )
        restart.assert_called()
        check_call.assert_called_with(['/usr/sbin/update-rc.d', '-f', 'ondemand', 'defaults', '>', '/dev/null', '2>&1'])

    @mock.patch("lib_sysconfig.subprocess.check_call")
    @mock.patch("lib_sysconfig.host.get_distrib_codename")
    @mock.patch("lib_sysconfig.hookenv.config")
    @mock.patch("lib_sysconfig.host.service_restart")
    @mock.patch("lib_sysconfig.render")
    def test_update_cpufreq_governor_not_available(self, render, restart, config, codename, check_call):
        codename.return_value = "xenial"
        expected = {"governor": "wrong"}
        config.return_value = expected
        sysh = lib_sysconfig.SysConfigHelper()
        sysh.update_cpufreq()
        render.assert_not_called()
        restart.assert_not_called()
        check_call.assert_not_called()

    @mock.patch("lib_sysconfig.subprocess.check_call")
    @mock.patch("lib_sysconfig.hookenv.config")
    @mock.patch("lib_sysconfig.hookenv.log")
    @mock.patch("lib_sysconfig.render")
    def test_update_grub_file(self, render, log, config, check_call):
        config.return_value = {
            "reservation": "isolcpus",
            "cpu-range": "0-10",
            "hugepages": "400",
            "hugepagesz": "1G",
            "raid-autodetection": "noautodetect",
            "enable-pti": "false",
            "enable-iommu": "false",
            "grub-config-flags": "GRUB_TIMEOUT=0",
            "kernel-version": "4.15.0-38-generic",
            "update-grub": True
        }

        expected = {
            "cpu_range": "0-10",
            "hugepages": "400",
            "hugepagesz": "1G",
            "raid": "noautodetect",
            "iommu": True,
            "grub_config_flags": {"GRUB_TIMEOUT": "0"},
            "grub_default": "Advanced options for Ubuntu>Ubuntu, with Linux 4.15.0-38-generic"
        }

        sysh = lib_sysconfig.SysConfigHelper()
        sysh.update_grub_file()
        render.assert_called_with(
            source=lib_sysconfig.GRUB_CONF_TMPL,
            target=lib_sysconfig.GRUB_CONF,
            templates_dir="templates",
            context=expected,
        )
        check_call.assert_called()

    @mock.patch("lib_sysconfig.subprocess.check_call")
    @mock.patch("lib_sysconfig.hookenv.config")
    @mock.patch("lib_sysconfig.hookenv.log")
    @mock.patch("lib_sysconfig.render")
    def test_update_grub_file_no_update_grub(self, render, log, config, check_call):
        config.return_value = {
            "reservation": "isolcpus",
            "cpu-range": "0-10",
            "hugepages": "400",
            "hugepagesz": "1G",
            "raid-autodetection": "noautodetect",
            "enable-pti": False,
            "enable-iommu": "false",
            "grub-config-flags": "GRUB_TIMEOUT=0",
            "kernel-version": "4.15.0-38-generic",
            "update-grub": False
        }

        expected = {
            "cpu_range": "0-10",
            "hugepages": "400",
            "hugepagesz": "1G",
            "raid": "noautodetect",
            "iommu": True,
            "grub_config_flags": {"GRUB_TIMEOUT": "0"},
            "grub_default": "Advanced options for Ubuntu>Ubuntu, with Linux 4.15.0-38-generic",
            'pti_off': True
        }

        sysh = lib_sysconfig.SysConfigHelper()
        sysh.update_grub_file()
        render.assert_called_with(
            source=lib_sysconfig.GRUB_CONF_TMPL,
            target=lib_sysconfig.GRUB_CONF,
            templates_dir="templates",
            context=expected,
        )
        check_call.assert_not_called()

    @mock.patch("lib_sysconfig.hookenv.config")
    @mock.patch("lib_sysconfig.hookenv.log")
    @mock.patch("lib_sysconfig.render")
    def test_update_systemd_system_file(self, render, log, config):
        config.return_value = {
            "reservation": "affinity",
            "cpu-range": "0-10",
            "systemd-config-flags": "DefaultLimitRTTIME=1,DefaultTasksMax=10"
        }

        expected = {
            "cpu_range": "0-10",
            "systemd_config_flags": {
                "DefaultLimitRTTIME": "1",
                "DefaultTasksMax": "10"
            }
        }

        sysh = lib_sysconfig.SysConfigHelper()
        sysh.update_systemd_system_file()
        render.assert_called_with(
            source=lib_sysconfig.SYSTEMD_SYSTEM_TMPL,
            target=lib_sysconfig.SYSTEMD_SYSTEM,
            templates_dir="templates",
            context=expected,
        )

    @mock.patch("lib_sysconfig.apt_install")
    @mock.patch("lib_sysconfig.apt_update")
    @mock.patch("lib_sysconfig.hookenv.config")
    @mock.patch("lib_sysconfig.running_kernel")
    @mock.patch("lib_sysconfig.hookenv.log")
    def test_install_configured_kernel_true(self, log, running_kernel, config, apt_update, apt_install):
        config.return_value = {
            "kernel-version": "4.15.0-38-generic"
        }

        running_kernel.return_value = "4.4.0-38-generic"
        sysh = lib_sysconfig.SysConfigHelper()
        sysh.install_configured_kernel()

        apt_install.assert_called_with(
            ["linux-image-{}".format("4.15.0-38-generic"), "linux-modules-extra-{}".format("4.15.0-38-generic")]
        )

    @mock.patch("lib_sysconfig.apt_install")
    @mock.patch("lib_sysconfig.apt_update")
    @mock.patch("lib_sysconfig.hookenv.config")
    @mock.patch("lib_sysconfig.running_kernel")
    @mock.patch("lib_sysconfig.hookenv.log")
    def test_install_configured_kernel_false(self, log, running_kernel, config, apt_update, apt_install):
        kernel_version = "4.15.0-38-generic"
        config.return_value = {
            "kernel-version": kernel_version
        }

        running_kernel.return_value = "4.15.0-38-generic"
        sysh = lib_sysconfig.SysConfigHelper()
        sysh.install_configured_kernel()

        apt_install.assert_not_called()

    @mock.patch("lib_sysconfig.apt_install")
    @mock.patch("lib_sysconfig.apt_update")
    @mock.patch("lib_sysconfig.hookenv.config")
    @mock.patch("lib_sysconfig.running_kernel")
    @mock.patch("lib_sysconfig.hookenv.log")
    def test_install_configured_kernel_no_specified(self, log, running_kernel, config, apt_update, apt_install):
        config.return_value = {
            "kernel-version": ""
        }

        running_kernel.return_value = "4.15.0-38-generic"
        sysh = lib_sysconfig.SysConfigHelper()
        sysh.install_configured_kernel()

        apt_install.assert_not_called()

    @mock.patch("lib_sysconfig.hookenv.config")
    @mock.patch("lib_sysconfig.os.remove")
    @mock.patch("lib_sysconfig.hookenv.log")
    @mock.patch("lib_sysconfig.os.path.exists")
    def test_remove_grub_configuration(self, exists, log, os_remove, config):
        config.return_value = {
            "update-grub": False
        }
        exists.return_value = True

        sysh = lib_sysconfig.SysConfigHelper()
        sysh.remove_grub_configuration()

        os_remove.assert_called_with(lib_sysconfig.GRUB_CONF)

    @mock.patch("lib_sysconfig.hookenv.config")
    @mock.patch("lib_sysconfig.os.remove")
    @mock.patch("lib_sysconfig.hookenv.log")
    @mock.patch("lib_sysconfig.os.path.exists")
    def test_remove_grub_configuration_true(self, exists, log, os_remove, config):
        config.return_value = {
            "update-grub": False
        }
        exists.return_value = True

        sysh = lib_sysconfig.SysConfigHelper()
        sysh.remove_grub_configuration()

        os_remove.assert_called_with(lib_sysconfig.GRUB_CONF)

    @mock.patch("lib_sysconfig.hookenv.config")
    @mock.patch("lib_sysconfig.os.remove")
    @mock.patch("lib_sysconfig.hookenv.log")
    @mock.patch("lib_sysconfig.os.path.exists")
    def test_remove_grub_configuration_false(self, exists, log, os_remove, config):
        config.return_value = {
            "update-grub": False
        }
        exists.return_value = False

        sysh = lib_sysconfig.SysConfigHelper()
        sysh.remove_grub_configuration()

        os_remove.assert_not_called()

    @mock.patch("lib_sysconfig.hookenv.config")
    @mock.patch("lib_sysconfig.hookenv.log")
    @mock.patch("lib_sysconfig.render")
    def test_remove_systemd_configuration(self, render, log, config):
        sysh = lib_sysconfig.SysConfigHelper()
        sysh.remove_systemd_configuration()

        render.assert_called_with(
            source=lib_sysconfig.SYSTEMD_SYSTEM_TMPL,
            target=lib_sysconfig.SYSTEMD_SYSTEM,
            templates_dir="templates",
            context={}
        )

    @mock.patch("lib_sysconfig.hookenv.config")
    @mock.patch("lib_sysconfig.render")
    @mock.patch("lib_sysconfig.host.service_restart")
    @mock.patch("lib_sysconfig.subprocess.check_call")
    @mock.patch("lib_sysconfig.host.get_distrib_codename")
    @mock.patch("lib_sysconfig.hookenv.log")
    def test_remove_cpufreq_configuration_xenial(self, log, distrib_codename, check_call, restart, render, config):
        distrib_codename.return_value = "xenial"
        sysh = lib_sysconfig.SysConfigHelper()
        sysh.remove_cpufreq_configuration()

        check_call.assert_called()
        render.assert_called_with(
            source=lib_sysconfig.CPUFREQUTILS_TMPL,
            target=lib_sysconfig.CPUFREQUTILS,
            templates_dir="templates",
            context={}
        )
        restart.assert_called()

    @mock.patch("lib_sysconfig.hookenv.config")
    def test_wrong_reservation(self, config):
        config.return_value = {
            "reservation": "wrong",
            "raid-autodetection": "",
            "governor": ""
        }
        sysh = lib_sysconfig.SysConfigHelper()
        assert not sysh.is_config_valid()

    @mock.patch("lib_sysconfig.hookenv.config")
    def test_wrong_raid(self, config):
        config.return_value = {
            "reservation": "off",
            "raid-autodetection": "wrong",
            "governor": ""
        }
        sysh = lib_sysconfig.SysConfigHelper()
        assert not sysh.is_config_valid()

    @mock.patch("lib_sysconfig.hookenv.config")
    def test_wrong_governor(self, config):
        config.return_value = {
            "reservation": "off",
            "raid-autodetection": "",
            "governor": "wrong"
        }
        sysh = lib_sysconfig.SysConfigHelper()
        assert not sysh.is_config_valid()

    @mock.patch("lib_sysconfig.hookenv.config")
    def test_enable_container(self, config):
        config.return_value = {
            "enable-container": True
        }
        sysh = lib_sysconfig.SysConfigHelper()

        assert sysh.enable_container
