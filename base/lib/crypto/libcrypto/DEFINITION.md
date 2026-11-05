# libcrypto (inherited)

STATUS: see `STATUS`. The base system's program at the pin of `UPSTREAM.toml`, in this
layout (the user's decision of 2026-11-04): `src/` is OpenBSD's `lib/libcrypto` byte for byte,
every notice in it kept whole, rewritten from the pin by `tools/layout.py` and never edited
by hand. What we change is a patch under `patches/`. Manual libcrypto(3), in `src/`.

## What it is for here

## Compatibility

Who in the base system depends on it and how (flags, output, exit codes, configuration
paths). Our patches, if any, never change what callers see.

## Patches

The series under `patches/`, each with its reason in its header: none today.

## Security history

The advisories and errata of the base system that touch `lib/libcrypto` at the pin, the pin bump
that closes them, and `tests/cve/` for what we patched ourselves.

| Advisory | Fix | Here |
|---|---|---|

## Open questions

