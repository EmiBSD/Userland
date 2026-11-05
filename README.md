# EmiBSD Userland

<p align="center">
  <img src="docs/Ferffy.jpg" alt="Ferffy, the EmiBSD mascot: a centolla, the spiky orange crab of the southern seas, in front of a shield, above the EmiBSD name" width="380">
</p>

<p align="center"><em>Ferffy, the EmiBSD mascot: a <a href="https://en.wikipedia.org/wiki/Lithodes_santolla">centolla</a>, the child of Ferris (Rust's crab) and Puffy (OpenBSD's pufferfish).</em></p>

<p align="center"><strong>The base system above the kernel: one tree, every program placed by what it does.</strong></p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-ISC-007ec6" alt="License: ISC"></a>
  <a href="catastro.md"><img src="https://img.shields.io/badge/status-experimental-e05d44" alt="Status: experimental"></a>
  <a href="https://www.emibsd.org"><img src="https://img.shields.io/badge/website-emibsd.org-9f9f9f" alt="Website: www.emibsd.org"></a>
</p>

> **Not for production.** EmiBSD is an experiment. It runs only in QEMU, and its crypto,
> network and storage code is unaudited. Do not use it to protect real data or real networks.

The monorepo of EmiBSD's userland: the programs, libraries and configuration that run
above the [Kernel](https://github.com/EmiBSD/Kernel). Phase 3 of the project. Its base is
OpenBSD's base system at the pin, the same C the kernel runs today, in an order of our own:
every program placed by what it does instead of where thirty years of accretion left it. The
written programs grow from that base one at a time, as the kernel's redesign replaces its
inherited tree subsystem by subsystem.

## Where it sits

```mermaid
flowchart LR
    obsd["OpenBSD-src (mirror)"] -- "the base system's sources, at the pin;<br/>the imports (ssh, LibreSSL, ...)" --> ul["Userland"]
    lz["LandingZone"] -. "the pin" .-> ul
    dev["DevTools"] -- "clang, lld, libc++; rustc, cargo, std" --> ul
    ul -- "the base sets" --> os["OS"]
    ul -. "sysroot: libc, crt, headers" .-> dev
```

The pin is LandingZone's, because it fixes the ABI the kernel implements; the toolchains come
from DevTools; OS assembles the sets with the kernel into a release.

## Rules (the user's decisions of 2026-10-23, revised on 2026-11-04)

- **Three classes of program** (`docs/PROGRAM.md`; the user's decision of 2026-11-04,
  replacing the two classes of 2026-10-23). *Inherited*: the base system's C at
  LandingZone's pin, from the `EmiBSD/OpenBSD-src` mirror, every notice kept whole, placed
  in this layout and changed only by `patches/`, never rewritten in place: the base EmiBSD
  runs. *Imported*: cryptography, the security and network protocols with a living upstream
  and a CVE history, and the legacy giants (`ssh`, LibreSSL, `unbound`, `smtpd`, `vi`,
  `tmux`, `mandoc`, ncurses, ...) are compiled from their upstream at the pin of their
  `UPSTREAM.toml`, never rewritten; our patches are a numbered series, ideally empty.
  *Written*: from scratch, under a definition, in Rust, one program at a time where a program
  is worth it; nothing is a port or a translation of another system's program. `just status`
  counts the three. No program is imported today: the entries once imported (ssh, LibreSSL,
  ncurses, unbound, ...) come from the same mirror at the same pin and are inherited since
  2026-11-04, their CPE kept in `UPSTREAM.toml` for their CVE history; the class stays for an
  upstream outside the base system's tree.
- **The first written programs were a proof of concept.** `cli`, `sys`, `ls` and `cp`
  showed the written class and its grammar; their code and documents live on the
  `experimental` branch. `ls` and `cp` are inherited here like every other program; the
  documents of the two shared crates stay at `designed`. `main` carries no Rust code, no
  workspace and no toolchain pin until a written program returns.
- **Rust** for what is written; C only where the ABI demands it, assembly only in libc's
  syscall stubs. `#![forbid(unsafe_code)]` in every program; `unsafe` only in `base/lib/libc`,
  `base/libexec/rtld` and `base/lib/crates/sys` (the thin FFI the programs share), each site with a
  written proof, as the kernel's `hal`.
- **One grammar for every program** (`docs/PROGRAM.md`, "The common grammar"; the user's
  decision of 2026-10-24, taken with `ls`): a program is a query over records with a schema;
  `-o name|table|wide|json|yaml|custom-columns=...` picks the renderer, `--sort-by=.field`
  the order, `--no-headers` the table's header; `--request` takes the whole invocation as
  one JSON document (a file, or inline) and `--show-request` prints it; under `-o json` the
  diagnostics are records too (`severity`, `code`, `subject`), one per line on standard
  error, so a person and a machine drive the same program the same way. POSIX's short flags
  keep their meaning, and
  to a pipe the output is POSIX's byte for byte; to a terminal the defaults are modern (ISO
  dates, human sizes, headers). BSD-only flags nobody remembers are not kept.
