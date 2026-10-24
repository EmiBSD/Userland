# etc

What the system needs before any program exists: the users and groups it is born with, the device nodes, the protocol tables, the start-up scripts. A program's own default configuration (pf.conf, ntpd.conf, syslog.conf, sshd's moduli, ...) lives in that program's etc/ and is installed from there; this tree holds only what belongs to no program. OpenBSD's etc/, reduced.

| Directory | What |
|---|---|
| `rc/` | The start-up scripts and the terminal table. |
| `base/` | Users, groups, shells, the protocol tables, device nodes, the file-system skeleton, root's dotfiles, the per-architecture files. |

Nothing written yet.
