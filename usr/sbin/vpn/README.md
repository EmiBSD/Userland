# usr/sbin/vpn

IKE control, PPP and L2TP (the IPsec daemons are sbin/ipsec).

Covers, from OpenBSD's base system at the pin (its path in OpenBSD's `src`):

- [`ikectl`](ikectl/) (usr.sbin/ikectl) (imported)
- [`npppd`](npppd/) (usr.sbin/npppd) (imported)
- [`npppctl`](npppctl/) (usr.sbin/npppctl)
- [`pppd`](pppd/) (usr.sbin/pppd) (imported)
- [`sasyncd`](sasyncd/) (usr.sbin/sasyncd) (imported)

Each entry is a program directory laid out as `docs/PROGRAM.md` says.
