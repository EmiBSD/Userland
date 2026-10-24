#!/usr/bin/env python3
"""Generate the Userland monorepo's layout: the trees, one README.md per directory, and the
skeleton of every program and library (docs/PROGRAM.md is the contract).

usage: layout.py <openbsd-src root> <Userland root>

The top level is OpenBSD's own split by install path (bin, sbin, usr/bin, usr/sbin, libexec,
lib, include, compiler, etc, share, distrib); inside each, the programs are grouped by what
they do. Every program of OpenBSD's bin/, sbin/, usr.bin/, usr.sbin/, libexec/ and lib/ is
mapped to exactly one leaf, in the tree OpenBSD keeps it in; the script refuses to write
otherwise. Skeleton files are created only when missing, so refinement survives a rerun.
"""
import os
import sys
from pathlib import Path

SRC = Path(sys.argv[1])
OUT = Path(sys.argv[2])

# Where a top-level directory's bare names come from in OpenBSD's src.
SOURCE_DIR = {"bin": "bin", "sbin": "sbin", "usr/bin": "usr.bin", "usr/sbin": "usr.sbin",
              "libexec": "libexec", "lib": "lib"}
DEFAULT_SECTION = {"bin": "1", "usr/bin": "1", "sbin": "8", "usr/sbin": "8", "libexec": "8", "lib": "3"}

