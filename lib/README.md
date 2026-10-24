# lib

The libraries every program links. While the kernel keeps OpenBSD's ABI, libc speaks OpenBSD's system calls: this is the layer closest to OpenBSD by necessity, and with libexec/rtld the only place `unsafe` is allowed. OpenBSD's lib/ (35).

| Directory | What |
|---|---|
| `libc/` | The C library, its start-up files, threads and libm. |
| `crypto/` | Cryptography and authentication. |
| `terminal/` | Terminal handling and line editing. |
| `system/` | The rest. |

Each entry is a group; each group's README lists its programs.
