#!/usr/bin/env python3
"""Generate the Userland monorepo's directory layout with one README.md per directory.

usage: layout.py <openbsd-src root> <Userland root>

The top level is OpenBSD's own split by install path (bin, sbin, usr/bin, usr/sbin, libexec,
lib, include, gnu, etc, share, distrib); inside each, the programs are grouped by what they
do. Every program of OpenBSD's bin/, sbin/, usr.bin/, usr.sbin/, libexec/ and lib/ is mapped
to exactly one leaf, in the tree OpenBSD keeps it in; the script refuses to write otherwise.
"""
import os
import sys
from pathlib import Path

SRC = Path(sys.argv[1])
OUT = Path(sys.argv[2])

# Where a top-level directory's bare names come from in OpenBSD's src.
SOURCE_DIR = {"bin": "bin", "sbin": "sbin", "usr/bin": "usr.bin", "usr/sbin": "usr.sbin",
              "libexec": "libexec", "lib": "lib"}

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
    ("lib", "The libraries every program links. While the kernel keeps OpenBSD's ABI, libc speaks OpenBSD's system calls: this is the layer closest to OpenBSD by necessity. OpenBSD's lib/ (35).", [
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
    ("gnu", "The compiler and its runtime, kept apart as OpenBSD keeps them (Apache-2.0 with LLVM exception). OpenBSD's gnu/.", [
        ("compiler", "clang, lld and the C++ and compiler runtimes.", [
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

## Layout

OpenBSD's own split at the top: `bin/` and `sbin/` are what works with only the root
partition mounted (linked static), `usr/bin/` and `usr/sbin/` the rest; `bin` and `usr/bin`
are for the user, `sbin` and `usr/sbin` for operating the system. Inside each, the programs
are grouped by what they do. A concept that OpenBSD spreads over two trees keeps a distinct
name in each (`bin/files` and `usr/bin/file-tools`, `sbin/network` and `usr/sbin/network/`),
and the README of each says where its other half is. Every program is listed once, in the
tree OpenBSD keeps it in; `tools/layout.py` regenerates the READMEs from the map and refuses
to write when one is missing or doubled.

```
{tree}```

The lists are the map to what OpenBSD's base system provides at the pin of
`Kernel/reference/PINNED.md`, not a porting list: the programs written here are EmiBSD's own.

New code is ISC (`LICENSE`).
"""


def listing(d: str) -> set:
    return {n for n in os.listdir(SRC / d)
            if not n.lower().startswith("makefile") and n != "CVS"
            and not n.endswith(".inc") and not n.endswith(".mk")}


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

    tree = []
    for top, purpose, leaves in LAYOUT:
        tree.append(f"{top}/")
        (OUT / top).mkdir(parents=True, exist_ok=True)
        top_md = [f"# {top}", "", purpose, "", "| Directory | What |", "|---|---|"]
        for i, (leaf, what, progs) in enumerate(leaves):
            last = i == len(leaves) - 1
            tree.append(f"{'└── ' if last else '├── '}{leaf:<20} {what}")
            top_md.append(f"| `{leaf}/` | {what} |")
            d = OUT / top / leaf
            d.mkdir(parents=True, exist_ok=True)
            src = SOURCE_DIR.get(top)
            lines = [f"# {top}/{leaf}", "", what, "",
                     "Covers, from OpenBSD's base system at the pin (its path in OpenBSD's `src`):", ""]
            for p in progs:
                origin = p if "/" in p or src is None else f"{src}/{p}"
                lines.append(f"- `{origin.rsplit('/', 1)[-1]}` ({origin})")
            lines += ["", "Nothing written yet."]
            (d / "README.md").write_text("\n".join(lines) + "\n")
        top_md += ["", "Nothing written yet."]
        (OUT / top / "README.md").write_text("\n".join(top_md) + "\n")
    (OUT / "README.md").write_text(TOPLEVEL_README.format(tree="\n".join(tree) + "\n"))
    total = sum(len(progs) for _, _, leaves in LAYOUT for _, _, progs in leaves)
    print(f"ok: {len(LAYOUT)} trees, {sum(len(l) for _, _, l in LAYOUT)} leaves, {total} entries;",
          {d: len(s) for d, s in sorted(sources.items())})
    return 0


if __name__ == "__main__":
    sys.exit(main())
