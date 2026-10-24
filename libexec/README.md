# libexec

Programs run by other programs, never by a user. OpenBSD's libexec/ (28).

| Directory | What |
|---|---|
| `login/` | The authentication back ends login(1) calls. |
| `rtld/` | The run-time linker. |
| `network-daemons/` | Daemons inetd and the RPC services start. |
| `mail/` | Local delivery and the spam daemon. |
| `system/` | The login prompt, the nightly security check, the kernel relinker, the traditional cpp. |

Each entry is a group; each group's README lists its programs.
