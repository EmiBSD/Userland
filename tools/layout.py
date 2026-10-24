#!/usr/bin/env python3
"""Generate the Userland monorepo's directory layout with one README.md per directory.

usage: userland-layout.py <openbsd-src root> <Userland root>

Every program of OpenBSD's bin/, sbin/, usr.bin/, usr.sbin/, libexec/ and lib/ is mapped to
exactly one leaf; the script refuses to write if one is unmapped or mapped twice.
"""
import os
import sys
from pathlib import Path

SRC = Path(sys.argv[1])
OUT = Path(sys.argv[2])

# (category, leaf, one-line purpose, [programs])  -- a program is "name" or "dir/name" when
# it does not live in bin, sbin, usr.bin or usr.sbin.
LAYOUT = [
    ("core-utilities", "The commands a user types. OpenBSD's bin/ and most of usr.bin/; the split between the two (what works with only the root partition mounted, linked static) becomes a build attribute here, not a directory.", [
        ("shell", "The shells and the terminal line they run on.", ["ksh", "csh", "stty"]),
        ("files", "Listing, copying, moving, finding and describing files.", [
            "ls", "cp", "mv", "rm", "ln", "mkdir", "rmdir", "chmod", "cat", "dd", "df", "pwd", "pax",
            "touch", "find", "xargs", "file", "stat", "du", "mktemp", "readlink", "realpath", "basename",
            "dirname", "locate", "which", "what", "xinstall", "compress", "shar", "lndir", "md5"]),
        ("text", "Filters and transformers of text streams.", [
            "awk", "sed", "grep", "diff", "diff3", "sdiff", "cmp", "comm", "sort", "uniq", "join", "cut",
            "paste", "tr", "wc", "head", "tail", "fold", "fmt", "pr", "col", "colrm", "column", "expand",
            "unexpand", "nl", "rev", "rs", "lam", "csplit", "split", "look", "spell", "ul", "deroff", "vis",
            "unvis", "uuencode", "uudecode", "hexdump"]),
        ("editors", "Editors and pagers.", ["vi", "mg", "ed", "less"]),
        ("process", "Running, timing, listing and signalling processes; the shell's small helpers.", [
            "ps", "kill", "sleep", "sync", "test", "echo", "expr", "date", "env", "nice", "nohup", "renice",
            "time", "timeout", "pkill", "top", "fstat", "true", "false", "yes", "seq", "jot", "printf",
            "printenv", "getopt", "getconf", "tee", "tty", "tsort", "apply"]),
        ("users", "Logging in, identities, who is on the machine, talking to them.", [
            "login", "passwd", "su", "doas", "id", "who", "w", "users", "last", "lastcomm", "finger",
            "chpass", "lock", "mesg", "wall", "write", "talk", "encrypt", "skey", "skeyinit", "skeyinfo",
            "skeyaudit", "x99token", "logname", "getent"]),
        ("net-clients", "Network clients a user runs.", [
            "ssh", "nc", "ftp", "tftp", "telnet", "dig", "whois", "netstat", "tcpbench", "rsync", "rdist",
            "rdistd", "rup", "rusers", "rwall", "rpcinfo", "showmount", "nfsstat", "snmp", "ldap", "cu"]),
        ("calc", "Calculators and calendars.", ["bc", "dc", "units", "cal", "calendar"]),
        ("mail", "Reading and sending mail from the command line.", ["mail", "biff", "from", "vacation"]),
        ("media", "Audio, MIDI, radio and CD control.", [
            "aucat", "audioctl", "mixerctl", "midicat", "sndioctl", "sndiod", "radioctl", "cdio"]),
        ("docs", "Manual pages and terminal descriptions.", ["mandoc", "tic", "infocmp", "tput", "tset"]),
        ("scheduling", "Running things later.", ["crontab", "at", "leave"]),
        ("system-info", "What machine this is and how it is set up.", [
            "uname", "arch", "pagesize", "hostname", "domainname", "locale"]),
        ("misc", "What fits nowhere else.", [
            "banner", "tmux", "ts", "sendbug", "script", "watch", "logger", "quota"]),
    ]),
    ("system-libraries", "The libraries every program links and the headers they export. While the kernel keeps OpenBSD's ABI, libc speaks OpenBSD's system calls: this is the layer closest to OpenBSD by necessity.", [
        ("libc", "The C library, its start-up files and threads.", [
            "lib/libc", "lib/csu", "lib/librthread", "lib/libpthread", "lib/libm", "lib/check_sym"]),
        ("rtld", "The run-time linker.", ["libexec/ld.so"]),
        ("crypto", "Cryptography and authentication libraries.", [
            "lib/libcrypto", "lib/libssl", "lib/libtls", "lib/libfido2", "lib/libcbor", "lib/libskey",
            "lib/libkeynote", "lib/libradius"]),
        ("terminal", "Terminal handling and line editing.", [
            "lib/libcurses", "lib/libedit", "lib/libform", "lib/libmenu", "lib/libpanel"]),
        ("system", "The rest of the system libraries.", [
            "lib/libutil", "lib/libkvm", "lib/libevent", "lib/libz", "lib/libexpat", "lib/libelf",
            "lib/libfuse", "lib/libpcap", "lib/libusbhid", "lib/libossaudio", "lib/libsndio",
            "lib/libagentx", "lib/librpcsvc", "lib/libarch", "lib/libl", "lib/liby"]),
        ("include", "The headers installed under /usr/include.", ["include"]),
    ]),
    ("development-tools", "What builds the system and the programs on it.", [
        ("compiler", "The compiler, the linker and the C++ runtime.", [
            "gnu/usr.bin/clang", "gnu/lib/libcxx", "gnu/lib/libcxxabi", "gnu/lib/libclang_rt",
            "gnu/lib/libcompiler_rt", "libexec/tradcpp"]),
        ("build", "Build tools and source generators.", [
            "make", "yacc", "lex", "m4", "patch", "mkdep", "lorder", "nm", "gprof", "libtool", "pkgconf",
            "rcs", "unifdef", "indent", "ctags", "cap_mkdb", "getcap", "gencat", "mklocale", "rpcgen",
            "crunchgen", "config", "libexec/reorder_kernel", "cvs", "fgen"]),
        ("debug", "Tracing and inspecting running programs and the kernel.", [
            "ktrace", "kdump", "ctfconv", "ctfdump", "btrace", "procmap", "kgmon"]),
    ]),
    ("system-services", "Daemons and administration: what operates the system once it is up. OpenBSD's sbin/ and usr.sbin/, grouped by what they manage rather than by where they install.", [
        ("storage", "Disks, partitions, file systems, mounts, swap and backup.", [
            "disklabel", "fdisk", "pdisk", "mknod", "vnconfig", "scsi", "atactl", "bioctl", "badsect", "clri",
            "fsck", "fsck_ffs", "fsck_ext2fs", "fsck_msdos", "fsdb", "fsirand", "newfs", "newfs_ext2fs",
            "newfs_msdos", "growfs", "tunefs", "dumpfs", "scan_ffs", "ncheck_ffs", "mount", "umount",
            "mount_ffs", "mount_ext2fs", "mount_msdos", "mount_cd9660", "mount_nfs", "mount_ntfs",
            "mount_tmpfs", "mount_udf", "mount_vnd", "swapctl", "swapon", "dump", "restore", "savecore",
            "quotacheck", "quot", "edquota", "quotaon", "repquota", "installboot", "makefs", "mtree", "rmt",
            "iscsid", "iscsictl", "rdsetroot", "mt", "chio", "fdformat", "mksuncd", "mkuboot"]),
        ("network", "Interfaces, addresses, routes, the packet filter, DHCP and name resolution.", [
            "ifconfig", "route", "ping", "pfctl", "pflogd", "arp", "ndp", "rarpd", "traceroute", "tcpdump",
            "tcpdrop", "trpt", "lldp", "lldpd", "ifstated", "dhcpleased", "dhcp6leased", "dhcpleasectl",
            "dhcp6leasectl", "dhcpd", "dhcrelay", "dhcrelay6", "rad", "slaacd", "slaacctl", "resolvd",
            "unwind", "unwindctl", "bpflogd", "hostapd"]),
        ("routing", "Routing daemons and their control programs.", [
            "bgpd", "bgpctl", "bgplgd", "bgplg", "ospfd", "ospfctl", "ospf6d", "ospf6ctl", "ripd", "ripctl",
            "ldpd", "ldpctl", "eigrpd", "eigrpctl", "dvmrpd", "dvmrpctl", "rtrd", "rtrctl", "route6d",
            "mrouted", "mrinfo", "mtrace", "map-mbone", "rpki-client"]),
        ("daemons", "Servers: web, mail, time, DNS, LDAP, logging, cron, inetd.", [
            "httpd", "slowcgi", "smtpd", "libexec/mail.local", "mailwrapper", "libexec/lockspool",
            "libexec/comsat", "libexec/spamd", "libexec/spamd-setup", "libexec/spamlogd", "spamdb",
            "libexec/ftpd", "ftp-proxy", "tftpd", "tftp-proxy", "relayd", "relayctl", "identd",
            "libexec/fingerd", "libexec/talkd", "ntpd", "rdate", "zdump", "zic", "unbound", "nsd", "ldapd",
            "ldapctl", "inetd", "syslogd", "syslogc", "newsyslog", "cron", "ldomd", "ldomctl", "snmpd",
            "libexec/snmpd"]),
        ("vpn", "IPsec, IKE, PPP and L2TP.", [
            "iked", "ikectl", "isakmpd", "ipsecctl", "sasyncd", "npppd", "npppctl", "pppd"]),
        ("auth", "Authentication back ends, RADIUS and tokens.", [
            "libexec/login_passwd", "libexec/login_chpass", "libexec/login_lchpass", "libexec/login_ldap",
            "libexec/login_radius", "libexec/login_reject", "libexec/login_skey", "libexec/login_token",
            "libexec/login_yubikey", "tokenadm", "tokeninit", "radiusd", "radiusctl", "authpf",
            "libexec/security"]),
        ("crypto-tools", "Certificates, signatures and keys from the command line.", [
            "openssl", "signify", "htpasswd", "keynote", "acme-client", "ocspcheck"]),
        ("nfs-rpc", "NFS and the RPC services.", [
            "mountd", "nfsd", "portmap", "rpc.bootparamd", "rpc.lockd", "rpc.statd", "libexec/rpc.rquotad",
            "libexec/rpc.rstatd", "libexec/rpc.rusersd", "libexec/rpc.rwalld", "amd", "mopd", "rbootd"]),
        ("yp", "The YP/NIS directory service.", [
            "ypserv", "ypbind", "ypldap", "yppoll", "ypset", "ypcat", "ypmatch", "ypwhich"]),
        ("hardware", "Talking to the kernel about devices: sysctl, dmesg, consoles, buses, power, sensors.", [
            "sysctl", "dmesg", "kbd", "wsconsctl", "wsconscfg", "wsfontload", "wsmoused", "ldattach",
            "pcidump", "usbdevs", "usbhidaction", "usbhidctl", "gpioctl", "eeprom", "memconfig", "acpidump",
            "sensorsd", "apmd", "apm", "hotplugd", "watchdogd", "ractl"]),
        ("monitoring", "Statistics and accounting.", [
            "vmstat", "systat", "iostat", "pstat", "ipcs", "ipcrm", "pctr", "kstat", "sa", "ac", "accton"]),
        ("accounts", "Users, groups and the system databases built from them.", [
            "adduser", "user", "vipw", "chroot", "pwd_mkdb", "dev_mkdb", "kvm_mkdb", "netgroup_mkdb"]),
        ("print", "Printing.", ["lpd", "lpr"]),
        ("virtualization", "vmm(4)'s daemon and control program, and the guest-host channel.", [
            "vmd", "vmctl", "hostctl"]),
        ("packages", "Packages, firmware, patches and upgrades.", [
            "pkg_add", "fw_update", "syspatch", "sysupgrade", "sysmerge"]),
    ]),
    ("init", "What runs between the kernel and the first login: init, the rc scripts, the terminals.", [
        ("init", "Process 1 and how the system goes down.", ["init", "reboot", "shutdown", "nologin"]),
        ("rc", "The start-up scripts and their control; terminals and login prompts.", [
            "etc/rc", "etc/rc.conf", "etc/rc.d", "etc/netstart", "etc/daily", "etc/weekly", "etc/monthly",
            "etc/changelist", "rcctl", "libexec/getty", "etc/gettytab", "etc/ttys.pty", "ttyflags"]),
    ]),
    ("base-config", "The files of /etc that belong to no single program: the users and groups the system is born with, the device nodes, the protocol tables, the skeletons and examples.", [
        ("etc", "OpenBSD's etc/ apart from the rc scripts (init/rc).", [
            "etc/master.passwd", "etc/group", "etc/shells", "etc/services", "etc/protocols", "etc/rpc",
            "etc/MAKEDEV.mi", "etc/MAKEDEV.common", "etc/MAKEDEV.sub", "etc/MAKEDEV.man", "etc/MAKEDEV.mansub",
            "etc/mtree", "etc/moduli", "etc/skel", "etc/examples", "etc/mail", "etc/motd", "etc/ksh.kshrc",
            "etc/locate.rc", "etc/newsyslog.conf", "etc/syslog.conf", "etc/pf.conf", "etc/pf.os",
            "etc/ntpd.conf", "etc/nsd.conf", "etc/unbound.conf", "etc/ftpusers", "etc/fbtab.head",
            "etc/fbtab.tail", "etc/signify", "etc/rpki", "etc/minfree", "etc/root", "etc/crontab",
            "etc/mailer.conf", "etc/ppp", "etc/amd", "etc/etc.<arch>"]),
    ]),
    ("distrib", "How a release is made: the install sets, the installer and its ramdisk, and the shared data of share/ that belongs to no program.", [
        ("sets", "The install sets and their lists.", ["distrib/sets", "distrib/notes", "distrib/syspatch"]),
        ("installer", "The installer, its ramdisk and the per-architecture media.", [
            "distrib/miniroot", "distrib/special", "distrib/<arch>"]),
        ("share", "zoneinfo, locale, dictionaries, terminal types: data for everyone.", ["share"]),
    ]),
]