- **LLVM and Rust, nothing GPL.** The toolchains live in
  [DevTools](https://github.com/EmiBSD/DevTools): upstream LLVM at
  a pinned release, one compiler for the C and the backend of rustc, and rust-lang/rust at a
  pinned stable tag, so the `*-unknown-openbsd` targets, tier 3 in Rust, get their `std` from a
  stable release's source, not from nightly. Nothing of them comes from OpenBSD's tree.
- **Upstreams are mirrored in the organisation** (`EmiBSD/OpenBSD-src`, `EmiBSD/rust`, ...),
  so an upstream that moves or disappears does not take the build with it. A tarball upstream
  gets a repository where each release is one commit. Fetched sources live under `upstream/`,
  gitignored and read-only; a build applies `patches/` to a copy under `target/`, never to
  `upstream/`. `tools/upstream.py` fetches, verifies (commit, SHA-256, signature) and pins.
- **`just` and make.** Every program carries a `justfile` that imports `tools/program.just`;
  the root `justfile` runs over all of them. `cargo` builds the written programs; the
  inherited C is built by its own Makefiles with the base system's own make (the user's
  decision of 2026-11-04): `just host-make` builds that make for the development host from
  its inherited `src/` with DevTools' clang, without any make, and it reads the `share/mk` of
  the same pin. Nothing else is installed for it; `tools/host/compat.h` gives the host tools
  what macOS lacks, and is never shipped. `just world arm64` (`tools/world.py`) builds for
  EmiBSD: it copies every inherited `src/` back to its path in the base system's tree under
  `target/`, builds the host tools the Makefiles run (rpcgen, yacc, lex), then
  `/usr/include`, csu, the libraries and the programs, each by its own Makefile and the
  pin's `share/mk`, with DevTools' clang for `aarch64-emibsd-emibsd8.0`. It runs as a user:
  `tools/host/install.sh` records in `target/<arch>/metalog` the owner, group and mode a
  Makefile asks for instead of setting them. `just` is the recipes.
- **Versions.** Semver per program (`src/Cargo.toml`, or `version` in `UPSTREAM.toml` with
  our patch level as `+emibsd.N`); a calendar version, `YEAR.MONTH`, for the system release.
  A commit that changes a program's code carries `Change: breaking|feature|fix` and the bump
  it calls for; the `commit-msg` hook (`just setup`) refuses it otherwise, and `just changelog`
  writes each program's `CHANGELOG.md` from the trailers (`docs/PROGRAM.md`, Versions).
- **Performance, concurrency and security are part of every definition**: a performance
  budget measured against a reference system's program on the same input (`bench/`, `just bench`); the
  concurrency model, and stress tests on four CPUs for what serves many; a threat model, the
  `pledge`/`unveil` profile, and the program's CVE history (`tests/cve/`), each entry made
  impossible by a type, a check or the language, or tested.

## Layout

Under `base/`, the system that is built, the BSD split: `bin/` and `sbin/` are what works with only the root
partition mounted (linked static), `usr/bin/` and `usr/sbin/` the rest; `bin` and `usr/bin`
are for the user, `sbin` and `usr/sbin` for operating the system. Inside each, the programs
are grouped by what they do. A concept the tradition spreads over two trees keeps a distinct
name in each (`bin/files` and `usr/bin/file-tools`, `sbin/network` and `usr/sbin/network/`),
and the README of each says where its other half is. Every program is listed once, in the
tree the tradition keeps it in; `tools/layout.py` regenerates the READMEs and the skeletons from
the map and refuses to write when one is missing or doubled.

