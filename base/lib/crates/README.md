# lib/crates

The Rust crates the written programs share, each born with its first user and laid out as a program (docs/PROGRAM.md): `cli`, the common grammar (one declaration per program with typed options, --help as text and as a record, usage and diagnostics, exit codes; records, -o, --sort-by, tables, JSON, YAML, columns); `sys`, the thin FFI over libc (passwd and group lookups, the terminal, local time, pledge, uid and umask, mkfifo and mknod, file flags, a link's times and mode), the one place beside lib/libc and libexec/rtld where `unsafe` is allowed, each site with its proof. EmiBSD's own; no counterpart elsewhere.

Programs of this group:

- [`cli`](cli/) (EmiBSD's own crate)
- [`sys`](sys/) (EmiBSD's own crate)

Each entry is a program directory laid out as `docs/PROGRAM.md` says.
