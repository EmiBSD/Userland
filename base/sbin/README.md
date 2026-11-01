# sbin

What boots the system, repairs its disks and brings up its network, with only the root partition mounted (66).

| Directory | What |
|---|---|
| `boot/` | Process 1, going down, the console and the terminals. |
| `storage/disks/` | Partitions, labels, device nodes and controllers. |
| `storage/filesystems/` | Making, checking and tuning file systems. |
| `storage/mounts/` | Mounting, and serving file systems over NFS. |
| `storage/swap-backup/` | Swap, dumps, restores and quotas. |
| `network/` | Interfaces, routes, the packet filter, address configuration and name resolution. |
| `ipsec/` | IPsec and its key daemons. |
| `kernel/` | Reading and setting the kernel's state. |

Each entry is a group; each group's README lists its programs.
