# usr/sbin

Daemons and administration once the system is whole (151).

| Directory | What |
|---|---|
| `base-daemons/` | What rc starts on every system, and rc's control program. |
| `accounts/` | Creating users and groups, the databases built from them, accounting, tokens (what a user does with their own identity is usr/bin/users). |
| `storage-admin/` | Boot blocks, images, quotas, iSCSI, media (the root-partition tools are sbin/storage). |
| `network/admin/` | Neighbours, traces, captures, link state (the root-partition tools are sbin/network). |
| `network/dhcp/` | DHCP, DHCPv6 and router advertisements: the servers and the lease controls. |
| `network/routing/` | Routing daemons and their control programs. |
| `hardware/` | Buses, firmware, GPIO and the guest-host channel. |
| `stats/` | Kernel and I/O statistics. |
| `services/` | Servers: web, mail, time, DNS, LDAP, SNMP, domains. |
| `yp/` | The YP/NIS servers (the clients are usr/bin/yp-clients). |
| `auth/` | RADIUS, authpf, wireless authentication and certificate renewal. |
| `vpn/` | IKE control, PPP and L2TP (the IPsec daemons are sbin/ipsec). |
| `nfs-rpc/` | The RPC services and network boot. |
| `printing/` | Printing. |
| `virtualization/` | vmm(4)'s daemon and control program. |
| `packages/` | Packages, firmware, patches and upgrades. |
| `kernel-dev/` | Configuring, tracing and packaging kernels (the running kernel's state is sbin/kernel). |
| `wscons/` | Console screens, fonts and the console mouse. |

Each entry is a group; each group's README lists its programs.
