# lib

The libraries every program links. libc speaks the Kernel's system calls: this is the layer bound to the Kernel's ABI by necessity, and with libexec/rtld the only place `unsafe` is allowed (35).

| Directory | What |
|---|---|
| `libc/` | The C library, its start-up files, threads and libm. |
| `crypto/` | Cryptography and authentication. |
| `terminal/` | Terminal handling and line editing. |
| `system/` | The rest. |
| `crates/` | The Rust crates the written programs share, each born with its first user and laid out as a program (docs/PROGRAM.md): `cli`, the common grammar (one declaration per program with typed options, --help as text and as a record, usage and diagnostics, exit codes; records, -o, --sort-by, tables, JSON, YAML, columns); `sys`, the thin FFI over libc (passwd and group lookups, the terminal, local time, pledge, uid and umask, mkfifo and mknod, file flags, a link's times and mode), the one place beside lib/libc and libexec/rtld where `unsafe` is allowed, each site with its proof. EmiBSD's own; no counterpart elsewhere. |

Each entry is a group; each group's README lists its programs.
