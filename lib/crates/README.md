# lib/crates

The Rust crates the written programs share, each born with its first user and laid out as a program (docs/PROGRAM.md): `cli`, the common grammar and renderers (-o, --sort-by, tables, JSON, YAML, columns); `sys`, the thin FFI over libc (passwd and group lookups, the terminal, local time, pledge), the one place beside lib/libc and libexec/rtld where `unsafe` is allowed, each site with its proof. EmiBSD's own; no OpenBSD counterpart.

Covers, from OpenBSD's base system at the pin (its path in OpenBSD's `src`):

- [`cli`](cli/) (EmiBSD's own crate)
- [`sys`](sys/) (EmiBSD's own crate)

Each entry is a program directory laid out as `docs/PROGRAM.md` says.
