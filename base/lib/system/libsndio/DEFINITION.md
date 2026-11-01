# libsndio (imported)

STATUS: see `STATUS`. Compiled from its upstream at the pin of `UPSTREAM.toml`, never
rewritten (the user's decision of 2026-10-23). OpenBSD's `lib/libsndio`; manual libsndio(3).

## What it gives us

## What we build of it

The targets, libraries and tools taken from the source; what is left out and why.

## Constraints

Which libc, libtls and other libraries of this repository it must link; static or dynamic;
privileges.

## Compatibility

Who in the base system depends on it and how (flags, output, exit codes, configuration
paths). Our patches, if any, never change what callers see.

## Configuration we ship

The defaults installed under /etc, and how they differ from upstream's.

## Performance budget

As OpenBSD builds it, on the same machine and input; a build flag that changes it is a
decision in DESIGN.

## Security history

Tracked against the upstream (`UPSTREAM.toml` `[security] cpe`): open advisories at the pin,
what the pin bump that closes them is, and `tests/cve/` for what we patched ourselves.

| CVE | Upstream fix | Here |
|---|---|---|

## Open questions

