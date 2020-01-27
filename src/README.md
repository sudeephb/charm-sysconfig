# Overview

This is a subordinate charm to apply grub, systemd, kernel and cpufrequtils configuration. 

Note that the charm will override kernel parameters that were
previously configured. To add or keep kernel parameters you had
previously configured see the grub-config-flags option below.

Similarly, the charm will also override existing system-systemd
configuration. To add to the systemd configuration see the
systemd-config-flags option. 


# Usage

Deploy sysconfig alongside your service,

    juju deploy ubuntu
    juju deploy sysconfig

Add the relations:

    juju add-relation sysconfig ubuntu

# Configuration

## Enable-container

By default, the charm can not be installed in a container.
Configuring enable-container=true the charm will be installed in
a container too. This is intended only for testing purpose.

## Reservation

By default, the charm does not configure any CPU related reservation.
However, "isolcpus" or "affinity" can be configured on systemd hosts.

## cpu-range

In case of "isolcpus", it determines the pcpus that won't be used by the
host (ie. the same range is configured for QEMU usage).

In case of "affinity", it determines the pcpus that the host WILL use
(ie. a complementary range to the QEMU vcpu_pin_set).

If this value is left empty, charm behaves as if "reservation=off".

## Hugepages

It controls the number of hugepages to be set in the system. By default the
value is empty, if specified `hugepages={{ hugepages }}` will be attached to
the grub cmdline.

## Hugepagesz

It controls the size of each hugepage to be set in the system. By default the
value is empty, if specified `hugepagesz={{ hugepagesz }}` will be attached to
the grub cmdline.

## Raid autodetection

It controls the raid detection mode. By default it is empty, this means that
autodetection is enabled if 'md' module is compiled into the kernel. Possibles
values will be "noautodetect" that disables raid autodetection and "partitionable"
where all auto-detected arrays are assembled as partitionable.

## Enable Pti

By default Page Table Isolation is disabled passing "pti=off" to the grub cmdline.
Set to true to enable it.

## Enable Iommu

If true and VT-d enabled in the BIOS, it will allow to use direct I/O
bypassing DMA translation with pci-passthrough devices. Enable it to use SR-IOV

## grub-config-flags

If you need further options configured, this extra options will be added
to the files `/etc/default/grub`

For instance, if you need to set the kernel parameter
"nvme_core.multipath=0" you would add:

juju config sysconfig grub-config-flags='GRUB_CMDLINE_LINUX_DEFAULT="$GRUB_CMDLINE_LINUX_DEFAULT nvme_core.multipath=0"

## systemd-config-flags

If you need further options configured, this extra options will be added
to the files `/etc/systemd/system.conf`

For instance, if you need to set the "CrashReboot" parameter you would use:
juju config sysconfig systemd-config-flags="CrashReboot=yes"

## config-flags

DEPRECATED in favor of grub-config-flags or systemd-config-flags

If you need further options configured, these extra options will be added
to the files:
 * `/etc/default/grub` (reservation=isolcpus)
 * `/etc/systemd/system.conf` (reservation=affinity)

## Kernel Version

Upgrade kernel and modules-extra package to this version and add `GRUB_DEFAULT` to
`/etc/default/grub` to load the required kernel version. It does
nothing if same kernel already running.

## update-grub

By default, this value is set to "false". If enabled, charm will run
"update-grub" when changing `/etc/default/grub`.

## Governor
Governor is configured via cpufrequtils, possible values are:
 * '' (default): systemd will choose the first available between 'ondemand', 'powersave', 'performance'.
 Recommended option when Bios control power is set to the OS.
 * 'performance'
 * 'powersave'


# Release notes

With the new release default behaviour has changed.
To produce same configuration as was before default behaviour use the following configuration:

sysconfig:
    charm: cs:~canonical-bootstack/xenial/sysconfig
    options:
        raid-autodetection: "noautodetect"
        enable-iommu: true

# Contact Information

- Charm bugs: https://bugs.launchpad.net/charm-sysconfig