# (top-level, purpose, [(leaf, purpose, [programs])]); a leaf may nest ("storage/disks").
# A program is a bare name (looked up in the top-level's source directory) or a path under
# src for the trees that are not programs (etc/rc, gnu/usr.bin/clang, include, share).
LAYOUT = [
    ("bin", "What must work with only the root partition mounted, linked static: a shell and the means to move files. OpenBSD's bin/ (30).", [
        ("shells", "The shells.", ["ksh", "csh"]),
        ("files", "The basic file operations.", [
            "ls", "cp", "mv", "rm", "ln", "mkdir", "rmdir", "chmod", "cat", "dd", "df", "pwd", "pax", "ed"]),
        ("processes", "Listing, signalling and pacing processes; the shell's primitives.", [
            "ps", "kill", "sleep", "sync", "test", "echo", "expr", "date"]),
        ("system", "The machine's name, the terminal line, a checksum.", ["hostname", "domainname", "stty", "md5"]),
        ("tapes", "Tape and changer control.", ["mt", "chio"]),
    ]),
    ("sbin", "What boots the system, repairs its disks and brings up its network, with only the root partition mounted. OpenBSD's sbin/ (66).", [
        ("boot", "Process 1, going down, the console and the terminals.", [
            "init", "reboot", "shutdown", "nologin", "ttyflags", "kbd", "wsconsctl", "ldattach"]),
        ("storage/disks", "Partitions, labels, device nodes and controllers.", [
            "disklabel", "fdisk", "pdisk", "mknod", "vnconfig", "scsi", "atactl", "bioctl", "badsect", "clri"]),
        ("storage/filesystems", "Making, checking and tuning file systems.", [
            "fsck", "fsck_ffs", "fsck_ext2fs", "fsck_msdos", "fsdb", "fsirand", "newfs", "newfs_ext2fs",
            "newfs_msdos", "growfs", "tunefs", "dumpfs", "scan_ffs", "ncheck_ffs"]),
        ("storage/mounts", "Mounting, and serving file systems over NFS.", [
            "mount", "umount", "mount_ffs", "mount_ext2fs", "mount_msdos", "mount_cd9660", "mount_nfs",
            "mount_ntfs", "mount_tmpfs", "mount_udf", "mount_vnd", "mountd", "nfsd"]),
        ("storage/swap-backup", "Swap, dumps, restores and quotas.", [
            "swapctl", "swapon", "dump", "restore", "savecore", "quotacheck"]),
        ("network", "Interfaces, routes, the packet filter, address configuration and name resolution.", [
            "ifconfig", "route", "ping", "pfctl", "pflogd", "dhcpleased", "dhcp6leased", "slaacd", "resolvd", "unwind"]),
        ("ipsec", "IPsec and its key daemons.", ["iked", "isakmpd", "ipsecctl"]),
        ("kernel", "Reading and setting the kernel's state.", ["sysctl", "dmesg"]),
    ]),
    ("usr/bin", "The commands a user runs once /usr is mounted. OpenBSD's usr.bin/ (209).", [
        ("text", "Filters and transformers of text streams.", [
            "awk", "sed", "grep", "diff", "diff3", "sdiff", "cmp", "comm", "sort", "uniq", "join", "cut",
            "paste", "tr", "wc", "head", "tail", "fold", "fmt", "pr", "col", "colrm", "column", "expand",
            "unexpand", "nl", "rev", "rs", "lam", "csplit", "split", "look", "spell", "ul", "deroff", "vis",
            "unvis", "uuencode", "uudecode", "hexdump"]),
        ("editors", "Editors and the pager.", ["vi", "mg", "less"]),
        ("file-tools", "Finding, describing and installing files (the basic operations are bin/files).", [
            "find", "xargs", "file", "stat", "du", "touch", "mktemp", "readlink", "realpath", "basename",
            "dirname", "locate", "which", "what", "lndir", "xinstall", "compress", "shar"]),
        ("process-tools", "Running things under a changed environment, priority or limit; the shell's helpers (the primitives are bin/processes).", [
            "env", "nice", "nohup", "renice", "time", "timeout", "pkill", "top", "fstat", "true", "false",
            "yes", "seq", "jot", "printf", "printenv", "getopt", "getconf", "tee", "tty", "tsort", "apply"]),
        ("users", "Logging in, identities, who is on the machine, talking to them.", [
            "login", "passwd", "su", "doas", "id", "who", "w", "users", "last", "lastcomm", "finger",
            "chpass", "lock", "mesg", "wall", "write", "talk", "encrypt", "skey", "skeyinit", "skeyinfo",
            "skeyaudit", "x99token", "logname", "getent"]),
        ("network-clients", "Network clients a user runs.", [
            "ssh", "nc", "ftp", "tftp", "telnet", "dig", "whois", "netstat", "tcpbench", "rsync", "rdist",
            "rdistd", "rup", "rusers", "rwall", "rpcinfo", "showmount", "nfsstat", "snmp", "ldap", "cu", "bgplg"]),
        ("development", "Build tools, source generators, version control and tracing.", [
            "make", "yacc", "lex", "m4", "patch", "ctags", "indent", "mkdep", "lorder", "nm", "gprof",
            "libtool", "pkgconf", "rcs", "unifdef", "ctfconv", "ctfdump", "cap_mkdb", "getcap", "gencat",
            "mklocale", "rpcgen", "cvs", "fgen", "ktrace", "kdump"]),
        ("docs", "Manual pages and terminal descriptions.", ["mandoc", "tic", "infocmp", "tput", "tset"]),
        ("calc", "Calculators and calendars.", ["bc", "dc", "units", "cal", "calendar"]),
        ("mail", "Reading and sending mail from the command line.", ["mail", "biff", "from", "vacation"]),
        ("scheduling", "Running things later.", ["crontab", "at", "leave"]),
        ("media", "Audio, MIDI, radio and CD.", [
            "aucat", "audioctl", "mixerctl", "midicat", "sndioctl", "sndiod", "radioctl", "cdio"]),
        ("system-info", "What machine this is, how it is doing, and small system chores.", [
            "uname", "arch", "pagesize", "locale", "vmstat", "systat", "ipcs", "ipcrm", "pctr", "kstat",
            "quota", "logger", "newsyslog", "usbhidaction", "usbhidctl", "script", "watch"]),
        ("crypto", "Certificates, signatures and keys from the command line.", ["openssl", "signify", "htpasswd", "keynote"]),
        ("yp-clients", "Querying the YP/NIS directory (its servers are usr/sbin/yp).", ["ypcat", "ypmatch", "ypwhich"]),
        ("misc", "What fits nowhere else.", ["banner", "tmux", "ts", "sendbug"]),
    ]),
    ("usr/sbin", "Daemons and administration once the system is whole. OpenBSD's usr.sbin/ (151).", [
        ("base-daemons", "What rc starts on every system, and rc's control program.", [
            "rcctl", "inetd", "cron", "syslogd", "syslogc", "watchdogd", "hotplugd", "sensorsd", "apmd", "apm"]),
        ("accounts", "Creating users and groups, the databases built from them, accounting, tokens (what a user does with their own identity is usr/bin/users).", [
            "adduser", "user", "vipw", "chroot", "pwd_mkdb", "dev_mkdb", "kvm_mkdb", "netgroup_mkdb",
            "ac", "accton", "sa", "tokenadm", "tokeninit"]),
        ("storage-admin", "Boot blocks, images, quotas, iSCSI, media (the root-partition tools are sbin/storage).", [
            "installboot", "makefs", "mtree", "quot", "edquota", "quotaon", "repquota", "rmt", "iscsid",
            "iscsictl", "rdsetroot", "fdformat"]),
        ("network/admin", "Neighbours, traces, captures, link state (the root-partition tools are sbin/network).", [
            "arp", "ndp", "rarpd", "traceroute", "tcpdump", "tcpdrop", "trpt", "lldp", "lldpd", "ifstated", "bpflogd"]),
        ("network/dhcp", "DHCP, DHCPv6 and router advertisements: the servers and the lease controls.", [
            "dhcpd", "dhcrelay", "dhcrelay6", "dhcpleasectl", "dhcp6leasectl", "rad", "slaacctl"]),
        ("network/routing", "Routing daemons and their control programs.", [
            "bgpd", "bgpctl", "bgplgd", "ospfd", "ospfctl", "ospf6d", "ospf6ctl", "ripd", "ripctl", "ldpd",
            "ldpctl", "eigrpd", "eigrpctl", "dvmrpd", "dvmrpctl", "rtrd", "rtrctl", "route6d", "mrouted",
            "mrinfo", "mtrace", "map-mbone", "rpki-client"]),
        ("hardware", "Buses, firmware, GPIO and the guest-host channel.", [
            "pcidump", "usbdevs", "memconfig", "eeprom", "gpioctl", "ractl", "hostctl"]),
        ("stats", "Kernel and I/O statistics.", ["procmap", "pstat", "iostat", "kgmon"]),
        ("services", "Servers: web, mail, time, DNS, LDAP, SNMP, domains.", [
            "httpd", "slowcgi", "smtpd", "mailwrapper", "spamdb", "ftp-proxy", "tftpd", "tftp-proxy", "relayd",
            "relayctl", "identd", "ntpd", "rdate", "zdump", "zic", "unbound", "nsd", "unwindctl", "ldapd",
            "ldapctl", "ldomd", "ldomctl", "snmpd"]),
        ("yp", "The YP/NIS servers (the clients are usr/bin/yp-clients).", ["ypserv", "ypbind", "ypldap", "yppoll", "ypset"]),
        ("auth", "RADIUS, authpf, wireless authentication and certificate renewal.", [
            "radiusd", "radiusctl", "authpf", "hostapd", "acme-client", "ocspcheck"]),
        ("vpn", "IKE control, PPP and L2TP (the IPsec daemons are sbin/ipsec).", [
            "ikectl", "npppd", "npppctl", "pppd", "sasyncd"]),
        ("nfs-rpc", "The RPC services and network boot.", [
            "portmap", "rpc.bootparamd", "rpc.lockd", "rpc.statd", "amd", "mopd", "rbootd"]),
        ("printing", "Printing.", ["lpd", "lpr"]),
        ("virtualization", "vmm(4)'s daemon and control program.", ["vmd", "vmctl"]),
        ("packages", "Packages, firmware, patches and upgrades.", [
            "pkg_add", "fw_update", "syspatch", "sysupgrade", "sysmerge"]),
        ("kernel-dev", "Configuring, tracing and packaging kernels (the running kernel's state is sbin/kernel).", [
            "config", "crunchgen", "btrace", "acpidump", "mksuncd", "mkuboot"]),
        ("wscons", "Console screens, fonts and the console mouse.", ["wsconscfg", "wsfontload", "wsmoused"]),
    ]),
    ("libexec", "Programs run by other programs, never by a user. OpenBSD's libexec/ (28).", [
        ("login", "The authentication back ends login(1) calls.", [
            "login_passwd", "login_chpass", "login_lchpass", "login_ldap", "login_radius", "login_reject",
            "login_skey", "login_token", "login_yubikey"]),
        ("rtld", "The run-time linker.", ["ld.so"]),
        ("network-daemons", "Daemons inetd and the RPC services start.", [
            "ftpd", "fingerd", "talkd", "comsat", "rpc.rquotad", "rpc.rstatd", "rpc.rusersd", "rpc.rwalld", "snmpd"]),
        ("mail", "Local delivery and the spam daemon.", ["mail.local", "lockspool", "spamd", "spamd-setup", "spamlogd"]),
        ("system", "The login prompt, the nightly security check, the kernel relinker, the traditional cpp.", [
            "getty", "security", "reorder_kernel", "tradcpp"]),
    ]),
    ("lib", "The libraries every program links. While the kernel keeps OpenBSD's ABI, libc speaks OpenBSD's system calls: this is the layer closest to OpenBSD by necessity, and with libexec/rtld the only place `unsafe` is allowed. OpenBSD's lib/ (35).", [
        ("libc", "The C library, its start-up files, threads and libm.", [
            "libc", "csu", "librthread", "libpthread", "libm", "check_sym"]),
        ("crypto", "Cryptography and authentication.", [
            "libcrypto", "libssl", "libtls", "libfido2", "libcbor", "libskey", "libkeynote", "libradius"]),
        ("terminal", "Terminal handling and line editing.", ["libcurses", "libedit", "libform", "libmenu", "libpanel"]),
        ("system", "The rest.", [
            "libutil", "libkvm", "libevent", "libz", "libexpat", "libelf", "libfuse", "libpcap", "libusbhid",
            "libossaudio", "libsndio", "libagentx", "librpcsvc", "libarch", "libl", "liby"]),
    ]),
    ("include", "The headers installed under /usr/include. OpenBSD's include/.", [
        ("headers", "The exported headers.", ["include"]),
    ]),
    ("compiler", "The LLVM toolchain: clang, lld, libc++ and compiler-rt, Apache-2.0 with the LLVM exception, nothing GPL (the user's decision of 2026-10-23). OpenBSD keeps it under the historical name gnu/; the sources are a pinned dependency, not written here: this tree holds the pin and the build glue, as OpenBSD's gnu/usr.bin/clang does.", [
        ("llvm", "The pinned LLVM release and how it is built for the system.", [
            "gnu/usr.bin/clang", "gnu/lib/libcxx", "gnu/lib/libcxxabi", "gnu/lib/libclang_rt", "gnu/lib/libcompiler_rt"]),
    ]),
    ("etc", "The configuration the system is born with. OpenBSD's etc/.", [
        ("rc", "The start-up scripts and the terminal table.", [
            "etc/rc", "etc/rc.conf", "etc/rc.d", "etc/netstart", "etc/daily", "etc/weekly", "etc/monthly",
            "etc/changelist", "etc/gettytab", "etc/ttys.pty"]),
        ("base", "Users, groups, services, device nodes, skeletons, examples and the default configuration files.", [
            "etc/master.passwd", "etc/group", "etc/shells", "etc/services", "etc/protocols", "etc/rpc",
            "etc/MAKEDEV.mi", "etc/MAKEDEV.common", "etc/MAKEDEV.sub", "etc/MAKEDEV.man", "etc/MAKEDEV.mansub",
            "etc/mtree", "etc/moduli", "etc/skel", "etc/examples", "etc/mail", "etc/motd", "etc/ksh.kshrc",
            "etc/locate.rc", "etc/newsyslog.conf", "etc/syslog.conf", "etc/pf.conf", "etc/pf.os",
            "etc/ntpd.conf", "etc/nsd.conf", "etc/unbound.conf", "etc/ftpusers", "etc/fbtab.head",
            "etc/fbtab.tail", "etc/signify", "etc/rpki", "etc/minfree", "etc/root", "etc/crontab",
            "etc/mailer.conf", "etc/ppp", "etc/amd", "etc/etc.<arch>"]),
    ]),
    ("share", "Data for everyone: zoneinfo, locale, dictionaries, terminal types, the shared manuals. OpenBSD's share/.", [
        ("data", "What share/ holds that belongs to no program.", ["share"]),
    ]),
    ("distrib", "How a release is made. OpenBSD's distrib/.", [
        ("sets", "The install sets and their lists.", ["distrib/sets", "distrib/notes", "distrib/syspatch"]),
        ("installer", "The installer, its ramdisk and the per-architecture media.", [
            "distrib/miniroot", "distrib/special", "distrib/<arch>"]),
    ]),
]

