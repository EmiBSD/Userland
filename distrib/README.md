# distrib

How a release is made, and what else is generated at release time: the install sets, the installer and its ramdisk, /usr/include from the libraries' exported headers, /usr/share from every program's manual plus data/. OpenBSD's distrib/.

| Directory | What |
|---|---|
| `sets/` | The install sets and their lists; the release version is YEAR.MONTH (docs/PROGRAM.md, Versions). |
| `installer/` | The installer, its ramdisk and the per-architecture media. |
| `include/` | The recipe that assembles /usr/include from what each library of lib/ exports; no header is kept here. |
| `share/` | The recipe that assembles /usr/share: every program's man/ rendered, data/, share/mk; no file is kept here. |

Nothing written yet.
