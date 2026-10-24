# usr/sbin/base-daemons

What rc starts on every system, and rc's control program.

Covers, from OpenBSD's base system at the pin (its path in OpenBSD's `src`):

- [`rcctl`](rcctl/) (usr.sbin/rcctl)
- [`inetd`](inetd/) (usr.sbin/inetd)
- [`cron`](cron/) (usr.sbin/cron)
- [`syslogd`](syslogd/) (usr.sbin/syslogd)
- [`syslogc`](syslogc/) (usr.sbin/syslogc)
- [`watchdogd`](watchdogd/) (usr.sbin/watchdogd)
- [`hotplugd`](hotplugd/) (usr.sbin/hotplugd)
- [`sensorsd`](sensorsd/) (usr.sbin/sensorsd)
- [`apmd`](apmd/) (usr.sbin/apmd)
- [`apm`](apm/) (usr.sbin/apm)

Each entry is a program directory laid out as `docs/PROGRAM.md` says.