```
base/bin/
├── shells               The shells.
├── files                The basic file operations.
├── processes            Listing, signalling and pacing processes; the shell's primitives.
├── system               The machine's name, the terminal line, a checksum.
└── tapes                Tape and changer control.
base/sbin/
├── boot                 Process 1, going down, the console and the terminals.
├── storage/disks        Partitions, labels, device nodes and controllers.
├── storage/filesystems  Making, checking and tuning file systems.
├── storage/mounts       Mounting, and serving file systems over NFS.
├── storage/swap-backup  Swap, dumps, restores and quotas.
├── network              Interfaces, routes, the packet filter, address configuration and name resolution.
├── ipsec                IPsec and its key daemons.
└── kernel               Reading and setting the kernel's state.
base/usr/bin/
├── text                 Filters and transformers of text streams.
├── records              Querying the records the written programs emit (`-o json`); EmiBSD's own, no counterpart elsewhere.
├── editors              Editors and the pager.
├── file-tools           Finding, describing and installing files (the basic operations are bin/files).
├── process-tools        Running things under a changed environment, priority or limit; the shell's helpers (the primitives are bin/processes).
├── users                Logging in, identities, who is on the machine, talking to them.
├── network-clients      Network clients a user runs.
├── development          Build tools, source generators, version control and tracing.
├── docs                 Manual pages and terminal descriptions.
├── calc                 Calculators and calendars.
├── mail                 Reading and sending mail from the command line.
├── scheduling           Running things later.
├── media                Audio, MIDI, radio and CD.
├── system-info          What machine this is, how it is doing, and small system chores.
├── crypto               Certificates, signatures and keys from the command line.
├── yp-clients           Querying the YP/NIS directory (its servers are usr/sbin/yp).
└── misc                 What fits nowhere else.
base/usr/sbin/
├── base-daemons         What rc starts on every system, and rc's control program.
├── accounts             Creating users and groups, the databases built from them, accounting, tokens (what a user does with their own identity is usr/bin/users).
├── storage-admin        Boot blocks, images, quotas, iSCSI, media (the root-partition tools are sbin/storage).
├── network/admin        Neighbours, traces, captures, link state (the root-partition tools are sbin/network).
├── network/dhcp         DHCP, DHCPv6 and router advertisements: the servers and the lease controls.
├── network/routing      Routing daemons and their control programs.
├── hardware             Buses, firmware, GPIO and the guest-host channel.
├── stats                Kernel and I/O statistics.
├── services             Servers: web, mail, time, DNS, LDAP, SNMP, domains.
├── yp                   The YP/NIS servers (the clients are usr/bin/yp-clients).
├── auth                 RADIUS, authpf, wireless authentication and certificate renewal.
├── vpn                  IKE control, PPP and L2TP (the IPsec daemons are sbin/ipsec).
├── nfs-rpc              The RPC services and network boot.
├── printing             Printing.
├── virtualization       vmm(4)'s daemon and control program.
├── packages             Packages, firmware, patches and upgrades.
├── kernel-dev           Configuring, tracing and packaging kernels (the running kernel's state is sbin/kernel).
└── wscons               Console screens, fonts and the console mouse.
base/libexec/
├── login                The authentication back ends login(1) calls.
├── rtld                 The run-time linker.
├── network-daemons      Daemons inetd and the RPC services start.
├── mail                 Local delivery and the spam daemon.
└── system               The login prompt, the nightly security check, the kernel relinker, the traditional cpp.
base/lib/
├── libc                 The C library, its start-up files, threads and libm.
├── crypto               Cryptography and authentication.
├── terminal             Terminal handling and line editing.
├── system               The rest.
└── crates               The Rust crates the written programs share, each born with its first user and laid out as a program (docs/PROGRAM.md): `cli`, the common grammar (one declaration per program with typed options, --help as text and as a record, usage and diagnostics, exit codes; records, -o, --sort-by, tables, JSON, YAML, columns); `sys`, the thin FFI over libc (passwd and group lookups, the terminal, local time, pledge, uid and umask, mkfifo and mknod, file flags, a link's times and mode), the one place beside lib/libc and libexec/rtld where `unsafe` is allowed, each site with its proof. EmiBSD's own; no counterpart elsewhere.
base/etc/
├── rc                   The start-up scripts and the terminal table.
└── base                 Users, groups, shells, the protocol tables, device nodes, the file-system skeleton, root's dotfiles, the per-architecture files.
base/data/
├── zoneinfo             The IANA time zone database (tzdata; zic and zdump are usr/sbin/services).
├── locale               Locale definitions and character maps.
├── dict                 The word lists spell(1) and look(1) read.
├── termtypes            The terminal descriptions, source of terminfo (tic is usr/bin/docs).
└── misc                 Small tables of share/misc: ascii, airport codes, units, the magic of file(1) is in file itself.
base/distrib/
├── sets                 The install sets and their lists; the release version is YEAR.MONTH (docs/PROGRAM.md, Versions).
├── installer            The installer, its ramdisk and the per-architecture media.
├── include              /usr/include as include/Makefile assembles it: the C library's public headers (include/) and the kernel's, the ABI the kernel implements (sys/, headers only, without dev/microcode and dev/pci/drm, as that Makefile leaves them out). The libraries' own exported headers stay with each library.
├── share                /usr/share's own trees: share/mk, the rules every Makefile of the base system includes, and the manuals' shared pages.
└── build                The base system's build glue, which belongs to no program: the top Makefile and Makefile.cross, and the Makefile and Makefile.inc of each tree (bin/Makefile.inc makes every /bin program static).
regress/
├── scenarios            One directory per scenario: the steps, the expected lines, the comparison with a reference system.
└── harness              Booting the images, driving the console, collecting and comparing.
```