TOPLEVEL_README = """# EmiBSD Userland

The monorepo of EmiBSD's own userland: the programs, libraries and configuration that run
above the [Kernel](https://github.com/EmiBSD/Kernel). Phase 3 of the project: until the
kernel's redesign closes at N9, EmiBSD runs OpenBSD's base system unmodified; this repository
is where the system that replaces it is written.

## Layout

Grouped by what each part does, not by where it installs (OpenBSD's `bin/`, `sbin/`,
`usr.bin/`, `usr.sbin/` split by install path; that split, root partition only and linked
static or not, is a build attribute here). Every directory's `README.md` says what it is for
and which programs of OpenBSD's base system (at the pin of `Kernel/reference/PINNED.md`) it
covers, so nothing is forgotten and nothing is listed twice.

```
{tree}```

The lists are the map to what OpenBSD's base system provides, not a porting list: the
programs written here are EmiBSD's own.

New code is ISC (`LICENSE`).
"""


def main() -> int:
    # Coverage: every program of these directories must be mapped exactly once.
    sources = {}
    for d in ["bin", "sbin", "usr.bin", "usr.sbin", "libexec", "lib"]:
        names = sorted(n for n in os.listdir(SRC / d)
                       if not n.lower().startswith("makefile") and n != "CVS"
                       and not n.endswith(".inc") and not n.endswith(".mk"))
        sources[d] = set(names)
    seen = {}
    dup = []
    for cat, _, leaves in LAYOUT:
        for leaf, _, progs in leaves:
            for p in progs:
                key = p
                if key in seen:
                    dup.append((p, seen[key], f"{cat}/{leaf}"))
                seen[key] = f"{cat}/{leaf}"
    # Resolve bare names against bin/sbin/usr.bin/usr.sbin; "dir/name" against that dir.
    covered = {d: set() for d in sources}
    unknown = []
    for p in seen:
        if "/" in p:
            d, _, n = p.partition("/")
            if d in sources:
                if n in sources[d]:
                    covered[d].add(n)
                else:
                    unknown.append(p)
            continue
        hits = [d for d in ["bin", "sbin", "usr.bin", "usr.sbin"] if p in sources[d]]
        if not hits and not (SRC / p).is_dir():   # a whole top-level tree: include, share
            unknown.append(p)
        for d in hits:
            covered[d].add(p)
    missing = {d: sorted(sources[d] - covered[d]) for d in sources}
    missing = {d: m for d, m in missing.items() if m}
    if dup or unknown or missing:
        print("duplicates:", dup)
        print("unknown:", unknown)
        print("missing:", missing)
        return 1

    # Where does each program live in OpenBSD? For the README lines.
    def origin(p: str) -> str:
        if "/" in p:
            return p
        hits = [d for d in ["bin", "sbin", "usr.bin", "usr.sbin"] if p in sources[d]]
        return f"{hits[0]}/{p}" if hits else p

    tree_lines = []
    for cat, purpose, leaves in LAYOUT:
        tree_lines.append(f"{cat}/")
        (OUT / cat).mkdir(parents=True, exist_ok=True)
        cat_md = [f"# {cat}", "", purpose, "", "| Directory | What |", "|---|---|"]
        for i, (leaf, what, progs) in enumerate(leaves):
            last = i == len(leaves) - 1
            tree_lines.append(f"{'└── ' if last else '├── '}{leaf:<16} {what}")
            cat_md.append(f"| `{leaf}/` | {what} |")
            d = OUT / cat / leaf
            d.mkdir(parents=True, exist_ok=True)
            lines = [f"# {cat}/{leaf}", "", what, "",
                     "Covers, from OpenBSD's base system at the pin (origin directory in OpenBSD's `src`):", ""]
            for p in progs:
                o = origin(p)
                name = o.rsplit("/", 1)[-1]
                lines.append(f"- `{name}` ({o})")
            lines += ["", "Nothing written yet."]
            (d / "README.md").write_text("\n".join(lines) + "\n")
        cat_md += ["", "Nothing written yet."]
        (OUT / cat / "README.md").write_text("\n".join(cat_md) + "\n")
    (OUT / "README.md").write_text(TOPLEVEL_README.format(tree="\n".join(tree_lines) + "\n"))
    total = sum(len(progs) for _, _, leaves in LAYOUT for _, _, progs in leaves)
    print(f"ok: {len(LAYOUT)} categories, {sum(len(l) for _, _, l in LAYOUT)} leaves, {total} entries;",
          {d: len(s) for d, s in sources.items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
