# system-services

Daemons and administration: what operates the system once it is up. OpenBSD's sbin/ and usr.sbin/, grouped by what they manage rather than by where they install.

| Directory | What |
|---|---|
| `storage/` | Disks, partitions, file systems, mounts, swap and backup. |
| `network/` | Interfaces, addresses, routes, the packet filter, DHCP and name resolution. |
| `routing/` | Routing daemons and their control programs. |
| `daemons/` | Servers: web, mail, time, DNS, LDAP, logging, cron, inetd. |
| `vpn/` | IPsec, IKE, PPP and L2TP. |
| `auth/` | Authentication back ends, RADIUS and tokens. |
| `crypto-tools/` | Certificates, signatures and keys from the command line. |
| `nfs-rpc/` | NFS and the RPC services. |
| `yp/` | The YP/NIS directory service. |
| `hardware/` | Talking to the kernel about devices: sysctl, dmesg, consoles, buses, power, sensors. |
| `monitoring/` | Statistics and accounting. |
| `accounts/` | Users, groups and the system databases built from them. |
| `print/` | Printing. |
| `virtualization/` | vmm(4)'s daemon and control program, and the guest-host channel. |
| `packages/` | Packages, firmware, patches and upgrades. |

Nothing written yet.
