# rust (imported)

STATUS: see `STATUS`. Compiled from its upstream at the pin of `UPSTREAM.toml`, never
rewritten (the user's decision of 2026-10-23). OpenBSD's `https://github.com/rust-lang/rust`; manual rust(1).

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

- Two LLVMs, decided 2026-10-23: rustc 1.98.1 requires LLVM >= 21 (src/bootstrap, check_llvm_version) and OpenBSD's gnu/llvm at the pin is 18.1.8, so rustc builds the LLVM of its src/llvm-project submodule (rust-lang's fork, mirrored) and compiler/llvm stays OpenBSD's for clang, lld and the C. Built with x.py, host first, then target aarch64-unknown-openbsd: the std for the tier 3 target is built as part of the toolchain, from a stable release's source, without nightly. Needs a stage0 rustc: rustup's on the host; on EmiBSD, the previous build. Other submodules (books, stdarch, backtrace) stay on rust-lang/ until one is needed.