TOPLEVEL_README = """# EmiBSD Userland

The monorepo of EmiBSD's own userland: the programs, libraries and configuration that run
above the [Kernel](https://github.com/EmiBSD/Kernel). Phase 3 of the project: until the
kernel's redesign closes at N9, EmiBSD runs OpenBSD's base system unmodified; this repository
is where the system that replaces it is written.

## Rules (the user's decisions of 2026-10-23)

- **Written from scratch, under a definition.** Nothing here is a port or a translation of
  OpenBSD's programs. Each program is specified first (what it does, its inputs, outputs,
  exit codes, what the rest of the system expects of it), then designed, then written.
  OpenBSD's program and its manual are the reference for behaviour, read, not copied.
- **Rust.** Everything written here is Rust; C only where the ABI demands it, assembly only
  in the syscall stubs of libc. `#![forbid(unsafe_code)]` in every program; `unsafe` only in
  `lib/libc` and `libexec/rtld`, each site with a written proof, as the kernel's `hal`.
- **LLVM, nothing GPL.** The toolchain is clang and lld (`compiler/`).
- **`just`.** Every program carries a `justfile` that imports `tools/program.just`; the root
  `justfile` runs over all of them. `cargo` builds; `just` is the recipes. Not make: the
  build is Cargo's, and BSD make is itself one of the programs to write
  (`usr/bin/development/make`).
- **One contract per program**: `docs/PROGRAM.md`. Every program directory holds `STATUS`,
  `DEFINITION.md`, `DESIGN.md`, `DELIVERY.md`, `schemas/`, `src/`, `tests/`, `man/` and a
  `justfile`; `just status` counts the STATUS files.

## Layout

OpenBSD's own split at the top: `bin/` and `sbin/` are what works with only the root
partition mounted (linked static), `usr/bin/` and `usr/sbin/` the rest; `bin` and `usr/bin`
are for the user, `sbin` and `usr/sbin` for operating the system. Inside each, the programs
are grouped by what they do. A concept that OpenBSD spreads over two trees keeps a distinct
name in each (`bin/files` and `usr/bin/file-tools`, `sbin/network` and `usr/sbin/network/`),
and the README of each says where its other half is. Every program is listed once, in the
tree OpenBSD keeps it in; `tools/layout.py` regenerates the READMEs and the skeletons from
the map and refuses to write when one is missing or doubled.

```
{tree}```

The lists are the map to what OpenBSD's base system provides at the pin of
`Kernel/reference/PINNED.md`, not a porting list: the programs written here are EmiBSD's own.

## Open

- **The Rust target.** `aarch64-unknown-openbsd` and `x86_64-unknown-openbsd` are tier 3 in
  Rust: no prebuilt `std`, and building it needs nightly's `-Zbuild-std`, which the no-nightly
  rule excludes. The options (a custom target over our own libc with `no_std` + `alloc`,
  `std` built once by a pinned script, rustc bootstrapped on EmiBSD itself) are decided with
  the first slice, `lib/libc`.
- `include/` and `share/` are generated from the libraries and the programs; `etc/` shrinks
  to what the system needs before any program exists; `regress/` holds the integration
  battery. Pending the user's word.

New code is ISC (`LICENSE`).
"""

