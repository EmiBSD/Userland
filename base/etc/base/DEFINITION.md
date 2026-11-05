# etc/base (inherited)

STATUS: see `STATUS`. Files of the base system that belong to no program, at the pin of
`UPSTREAM.toml`, in this layout (the user's decision of 2026-11-04): `src/` holds OpenBSD's
`etc/master.passwd`, `etc/group`, `etc/shells`, `etc/services`, `etc/protocols`, `etc/rpc`, `etc/MAKEDEV.mi`, `etc/MAKEDEV.common`, `etc/MAKEDEV.sub`, `etc/MAKEDEV.man`, `etc/MAKEDEV.mansub`, `etc/mtree`, `etc/skel`, `etc/root`, `etc/motd`, `etc/minfree`, `etc/etc.arm64`, `etc/etc.amd64`, `etc/Makefile`, `etc/Makefile.inc`, `etc/amd`, `etc/crontab`, `etc/examples`, `etc/fbtab.head`, `etc/fbtab.tail`, `etc/ftpusers`, `etc/ksh.kshrc`, `etc/locate.rc`, `etc/mail`, `etc/mailer.conf`, `etc/moduli`, `etc/newsyslog.conf`, `etc/nsd.conf`, `etc/ntpd.conf`, `etc/pf.conf`, `etc/pf.os`, `etc/ppp`, `etc/rpki`, `etc/signify`, `etc/syslog.conf`, `etc/unbound.conf`, each at its own path in that tree, byte for byte and every notice kept whole,
rewritten from the pin by `tools/layout.py` and never edited by hand. What we change is a
patch under `patches/`.

## What it is for here

## Patches

The series under `patches/`, each with its reason; none today.