The lists are the map to what a complete base system provides, taken from the names at the pin of
`Kernel/reference/PINNED.md`: every program directory of the base system at the pin has exactly
one place in it, and each place is filled by its class.

## Open

- **The inherited class is in the tree, not built.** Every program of the base system has
  its directory at the pin in `src/`, copied by `tools/layout.py` (committed, the user's
  decision of 2026-11-04), and so does every tree that is not a program (`etc/`, `data/`,
  `distrib/`: share/mk, /usr/include with the kernel's headers, the build glue). `just
  world arm64` builds today /usr/include (identical to the Kernel's), csu, libc, libutil,
  libm, libz, libcurses, libkvm and the first 31 programs (init, ksh, mount, ls, ...),
  static, and `target/arm64/ramdisk.ffs`, made by the base system's makefs built for the
  host (`tools/host/makefs.h`, `makefs-host.c`) with the owners and modes the metalog
  recorded and the nodes of MAKEDEV's `ramdisk` target. It boots on the Kernel
  single-user: the Kernel mounts it as `rd0a`, init offers the shell and ksh runs (the
  Kernel's `xtask smoke --ramdisk`, 2026-11-04). Still to come: `/etc/pwd.db` (pwd_mkdb for
  the host), a multi-user boot (rc, getty, login), ld.so and the shared libraries, the other
  programs, amd64. `gnu/` stays out; the base system's own `regress/` is brought per program when needed.
- **Decisions the user has still to take** about the inherited class: whether the Kernel
  keeps its own userland build until N9 (proposed) or consumes this repository's ramdisk now;
  the milestone letter and the first milestone (proposed: the 110 programs the Kernel builds
  today, in this layout, booting its smokes).
- **Perl.** `pkg_add`, `adduser`, `libtool`, `pkgconf` and `security` are traditionally Perl, and
  Perl (Artistic or GPL, dual) is not in the tree: inherit it under the Artistic licence for
  those five, leave them out, or write them in Rust. The user's decision; their skeletons say so.
- `cargo audit` and `cargo deny` (`just audit`, part of `just check` when installed) are
  tools installed outside the repository with `cargo install`; `tools/cve.py` (`just cve
  <dir>`) queries NVD over the network. Both written, neither run: pending the user's OK.
- `data/` entries are imports like the programs (tzdata, the locales): their `UPSTREAM.toml`
  files are to be written.

New code is ISC (`LICENSE`).