PROGRAM_DOC = """# The contract of a program

Every program and library directory of this repository (`bin/`, `sbin/`, `usr/bin/`,
`usr/sbin/`, `libexec/`, `lib/`) is one solution, laid out the same way. `tools/layout.py`
creates the skeleton; the people and agents who work on the program fill it, in this order.

```
<group>/<name>/
├── STATUS            one word: planned | defined | designed | implemented | shipped
├── DEFINITION.md     the functional design: what it does, scope, constraints, inputs,
│                     parameters, outputs, exit codes, signals, compatibility
├── DESIGN.md         the architecture: mermaid diagrams, security (pledge, unveil,
│                     privileges), decisions with their reasons, dependencies
├── schemas/          the machine-readable contracts: output.v1.json, config.v1.json
│                     (what `-o json` / `-o yaml` emit; versioned, kubectl's apiVersion)
├── src/              the Rust sources, a Cargo package; unit tests beside the code
├── tests/            integration tests, property tests for every parser, and golden/,
│                     the differential tests: the same input to ours and to OpenBSD's
├── man/<name>.<n>    the manual, mdoc(7) source; HTML and Markdown are rendered from it
├── etc/              the default configuration installed under /etc, when it has one
├── DELIVERY.md       the install set, path, static or dynamic, owner and mode, MAKEDEV
└── justfile          `import` of tools/program.just: build, test, lint, man, status
```

## The order

1. **planned**: the skeleton exists. `DEFINITION.md` names the OpenBSD program and manual
   that are the reference for behaviour.
2. **defined**: `DEFINITION.md` is complete. Its *Compatibility* section is the one that
   matters most: what the rest of the base system expects of this program (the flags `rc`
   calls it with, the output another program parses, the exit codes a script branches on).
   The base system is an ecosystem; a program that works but breaks `netstart` is a failure.
3. **designed**: `DESIGN.md` and `schemas/` are complete; the security section says which
   `pledge(2)` promises and `unveil(2)` paths the program lives under, and whether it
   separates privileges or runs setuid. Nothing OpenBSD's program restricts may be relaxed.
4. **implemented**: `src/` builds, the unit, integration, property and differential tests
   pass, `man/` is complete with EXAMPLES. The package joined the workspace `Cargo.toml`.
5. **shipped**: `DELIVERY.md` is complete and `distrib/` installs it.

## Rules

- Written from scratch under the definition; OpenBSD's code is read for behaviour, never
  copied or translated (the user's decision of 2026-10-23).
- Rust; `#![forbid(unsafe_code)]` at the crate root. `unsafe` only in `lib/libc` and
  `libexec/rtld`, each site with a `// SAFETY:` proof.
- A new dependency needs the user's OK and a row in the allowlist (to be written with the
  first program).
- The manual's source is mdoc(7), the format of the system; `mandoc -T markdown` and
  `-T html` render it for the site. EXAMPLES is not optional.
- Every file starts with the author's ISC block (`LICENSE`).
- `just status` at the root counts the STATUS files; that count is the progress of the
  userland, as `cargo xtask lz status` is the kernel's.
"""

