# libform: integration

## How it is built

The source at the pin, copied to `target/`, `patches/` applied, built by `build/build.sh`
against this repository's libc and libraries. Flags that differ from OpenBSD's build, with
the reason.

## Patches

One line per patch of `patches/`: what it changes and why it could not stay upstream.

## Concurrency

As upstream has it; nothing added.

## Threat model and security

What the upstream restricts (pledge, unveil, privilege separation) and the proof we kept it:
the tests that run it under our kernel.

## Dependencies

The libraries of this repository it links, and any other upstream it needs.
