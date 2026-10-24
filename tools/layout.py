#!/usr/bin/env python3
"""Generate the Userland monorepo's layout: the trees, one README.md per directory, and the
skeleton of every program and library (docs/PROGRAM.md is the contract).

usage: layout.py <openbsd-src root> <Userland root>

The top level is the BSD split by install path (bin, sbin, usr/bin, usr/sbin, libexec,
lib, include, compiler, etc, share, distrib); inside each, the programs are grouped by what
they do. Every program name of the reference tree's bin/, sbin/, usr.bin/, usr.sbin/, libexec/
and lib/ is mapped to exactly one leaf, in the tree it lives in there; the script refuses to write
otherwise.

Two classes of program (docs/PROGRAM.md): `written` (from scratch, in Rust, under its
definition) and `imported` (compiled from its upstream at the pin of UPSTREAM.toml, never
rewritten). A skeleton whose STATUS is still `planned` or `imported` is regenerated from the
templates; one that moved on is left alone.
"""
import os
import sys
from pathlib import Path

SRC = Path(sys.argv[1])
OUT = Path(sys.argv[2])
PIN_FILE = SRC.parent / "PINNED.md"          # Kernel/reference/PINNED.md: the reference tree's pin
OPENBSD_MIRROR = "https://github.com/EmiBSD/OpenBSD-src"
OPENBSD_ORIGIN = "https://github.com/openbsd/src"

# Where a top-level directory's bare names come from in the reference tree.
SOURCE_DIR = {"bin": "bin", "sbin": "sbin", "usr/bin": "usr.bin", "usr/sbin": "usr.sbin",
              "libexec": "libexec", "lib": "lib"}
DEFAULT_SECTION = {"bin": "1", "usr/bin": "1", "sbin": "8", "usr/sbin": "8", "libexec": "8", "lib": "3"}

# The imported programs (the user's decision of 2026-10-23): cryptography, security protocols
# with a living upstream, and the legacy giants. name -> NVD CPE (product) when known.
IMPORTED = {
    # cryptography: never our own
    "libcrypto": "openbsd:libressl", "libssl": "openbsd:libressl", "libtls": "openbsd:libressl",
    "libfido2": "yubico:libfido2", "libcbor": "pjk:libcbor",
    "openssl": "openbsd:libressl", "ocspcheck": "openbsd:openbsd", "acme-client": "openbsd:openbsd",
    # security and network protocols with a history
    "ssh": "openbsd:openssh", "unbound": "nlnetlabs:unbound", "nsd": "nlnetlabs:nsd",
    "iked": "openbsd:openbsd", "isakmpd": "openbsd:openbsd", "ipsecctl": "openbsd:openbsd",
    "ikectl": "openbsd:openbsd", "sasyncd": "openbsd:openbsd",
    "smtpd": "opensmtpd:opensmtpd", "httpd": "openbsd:openbsd", "relayd": "openbsd:openbsd",
    "relayctl": "openbsd:openbsd", "tcpdump": "tcpdump:tcpdump", "libpcap": "tcpdump:libpcap",
    "pflogd": "openbsd:openbsd", "dhcpd": "isc:dhcp", "dhcrelay": "isc:dhcp", "dhcrelay6": "isc:dhcp",
    "rpki-client": "openbsd:rpki-client", "ntpd": "openbsd:openntpd", "ldapd": "openbsd:openbsd",
    "radiusd": "openbsd:openbsd", "npppd": "openbsd:openbsd", "pppd": "openbsd:openbsd",
    "snmpd": "openbsd:openbsd", "dig": "isc:bind", "telnet": "openbsd:openbsd",
    # the legacy giants
    "vi": "nvi:nvi", "less": "gnu:less", "tmux": "tmux_project:tmux", "mandoc": "mandoc:mandoc",
    "awk": "onetrueawk:awk", "bc": "openbsd:openbsd", "dc": "openbsd:openbsd", "m4": "openbsd:openbsd",
    "yacc": "byacc:byacc", "lex": "flex_project:flex", "make": "openbsd:openbsd", "patch": "openbsd:openbsd",
    "diff": "openbsd:openbsd", "diff3": "openbsd:openbsd", "sdiff": "openbsd:openbsd",
    "rcs": "openbsd:openrcs", "cvs": "openbsd:opencvs",
    "libcurses": "gnu:ncurses", "libform": "gnu:ncurses", "libmenu": "gnu:ncurses", "libpanel": "gnu:ncurses",
    "tic": "gnu:ncurses", "infocmp": "gnu:ncurses", "tput": "gnu:ncurses", "tset": "gnu:ncurses",
    "libedit": "libedit:libedit", "file": "file_project:file", "zic": "iana:tzcode", "zdump": "iana:tzcode",
    "libz": "zlib:zlib", "libexpat": "libexpat_project:libexpat", "libevent": "libevent_project:libevent",
    "sndiod": "openbsd:openbsd", "libsndio": "openbsd:openbsd", "aucat": "openbsd:openbsd",
}

# Programs whose traditional implementation is not C: the note goes to DEFINITION.md's open questions.
PERL = {"pkg_add", "adduser", "libtool", "pkgconf", "security"}
SHELL = {"rcctl", "fw_update", "syspatch", "sysupgrade", "sysmerge"}

# Programs whose output is an on-disk format: a from-scratch bug corrupts a file system.
ON_DISK = {"fsck", "fsck_ffs", "fsck_ext2fs", "fsck_msdos", "fsdb", "fsirand", "newfs", "newfs_ext2fs",
           "newfs_msdos", "growfs", "tunefs", "dumpfs", "scan_ffs", "ncheck_ffs", "dump", "restore",
           "disklabel", "fdisk", "pdisk", "installboot", "makefs", "badsect", "clri"}

