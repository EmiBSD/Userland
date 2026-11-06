# distrib/installer (inherited)

STATUS: see `STATUS`. Files of the base system that belong to no program, at the pin of
`UPSTREAM.toml`, in this layout (the user's decision of 2026-11-04): `src/` holds OpenBSD's
`distrib/miniroot`, `distrib/special`, `distrib/arm64`, `distrib/amd64`, each at its own path in that tree, byte for byte and every notice kept whole,
rewritten from the pin by `tools/layout.py` and never edited by hand. What we change is a
patch under `patches/`.

## What it is for here

## Patches

The series under `patches/`, each with its reason in its header:

- `0001-sets-in-zstd.patch`: The install sets are base80.tar.zst, comp80, man80 and game80, extracted through zstd; the X sets are gone.
- `0002-one-kernel-bsd-mp.patch`: arm64 installs one kernel, bsd.mp, which becomes /bsd on every machine, one CPU or many.
- `0003-sets-from-the-medium.patch`: The location of the sets offers the install medium only, disk or CD, not http or nfs.
- `0004-ramdisk-list.patch`: The arm64 ramdisk crunches zstd into instbin and leaves out the firmware files and the Raspberry Pi's boot files.
- `0005-special-zstd.patch`: distrib/special/zstd: the installer's zstd, the decompressor alone, for crunchgen.
- `0006-more-help-printf.patch`: distrib/special/more writes the opening of morehelp.h with printf, not echo -n.
- `0007-emibsd-name.patch`: The installer names the system it installs EmiBSD, and finds the latest boot in dmesg by EmiBSD's kernel banner.