PROGRAM_JUST = """# Shared recipes for every program and library; each one's justfile imports this file.
# The program's name is its directory's name.

name := file_name(justfile_directory())

# Build the package (once src/Cargo.toml exists).
build:
    cargo build --manifest-path src/Cargo.toml

# Unit and integration tests.
test:
    cargo test --manifest-path src/Cargo.toml

# Format check and clippy with warnings denied.
lint:
    cargo fmt --manifest-path src/Cargo.toml -- --check
    cargo clippy --manifest-path src/Cargo.toml -- -D warnings

# Render the manual to the terminal.
man:
    mandoc -T utf8 man/{{name}}.* | less -R

# This program's STATUS line.
status:
    @printf '%s\\t%s\\n' "$(cat STATUS)" "{{name}}"
"""

ROOT_JUST = """# EmiBSD Userland: the recipes over the whole monorepo. Each program has its own justfile
# importing tools/program.just; these run across all of them.

# Progress: how many programs sit at each STATUS.
status:
    @find bin sbin usr libexec lib -name STATUS | xargs cat | sort | uniq -c | sort -rn

# Every program at a given status: `just at implemented`.
at s:
    @find bin sbin usr libexec lib -name STATUS | while read f; do [ "$(cat "$f")" = "{{s}}" ] && dirname "$f"; done | sort

# Regenerate the READMEs and the missing skeletons from the map (needs Kernel's reference tree).
layout src="../Kernel/reference/openbsd-src":
    python3 -I tools/layout.py {{src}} .

# Format, clippy and tests over the workspace (the packages that joined Cargo.toml).
check:
    cargo fmt --all -- --check
    cargo clippy --workspace -- -D warnings
    cargo test --workspace
"""

