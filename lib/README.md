# lib

The libraries every program links. While the kernel keeps OpenBSD's ABI, libc speaks OpenBSD's system calls: this is the layer closest to OpenBSD by necessity, and with libexec/rtld the only place `unsafe` is allowed. OpenBSD's lib/ (35).

| Directory | What |
|---|---|
| `libc/` | The C library, its start-up files, threads and libm. |
| `crypto/` | Cryptography and authentication. |
| `terminal/` | Terminal handling and line editing. |
| `system/` | The rest. |
| `crates/` | The Rust crates the written programs share, each born with its first user and laid out as a program (docs/PROGRAM.md): `cli`, the common grammar and renderers (-o, --sort-by, tables, JSON, YAML, columns); `sys`, the thin FFI over libc (passwd and group lookups, the terminal, local time, pledge), the one place beside lib/libc and libexec/rtld where `unsafe` is allowed, each site with its proof. EmiBSD's own; no OpenBSD counterpart. |

Each entry is a group; each group's README lists its programs.
