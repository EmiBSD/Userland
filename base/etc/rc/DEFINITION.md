# etc/rc (inherited)

STATUS: see `STATUS`. Files of the base system that belong to no program, at the pin of
`UPSTREAM.toml`, in this layout (the user's decision of 2026-11-04): `src/` holds OpenBSD's
`etc/rc`, `etc/rc.conf`, `etc/rc.d`, `etc/netstart`, `etc/daily`, `etc/weekly`, `etc/monthly`, `etc/changelist`, `etc/gettytab`, `etc/ttys.pty`, each at its own path in that tree, byte for byte and every notice kept whole,
rewritten from the pin by `tools/layout.py` and never edited by hand. What we change is a
patch under `patches/`.

## What it is for here

## Patches

The series under `patches/`, each with its reason in its header: none today.
