# usr/sbin/accounts

Creating users and groups, the databases built from them, accounting, tokens (what a user does with their own identity is usr/bin/users).

Covers, from OpenBSD's base system at the pin (its path in OpenBSD's `src`):

- [`adduser`](adduser/) (usr.sbin/adduser)
- [`user`](user/) (usr.sbin/user)
- [`vipw`](vipw/) (usr.sbin/vipw)
- [`chroot`](chroot/) (usr.sbin/chroot)
- [`pwd_mkdb`](pwd_mkdb/) (usr.sbin/pwd_mkdb)
- [`dev_mkdb`](dev_mkdb/) (usr.sbin/dev_mkdb)
- [`kvm_mkdb`](kvm_mkdb/) (usr.sbin/kvm_mkdb)
- [`netgroup_mkdb`](netgroup_mkdb/) (usr.sbin/netgroup_mkdb)
- [`ac`](ac/) (usr.sbin/ac)
- [`accton`](accton/) (usr.sbin/accton)
- [`sa`](sa/) (usr.sbin/sa)
- [`tokenadm`](tokenadm/) (usr.sbin/tokenadm)
- [`tokeninit`](tokeninit/) (usr.sbin/tokeninit)

Each entry is a program directory laid out as `docs/PROGRAM.md` says.
