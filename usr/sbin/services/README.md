# usr/sbin/services

Servers: web, mail, time, DNS, LDAP, SNMP, domains.

Covers, from OpenBSD's base system at the pin (its path in OpenBSD's `src`):

- [`httpd`](httpd/) (usr.sbin/httpd)
- [`slowcgi`](slowcgi/) (usr.sbin/slowcgi)
- [`smtpd`](smtpd/) (usr.sbin/smtpd)
- [`mailwrapper`](mailwrapper/) (usr.sbin/mailwrapper)
- [`spamdb`](spamdb/) (usr.sbin/spamdb)
- [`ftp-proxy`](ftp-proxy/) (usr.sbin/ftp-proxy)
- [`tftpd`](tftpd/) (usr.sbin/tftpd)
- [`tftp-proxy`](tftp-proxy/) (usr.sbin/tftp-proxy)
- [`relayd`](relayd/) (usr.sbin/relayd)
- [`relayctl`](relayctl/) (usr.sbin/relayctl)
- [`identd`](identd/) (usr.sbin/identd)
- [`ntpd`](ntpd/) (usr.sbin/ntpd)
- [`rdate`](rdate/) (usr.sbin/rdate)
- [`zdump`](zdump/) (usr.sbin/zdump)
- [`zic`](zic/) (usr.sbin/zic)
- [`unbound`](unbound/) (usr.sbin/unbound)
- [`nsd`](nsd/) (usr.sbin/nsd)
- [`unwindctl`](unwindctl/) (usr.sbin/unwindctl)
- [`ldapd`](ldapd/) (usr.sbin/ldapd)
- [`ldapctl`](ldapctl/) (usr.sbin/ldapctl)
- [`ldomd`](ldomd/) (usr.sbin/ldomd)
- [`ldomctl`](ldomctl/) (usr.sbin/ldomctl)
- [`snmpd`](snmpd/) (usr.sbin/snmpd)

Each entry is a program directory laid out as `docs/PROGRAM.md` says.
