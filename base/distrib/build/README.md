# distrib/build

The base system's build glue, which belongs to no program: the top Makefile and Makefile.cross, and the Makefile and Makefile.inc of each tree (bin/Makefile.inc makes every /bin program static).

Programs of this group:

- `Makefile` (Makefile)
- `Makefile.cross` (Makefile.cross)
- `Makefile` (bin/Makefile)
- `Makefile.inc` (bin/Makefile.inc)
- `Makefile` (sbin/Makefile)
- `Makefile.inc` (sbin/Makefile.inc)
- `Makefile` (usr.bin/Makefile)
- `Makefile.inc` (usr.bin/Makefile.inc)
- `Makefile` (usr.sbin/Makefile)
- `Makefile.inc` (usr.sbin/Makefile.inc)
- `Makefile` (libexec/Makefile)
- `Makefile.inc` (libexec/Makefile.inc)
- `Makefile` (lib/Makefile)
- `Makefile` (distrib/Makefile)
- `Makefile` (games/Makefile)
- `Makefile.inc` (games/Makefile.inc)

Inherited: `src/` holds these at their paths in the base system's tree, at the pin of `UPSTREAM.toml`.
