# zstd (imported)

STATUS: see `STATUS`. Compiled from its upstream at the pin of `UPSTREAM.toml` (the
organisation's mirror `EmiBSD/zstd` of `facebook/zstd`, tag `v1.5.7`), never rewritten (the
user's decision of 2026-10-23). Imported into the base system on 2026-11-05 (the user's
decision): the install sets are zstd archives, and the installer and the system read them
with it. Licence: upstream's dual BSD-3-Clause or GPL-2.0-only; EmiBSD takes the BSD side
(no GPL in the base system), whose text is `LICENSE` in the source.

## What it gives us

`/usr/bin/zstd`, with `unzstd` and `zstdcat` as links to it, and the manual zstd(1) with
unzstd(1) and zstdcat(1) as links: the command line program as upstream's
`programs/Makefile` builds it by default, its library compiled in.

## What we build of it

`build/Makefile`, for the base system's make: `programs/` and `lib/` (common, compress,
decompress, dictBuilder). Threads (`ZSTD_MULTITHREAD`, `-lpthread`), dictionaries and the
benchmark are in; the legacy formats (`ZSTD_LEGACY_SUPPORT=0`), the gzip, xz and lz4
formats (they link zlib, liblzma and liblz4, which the base system does not have or does
not link here) and the x86-64 assembly decoder (`ZSTD_DISABLE_ASM`) are out. No shared
libzstd: nothing in the base system links it yet. `world.py` puts the pinned source and
`build/` at `usr.bin/zstd` of the copied tree (`UPSTREAM.toml`, `[build] tree`) and builds
and installs it after the base system's trees.

## Compatibility

The installer (`base/distrib/installer`, its patches) extracts the sets with
`zstd -dc | tar -xphf -`; the sets step writes them with libarchive's zstd at level 19. A
frame either writes is read by the other.

## Patches

The series under `patches/`, each with its reason in its header: none today.

## Security history

Tracked against the CPE `facebook:zstandard` (`tools/cve.py`); a pin bump lists what it
closes.

| Advisory | Fix | Here |
|---|---|---|

## Open questions

- The installer's crunched copy (`distrib/special/zstd`) is the decompressor alone; whether
  the base system's should also link a shared libzstd once a second program needs it.