ROOT_CARGO = """# The workspace. A program's package (src/Cargo.toml) is added to `members` when its STATUS
# reaches `implemented`; until then the skeletons are not built.
[workspace]
resolver = "3"
members = []

[workspace.package]
edition = "2024"
license = "ISC"
authors = ["Emilio Navarrete Lineros <enavarre@outlook.com>"]
"""

TOOLCHAIN = """# Stable, pinned, the same channel as Kernel. Bumping is its own commit.
# No targets yet: the OpenBSD targets are tier 3 (README, Open).
[toolchain]
channel = "1.98.1"
profile = "minimal"
components = ["rustfmt", "clippy", "rust-src"]
"""

DEFINITION = """# {name}

STATUS: see `STATUS`. Reference for behaviour: OpenBSD's `{origin}`, manual {name}({section}).
Written from scratch under this definition; not a port (the user's decision of 2026-10-23).

## What it does

## Scope

What is in, what is out, and why.

## Constraints

Root partition only (static) or not; privileges; what it may never do.

## Inputs

Arguments, standard input, environment variables, files it reads, configuration.

## Parameters

| Flag | Argument | Meaning | Default |
|---|---|---|---|

## Outputs

Human output; `-o json` / `-o yaml` (`schemas/output.v1.json`); what goes to stderr.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success |

## Signals and failure behaviour

SIGHUP, SIGTERM, SIGINT; disk full, permission denied, interrupted.

## Compatibility

What the rest of the base system expects of this program: who calls it (rc, other
programs, the installer), with which flags, which output they parse, which exit codes they
branch on. Nothing here changes without checking every caller.

## Open questions
"""