# (top-level, purpose, [(leaf, purpose, [programs])]); a leaf may nest ("storage/disks").
# A program is a bare name (looked up in the top-level's source directory) or a path under
# src for the trees that are not programs (etc/rc, include, share). The compiler tree's
# entries are imported toolchains with their own upstream (COMPILERS below).
LAYOUT = [
    ("bin", "What must work with only the root partition mounted, linked static: a shell and the means to move files (30).", [
        ("shells", "The shells.", ["ksh", "csh"]),
        ("files", "The basic file operations.", [
            "ls", "cp", "mv", "rm", "ln", "mkdir", "rmdir", "chmod", "cat", "dd", "df", "pwd", "pax", "ed"]),
        ("processes", "Listing, signalling and pacing processes; the shell's primitives.", [
            "ps", "kill", "sleep", "sync", "test", "echo", "expr", "date"]),
        ("system", "The machine's name, the terminal line, a checksum.", ["hostname", "domainname", "stty", "md5"]),
        ("tapes", "Tape and changer control.", ["mt", "chio"]),
    ]),
    ("sbin", "What boots the system, repairs its disks and brings up its network, with only the root partition mounted (66).", [
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
    ("usr/bin", "The commands a user runs once /usr is mounted (209).", [
        ("text", "Filters and transformers of text streams.", [
            "awk", "sed", "grep", "diff", "diff3", "sdiff", "cmp", "comm", "sort", "uniq", "join", "cut",
            "paste", "tr", "wc", "head", "tail", "fold", "fmt", "pr", "col", "colrm", "column", "expand",
            "unexpand", "nl", "rev", "rs", "lam", "csplit", "split", "look", "spell", "ul", "deroff", "vis",
            "unvis", "uuencode", "uudecode", "hexdump"]),
        ("records", "Querying the records the written programs emit (`-o json`); EmiBSD's own, no counterpart elsewhere.", ["own:jpath"]),
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
    ("usr/sbin", "Daemons and administration once the system is whole (151).", [
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
    ("libexec", "Programs run by other programs, never by a user (28).", [
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
    ("lib", "The libraries every program links. libc speaks the Kernel's system calls: this is the layer bound to the Kernel's ABI by necessity, and with libexec/rtld the only place `unsafe` is allowed (35).", [
        ("libc", "The C library, its start-up files, threads and libm.", [
            "libc", "csu", "librthread", "libpthread", "libm", "check_sym"]),
        ("crypto", "Cryptography and authentication.", [
            "libcrypto", "libssl", "libtls", "libfido2", "libcbor", "libskey", "libkeynote", "libradius"]),
        ("terminal", "Terminal handling and line editing.", ["libcurses", "libedit", "libform", "libmenu", "libpanel"]),
        ("system", "The rest.", [
            "libutil", "libkvm", "libevent", "libz", "libexpat", "libelf", "libfuse", "libpcap", "libusbhid",
            "libossaudio", "libsndio", "libagentx", "librpcsvc", "libarch", "libl", "liby"]),
        ("crates", "The Rust crates the written programs share, each born with its first user and laid out as a program (docs/PROGRAM.md): `cli`, the common grammar (one declaration per program with typed options, --help as text and as a record, usage and diagnostics, exit codes; records, -o, --sort-by, tables, JSON, YAML, columns); `sys`, the thin FFI over libc (passwd and group lookups, the terminal, local time, pledge, uid and umask, mkfifo and mknod, file flags, a link's times and mode), the one place beside lib/libc and libexec/rtld where `unsafe` is allowed, each site with its proof. EmiBSD's own; no counterpart elsewhere.", [
            "crate:cli", "crate:sys"]),
    ]),
    ("compiler", "The toolchains, both imported: LLVM as OpenBSD ships it (clang, lld, libc++, compiler-rt; Apache-2.0 with the LLVM exception, nothing GPL) and Rust (rustc, cargo, std; Apache-2.0 and MIT), so the system builds itself, as OpenBSD's comp set does. The user's decisions of 2026-10-23.", [
        ("llvm", "LLVM with OpenBSD's patches and build glue (gnu/llvm, gnu/usr.bin/clang), from the pinned tree.", ["compiler:llvm"]),
        ("rust", "rust-lang/rust at the pinned stable tag, built with x.py against compiler/llvm; its std for the `*-unknown-openbsd` targets (the Kernel's ABI) is how the tier 3 problem is solved without nightly.", ["compiler:rust"]),
    ]),
    ("etc", "What the system needs before any program exists: the users and groups it is born with, the device nodes, the protocol tables, the start-up scripts. A program's own default configuration (pf.conf, ntpd.conf, syslog.conf, sshd's moduli, ...) lives in that program's etc/ and is installed from there; this tree holds only what belongs to no program.", [
        ("rc", "The start-up scripts and the terminal table.", [
            "etc/rc", "etc/rc.conf", "etc/rc.d", "etc/netstart", "etc/daily", "etc/weekly", "etc/monthly",
            "etc/changelist", "etc/gettytab", "etc/ttys.pty"]),
        ("base", "Users, groups, shells, the protocol tables, device nodes, the file-system skeleton, root's dotfiles, the per-architecture files.", [
            "etc/master.passwd", "etc/group", "etc/shells", "etc/services", "etc/protocols", "etc/rpc",
            "etc/MAKEDEV.mi", "etc/MAKEDEV.common", "etc/MAKEDEV.sub", "etc/MAKEDEV.man", "etc/MAKEDEV.mansub",
            "etc/mtree", "etc/skel", "etc/root", "etc/motd", "etc/minfree", "etc/etc.<arch>"]),
    ]),
    ("data", "Data for everyone that no program owns, imported from its upstream like a program is (an UPSTREAM.toml per entry, to be written): the time zone database, locales, dictionaries, terminal types. A program's manual lives beside the program; `share/` as a tree is generated at install time, not kept.", [
        ("zoneinfo", "The IANA time zone database (tzdata; zic and zdump are usr/sbin/services).", ["share/zoneinfo"]),
        ("locale", "Locale definitions and character maps.", ["share/locale"]),
        ("dict", "The word lists spell(1) and look(1) read.", ["share/dict"]),
        ("termtypes", "The terminal descriptions, source of terminfo (tic is usr/bin/docs).", ["share/termtypes", "share/tabset"]),
        ("misc", "Small tables of share/misc: ascii, airport codes, units, the magic of file(1) is in file itself.", ["share/misc"]),
    ]),
    ("distrib", "How a release is made, and what else is generated at release time: the install sets, the installer and its ramdisk, /usr/include from the libraries' exported headers, /usr/share from every program's manual plus data/.", [
        ("sets", "The install sets and their lists; the release version is YEAR.MONTH (docs/PROGRAM.md, Versions).", ["distrib/sets", "distrib/notes", "distrib/syspatch"]),
        ("installer", "The installer, its ramdisk and the per-architecture media.", [
            "distrib/miniroot", "distrib/special", "distrib/<arch>"]),
        ("include", "The recipe that assembles /usr/include from what each library of lib/ exports; no header is kept here.", []),
        ("share", "The recipe that assembles /usr/share: every program's man/ rendered, data/, share/mk; no file is kept here.", ["share/mk", "share/man"]),
    ]),
    ("regress", "The integration battery: what no single program's tests can see. Boots EmiBSD in QEMU and runs scenarios across programs (login over the console, rc bringing up the network, an install from the ramdisk, ssh in, pf rules, a mail delivered), each also run on a reference system and compared, as the kernel's differential battery does.", [
        ("scenarios", "One directory per scenario: the steps, the expected lines, the comparison with a reference system.", []),
        ("harness", "Booting the images, driving the console, collecting and comparing.", []),
    ]),
]

# The compiler tree's imports: (name, upstream description for UPSTREAM.toml).
COMPILERS = {
    "llvm": dict(name="LLVM, as OpenBSD ships it", kind="git", repo=OPENBSD_MIRROR, origin=OPENBSD_ORIGIN,
                 path=["gnu/llvm", "gnu/usr.bin/clang", "gnu/lib/libcxx", "gnu/lib/libcxxabi",
                       "gnu/lib/libclang_rt", "gnu/lib/libcompiler_rt"],
                 commit="@PIN@", version="", license=["Apache-2.0 WITH LLVM-exception"], cpe="llvm:llvm",
                 note="OpenBSD's patches (RETGUARD, -fret-clean, the fixed X18, BTI and PAC defaults) and its BSD-make build glue come with the tree; Kernel's `just comp` builds it this way today. The longest build of the repository: built once, cached."),
    "rust": dict(name="Rust", kind="git", repo="https://github.com/EmiBSD/rust", origin="https://github.com/rust-lang/rust",
                 path=[], commit="18ed059b1465ce6195154de3250a668f1dd3b1fa", tag="1.98.1", version="1.98.1+emibsd.1",
                 license=["Apache-2.0", "MIT"], cpe="rust-lang:rust",
                 submodules=[
                     dict(path="src/llvm-project", repo="https://github.com/EmiBSD/llvm-project",
                          origin="https://github.com/rust-lang/llvm-project", commit="52ed14fcd56afc30f9cccd8ca8ce237c2eef7e04"),
                     dict(path="src/tools/cargo", repo="https://github.com/EmiBSD/cargo",
                          origin="https://github.com/rust-lang/cargo", commit="797e8a9bca276c1c9f9f738d2a20f484fa4eea9d"),
                 ],
                 note="Two LLVMs, decided 2026-10-23: rustc 1.98.1 requires LLVM >= 21 (src/bootstrap, check_llvm_version) and OpenBSD's gnu/llvm at the pin is 18.1.8, so rustc builds the LLVM of its src/llvm-project submodule (rust-lang's fork, mirrored) and compiler/llvm stays OpenBSD's for clang, lld and the C. Built with x.py, host first, then target aarch64-unknown-openbsd: the std for the tier 3 target is built as part of the toolchain, from a stable release's source, without nightly. Needs a stage0 rustc: rustup's on the host; on EmiBSD, the previous build. Other submodules (books, stdarch, backtrace) stay on rust-lang/ until one is needed."),
}

TOPLEVEL_README = """# EmiBSD Userland

The monorepo of EmiBSD's own userland: the programs, libraries and configuration that run
above the [Kernel](https://github.com/EmiBSD/Kernel). Phase 3 of the project: until the
kernel's redesign closes at N9, EmiBSD runs an inherited base system unmodified; this repository
is where the system that replaces it is written.

## Rules (the user's decisions of 2026-10-23)

- **Two classes of program** (`docs/PROGRAM.md`). *Written*: from scratch, under a
  definition, in Rust; nothing is a port or a translation of another system's program: the
  as the reference for behaviour. *Imported*: cryptography, the security and network
  protocols with a living upstream and a CVE history, and the legacy giants (`ssh`, LibreSSL,
  `unbound`, `smtpd`, `vi`, `tmux`, `mandoc`, ncurses, the compilers, ...) are compiled from
  their upstream at the pin of their `UPSTREAM.toml`, never rewritten; our patches are a
  numbered series, ideally empty. `just status` counts both.
- **Rust** for what is written; C only where the ABI demands it, assembly only in libc's
  syscall stubs. `#![forbid(unsafe_code)]` in every program; `unsafe` only in `lib/libc`,
  `libexec/rtld` and `lib/crates/sys` (the thin FFI the programs share), each site with a
  written proof, as the kernel's `hal`.
- **One grammar for every program** (`docs/PROGRAM.md`, "The common grammar"; the user's
  decision of 2026-10-24, taken with `ls`): a program is a query over records with a schema;
  `-o name|table|wide|json|yaml|custom-columns=...` picks the renderer, `--sort-by=.field`
  the order, `--no-headers` the table's header. POSIX's short flags keep their meaning, and
  to a pipe the output is POSIX's byte for byte; to a terminal the defaults are modern (ISO
  dates, human sizes, headers). BSD-only flags nobody remembers are not kept.
- **LLVM and Rust, nothing GPL.** `compiler/llvm` is LLVM as OpenBSD ships it, with its
  patches and build glue; `compiler/rust` is rust-lang/rust at the pinned stable tag, built
  against that LLVM, so the system builds itself (the `comp` set) and the `*-unknown-openbsd`
  targets, tier 3 in Rust, get their `std` from a stable release's source, not from nightly.
- **Upstreams are mirrored in the organisation** (`EmiBSD/OpenBSD-src`, `EmiBSD/rust`, ...),
  so an upstream that moves or disappears does not take the build with it. A tarball upstream
  gets a repository where each release is one commit. Fetched sources live under `upstream/`,
  gitignored and read-only; a build applies `patches/` to a copy under `target/`, never to
  `upstream/`. `tools/upstream.py` fetches, verifies (commit, SHA-256, signature) and pins.
- **`just`.** Every program carries a `justfile` that imports `tools/program.just`; the root
  `justfile` runs over all of them. `cargo` builds; `just` is the recipes. Not make: the build
  is Cargo's, and BSD make is itself one of the programs (imported).
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

The BSD split at the top: `bin/` and `sbin/` are what works with only the root
partition mounted (linked static), `usr/bin/` and `usr/sbin/` the rest; `bin` and `usr/bin`
are for the user, `sbin` and `usr/sbin` for operating the system. Inside each, the programs
are grouped by what they do. A concept the tradition spreads over two trees keeps a distinct
name in each (`bin/files` and `usr/bin/file-tools`, `sbin/network` and `usr/sbin/network/`),
and the README of each says where its other half is. Every program is listed once, in the
tree the tradition keeps it in; `tools/layout.py` regenerates the READMEs and the skeletons from
the map and refuses to write when one is missing or doubled.

```
{tree}```

The lists are the map to what a complete base system provides, taken from the names at the pin of
`Kernel/reference/PINNED.md`, not a porting list: the written programs are EmiBSD's own.

## Open

- **Perl.** `pkg_add`, `adduser`, `libtool`, `pkgconf` and `security` are traditionally Perl, and
  Perl (Artistic or GPL, dual) is not in the tree: import it under the Artistic licence, or
  write those five in Rust. The user's decision; their skeletons say so.
- `cargo audit` and `cargo deny` (`just audit`, part of `just check` when installed) are
  tools installed outside the repository with `cargo install`; `tools/cve.py` (`just cve
  <dir>`) queries NVD over the network. Both written, neither run: pending the user's OK.
- `data/` entries are imports like the programs (tzdata, the locales): their `UPSTREAM.toml`
  files are to be written.

New code is ISC (`LICENSE`).
"""

PROGRAM_DOC = """# The contract of a program

Every program and library directory of this repository (`bin/`, `sbin/`, `usr/bin/`,
`usr/sbin/`, `libexec/`, `lib/`, `compiler/`) is one solution, laid out the same way.
`tools/layout.py` creates the skeleton; the people and agents who work on the program fill
it. There are two classes, told apart by the first word of `STATUS`.

## Written (from scratch, in Rust)

```
<group>/<name>/
├── STATUS            planned | defined | designed | implemented | shipped
├── DEFINITION.md     the functional design: what it does, scope, constraints, inputs,
│                     parameters, outputs, exit codes, signals, compatibility, the
│                     performance budget, the security history (CVEs of the reference)
├── DESIGN.md         the architecture: mermaid diagrams, concurrency model, threat model,
│                     security (pledge, unveil, privileges), decisions, dependencies
├── schemas/          the machine-readable contracts: output.v1.json, config.v1.json
│                     (what `-o json` / `-o yaml` emit; versioned, kubectl's apiVersion)
├── src/              the Rust sources, a Cargo package; unit tests beside the code
├── tests/            integration tests; property tests for every parser; stress/ on four
│                     CPUs for what serves many; cve/ one test per entry of the security
│                     history; golden/ the differential tests against a reference system
├── bench/            host benchmarks (harness = false) against a reference system's program on the
│                     same input; `just bench` prints the ratio
├── man/<name>.<n>    the manual, mdoc(7) source; HTML and Markdown are rendered from it
├── etc/              the default configuration installed under /etc, when it has one
├── DELIVERY.md       the install set, path, static or dynamic, owner and mode, MAKEDEV
└── justfile          `import` of tools/program.just
```

The order: **planned** (the skeleton; DEFINITION names the standard that defines the program), **defined**
(DEFINITION complete; *Compatibility* is the section that matters most: what the rest of the
base system expects, the flags `rc` uses, the output another program parses, the exit codes
a script branches on), **designed** (DESIGN and schemas complete; the pledge and unveil
profile is the least the program needs), **implemented** (builds; unit,
integration, property, stress, cve and differential tests pass; bench within budget; the
manual complete with EXAMPLES; the package joined the workspace), **shipped** (DELIVERY
complete, `distrib/` installs it).

## Imported (compiled from upstream, never rewritten)

```
<group>/<name>/
├── STATUS            imported | imported-built | imported-shipped
├── UPSTREAM.toml     the pin: mirror, origin, path, commit or tag, version, licence, CPE
├── patches/          our patches, a numbered series, each with its reason in its header
├── build/            the glue: what is built, with which flags, against which libc and libtls
├── DEFINITION.md     what it gives us, what we build of it, compatibility, configuration we
│                     ship, the security history tracked against the upstream's CPE
├── DESIGN.md         the integration: pledge kept, privileges, concurrency as upstream has it
├── tests/            our integration: it builds against our libc, starts under our rc, and
│                     behaves as OpenBSD's binary (golden/); cve/ for what we patched
├── man/              the upstream manual; a change to it is one more patch
├── DELIVERY.md
└── justfile
```

The source itself lives under `upstream/`, gitignored and read-only, fetched by
`tools/upstream.py fetch` and verified against `UPSTREAM.toml` (commit for git, SHA-256 and
signature for a tarball); a build copies it to `target/`, applies `patches/`, builds there.
`upstream/.pin` must match the TOML or `just build` refuses. Most imports point at
`EmiBSD/OpenBSD-src` at the Kernel's pin (OpenSSH, LibreSSL, `unbound`, `smtpd`, `nvi`,
`mandoc`, ncurses, LLVM all live in that tree): one shared clone, one fetch. Moving an
import to a newer version is a `upstream:` commit that bumps the pin and lists the CVEs it
closes, as the kernel bumps its LZ pin.

## Rules

- A written program is written from scratch under its definition. The definition is the
  specification, written from POSIX where the standard defines the program and from what the
  tradition settled (what each parameter does, how the output is formatted, the exit codes);
  the code is written from the definition alone, and nothing in the repository names another
  system for a written program. An imported one is never edited in place:
  patches only, and a patch needs a reason.
- Rust; `#![forbid(unsafe_code)]` at the crate root. `unsafe` only in `lib/libc`,
  `libexec/rtld` and `lib/crates/sys`, each site with a `// SAFETY:` proof. Miri on their
  host tests.

## The common grammar (the user's decision of 2026-10-24, taken with `ls`)

A written program is a query over records with a schema (`schemas/<record>.v1.json`); the
human and machine outputs are renderers of the same record, from the shared crate
`lib/crates/cli`, so the user learns the grammar once:

| | |
|---|---|
| `-o name` | one identifier per line (to a pipe) or in columns (to a terminal) |
| `-o table` | the classic columns; `--no-headers` drops the header line |
| `-o wide` | every field of the record as a table |
| `-o json`, `-o yaml` | the record, versioned (`apiVersion`) |
| `-o custom-columns=NAME:.name,SIZE:.size` | the fields you ask for |
| `--sort-by=.field`, `-r` | any field of the record, reversed |
| `--type=`, `--since=`, `--max-depth=` | filters, where the record has them |

POSIX's short flags keep their meaning (`ls -la` is `ls -la`). To a pipe, the output of a
POSIX-defined form (`ls -l`, `-1`, `-i`, `-s`) is POSIX's byte for byte, so the world's
scripts keep working. To a terminal, the defaults are modern: ISO 8601 dates, human sizes,
a header on tables. BSD extensions nobody remembers are not carried (`ls -m`, `-x`, `-T`);
what they did is `-o` or `--sort-by`. `-o` itself is the one conscious break with POSIX
XSI: it is the output selector, as in kubectl.

**One declaration per program** (the user's decision of 2026-10-24, taken with `cli` 0.2 and
`cp`): a `Command` in `src/options.rs` names every option once, with its type (`Flag`,
`Str`, `Choice`, `List`, `Int {min, max}`, `Duration`, `Size`, `Path`, `Field`, `Format`).
From that one table `cli` derives the parser (values arrive converted and checked, the
error already worded, as in `ls: --max-depth: 'x' is not a whole number` with the value
in backticks), `--help` as text,
`--help -o json` as a `CommandHelp` record (`lib/crates/cli/schemas/command-help.v1.json`,
with the type of every option, so an agent can drive the program without reading prose), the
usage line, and the `name: message` prefix of every diagnostic. No program declares `--help`
or writes a `parse::<usize>()` of its own. Every option carries its origin, and `--help`
shows the options in four sections, POSIX's, BSD compatibility (flags the BSDs have beyond
POSIX, kept so their scripts work), EmiBSD's own for this program, and the common grammar
every program shares (`-o`, `--sort-by`, `--no-headers`,
`--help`; `origin` in the record), so a user tells at a glance what works everywhere, what
is this program's, and what is the same in every EmiBSD program: `cli` knows the grammar's
names; a short flag is POSIX's unless the declaration says `.bsd()` or `.emibsd()`; a
long-only option is EmiBSD's. The exit codes are shared: **0** everything asked
was done, **1** something could not be done and the rest was, **2** the command line was
wrong and nothing was done; a program may define more above 2 and lists them in its
`Command`. An action is a stream of records too: `cp` makes one record per source examined,
with `action` saying what happened (created, replaced, merged, skipped, planned, failed);
`-v` and `-o` are two renderings of the same records, and `--dry-run` produces them without
the effect. The `pledge` promises follow the options (`cp` adds `dpath` under `-R` and
`chown` under `-p`); `cli` may grow a general form of that.
- A new crate dependency needs the user's OK and a row in the allowlist (to be written with
  the first program). Fuzzing: property tests on stable (`cargo-fuzz` needs nightly).
- Performance: a commit that moves a benchmark more than 10 % carries `Bench:` lines and a
  reason, or stops (the kernel's decision 43).
- Security: three layers. What the program forbids itself (pledge, unveil, privileges,
  verified by running its tests on EmiBSD, where a violation kills the process); the CVE
  history of the reference or upstream (a table in DEFINITION, a test per entry in
  `tests/cve/`); and our dependencies (`cargo audit`, `cargo deny` in `just check`, pending).
- The manual's source is mdoc(7), the format of the system; `mandoc -T markdown` and
  `-T html` render it for the site. EXAMPLES is not optional.
- Every file starts with the author's ISC block (`LICENSE`).
- `just status` at the root counts the STATUS files; that count is the progress of the
  userland, as `cargo xtask lz status` is the kernel's.

## Linking (the user's decision of 2026-10-24)

The BSD rule, kept: the programs of `bin/` and `sbin/` are linked **statically**, so
they run with only the root partition mounted, in single-user mode and on the installer's
ramdisk, without `/usr/lib` or `ld.so`; everything under `usr/` and `libexec/` is dynamic,
so a fix in a shared library reaches every program that links it. A `bin/` or `sbin/`
program carries `src/build.rs` emitting `cargo:rustc-link-arg-bins=-static` when the target
is `openbsd` (the Kernel's ABI; no flag on the development host, where static linking does not
exist); the toolchain's `crt-static` replaces it if `compiler/rust` finds that target respects
it. `DELIVERY.md` says `static` or `dynamic` and the measured size. The installer's ramdisk
does not pay `std` once per program: `distrib/installer` builds `bin/` and `sbin/` into one
multi-call crate, the Rust form of `crunchgen(8)`.

## Versions (the user's decision of 2026-10-23)

Two levels, because they answer two questions.

- **A program: semver, `MAJOR.MINOR.PATCH`**, because a program has interfaces others depend
  on (flags, `-o json`, exit codes, its configuration format) and the question its users ask
  is "does it break me?". `MAJOR` rises when a flag, an exit code, a schema (`output.v1` to
  `v2`) or the configuration format is removed or changed; `MINOR` when something is added;
  `PATCH` when something is fixed with nothing visible changed. A written program's version
  is `version` in `src/Cargo.toml`, starting at `0.1.0`; while `MAJOR` is 0, Cargo's reading
  applies: `breaking` bumps `MINOR`, `feature` and `fix` bump `PATCH`. An imported program's
  version is `version` in `UPSTREAM.toml`: the upstream's, plus our patch level as build
  metadata (`9.9+emibsd.2`); a new patch raises the level, a pin bump changes the base.
- **The system: calendar, `YEAR.MONTH`** (`2027.04`), the release `distrib/` builds, like
  the BSDs' release every six months with the date said. The question there is "how old is
  what I run?". It is a level apart from the `EmiBSD 8.0` the kernel shows userland, which
  does not move while the Kernel's ABI does not.

The rule, mechanical: a commit that changes a program's code (`src/`; for an import
`patches/`, `build/` or `UPSTREAM.toml`) carries one trailer, `Change: breaking`, `Change:
feature` or `Change: fix`, and the version it carries is the bump that trailer calls for.
`tools/version.py check-commit` runs as the `commit-msg` hook (`just setup` installs
`.githooks/`) and refuses the commit otherwise; a commit that touches only tests, manuals or
docs needs no trailer and no bump. `CHANGELOG.md` of a program is generated from those
trailers by `just changelog`, never written by hand. A schema carries its own `apiVersion`,
raised only when the JSON stops being compatible, and that raise is `breaking` by
definition.
"""

PROGRAM_JUST = """# Shared recipes for every program and library; each one's justfile imports this file.
# The program's name is its directory's name; the class is the first word of STATUS.

name := file_name(justfile_directory())
root := justfile_directory() / "../../.."

# Build: a written program through cargo; an imported one through build/ after fetch.
build:
    #!/bin/sh
    set -e
    case "$(cat STATUS)" in
      imported*) python3 -I "{{root}}/tools/upstream.py" check . && sh build/build.sh ;;
      *) cargo build --manifest-path src/Cargo.toml ;;
    esac

# Fetch and verify the upstream source (imported programs).
fetch:
    python3 -I "{{root}}/tools/upstream.py" fetch .

# Unit and integration tests (tests/, with stress/, cve/ and golden/ inside).
test:
    cargo test --manifest-path src/Cargo.toml

# The stress tests alone, on four CPUs.
stress:
    EMIBSD_NCPU=4 cargo test --manifest-path src/Cargo.toml --test 'stress*'

# Host benchmarks against a reference system's program on the same input.
bench:
    cargo bench --manifest-path src/Cargo.toml

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

# CHANGELOG.md from this program's commits' Change: trailers.
changelog:
    python3 -I "{{root}}/tools/version.py" changelog .

# This program's CVE history from NVD (network), as rows for DEFINITION.md.
cve:
    python3 -I "{{root}}/tools/cve.py" .
"""

ROOT_JUST = """# EmiBSD Userland: the recipes over the whole monorepo. Each program has its own justfile
# importing tools/program.just; these run across all of them.

trees := "bin sbin usr libexec lib compiler"

# Progress: how many programs sit at each STATUS (written: planned..shipped; imported: imported..).
status:
    @find {{trees}} -name STATUS | xargs cat | sort | uniq -c | sort -rn

# Every program at a given status: `just at implemented`, `just at imported`.
at s:
    @find {{trees}} -name STATUS | while read f; do [ "$(cat "$f")" = "{{s}}" ] && dirname "$f"; done | sort

# Fetch and verify every upstream named by an UPSTREAM.toml (shared clones under upstream/).
fetch:
    python3 -I tools/upstream.py fetch

# Check every fetched upstream against its pin.
fetch-check:
    python3 -I tools/upstream.py check

# Regenerate the READMEs and the skeletons still at planned/imported (needs Kernel's reference tree).
layout src="../Kernel/reference/openbsd-src":
    python3 -I tools/layout.py {{src}} .

# Format, clippy and tests over the workspace (the packages that joined Cargo.toml).
check:
    cargo fmt --all -- --check
    cargo clippy --workspace -- -D warnings
    cargo test --workspace

# Install the repository's git hooks (commit-msg: the Change: trailer and the version bump).
setup:
    git config core.hooksPath .githooks
    @echo "hooks: core.hooksPath = .githooks"

# Regenerate CHANGELOG.md of one program from its commits' Change: trailers.
changelog dir:
    python3 -I tools/version.py changelog {{dir}}

# cargo-audit and cargo-deny are `cargo install`ed tools, outside the repository: installed only with the user's OK.
# Advisories against our crate dependencies (RustSec) and the licence and duplicate policy.
audit:
    #!/bin/sh
    if command -v cargo-audit >/dev/null; then cargo audit; else echo "audit: cargo-audit not installed (cargo install cargo-audit, with the user's OK)"; fi
    if command -v cargo-deny >/dev/null; then cargo deny check; else echo "audit: cargo-deny not installed (cargo install cargo-deny, with the user's OK)"; fi

# The CVE history of one program from NVD, as rows for DEFINITION.md's Security history (network).
cve dir:
    python3 -I tools/cve.py {{dir}}
"""

COMMIT_MSG_HOOK = """#!/bin/sh
# commit-msg: a change to a program's code carries a Change: trailer and the version bump it
# calls for (docs/PROGRAM.md, Versions). Installed by `just setup` (core.hooksPath).
exec python3 -I "$(git rev-parse --show-toplevel)/tools/version.py" check-commit "$1"
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
# No targets yet: the `*-unknown-openbsd` targets (the Kernel's ABI) are tier 3; compiler/rust builds their std (README).
[toolchain]
channel = "1.98.1"
profile = "minimal"
components = ["rustfmt", "clippy", "rust-src"]
"""

GITIGNORE = """# Fetched upstream sources (tools/upstream.py), read-only, never committed.
upstream/
# Build output.
target/
"""

SETTINGS = """{
  "permissions": {
    "allow": [
      "Bash(just:*)",
      "Bash(cargo:*)"
    ],
    "deny": [
      "Edit(upstream/**)",
      "Write(upstream/**)",
      "Edit(**/upstream/**)",
      "Write(**/upstream/**)"
    ]
  }
}
"""

UPSTREAM_PY = r'''#!/usr/bin/env python3
"""Fetch, verify and pin the upstream sources of the imported programs (docs/PROGRAM.md).

usage: upstream.py fetch [<program dir>...]     fetch what the UPSTREAM.toml files name
       upstream.py check [<program dir>...]     every fetched upstream matches its pin

Git upstreams are cloned sparse, blob-less, into upstream/<mirror name>/ at the repository
root, one clone per mirror shared by every program that names it (EmiBSD/OpenBSD-src holds
most of them), checked out at the pinned commit (or the commit a pinned tag resolves to).
Tarball upstreams are downloaded into upstream/<name>/, their SHA-256 verified before
extraction. Everything fetched is made read-only; upstream/<key>/.pin records the hash.
Stdlib only.
"""
import hashlib
import os
import stat
import subprocess
import sys
import tomllib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = ROOT / "upstream"


def tomls(args):
    dirs = [Path(a).resolve() for a in args] or [p.parent for p in ROOT.rglob("UPSTREAM.toml")
                                                   if "upstream" not in p.parts and "target" not in p.parts]
    for d in dirs:
        f = d / "UPSTREAM.toml"
        if f.exists():
            with open(f, "rb") as fh:
                doc = tomllib.load(fh)
            up = dict(doc["upstream"])
            up["submodules"] = doc.get("submodules", [])
            yield d, up


def key_of(up):
    return up["repo"].rstrip("/").rsplit("/", 1)[-1] if up["kind"] == "git" else up["name"]


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


def readonly(path: Path):
    for root, dirs, files in os.walk(path):
        for n in dirs + files:
            p = Path(root) / n
            if not p.is_symlink():
                p.chmod(p.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def fetch_git(key, ups):
    dest = UPSTREAM / key
    repo = ups[0]["repo"]
    commits = {u.get("commit") or u.get("tag") for u in ups}
    if len(commits) != 1:
        raise SystemExit(f"upstream: {key}: programs disagree on the pin: {sorted(commits)}")
    want = commits.pop()
    if not want:
        raise SystemExit(f"upstream: {key}: no commit or tag pinned")
    paths = sorted({p for u in ups for p in u.get("path", [])})
    if not dest.exists():
        UPSTREAM.mkdir(exist_ok=True)
        subprocess.run(["git", "clone", "--no-checkout", "--filter=blob:none", repo, str(dest)], check=True)
        if paths:
            git(dest, "sparse-checkout", "set", "--no-cone", *paths)
    else:
        for p in paths:
            readonly_off(dest / ".git")
        if paths:
            git(dest, "sparse-checkout", "set", "--no-cone", *paths)
    readonly_off(dest)
    git(dest, "fetch", "--filter=blob:none", "origin", want)
    git(dest, "checkout", "--detach", "FETCH_HEAD" if not all(c in "0123456789abcdef" for c in want) else want)
    head = git(dest, "rev-parse", "HEAD")
    for sm in [s for u in ups for s in u.get("submodules", [])]:
        sub = dest / sm["path"]
        if not (sub / ".git").exists():
            if sub.exists():
                sub.rmdir()   # the empty directory git leaves for an uninitialised submodule
            subprocess.run(["git", "clone", "--no-checkout", "--filter=blob:none", sm["repo"], str(sub)], check=True)
        git(sub, "fetch", "--filter=blob:none", "origin", sm["commit"])
        git(sub, "checkout", "--detach", sm["commit"])
        print(f"upstream: {key}: submodule {sm['path']} at {sm['commit'][:12]} from {sm['repo']}")
    (dest / ".pin").write_text(head + "\n")
    readonly(dest)
    print(f"upstream: {key}: {head[:12]} ({len(paths)} paths) pinned")


def readonly_off(path: Path):
    for root, dirs, files in os.walk(path):
        for n in dirs + files:
            p = Path(root) / n
            if not p.is_symlink():
                p.chmod(p.stat().st_mode | stat.S_IWUSR)
    path.chmod(path.stat().st_mode | stat.S_IWUSR)


def fetch_tarball(key, up):
    dest = UPSTREAM / key
    if dest.exists():
        readonly_off(dest)
    dest.mkdir(parents=True, exist_ok=True)
    url = up.get("mirror") or up["url"]
    archive = dest / url.rsplit("/", 1)[-1]
    if not archive.exists():
        print(f"upstream: {key}: downloading {url}")
        urllib.request.urlretrieve(url, archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != up["sha256"]:
        archive.unlink()
        raise SystemExit(f"upstream: {key}: SHA-256 mismatch: {digest} != {up['sha256']}")
    if "signature" in up:
        print(f"upstream: {key}: signature check ({up['signature'].get('kind')}) not implemented yet: verify by hand")
    subprocess.run(["tar", "-xf", str(archive), "-C", str(dest)], check=True)
    (dest / ".pin").write_text(digest + "\n")
    readonly(dest)
    print(f"upstream: {key}: {digest[:12]} pinned")


def cmd_fetch(args):
    groups = {}
    for d, up in tomls(args):
        groups.setdefault(key_of(up), []).append(up)
    for key, ups in groups.items():
        if ups[0]["kind"] == "git":
            fetch_git(key, ups)
        else:
            fetch_tarball(key, ups[0])


def cmd_check(args):
    bad = 0
    for d, up in tomls(args):
        key = key_of(up)
        pin = UPSTREAM / key / ".pin"
        if not pin.exists():
            print(f"upstream: {d.relative_to(ROOT)}: {key} not fetched (just fetch)")
            bad += 1
            continue
        have = pin.read_text().strip()
        want = up.get("commit") or up.get("sha256") or ""
        if want and have != want and not want.startswith(have[:len(want)]):
            # a tag pins by name: accept whatever it resolved to (recorded in .pin)
            if up.get("commit") or up.get("sha256"):
                print(f"upstream: {d.relative_to(ROOT)}: {key} at {have[:12]}, pinned {want[:12]}")
                bad += 1
    if bad:
        raise SystemExit(bad)
    print("upstream: every fetched upstream matches its pin")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("fetch", "check"):
        print(__doc__)
        sys.exit(2)
    (cmd_fetch if sys.argv[1] == "fetch" else cmd_check)(sys.argv[2:])
'''

BUILD_SH = """#!/bin/sh
# The build glue of an imported program: copy the pinned source to target/, apply patches/,
# build there. To be written with the first build; never touches upstream/.
set -e
echo "build/build.sh: not written yet" >&2
exit 1
"""

DEFINITION = """# {name}

STATUS: see `STATUS`. EmiBSD's own `{name}`, written from scratch under this definition (the
user's decision of 2026-10-23): this document is the specification, written from POSIX where
the standard defines the program and from the behaviour the tradition settled; the code is
written from this document alone.

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

## Performance budget

The measure that matters for this program and its floor: never slower than a reference
system's {name} on the same machine and input (`bench/`, `just bench`).

## Security history

The CVEs of the programs of this name on other systems, each with its class
and what makes it impossible here (a type, a check, the language) or the test in
`tests/cve/` that proves it.

| CVE | Class | Here |
|---|---|---|

## Open questions
{notes}"""

DEFINITION_IMPORTED = """# {name} (imported)

STATUS: see `STATUS`. Compiled from its upstream at the pin of `UPSTREAM.toml`, never
rewritten (the user's decision of 2026-10-23). OpenBSD's `{origin}`; manual {name}({section}).

## What it gives us

## What we build of it

The targets, libraries and tools taken from the source; what is left out and why.

## Constraints

Which libc, libtls and other libraries of this repository it must link; static or dynamic;
privileges.

## Compatibility

Who in the base system depends on it and how (flags, output, exit codes, configuration
paths). Our patches, if any, never change what callers see.

## Configuration we ship

The defaults installed under /etc, and how they differ from upstream's.

## Performance budget

As OpenBSD builds it, on the same machine and input; a build flag that changes it is a
decision in DESIGN.

## Security history

Tracked against the upstream (`UPSTREAM.toml` `[security] cpe`): open advisories at the pin,
what the pin bump that closes them is, and `tests/cve/` for what we patched ourselves.

| CVE | Upstream fix | Here |
|---|---|---|

## Open questions
{notes}"""

DESIGN = """# {name}: design

## Architecture

```mermaid
flowchart LR
    A[input] --> B[{name}] --> C[output]
```

## Concurrency

The model (single-threaded, a process per privilege or connection as the BSD daemons do,
a thread pool, an event loop); what is shared and how; whether and how it uses more than one
core. What serves many has stress tests in `tests/stress/` on four CPUs.

## Threat model

Which inputs are hostile (the network, a user's file, an argument from root), what an
attacker gains from each failure, and what bounds it.

## Security

`pledge(2)` promises, `unveil(2)` paths, privilege separation, setuid: the least the
program needs, and never relaxed afterwards.

## Data

The schemas in `schemas/`; their versions; who consumes them.

## Decisions

Numbered, each with its reason and what was rejected.

## Dependencies

Crates used, each with why; the allowlist governs.
"""

DESIGN_IMPORTED = """# {name}: integration

## How it is built

The source at the pin, copied to `target/`, `patches/` applied, built by `build/build.sh`
against this repository's libc and libraries. Flags that differ from OpenBSD's build, with
the reason.

## Patches

One line per patch of `patches/`: what it changes and why it could not stay upstream.

## Concurrency

As upstream has it; nothing added.

## Threat model and security

What the upstream restricts (pledge, unveil, privilege separation) and the proof we kept it:
the tests that run it under our kernel.

## Dependencies

The libraries of this repository it links, and any other upstream it needs.
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

MAN = """.\\" {name}({section}): EmiBSD's own, written from scratch under its definition.
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

MAN_IMPORTED = """.\\" {name}({section}) is imported: the manual is the upstream's, rendered from upstream/ at build time.
.\\" A change to it is a patch in patches/. This file only says where it comes from.
"""


def upstream_toml(name: str, spec: dict) -> str:
    def arr(v):
        return "[" + ", ".join(f'"{x}"' for x in v) + "]"
    lines = ["# The pin of an imported program (docs/PROGRAM.md). tools/upstream.py fetches and verifies it.",
             "[upstream]",
             f'name    = "{spec["name"]}"',
             f'kind    = "{spec["kind"]}"',
             f'repo    = "{spec["repo"]}"           # the organisation\'s mirror, always',
             f'origin  = "{spec["origin"]}"          # what the mirror is fed from',
             f'path    = {arr(spec.get("path", []))}']
    if spec.get("commit"):
        lines.append(f'commit  = "{spec["commit"]}"')
    if spec.get("tag"):
        lines.append(f'tag     = "{spec["tag"]}"                 # resolved to a commit at fetch, recorded in upstream/.pin')
    lines += [f'version = "{spec.get("version", "")}"                 # the human version; to fill from the source when empty',
              f'license = {arr(spec.get("license", []))}   # the families; the texts stay in the source',
              "",
              "[security]",
              f'cpe     = "{spec.get("cpe", "")}"            # NVD product, for tools/cve.py',
              "",
              "[patches]",
              "series  = []                              # patches/NNNN-*.patch, in order; each with its reason"]
    for sm in spec.get("submodules", []):
        lines += ["",
                  "[[submodules]]                            # fetched from the mirror at this commit, in place of the upstream's URL",
                  f'path    = "{sm["path"]}"',
                  f'repo    = "{sm["repo"]}"',
                  f'origin  = "{sm["origin"]}"',
                  f'commit  = "{sm["commit"]}"']
    if spec.get("note"):
        lines += ["", "# " + spec["note"]]
    return "\n".join(lines) + "\n"


def listing(d: str) -> set:
    return {n for n in os.listdir(SRC / d)
            if not n.lower().startswith("makefile") and n != "CVS"
            and not n.endswith(".inc") and not n.endswith(".mk")}


def pin() -> str:
    for line in PIN_FILE.read_text().splitlines():
        if line.startswith("Commit:"):
            return line.split(":", 1)[1].strip()
    raise SystemExit(f"{PIN_FILE}: no Commit: line")


def man_section(top: str, src_dir: str, name: str) -> str:
    """The manual section of this program in the reference tree: <name>.<n> in its directory (one
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


def notes_for(name: str) -> str:
    out = []
    if name in PERL:
        out.append("- Traditionally this program is Perl, and Perl is not in this tree (Artistic or GPL, dual): "
                   "the user decides between importing Perl under the Artistic licence and writing this in Rust.")
    if name in SHELL:
        out.append("- Traditionally this is a shell script: here Rust, or a script for our ksh; decided at `defined`.")
    if name in ON_DISK:
        out.append("- Writes or repairs an on-disk format: a bug corrupts a file system. The differential tests "
                   "against a reference system's program compare the resulting image bit for bit; a condition of `implemented`.")
    return ("\n" + "\n".join(out) + "\n") if out else "\n"


def regenerable(d: Path) -> bool:
    s = d / "STATUS"
    return not s.exists() or s.read_text().strip() in ("planned", "imported")


def put(path: Path, text: str, force: bool) -> int:
    if path.exists() and not force:
        return 0
    # A .gitkeep only holds an empty directory's place: never beside real files.
    if path.name == ".gitkeep" and path.parent.is_dir() and any(path.parent.iterdir()):
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return 1


def crate_skeleton(leaf: str, name: str) -> int:
    """A shared Rust crate: a written program with no counterpart elsewhere, section 3."""
    d = OUT / "lib" / leaf / name
    force = regenerable(d)
    rel = os.path.relpath(OUT / "tools" / "program.just", d)
    n = 0
    n += put(d / "STATUS", "planned\n", force)
    n += put(d / "justfile", f"import '{rel}'\n", force)
    n += put(d / "DELIVERY.md", DELIVERY.format(name=name, section="3"), force)
    n += put(d / "DEFINITION.md", DEFINITION.format(name=name, origin="none: EmiBSD's own crate", section="3",
                                                     notes="\n- No counterpart elsewhere: the reference is its first user's needs.\n"), force)
    n += put(d / "DESIGN.md", DESIGN.format(name=name, section="3"), force)
    n += put(d / "man" / f"{name}.3", MAN.format(name=name, NAME=name.upper(), section="3"), force)
    for sub in ("schemas", "src", "tests", "bench"):
        n += put(d / sub / ".gitkeep", "", False)
    return n


def own_skeleton(top: str, leaf: str, name: str) -> int:
    """A program of EmiBSD's own: written, with no counterpart in any reference tree; its
    specification comes from the standards it implements and from the common grammar."""
    d = OUT / top / leaf / name
    force = regenerable(d)
    section = DEFAULT_SECTION[top]
    rel = os.path.relpath(OUT / "tools" / "program.just", d)
    n = 0
    n += put(d / "STATUS", "planned\n", force)
    n += put(d / "justfile", f"import '{rel}'\n", force)
    n += put(d / "DELIVERY.md", DELIVERY.format(name=name, section=section), force)
    n += put(d / "DEFINITION.md", DEFINITION.format(name=name, origin="none: EmiBSD's own program", section=section,
                                                     notes="\n- No counterpart elsewhere: the specification is written from the standards the program\n  implements and from the common grammar; there is no reference implementation to survey.\n"), force)
    n += put(d / "DESIGN.md", DESIGN.format(name=name, section=section), force)
    n += put(d / "man" / f"{name}.{section}", MAN.format(name=name, NAME=name.upper(), section=section), force)
    for sub in ("schemas", "src", "tests", "bench"):
        n += put(d / sub / ".gitkeep", "", False)
    n += put(d / "tests" / "cve" / ".gitkeep", "", False)
    return n


def skeleton(top: str, leaf: str, name: str, src_dir: str, the_pin: str) -> int:
    d = OUT / top / leaf / name
    force = regenerable(d)
    section = man_section(top, src_dir, name)
    origin = f"{src_dir}/{name}"
    rel = os.path.relpath(OUT / "tools" / "program.just", d)
    imported = name in IMPORTED
    n = 0
    n += put(d / "STATUS", ("imported\n" if imported else "planned\n"), force)
    n += put(d / "justfile", f"import '{rel}'\n", force)
    n += put(d / "DELIVERY.md", DELIVERY.format(name=name, section=section), force)
    for sub in ("schemas", "src", "tests", "bench") if not imported else ("tests",):
        n += put(d / sub / ".gitkeep", "", False)
    n += put(d / "tests" / "cve" / ".gitkeep", "", False)
    if imported:
        n += put(d / "DEFINITION.md", DEFINITION_IMPORTED.format(name=name, origin=origin, section=section, notes=notes_for(name)), force)
        n += put(d / "DESIGN.md", DESIGN_IMPORTED.format(name=name), force)
        n += put(d / "UPSTREAM.toml", upstream_toml(name, dict(
            name=name, kind="git", repo=OPENBSD_MIRROR, origin=OPENBSD_ORIGIN, path=[origin],
            commit=the_pin, version="", license=[], cpe=IMPORTED[name])), force)
        n += put(d / "patches" / ".gitkeep", "", False)
        n += put(d / "build" / "build.sh", BUILD_SH, force)
        n += put(d / "man" / "README.md", MAN_IMPORTED.format(name=name, section=section), force)
        for stale in (d / "schemas", d / "src", d / "bench", d / "man" / f"{name}.{section}"):
            if stale.is_file():
                stale.unlink()
            elif stale.is_dir() and not any(p.name != ".gitkeep" for p in stale.iterdir()):
                for p in stale.iterdir():
                    p.unlink()
                stale.rmdir()
    else:
        n += put(d / "DEFINITION.md", DEFINITION.format(name=name, origin=origin, section=section, notes=notes_for(name)), force)
        n += put(d / "DESIGN.md", DESIGN.format(name=name, section=section), force)
        n += put(d / "man" / f"{name}.{section}", MAN.format(name=name, NAME=name.upper(), section=section), force)
        n += put(d / "tests" / "stress" / ".gitkeep", "", False)
        n += put(d / "tests" / "golden" / ".gitkeep", "", False)
    return n


def compiler_skeleton(name: str, the_pin: str) -> int:
    d = OUT / "compiler" / name
    force = regenerable(d)
    spec = dict(COMPILERS[name])
    if spec.get("commit") == "@PIN@":
        spec["commit"] = the_pin
    rel = os.path.relpath(OUT / "tools" / "program.just", d)
    n = 0
    n += put(d / "STATUS", "imported\n", force)
    n += put(d / "justfile", f"import '{rel}'\n", force)
    n += put(d / "UPSTREAM.toml", upstream_toml(name, spec), force)
    n += put(d / "DEFINITION.md", DEFINITION_IMPORTED.format(name=name, origin=", ".join(spec["path"]) or spec["origin"], section="1", notes="\n- " + spec["note"] + "\n"), force)
    n += put(d / "DESIGN.md", DESIGN_IMPORTED.format(name=name), force)
    n += put(d / "DELIVERY.md", DELIVERY.format(name=name, section="1"), force)
    n += put(d / "build" / "build.sh", BUILD_SH, force)
    n += put(d / "patches" / ".gitkeep", "", False)
    n += put(d / "tests" / ".gitkeep", "", False)
    n += put(d / "man" / "README.md", MAN_IMPORTED.format(name=name, section="1"), force)
    return n


def main() -> int:
    the_pin = pin()
    sources = {d: listing(d) for d in set(SOURCE_DIR.values())}
    seen, dup, unknown, misplaced = {}, [], [], []
    covered = {d: set() for d in sources}
    for top, _, leaves in LAYOUT:
        src = SOURCE_DIR.get(top)
        for leaf, _, progs in leaves:
            for p in progs:
                where = f"{top}/{leaf}"
                key = p if ("/" in p or ":" in p) else f"{src}/{p}"
                if key in seen:
                    dup.append((p, seen[key], where))
                seen[key] = where
                if ":" in p:
                    kind, _, nm = p.partition(":")
                    if kind == "compiler" and nm not in COMPILERS:
                        unknown.append(p)
                    elif kind not in ("compiler", "crate", "own"):
                        unknown.append(p)
                    continue
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
    unknown_imports = sorted(n for n in IMPORTED if not any(n in s for s in sources.values()))
    if dup or unknown or misplaced or missing or unknown_imports:
        print("duplicates:", dup)
        print("unknown:", unknown)
        print("misplaced (name not in that tree of the reference):", misplaced)
        print("missing:", missing)
        print("IMPORTED names that are no program:", unknown_imports)
        return 1

    tree, created, programs, imported = [], 0, 0, 0
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
                     "Programs of this group:", ""]
            for p in progs:
                if p.startswith("crate:"):
                    name = p.split(":", 1)[1]
                    lines.append(f"- [`{name}`]({name}/) (EmiBSD's own crate)")
                    created += crate_skeleton(leaf, name)
                    programs += 1
                    continue
                if p.startswith("own:"):
                    name = p.split(":", 1)[1]
                    lines.append(f"- [`{name}`]({name}/) (EmiBSD's own)")
                    created += own_skeleton(top, leaf, name)
                    programs += 1
                    continue
                if ":" in p:
                    name = p.split(":", 1)[1]
                    lines.append(f"- [`{name}`](../{name}/) (imported: {', '.join(COMPILERS[name]['path']) or COMPILERS[name]['origin']})")
                    created += compiler_skeleton(name, the_pin)
                    programs += 1
                    imported += 1
                    continue
                origin = p if "/" in p or src is None else f"{src}/{p}"
                name = origin.rsplit("/", 1)[-1]
                if src is not None:
                    tag = " (imported)" if name in IMPORTED else ""
                    lines.append(f"- [`{name}`]({name}/){tag}")
                    created += skeleton(top, leaf, name, src, the_pin)
                    programs += 1
                    imported += name in IMPORTED
                else:
                    lines.append(f"- `{name}` ({origin})")
            if src is not None or top == "compiler":
                lines += ["", "Each entry is a program directory laid out as `docs/PROGRAM.md` says."]
            else:
                lines += ["", "Nothing written yet."]
            if top == "compiler":
                continue   # the compiler tree's leaves are the programs themselves
            (d / "README.md").write_text("\n".join(lines) + "\n")
        top_md += ["", "Each entry is a group; each group's README lists its programs." if (src or top == "compiler") else "Nothing written yet."]
        (OUT / top / "README.md").write_text("\n".join(top_md) + "\n")
    (OUT / "README.md").write_text(TOPLEVEL_README.format(tree="\n".join(tree) + "\n"))
    (OUT / "docs").mkdir(exist_ok=True)
    (OUT / "docs" / "PROGRAM.md").write_text(PROGRAM_DOC)
    (OUT / "tools" / "program.just").write_text(PROGRAM_JUST)
    (OUT / "tools" / "upstream.py").write_text(UPSTREAM_PY)
    cve_src = Path(__file__).resolve().parent / "cve.py"
    if cve_src.exists() and cve_src != OUT / "tools" / "cve.py":
        (OUT / "tools" / "cve.py").write_text(cve_src.read_text())
    (OUT / "justfile").write_text(ROOT_JUST)
    hook = OUT / ".githooks" / "commit-msg"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text(COMMIT_MSG_HOOK)
    hook.chmod(0o755)
    put(OUT / "Cargo.toml", ROOT_CARGO, False)
    put(OUT / "rust-toolchain.toml", TOOLCHAIN, False)
    put(OUT / ".gitignore", GITIGNORE, False)
    put(OUT / ".claude" / "settings.json", SETTINGS, False)
    total = sum(len(progs) for _, _, leaves in LAYOUT for _, _, progs in leaves)
    print(f"ok: {len(LAYOUT)} trees, {sum(len(l) for _, _, l in LAYOUT)} leaves, {total} entries, "
          f"{programs} programs ({imported} imported, {programs - imported} written; {created} files written this run);",
          {d: len(s) for d, s in sorted(sources.items())})
    return 0


if __name__ == "__main__":
    sys.exit(main())
