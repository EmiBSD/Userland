# distrib/share (inherited)

STATUS: see `STATUS`. Files of the base system that belong to no program, at the pin of
`UPSTREAM.toml`, in this layout (the user's decision of 2026-11-04): `src/` holds OpenBSD's
`share/mk`, `share/man`, `share/btrace`, `share/snmp`, `share/tmac`, `share/Makefile`, `share/Makefile.inc`, each at its own path in that tree, byte for byte and every notice kept whole,
rewritten from the pin by `tools/layout.py` and never edited by hand. What we change is a
patch under `patches/`.

## What it is for here

## Patches

The series under `patches/`, each with its reason in its header:

- `0001-makewhatis-by-variable.patch`: makedb runs makewhatis named by MAKEWHATIS, /usr/sbin/makewhatis when unset, so a cross build gives it one that runs on the host.
