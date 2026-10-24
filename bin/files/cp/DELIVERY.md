# cp: delivery

| | |
|---|---|
| Install set | `base` |
| Install path | `/bin/cp` |
| Linking | static: `bin/` and `sbin/` are linked statically (`src/build.rs` passes `-static` for the `openbsd` target, the Kernel's ABI), so `cp` runs in single-user mode and on the installer's ramdisk without `/usr/lib` or `ld.so` |
| Owner and mode | `root:bin`, `0555` |
| MAKEDEV | none |
| Manual | `man/cp.1`, installed as `/usr/share/man/man1/cp.1` |
| Default configuration | none |
| Size | 681 KB dynamic in release on macOS (the development host, 2026-10-24); the static size is measured when the target exists |

The installer's ramdisk does not carry one static binary per program: `distrib/installer`
builds the `bin/` and `sbin/` programs into one multi-call crate with `std` linked once, the
Rust form of the BSD `crunchgen`.
