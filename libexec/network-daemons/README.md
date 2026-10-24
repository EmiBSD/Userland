# libexec/network-daemons

Daemons inetd and the RPC services start.

Covers, from OpenBSD's base system at the pin (its path in OpenBSD's `src`):

- [`ftpd`](ftpd/) (libexec/ftpd)
- [`fingerd`](fingerd/) (libexec/fingerd)
- [`talkd`](talkd/) (libexec/talkd)
- [`comsat`](comsat/) (libexec/comsat)
- [`rpc.rquotad`](rpc.rquotad/) (libexec/rpc.rquotad)
- [`rpc.rstatd`](rpc.rstatd/) (libexec/rpc.rstatd)
- [`rpc.rusersd`](rpc.rusersd/) (libexec/rpc.rusersd)
- [`rpc.rwalld`](rpc.rwalld/) (libexec/rpc.rwalld)
- [`snmpd`](snmpd/) (libexec/snmpd)

Each entry is a program directory laid out as `docs/PROGRAM.md` says.