DESIGN = """# {name}: design

## Architecture

```mermaid
flowchart LR
    A[input] --> B[{name}] --> C[output]
```

## Security

`pledge(2)` promises, `unveil(2)` paths, privilege separation, setuid. Never less than
OpenBSD's {name}({section}) restricts.

## Data

The schemas in `schemas/`; their versions; who consumes them.

## Decisions

Numbered, each with its reason and what was rejected.

## Dependencies

Crates used, each with why; the allowlist governs.
"""

DELIVERY = """# {name}: delivery

| | |
|---|---|
| Install set | |
| Install path | |
| Linking | static / dynamic |
| Owner and mode | |
| MAKEDEV | none / the node |
| Manual | man/{name}.{section} |
| Default configuration | none / etc/ |
"""

MAN = """.\\" {name}({section}): written from scratch; OpenBSD's {name}({section}) is the behavioural reference.
.Dd $Mdocdate$
.Dt {NAME} {section}
.Os
.Sh NAME
.Nm {name}
.Nd
.Sh SYNOPSIS
.Nm
.Sh DESCRIPTION
.Sh EXIT STATUS
.Sh EXAMPLES
.Sh SEE ALSO
.Sh STANDARDS
.Sh HISTORY
"""


def listing(d: str) -> set:
    return {n for n in os.listdir(SRC / d)
            if not n.lower().startswith("makefile") and n != "CVS"
            and not n.endswith(".inc") and not n.endswith(".mk")}


def man_section(top: str, src_dir: str, name: str) -> str:
    """The section of OpenBSD's manual for this program: <name>.<n> in its directory (one
    level of subdirectories too), else the tree's default."""
    base = SRC / src_dir / name
    candidates = []
    for root, _, files in os.walk(base):
        depth = Path(root).relative_to(base).parts
        if len(depth) > 1:
            continue
        for f in files:
            stem, _, ext = f.rpartition(".")
            if stem == name and ext.isdigit():
                candidates.append(ext)
    # The program's own page, not its file format (5) or device (4) page: disklabel has
    # disklabel.5 and .8, arp has arp.4 and .8.
    default = DEFAULT_SECTION[top]
    if default in candidates:
        return default
    commands = [c for c in candidates if c in ("1", "8", "6", "3")]
    return min(commands) if commands else (min(candidates) if candidates else default)


