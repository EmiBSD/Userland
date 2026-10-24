# system-libraries

The libraries every program links and the headers they export. While the kernel keeps OpenBSD's ABI, libc speaks OpenBSD's system calls: this is the layer closest to OpenBSD by necessity.

| Directory | What |
|---|---|
| `libc/` | The C library, its start-up files and threads. |
| `rtld/` | The run-time linker. |
| `crypto/` | Cryptography and authentication libraries. |
| `terminal/` | Terminal handling and line editing. |
| `system/` | The rest of the system libraries. |
| `include/` | The headers installed under /usr/include. |

Nothing written yet.