def write_if_missing(path: Path, text: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return True


def skeleton(top: str, leaf: str, name: str, src_dir: str) -> int:
    d = OUT / top / leaf / name
    section = man_section(top, src_dir, name)
    origin = f"{src_dir}/{name}"
    rel = os.path.relpath(OUT / "tools" / "program.just", d)
    n = 0
    n += write_if_missing(d / "STATUS", "planned\n")
    n += write_if_missing(d / "DEFINITION.md", DEFINITION.format(name=name, origin=origin, section=section))
    n += write_if_missing(d / "DESIGN.md", DESIGN.format(name=name, section=section))
    n += write_if_missing(d / "DELIVERY.md", DELIVERY.format(name=name, section=section))
    n += write_if_missing(d / "justfile", f"import '{rel}'\n")
    n += write_if_missing(d / "man" / f"{name}.{section}", MAN.format(name=name, NAME=name.upper(), section=section))
    for sub in ("schemas", "src", "tests"):
        n += write_if_missing(d / sub / ".gitkeep", "")
    return n


def main() -> int:
    sources = {d: listing(d) for d in set(SOURCE_DIR.values())}
    seen, dup, unknown, misplaced = {}, [], [], []
    covered = {d: set() for d in sources}
    for top, _, leaves in LAYOUT:
        src = SOURCE_DIR.get(top)
        for leaf, _, progs in leaves:
            for p in progs:
                where = f"{top}/{leaf}"
                key = p if "/" in p else f"{src}/{p}"
                if key in seen:
                    dup.append((p, seen[key], where))
                seen[key] = where
                if "/" in p:
                    if not (SRC / p.replace("<arch>", "amd64")).exists():
                        unknown.append(p)
                    continue
                if src is None:
                    if not (SRC / p).is_dir():   # a whole tree: include, share
                        unknown.append(p)
                elif p not in sources[src]:
                    hits = [d for d, s in sources.items() if p in s]
                    (misplaced if hits else unknown).append((p, where, hits))
                else:
                    covered[src].add(p)
    missing = {d: sorted(sources[d] - covered[d]) for d in sources if sources[d] - covered[d]}
    if dup or unknown or misplaced or missing:
        print("duplicates:", dup)
        print("unknown:", unknown)
        print("misplaced (name not in that tree in OpenBSD):", misplaced)
        print("missing:", missing)
        return 1

    tree, created, programs = [], 0, 0
    for top, purpose, leaves in LAYOUT:
        tree.append(f"{top}/")
        (OUT / top).mkdir(parents=True, exist_ok=True)
        top_md = [f"# {top}", "", purpose, "", "| Directory | What |", "|---|---|"]
        src = SOURCE_DIR.get(top)
        for i, (leaf, what, progs) in enumerate(leaves):
            last = i == len(leaves) - 1
            tree.append(f"{'└── ' if last else '├── '}{leaf:<20} {what}")
            top_md.append(f"| `{leaf}/` | {what} |")
            d = OUT / top / leaf
            d.mkdir(parents=True, exist_ok=True)
            lines = [f"# {top}/{leaf}", "", what, "",
                     "Covers, from OpenBSD's base system at the pin (its path in OpenBSD's `src`):", ""]
            for p in progs:
                origin = p if "/" in p or src is None else f"{src}/{p}"
                name = origin.rsplit("/", 1)[-1]
                if src is not None:
                    lines.append(f"- [`{name}`]({name}/) ({origin})")
                    created += skeleton(top, leaf, name, src)
                    programs += 1
                else:
                    lines.append(f"- `{name}` ({origin})")
            if src is not None:
                lines += ["", "Each entry is a program directory laid out as `docs/PROGRAM.md` says."]
            else:
                lines += ["", "Nothing written yet."]
            (d / "README.md").write_text("\n".join(lines) + "\n")
        top_md += ["", "Each entry is a group; each group's README lists its programs." if src else "Nothing written yet."]
        (OUT / top / "README.md").write_text("\n".join(top_md) + "\n")
    (OUT / "README.md").write_text(TOPLEVEL_README.format(tree="\n".join(tree) + "\n"))
    (OUT / "docs").mkdir(exist_ok=True)
    (OUT / "docs" / "PROGRAM.md").write_text(PROGRAM_DOC)
    (OUT / "tools" / "program.just").write_text(PROGRAM_JUST)
    write_if_missing(OUT / "justfile", ROOT_JUST)
    write_if_missing(OUT / "Cargo.toml", ROOT_CARGO)
    write_if_missing(OUT / "rust-toolchain.toml", TOOLCHAIN)
    total = sum(len(progs) for _, _, leaves in LAYOUT for _, _, progs in leaves)
    print(f"ok: {len(LAYOUT)} trees, {sum(len(l) for _, _, l in LAYOUT)} leaves, {total} entries, "
          f"{programs} program skeletons ({created} files created this run);",
          {d: len(s) for d, s in sorted(sources.items())})
    return 0


if __name__ == "__main__":
    sys.exit(main())
