#!/usr/bin/env python3
# Copyright (c) 2026 Emilio Navarrete Lineros <enavarre@outlook.com>
#
# Permission to use, copy, modify, and distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
"""Build the inherited base system for EmiBSD with the base system's own make.

usage: world.py <arch> [step...]

The steps, in order (the first eight, through sets, when none is named):

  tree      target/<arch>/src: every inherited directory's src/ copied back to its path in
            the base system's tree, so each Makefile finds its neighbours where it expects
            them (${.CURDIR}/.., BSDSRCDIR); patches/ applied to the copy, src/ only read;
            __OpenBSD__ renamed __EmiBSD__ in the copy
  host      the base system's own tools the build runs on the development host (rpcgen,
            yacc, lex, mklocale, strfile, mkdict, mkindex, makefs, pax, mtree, sha256,
            pwd_mkdb, tic), built by the same make, into target/host/bin
  obj       `make obj` over lib/ and the trees of the base
  includes  target/<arch>/sysroot/usr/include, by include/Makefile's own targets
  lib       lib/ as Makefile.cross builds it: csu and libc first, then the rest
  base      every directory the trees' SUBDIR reach, each built and installed on its own;
            the failures are listed in target/<arch>/failed
  etc       etc/Makefile's distribution-etc-root-var: /etc, /root, /var, pwd.db, etc.tgz;
            the manual's mandoc.db
  sets      target/<arch>/sets: base, comp, game and man as gzipped archives, from the
            sysroot by distrib/sets/lists, and their SHA256
  retry     the directories that failed, again
  image     target/<arch>/ramdisk.ffs: the mtree skeleton, the programs, ld.so and the
            shared libraries, /etc from the tree, /dev by MAKEDEV's `ramdisk` target, made
            by the base system's makefs with the owners, modes and nodes the metalog
            recorded

make is target/host/bin/make (`just host-make`); the compiler is DevTools' clang, whose
default target is EmiBSD's (EMIBSD_LLVM_BIN). Nothing is installed on the host and nothing
is written outside target/.

A build is reproducible: two builds of one commit, in any two checkouts, give the same
sets and the same SHA256. Every time a build writes into what it ships is
$SOURCE_DATE_EPOCH, or the commit's time when it is unset (the reproducible builds' rule),
and no path of the checkout reaches a file.
"""
import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "base"
TREES = ("etc", "data", "distrib")   # their entries keep their full paths under src/
LLVM = Path(os.environ.get("EMIBSD_LLVM_BIN",
                           Path.home() / "devel/emibsd/toolchains/llvm-23.1.4+emibsd.1-aarch64-apple-darwin/bin"))
EPOCH = os.environ.get("SOURCE_DATE_EPOCH") or \
    subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--format=%ct"], capture_output=True,
                   text=True, check=True).stdout.strip()
MACHINES = {"arm64": dict(MACHINE="arm64", MACHINE_ARCH="aarch64", MACHINE_CPU="aarch64",
                          triple="aarch64-emibsd-emibsd8.0")}


def inherited():
    """(directory, the paths it holds in the base system's tree) of every inherited entry."""
    for status in sorted(BASE.rglob("STATUS")):
        d = status.parent
        if not status.read_text().startswith("inherited"):
            continue
        with open(d / "UPSTREAM.toml", "rb") as fh:
            paths = tomllib.load(fh)["upstream"]["path"]
        yield d, paths


def step_tree(arch: str, out: Path) -> None:
    view = out / "src"
    if view.exists():
        shutil.rmtree(view)
    view.mkdir(parents=True)
    # The metalog records what the sysroot holds: new with a new sysroot, kept with one that
    # stays, where a Makefile that installs only what changed (`cmp -s || install`, the
    # libraries' headers) records nothing for what it leaves in place.
    if not (out / "sysroot").exists():
        (out / "metalog").unlink(missing_ok=True)
    n = 0
    for d, paths in inherited():
        tree = d.relative_to(BASE).parts[0] in TREES
        if tree:
            shutil.copytree(d / "src", view, symlinks=True, dirs_exist_ok=True)
        else:
            shutil.copytree(d / "src", view / paths[0], symlinks=True, dirs_exist_ok=True)
        for patch in sorted((d / "patches").glob("*.patch")):
            where = view if tree else view / paths[0]
            # Exactly (no fuzz: a patch that no longer fits the pin must fail), in batch
            # mode, leaving no backup files in the tree.
            subprocess.run(["patch", "-s", "-p1", "-F", "0", "-V", "none", "-t", "-N", "-d", str(where),
                            "-i", str(patch)], check=True)
        n += 1
    # In the userland __OpenBSD__ becomes __EmiBSD__ (the user's decision of 2026-11-04): the
    # compiler predefines __EmiBSD__ alone, so every place the inherited C tests or names
    # the macro is made to name __EmiBSD__, here in the copy; src/ stays the pin.
    renamed = 0
    for f in view.rglob("*"):
        if f.is_file() and not f.is_symlink():
            data = f.read_bytes()
            if b"__OpenBSD__" in data:
                f.write_bytes(data.replace(b"__OpenBSD__", b"__EmiBSD__"))
                renamed += 1
    print(f"tree: {n} inherited entries in {view}; __OpenBSD__ renamed in {renamed} files")


HOST = ROOT / "target" / "host"
# The tools a Makefile of the base system runs while building, built for the host first so
# no host program of the same name (macOS's rpcgen, bison, flex) is ever used.
HOST_TOOLS = ("usr.bin/rpcgen", "usr.bin/yacc", "usr.bin/lex", "usr.bin/mklocale",
              # fortune's data files are indexed by it; its index is in network byte order
              "games/fortune/strfile",
              # boggle's dictionary and its index, both text
              "games/boggle/mkdict", "games/boggle/mkindex")
# A host tool's own header, forced in after compat.h (tools/host).
HOST_HEADERS = {"usr.bin/mklocale": "mklocale.h"}


def host_cc() -> str:
    sdk = subprocess.run(["xcrun", "--show-sdk-path"], capture_output=True, text=True, check=True).stdout.strip()
    return (f"{LLVM}/clang --target={os.uname().machine}-apple-macos -isysroot {sdk} "
            f"-include {ROOT / 'tools/host/compat.h'}")


def make_env(arch: str, out: Path) -> dict:
    m = MACHINES[arch]
    env = dict(os.environ)
    env.update(MACHINE=m["MACHINE"], MACHINE_ARCH=m["MACHINE_ARCH"], MACHINE_CPU=m["MACHINE_CPU"])
    env["PATH"] = f"{HOST / 'bin'}:{env['PATH']}"
    env["STRIP"] = f"{LLVM}/llvm-strip"
    env["WORLD_METALOG"] = str(out / "metalog")
    # For the tools built with owners.h: the tree whose owners the metalog holds, and the
    # tree's own users and groups, which give the recorded names their numbers.
    env["WORLD_DESTDIR"] = str(out / "sysroot")
    env["WORLD_PASSWD"] = str(out / "src/etc/master.passwd")
    env["WORLD_GROUP"] = str(out / "src/etc/group")
    # The objects, root's and wheel's when a re-link kit archives them (owners.h).
    env["WORLD_OBJDIR"] = str(out / "obj")
    # clang's __DATE__ and __TIME__, owners.h's clamp of the tree's times.
    env["SOURCE_DATE_EPOCH"] = EPOCH
    # sort.sh's seed for -R: 32 bytes (the host's sort takes no more) from the epoch.
    seed = HOST / "random-source"
    digest = hashlib.sha256(f"emibsd sort -R {EPOCH}".encode()).digest()
    if not seed.exists() or seed.read_bytes() != digest:
        seed.parent.mkdir(parents=True, exist_ok=True)
        seed.write_bytes(digest)
    env["WORLD_RANDOM"] = str(seed)
    return env


# The stand-ins for a build run by a user (tools/host): they record in the metalog what
# they cannot do (owners, groups, device nodes) instead of failing.
WRAPPERS = {"install": "install.sh", "chown": "chown.sh", "chgrp": "chgrp.sh", "chmod": "chmod.sh",
            "mknod": "mknod.sh", "gzip": "gzip.sh", "sort": "sort.sh"}


def step_host(arch: str, out: Path) -> None:
    """Each tool by its own Makefile, for the host: no target start-up files or libc."""
    (HOST / "bin").mkdir(parents=True, exist_ok=True)
    for name, script in WRAPPERS.items():
        link = HOST / "bin" / name
        link.unlink(missing_ok=True)
        link.symlink_to(ROOT / "tools/host" / script)
    # Some rules call the binary tools by name, not through ${AR} (bsd.lib.mk's `ar cqD`):
    # under those names the build finds DevTools' LLVM ones, never the host's.
    for name in ("ar", "ranlib", "nm", "objcopy", "objdump", "readelf", "size", "strings"):
        link = HOST / "bin" / name
        link.unlink(missing_ok=True)
        link.symlink_to(LLVM / f"llvm-{name}")
    for tool in HOST_TOOLS:
        obj = HOST / "obj" / tool
        obj.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, MAKEOBJDIR=str(obj))
        extra = f" -include {ROOT / 'tools/host' / HOST_HEADERS[tool]}" if tool in HOST_HEADERS else ""
        subprocess.run([str(HOST / "bin/make"), "-m", str(out / "src/share/mk"), f"CC={host_cc()}{extra}",
                        "NOMAN=1", "CRTBEGIN=", "CRTEND=", "LIBCRT0=", "LIBC=", "WARNINGS=no"],
                       cwd=out / "src" / tool, env=env, check=True)
        prog = Path(tool).name
        shutil.copy2(obj / prog, HOST / "bin" / prog)
        print(f"host: {HOST / 'bin' / prog}")
    host_makefs(out)
    host_base(out)
    host_base_tools(out)
    host_tic(out)


def host_tic(out: Path) -> None:
    """tic(1) for the host, on libcurses built for the host from the same tree: the terminfo
    database share/termtypes compiles must be the base system's tic's, never the host's
    (macOS's lays it out in other directories)."""
    env = dict(os.environ, PATH=f"{HOST / 'bin'}:{os.environ['PATH']}")   # its ar is LLVM's
    lib = HOST / "obj/lib/libcurses"
    lib.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(HOST / "bin/make"), "-m", str(out / "src/share/mk"), f"CC={host_cc()}",
                    f"HOSTCC={host_cc()}", "AWK=awk", "NOMAN=1", "NOPIC=1", "NOPROFILE=1", "WARNINGS=no"],
                   cwd=out / "src/lib/libcurses", env=dict(env, MAKEOBJDIR=str(lib)), check=True)
    obj = HOST / "obj/usr.bin/tic"
    obj.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(HOST / "bin/make"), "-m", str(out / "src/share/mk"), f"CC={host_cc()}",
                    "NOMAN=1", "CRTBEGIN=", "CRTEND=", "LIBCRT0=", "LIBC=", "DPADD=",
                    f"LDADD={lib / 'libcurses.a'}", "WARNINGS=no"],
                   cwd=out / "src/usr.bin/tic", env=dict(env, MAKEOBJDIR=str(obj)), check=True)
    shutil.copy2(obj / "tic", HOST / "bin/tic")
    print(f"host: {HOST / 'bin/tic'}")


# The base system's headers the host tools take beside the host's own (after them, so a
# header both have is the host's), and the libc and libutil sources compiled for the host
# into libbasehost.a: ohash (make's generate), the hash functions (sha256, mtree), pw_scan
# (pwd_mkdb), recallocarray (mandoc).
BASE_HOST_HEADERS = ("lib/libutil/ohash.h", "include/md5.h", "include/rmd160.h", "include/sha1.h",
                     "include/sha2.h")
BASE_HOST_SOURCES = ("lib/libutil/ohash.c", "lib/libutil/passwd.c", "lib/libc/stdlib/recallocarray.c", "lib/libc/hash/md5.c",
                     "lib/libc/hash/rmd160.c", "lib/libc/hash/sha1.c", "lib/libc/hash/sha256.c",
                     "lib/libc/hash/sha512.c")
# libc's hash helpers (MD5File, SHA256End, ...), each made from helper.c as its Makefile.inc
# makes it: the hash's name and header, and the one context type of the SHA-2 family.
HASH_HELPERS = (("MD5", "md5.h"), ("RMD160", "rmd160.h"), ("SHA1", "sha1.h"), ("SHA224", "sha2.h"),
                ("SHA256", "sha2.h"), ("SHA384", "sha2.h"), ("SHA512", "sha2.h"), ("SHA512_256", "sha2.h"))


def host_base(out: Path) -> None:
    """What the base system's tools built for the host take from its libc and libutil and the
    host lacks: their headers into include-base, their objects into libbasehost.a, with
    tools/host's hash-host.c (the hash block functions an architecture's file gives) and
    owners.c (owners.h's functions)."""
    src = out / "src"
    inc, lib, obj = HOST / "include-base", HOST / "lib", HOST / "obj/base"
    for d in (inc, lib, obj / "hidden"):
        d.mkdir(parents=True, exist_ok=True)
    for h in BASE_HOST_HEADERS:
        shutil.copy2(src / h, inc / Path(h).name)
    # libc's own declarations of its hash internals, alone: the rest of lib/libc/hidden
    # wraps every system header.
    for h in ("sha1.h", "sha2.h"):
        shutil.copy2(src / "lib/libc/hidden" / h, obj / "hidden" / h)
    pwd_base(src / "include/pwd.h", inc / "pwd-base.h")
    sources = [ROOT / "tools/host/hash-host.c", ROOT / "tools/host/owners.c"] + [src / s for s in BASE_HOST_SOURCES]
    helper = (src / "lib/libc/hash/helper.c").read_text()
    for name, header in HASH_HELPERS:
        text = helper.replace("hashinc", header).replace("HASH", name)
        if header == "sha2.h":
            text = re.sub(r"SHA512_256_CTX" if name == "SHA512_256" else r"SHA[0-9][0-9][0-9]_CTX", "SHA2_CTX", text)
        c = obj / f"{name.lower()}hl.c"
        c.write_text(text)
        sources.append(c)
    objs = []
    for c in sources:
        o = obj / (c.stem + ".o")
        extra = f"-include {inc / 'pwd-base.h'}" if c.name == "passwd.c" else ""
        subprocess.run(f"{host_cc()} -I{ROOT / 'tools/host/include'} -I{obj / 'hidden'} -idirafter {inc} "
                       f"{extra} -c {c} -o {o}", shell=True, check=True)
        objs.append(str(o))
    archive = lib / "libbasehost.a"
    archive.unlink(missing_ok=True)
    subprocess.run([f"{LLVM}/llvm-ar", "rcs", str(archive), *objs], check=True)
    print(f"host: {archive}")


def pwd_base(header: Path, dst: Path) -> None:
    """The base system's pwd.h constants (_PW_*, _PASSWORD_*) the host's pwd.h lacks, and
    libutil's pw_scan, for pwd_mkdb: the host's struct passwd has the base system's fields in
    the base system's order, so only these are missing."""
    lines = ["/* The base system's pwd.h constants the host's lacks: written by tools/world.py. */",
             "#include <pwd.h>"]
    for m in re.finditer(r"^#define\s+(_PW_\w+|_PASSWORD_\w+)\s+(.*?)\s*(/\*.*)?$", header.read_text(), re.M):
        lines += [f"#ifndef {m.group(1)}", f"#define {m.group(1)} {m.group(2)}", "#endif"]
    lines.append("int pw_scan(char *, struct passwd *, int *);")
    dst.write_text("\n".join(lines) + "\n")


# The base system's tools built for the host on libbasehost.a: what each is called in
# target/host/bin, what it compiles with beyond compat.h, and what else it links. Those
# etc/Makefile's distribution runs take tools/host/owners.h, so they see DESTDIR's owners
# as the metalog records them and the tree's users and groups.
OWNERS = f"-include {ROOT / 'tools/host/owners.h'}"
BASE_TOOLS = {"bin/pax": (("pax", "tar"), OWNERS, ""),     # tar: a re-link kit's archive
              "usr.sbin/mtree": (("mtree",), OWNERS, ""),
              "bin/md5": (("sha256",), OWNERS, "-lresolv"),     # b64_ntop is libresolv's on the host
              "usr.sbin/pwd_mkdb": (("pwd_mkdb",), f"{OWNERS} -include {HOST / 'include-base/pwd-base.h'}", ""),
              # makewhatis, for share/man's mandoc.db; MACHINE, which the base system's
              # machine/param.h gives, only steers man's search
              "usr.bin/mandoc": (("makewhatis",), "-DMACHINE='\"unknown\"'", "-lz")}


def host_base_tools(out: Path) -> None:
    inc = HOST / "include-base"
    for tool, (names, cflags, libs) in BASE_TOOLS.items():
        obj = HOST / "obj" / tool
        obj.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, MAKEOBJDIR=str(obj), PATH=f"{HOST / 'bin'}:{os.environ['PATH']}")
        cc = f"{host_cc()} -I{ROOT / 'tools/host/include'} -idirafter {inc} {cflags}"
        subprocess.run([str(HOST / "bin/make"), "-m", str(out / "src/share/mk"), f"CC={cc}", "NOMAN=1",
                        "CRTBEGIN=", "CRTEND=", "LIBCRT0=", "LIBC=", "LDSTATIC=", "WARNINGS=no",
                        # the library, not the target's, is what a tool relinks after
                        f"DPADD={HOST / 'lib/libbasehost.a'}", f"LDADD={HOST / 'lib/libbasehost.a'} {libs}"],
                       cwd=out / "src" / tool, env=env, check=True)
        prog = subprocess.run([str(HOST / "bin/make"), "-m", str(out / "src/share/mk"), "-V", "PROG"],
                              cwd=out / "src" / tool, env=env, capture_output=True, text=True).stdout.strip()
        for name in names:
            shutil.copy2(obj / prog, HOST / "bin" / name)
            print(f"host: {HOST / 'bin' / name}")


def target_hostcc() -> str:
    """HOSTCC for the target builds: the host compiler, with libutil's ohash."""
    return f"{host_cc()} -idirafter {HOST / 'include-base'} {HOST / 'lib/libbasehost.a'}"


# The base system's headers makefs needs that the host lacks, copied from the tree for its
# host build only; sys/uuid.h's uuid_t is renamed there, the host having its own.
MAKEFS_HEADERS = {"sys/ufs": "ufs", "sys/msdosfs": "msdosfs", "sys/sys/disklabel.h": "sys/disklabel.h",
                  "sys/sys/uuid.h": "sys/uuid.h"}


def host_makefs(out: Path) -> None:
    """makefs(8) for the host (tools/host/makefs.h, makefs-host.c): with scan_scaled() and
    getdiskbyname() compiled from libutil's and libc's own sources."""
    import re
    inc = HOST / "include-makefs"
    if inc.exists():
        shutil.rmtree(inc)
    for src, dst in MAKEFS_HEADERS.items():
        s, d = out / "src" / src, inc / dst
        d.parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree if s.is_dir() else shutil.copy2)(s, d)
    (inc / "machine").mkdir()
    shutil.copy2(out / f"src/sys/arch/{os.uname().machine.replace('x86_64', 'amd64')}/include/disklabel.h",
                 inc / "machine/disklabel.h")
    for h in inc.rglob("*.h"):
        text = h.read_text()
        if re.search(r"\buuid_t\b", text):
            h.write_text(re.sub(r"\buuid_t\b", "emibsd_uuid_t", text))
    flags = f"-I{ROOT / 'tools/host/include'} -I{inc}"
    helpers = HOST / "obj/makefs-host"
    if helpers.exists():
        shutil.rmtree(helpers)
    helpers.mkdir(parents=True)
    objs = []
    # The libc and libutil sources take makefs.h like makefs itself (getdiskbyname's
    # cgetent is the wrapped one); the wrappers' own file must not, or they would call
    # themselves.
    for c, wrapped in ((ROOT / "tools/host/makefs-host.c", False), (out / "src/lib/libutil/fmt_scaled.c", True),
                       (out / "src/lib/libc/gen/disklabel.c", True)):
        o = helpers / (c.stem + ".o")
        include = f"-include {ROOT / 'tools/host/makefs.h'}" if wrapped else ""
        subprocess.run(f"{host_cc()} {include} {flags} -c {c} -o {o}", shell=True, check=True)
        objs.append(str(o))
    lib = helpers / "libmakefshost.a"
    subprocess.run([f"{LLVM}/llvm-ar", "rcs", str(lib), *objs], check=True)
    obj = HOST / "obj/usr.sbin/makefs"
    obj.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(HOST / "bin/make"), "-m", str(out / "src/share/mk"),
                    f"CC={host_cc()} -include {ROOT / 'tools/host/makefs.h'} {flags}",
                    "NOMAN=1", "CRTBEGIN=", "CRTEND=", "LIBCRT0=", "LIBC=", "DPADD=", f"LDADD={lib}",
                    "WARNINGS=no"],
                   cwd=out / "src/usr.sbin/makefs", env=dict(os.environ, MAKEOBJDIR=str(obj)), check=True)
    shutil.copy2(obj / "makefs", HOST / "bin/makefs")
    print(f"host: {HOST / 'bin/makefs'}")


def make(arch: str, out: Path, directory: str, *targets: str, extra=(), objdir=True) -> None:
    """Run the host make in the copied tree's `directory` with the cross settings."""
    m = MACHINES[arch]
    sysroot = out / "sysroot"
    cc = f"{LLVM}/clang --target={m['triple']} --sysroot={sysroot}"
    args = [str(ROOT / "target/host/bin/make"), "-m", str(out / "src/share/mk"),
            f"BSDSRCDIR={out / 'src'}", f"BSDOBJDIR={out / 'obj'}", f"DESTDIR={sysroot}",
            f"CC={cc}", f"CXX={LLVM}/clang++ --target={m['triple']} --sysroot={sysroot}",
            f"CPP={cc} -E", f"LD={LLVM}/ld.lld", f"AR={LLVM}/llvm-ar", f"RANLIB={LLVM}/llvm-ranlib",
            f"NM={LLVM}/llvm-nm", f"OBJCOPY={LLVM}/llvm-objcopy", f"STRIP={LLVM}/llvm-strip",
            f"HOSTCC={host_cc()}", "NOMAN=1", *extra, *targets]
    env = make_env(arch, out)
    if objdir:   # a directory whose Makefile works where it is (include/) gets none
        obj = out / "obj" / directory
        obj.mkdir(parents=True, exist_ok=True)
        env["MAKEOBJDIR"] = str(obj)
    subprocess.run(args, cwd=out / "src" / directory, env=env, check=True)


def mtree_entries(spec: Path) -> list:
    """The directories an mtree(8) specification lists (etc/mtree/4.4BSD.dist), in order, each
    with its keywords (uname, gname, mode), `/set` defaults applied: the skeleton OpenBSD's
    `make distrib-dirs` lays out before anything is installed."""
    stack, entries, defaults = [], [], {}
    for line in spec.read_text().splitlines():
        word = line.split("#", 1)[0].split()
        if not word:
            continue
        if word[0] == "/set":
            defaults.update(w.split("=", 1) for w in word[1:] if "=" in w)
            continue
        if word[0].startswith("/"):
            continue
        if word[0] == "..":
            stack.pop()
            continue
        keys = dict(defaults, **dict(w.split("=", 1) for w in word[1:] if "=" in w))
        if word[0] == ".":
            entries.append((".", keys))
            continue
        stack.append(word[0])
        entries.append(("/".join(stack), keys))
    return entries


def mtree_dirs(spec: Path) -> list:
    return [path for path, _ in mtree_entries(spec) if path != "."]


def distrib_dirs(out: Path, root: Path) -> None:
    for d in mtree_dirs(out / "src/etc/mtree/4.4BSD.dist"):
        (root / d).mkdir(parents=True, exist_ok=True)


def step_includes(arch: str, out: Path) -> None:
    sysroot = out / "sysroot"
    distrib_dirs(out, sysroot)
    # libc and the programs link -lcompiler_rt, which the base system builds from gnu/: the
    # compiler's runtime is DevTools', the builtins of its clang for this target.
    triple = MACHINES[arch]["triple"]
    resources = subprocess.run([f"{LLVM}/clang", "-print-resource-dir"], capture_output=True, text=True,
                               check=True).stdout.strip()
    shutil.copy2(Path(resources) / f"lib/{triple}/libclang_rt.builtins.a", sysroot / "usr/lib/libcompiler_rt.a")
    make(arch, out, "include", "includes", "copies", objdir=False)
    compiler_headers(out)


# What the ramdisk's /etc holds, from the tree (the arm64 files from etc/etc.<arch>), and
# the modes the base system's etc/Makefile installs them with.
ETC_FILES = {"etc/master.passwd": 0o600, "etc/group": 0o644, "etc/shells": 0o644,
             "etc/motd": 0o644, "etc/gettytab": 0o644, "etc/protocols": 0o644,
             "etc/services": 0o644, "etc/ksh.kshrc": 0o644, "etc/rc": 0o644,
             "etc/rc.conf": 0o644, "etc/netstart": 0o644, "etc/etc.<arch>/ttys": 0o644,
             "etc/etc.<arch>/login.conf": 0o644}
# The trees of the sysroot the ramdisk takes: the programs and what runs them (ld.so in
# usr/libexec, the shared libraries), not the headers and archives.
IMAGE_TREES = ("bin", "sbin", "usr/bin", "usr/sbin", "usr/libexec")
IMAGE_LIBS = re.compile(r"^lib.*\.so\.[0-9.]+$")


def copy_tree(src: Path, dst: Path, links: dict) -> None:
    """src into dst keeping hard links (one inode, several names) and symbolic links."""
    for path in sorted(src.rglob("*")):
        target = dst / path.relative_to(src)
        st = path.lstat()
        if path.is_symlink():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(os.readlink(path))
        elif path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif (st.st_dev, st.st_ino) in links:
            os.link(links[(st.st_dev, st.st_ino)], target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            links[(st.st_dev, st.st_ino)] = target


def read_metalog(path: Path, root: Path) -> dict:
    """The metalog's records under `root`, by path relative to it, later fields winning."""
    records = {}
    if not path.exists():
        return records
    base = str(root.resolve())
    for line in path.read_text().splitlines():
        first, *fields = line.split()
        full = str(Path(first).resolve()) if Path(first).exists() else first
        if not full.startswith(base + "/"):
            continue
        records.setdefault(full[len(base) + 1:], {}).update(f.split("=", 1) for f in fields)
    return records


def ids(staging: Path) -> tuple:
    users = {l.split(":")[0]: int(l.split(":")[2]) for l in (staging / "etc/master.passwd").read_text().splitlines()
             if l and not l.startswith("#")}
    groups = {l.split(":")[0]: int(l.split(":")[2]) for l in (staging / "etc/group").read_text().splitlines()
              if l and not l.startswith("#")}
    return users, groups


def step_image(arch: str, out: Path) -> None:
    sysroot, staging = out / "sysroot", out / "ramdisk"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()
    entries = mtree_entries(out / "src/etc/mtree/4.4BSD.dist")
    for path, _ in entries:
        (staging / path).mkdir(parents=True, exist_ok=True)
    links = {}
    for tree in IMAGE_TREES:
        if (sysroot / tree).is_dir():
            copy_tree(sysroot / tree, staging / tree, links)
    for lib in (sysroot / "usr/lib").iterdir():
        if IMAGE_LIBS.match(lib.name):
            shutil.copy2(lib, staging / "usr/lib" / lib.name)
    modes = {}
    for src, mode in ETC_FILES.items():
        src = src.replace("<arch>", arch)
        dst = staging / "etc" / Path(src).name
        shutil.copy2(out / "src" / src, dst)
        dst.chmod(mode)
        modes[f"etc/{dst.name}"] = mode
    # The password databases etc/Makefile's distribution made with pwd_mkdb, when the etc
    # step has run: names for the ids, as getpwuid(3) reads them.
    for name, mode in (("passwd", 0o644), ("pwd.db", 0o644), ("spwd.db", 0o640)):
        if (out / "sysroot/etc" / name).exists():
            shutil.copy2(out / "sysroot/etc" / name, staging / "etc" / name)
            (staging / "etc" / name).chmod(mode)
            modes[f"etc/{name}"] = mode
    (staging / "etc/fstab").write_text("/dev/rd0a / ffs rw 1 1\n")
    # /dev by the base system's MAKEDEV, its nodes recorded by the mknod stand-in.
    devlog = out / "image-metalog"
    devlog.unlink(missing_ok=True)
    makedev = out / f"src/etc/etc.{arch}/MAKEDEV"
    shutil.copy2(makedev, staging / "dev/MAKEDEV")
    # Run from a build copy whose one difference is its PATH line: the script sets PATH to
    # the system's directories, which on the host lead to the host's mknod and chgrp, not to
    # the stand-ins. The image gets the script unchanged. bash, not the host's sh: the
    # script relies on `echo -n` and `local`, as the base system's sh has them;
    # MAKEDEV_PARTITIONS is the sysctl kern.maxpartitions it would ask the host.
    runner = out / "MAKEDEV.build"
    text = makedev.read_text()
    assert "\nPATH=/sbin:/usr/sbin:/bin:/usr/bin\n" in text, "MAKEDEV's PATH line moved"
    runner.write_text(text.replace("\nPATH=/sbin:/usr/sbin:/bin:/usr/bin\n",
                                   f"\nPATH={HOST / 'bin'}:/bin:/usr/bin\n"))
    env = make_env(arch, out)
    env.update(WORLD_METALOG=str(devlog), MAKEDEV_PARTITIONS="16")
    subprocess.run(["/bin/bash", str(runner), "ramdisk"], cwd=staging / "dev", env=env, check=True)
    # The table makefs's lstat reads: every path the mtree, the metalogs or the device
    # nodes speak of; the rest is root's and wheel's with the mode it has.
    users, groups = ids(staging)
    attrs = {}
    for path, keys in entries:
        attrs[path] = dict(keys)
    for path, rec in read_metalog(out / "metalog", sysroot).items():
        if (staging / path).exists():
            attrs.setdefault(path, {}).update(rec)
    for path, rec in read_metalog(devlog, staging).items():
        attrs.setdefault(path, {}).update(rec)
    lines = []
    for path, rec in sorted(attrs.items()):
        f = staging / path
        if not (f.exists() or f.is_symlink()):
            continue
        st = f.lstat()
        mode = int(rec["mode"], 8) if "mode" in rec and rec["mode"].isdigit() else st.st_mode & 0o7777
        kind = {"char": "c", "block": "b"}.get(rec.get("type", ""), "d" if f.is_dir() else "f")
        lines.append(f"{mode:o} {users.get(rec.get('uname', 'root'), 0)} {groups.get(rec.get('gname', 'wheel'), 0)} "
                     f"{kind} {rec.get('major', 0)} {rec.get('minor', 0)} {path}")
    (out / "attrs").write_text("\n".join(lines) + "\n")
    # rd(4) wants a disklabel: an `rdroot` entry the size of the tree, in the base system's
    # disktab form (etc/etc.arm64/disktab's), with room for the file system's own blocks.
    # Each inode once (sbin's hard links are one file), and a quarter more for the file
    # system's own blocks: the boot medium holds the kernel and this image together.
    inodes = {(s.st_dev, s.st_ino): s.st_size for s in (p.lstat() for p in staging.rglob("*"))
              if stat.S_ISREG(s.st_mode)}
    used = sum(inodes.values())
    cylinder = 2 * 768
    sectors = ((used * 5 // 4 // 512 + 32768) // cylinder + 1) * cylinder
    (out / "disktab").write_text(
        f"rdroot|ramdiskroot|RAM-disk root FS image:\\\n"
        f"\t:dt=rdroot:se#512:nc#{sectors // cylinder}:nt#2:ns#768:\\\n"
        f"\t:ta=4.2BSD:oa#0:pa#{sectors}:fa#512:ba#4096:\\\n"
        f"\t:oc#0:pc#{sectors}:\n")
    image = out / "ramdisk.ffs"
    image.unlink(missing_ok=True)
    env = dict(os.environ, WORLD_STAGING=str(staging), WORLD_ATTRS=str(out / "attrs"),
               WORLD_DISKTAB=str(out / "disktab"))
    subprocess.run([str(HOST / "bin/makefs"), "-o", "disklabel=rdroot,minfree=0,density=4096",
                    str(image), str(staging)], env=env, check=True)
    print(f"image: {image} ({image.stat().st_size // 1024} KiB, {len(lines)} entries with attributes)")


# The trees `make build` walks after the libraries, by their own Makefiles' SUBDIR. gnu/ is
# DevTools' (the compiler) or GPL (left out).
BASE_TREES = ("bin", "libexec", "sbin", "usr.bin", "usr.sbin", "share", "games")


# The base system's lld takes these by default when it targets the base system (its
# Driver.cpp, under __OpenBSD__): a version script may name symbols a library does not
# define (libc's Symbols.list names __data_start), and protected symbols stay preemptible.
# DevTools' lld for aarch64-emibsd does not yet; until it does (a DevTools matter), they are
# given to every link, and only to links, by a clang configuration file under target/.
LINK_DEFAULTS = ("--undefined-version", "--ignore-function-address-equality")
# Likewise the base system's clang leaves -Wpointer-sign off by default and upstream's turns
# it on: the Makefiles that build with -Werror (LibreSSL's) mix char and unsigned char
# pointers and expect no warning for it.
COMPILE_DEFAULTS = ("-Wno-pointer-sign",
                    # a warning DevTools' clang has and the pin's does not: kept, not fatal
                    # under -Werror (sshd-auth)
                    "-Wno-error=unused-but-set-global",
                    # implicit declarations stay warnings, as the base system's clang has
                    # them; the Makefiles that want them fatal still say so
                    # (bin/Makefile.inc's -Werror-implicit-function-declaration comes after)
                    "-Wno-error=implicit-function-declaration", "-Wno-error=implicit-int",
                    # the DWARF version the base system's clang emits by default, 2, not
                    # DevTools' 5, whose line table carries each source's MD5: a generated
                    # source naming the checkout's path (libelf's, libcurses') would differ
                    # from one checkout to the next in the libraries' debug information
                    "-fdebug-default-version=2")


def compiler_headers(out: Path) -> Path:
    """The compiler's own headers the base system's /usr/include does not have
    (stdnoreturn.h, arm_neon.h, ...): a build with DESTDIR set compiles with -nostdinc
    (bsd.sys.mk), which drops them, though the compiler provides them to every native
    build. Only names absent from the sysroot, so adding them after it changes nothing the
    sysroot already resolves."""
    resources = Path(subprocess.run([f"{LLVM}/clang", "-print-resource-dir"], capture_output=True,
                                    text=True, check=True).stdout.strip()) / "include"
    sysinc = out / "sysroot/usr/include"
    dst = out / "compiler-include"
    if dst.exists():
        shutil.rmtree(dst)
    for h in resources.rglob("*"):
        rel = h.relative_to(resources)
        if h.is_file() and not (sysinc / rel).exists():
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(h, dst / rel)
    return dst


def link_config(out: Path) -> Path:
    cfg = out / "clang-link.cfg"
    # The checkout's paths out of what is compiled (__FILE__ in an assert's message): the
    # tree, its objects and the sysroot as the base system's own build has them.
    prefixes = (f"-ffile-prefix-map={out / 'src'}=/usr/src", f"-ffile-prefix-map={out / 'obj'}=/usr/obj",
                f"-ffile-prefix-map={out / 'sysroot'}/=/")
    cfg.write_text("".join(f"{flag}\n" for flag in COMPILE_DEFAULTS + prefixes) +
                   f"-idirafter {out / 'compiler-include'}\n" +
                   "".join(f"$-Wl,{flag}\n" for flag in LINK_DEFAULTS))
    return cfg


# The answers a configure script gets by running a test program, which a cross build cannot
# do; these are what the base system's libc gives.
CONFIGURE_ANSWERS = {"ac_cv_func_memcmp_working": "yes", "ac_cv_func_malloc_0_nonnull": "yes",
                     "ac_cv_func_realloc_0_nonnull": "yes"}


# The host tools a Makefile names by path, or finds as the program it just built for the
# target, by the variable that names them, for that directory only (tput's TIC is the
# directory of tic's sources, not the program).
HOST_TOOL_VARS = {"share/termtypes": (("TIC", "tic"),),
                  "games/fortune/datfiles": (("STRFILE", "strfile"),),
                  "games/boggle": (("MKDICT", "mkdict"), ("MKINDEX", "mkindex")),
                  "share/man": (("MAKEWHATIS", "makewhatis"),)}


def make_walk(arch: str, out: Path, directory: str, *targets: str) -> int:
    """make in `directory` and down its SUBDIR, each subdirectory in its own `obj` (made by
    `make obj`); -k, so one failure does not hide the next. A parallel run that fails is run
    again serially: some Makefiles do not order a generated header before its users
    (librpcsvc's rpcgen output), which a serial run does. Returns make's status."""
    m = MACHINES[arch]
    sysroot = out / "sysroot"
    cfg = link_config(out)
    cc = f"{LLVM}/clang --config={cfg} --target={m['triple']} --sysroot={sysroot}"
    args = [str(HOST / "bin/make"), "-k", f"-j{os.cpu_count()}", "-m", str(out / "src/share/mk"),
            f"BSDSRCDIR={out / 'src'}", f"BSDOBJDIR={out / 'obj'}", f"DESTDIR={sysroot}",
            f"CC={cc}", f"CXX={LLVM}/clang++ --config={cfg} --target={m['triple']} --sysroot={sysroot}",
            f"CPP={cc} -E", f"LD={LLVM}/ld.lld", f"AR={LLVM}/llvm-ar", f"RANLIB={LLVM}/llvm-ranlib",
            f"NM={LLVM}/llvm-nm", f"OBJCOPY={LLVM}/llvm-objcopy", f"STRIP={LLVM}/llvm-strip",
            f"HOSTCC={target_hostcc()}",
            # DevTools' clang protects the stack by default, where the base system's relies on
            # RETGUARD for aarch64 and amd64: ld.so then needs its own stack-protector stubs,
            # the branch its Makefile has for the architectures that use the protector.
            "STACK_PROTECTOR=",
            # A cross build, as Makefile.cross says it: ld.so then does not run the test
            # program it just linked, which the host cannot execute (only ld.so reads it).
            f"CROSSDIR={sysroot}",
            # A re-link kit runs on the installed system, whose compiler is cc.
            "RELINK_CC=cc",
            *(f"{var}={HOST / 'bin' / tool}" for var, tool in HOST_TOOL_VARS.get(directory, ())),
            *targets]
    env = make_env(arch, out)
    if (out / "src" / directory / "Makefile.bsd-wrapper").exists():   # as bsd.subdir.mk does
        args[1:1] = ["-f", "Makefile.bsd-wrapper"]
        # Its configure must know it cross-compiles: the wrapper's own options, plus the
        # target in the GNU form its config.sub knows (it knows no EmiBSD) and the host.
        # The variable is the one its configure line passes (CONFIGURE_OPTS, or nsd's and
        # unbound's own); a library it is told is in /usr is in the sysroot's /usr.
        wrapper = (out / "src" / directory / "Makefile.bsd-wrapper").read_text()
        found = re.search(r"configure \$\{(CONFIGURE_OPTS\w*)\}", wrapper)
        if found:
            var = found.group(1)
            opts = subprocess.run(args[:1] + ["-f", "Makefile.bsd-wrapper", "-m", str(out / "src/share/mk"),
                                   "-V", var], cwd=out / "src" / directory, env=env,
                                  capture_output=True, text=True).stdout.strip()
            opts = re.sub(r"(--with-(?:ssl|libevent|libexpat))=/usr\b", rf"\1={sysroot}/usr", opts)
            args.append(f"{var}={opts} --host={m['MACHINE_ARCH']}-unknown-openbsd "
                        f"--build={os.uname().machine}-apple-darwin")
            # What a cross configure cannot learn by running a program, as the target answers.
            env.update(CONFIGURE_ANSWERS)
    status = subprocess.run(args, cwd=out / "src" / directory, env=env).returncode
    if status:
        serial = [a if not a.startswith("-j") else "-j1" for a in args]
        status = subprocess.run(serial, cwd=out / "src" / directory, env=env).returncode
    return status


def step_obj(arch: str, out: Path) -> None:
    (out / "obj").mkdir(parents=True, exist_ok=True)
    for d in ("lib",) + BASE_TREES:
        make_walk(arch, out, d, "obj")


def step_lib(arch: str, out: Path) -> None:
    """lib/ as Makefile.cross builds it, csu and libc first, then every library of its SUBDIR
    built and installed before the next, as the base system's own /usr/lib would already
    hold them for a native build (libssl links -lcrypto, libedit -lcurses). One that needs
    a library later in the order is built again at the end."""
    order = ["lib/csu", "lib/libc"] + [d for d in subdirs(arch, out, "lib") if d not in ("lib/csu", "lib/libc")]
    bad = [d for d in order if make_walk(arch, out, d) or make_walk(arch, out, d, "install")]
    bad = [d for d in bad if make_walk(arch, out, d) or make_walk(arch, out, d, "install")]
    # libc's tags name its sources by the path they were compiled from: the base system's
    # /usr/src, not the checkout's, as the compiler's prefix maps have it.
    tags = out / "sysroot/var/db/libc.tags"
    if tags.exists():
        tags.write_bytes(tags.read_bytes().replace(f"{out / 'src'}/".encode(), b"/usr/src/"))
    print(f"lib: {len(order) - len(bad)} of {len(order)} built and installed" +
          (f"; failed: {' '.join(bad)}" if bad else ""))
    if "lib/libc" in bad or "lib/csu" in bad:
        raise SystemExit("lib: csu and libc are needed by everything else")


def subdirs(arch: str, out: Path, directory: str, target: str = "") -> list:
    """The directories under `directory` that build something, in its Makefiles' SUBDIR
    order (make -V SUBDIR, down to the directories that have none). With `target`, the
    SUBDIR a make of that target walks (games/fortune leaves strfile out of `install`)."""
    env = make_env(arch, out)
    makefile = out / "src" / directory / "Makefile"
    text = makefile.read_text(errors="replace") if makefile.exists() else ""
    # A directory that builds something itself (a program, a library: libcrypto has
    # SUBDIR=man beside its library) is made as one: its own make goes down its SUBDIR.
    if not makefile.exists() or re.search(r"bsd\.(prog|lib)\.mk", text):
        return [directory]
    value = subprocess.run([str(HOST / "bin/make"), "-m", str(out / "src/share/mk"), "-V", "SUBDIR",
                            *([target] if target else [])],
                           cwd=out / "src" / directory, env=env, capture_output=True, text=True).stdout.split()
    if not value:
        return [directory]
    found = []
    for s in value:
        if (out / "src" / directory / s).is_dir():
            found += subdirs(arch, out, f"{directory}/{s}", target)
    return found


def install_hooks(out: Path, tree: str, dirs: list) -> list:
    """The directories above `dirs` whose own Makefile walks a SUBDIR and adds to its
    install (share/man's COPYRIGHT, games/boggle's dictionary): bsd.subdir.mk runs their
    beforeinstall and afterinstall around the walk, which building each directory on its
    own skips."""
    parents = sorted({str(Path(d).parents[i]) for d in dirs for i in range(len(Path(d).parts) - 1)
                      if Path(d).parents[i].is_relative_to(tree)} - set(dirs))
    hooks = []
    for d in parents:
        makefile = out / "src" / d / "Makefile"
        if makefile.exists() and re.search(r"^(before|after)install:", makefile.read_text(errors="replace"), re.M):
            hooks.append(d)
    return hooks


# What cannot be built inside the tree, and why: the userland takes nothing GPL.
EXCLUDED = {
    "usr.bin/bgplg/bgplgsh": "links readline, gnu/lib/libreadline (GPL), outside the tree",
    "usr.sbin/amd/doc": "its info manual needs makeinfo (texinfo, GPL), outside the tree",
    # Pending: their configure answers its tests by running programs, which a cross build
    # cannot (it then assumes a broken memcmp, whose replacement the tree does not carry);
    # the base system's own Makefile.cross skips nsd for that. They need the target's
    # answers given to configure, or a build on EmiBSD itself.
    "usr.sbin/nsd": "configure cannot run its tests when cross-compiling (pending)",
    "usr.sbin/unbound": "configure cannot run its tests when cross-compiling (pending)",
}


def step_retry(arch: str, out: Path) -> None:
    """Build again only the directories the last `base` listed as failed."""
    dirs = (out / "failed").read_text().split()
    bad = [d for d in dirs if make_walk(arch, out, d) or make_walk(arch, out, d, "install")]
    (out / "failed").write_text("".join(f"{d}\n" for d in bad))
    print(f"retry: {len(dirs) - len(bad)} of {len(dirs)} now built; {len(bad)} still fail")


def step_base(arch: str, out: Path) -> None:
    """Each directory the trees' SUBDIR reach, built and installed on its own: the base
    system's subdir loop stops at the first failure, and one program must not hide the
    rest. The failures are listed in target/<arch>/failed."""
    failed = []
    for tree in BASE_TREES:
        dirs = [d for d in subdirs(arch, out, tree) if d not in EXCLUDED]
        installed = set(subdirs(arch, out, tree, "install"))
        bad = [d for d in dirs if make_walk(arch, out, d) or (d in installed and make_walk(arch, out, d, "install"))]
        # Their hooks alone, after their subdirectories: SUBDIR emptied, so the walk is not
        # made again (afterinstall depends on beforeinstall through realinstall).
        bad += [d for d in install_hooks(out, tree, dirs) if make_walk(arch, out, d, "SUBDIR=", "afterinstall")]
        failed += bad
        print(f"base: {tree}: {len(dirs) - len(bad)} of {len(dirs)} built and installed")
    (out / "failed").write_text("".join(f"{d}\n" for d in failed))
    print(f"base: {len(failed)} failed, listed in {out / 'failed'}")


def step_etc(arch: str, out: Path) -> None:
    """/etc, /root, /var and their kin as etc/Makefile's distribution-etc-root-var lays them
    out, after the programs (as `make distribution` runs it before `make install`, whose
    work `base` has done): pwd_mkdb, mtree, sha256 and pax are the host builds owners.h
    gives the tree's owners, so etc.tgz and etcsum carry them, not the building user's."""
    # install-mtree is the top Makefile's beforeinstall, which building each directory on its
    # own skips; etc.tgz and etcsum are made of what distribution-etc-root-var installs.
    if make_walk(arch, out, "etc", "install-mtree", "distribution-etc-root-var"):
        raise SystemExit("etc: distribution-etc-root-var failed")
    print(f"etc: {out / 'sysroot/var/sysmerge/etc.tgz'}")
    # The top Makefile's afterinstall, the manual's database; the locate database beside it
    # (distrib/sets's makedb) is not made yet: makelocatedb names the target's own tools.
    if make_walk(arch, out, "share/man", "makedb"):
        raise SystemExit("etc: share/man's makedb failed")
    print(f"etc: {out / 'sysroot/usr/share/man/mandoc.db'}")


# The install sets maketars makes from DESTDIR, by distrib/sets/lists/<set>/{mi,md.<arch>}.
SETS = ("base", "comp", "game", "man")
OSREV = os.environ.get("WORLD_OSREV", "80")   # the kernel says EmiBSD 8.0


def set_list(out: Path, name: str, arch: str) -> list:
    lists = out / "src/distrib/sets/lists" / name
    entries = set()
    for f in ("mi", f"md.{arch}", f"clang.{arch}"):
        if (lists / f).exists():
            entries.update(l.strip() for l in (lists / f).read_text().splitlines() if l.strip())
    return sorted(entries)


def step_sets(arch: str, out: Path) -> None:
    """The install sets, as distrib/sets/maketars makes them (one gzipped archive per set,
    from DESTDIR, in its list's order with the libraries first), with the owners, groups and
    modes the metalog and the mtree specification give, not the building user's: bsdtar
    reads an mtree description of each entry. Every entry's time is the epoch and the gzip
    header has none, so the archives are the same in every build of one commit; SHA256 is
    the base system's sha256 over them, as a release lists them. distrib/sets/checkflist's
    comparison of the lists with DESTDIR is written to sets/checkflist."""
    sysroot, sets = out / "sysroot", out / "sets"
    if sets.exists():
        shutil.rmtree(sets)
    sets.mkdir()
    users, groups = ids_of(out / "src/etc")
    attrs = {p: dict(k) for p, k in mtree_entries(out / "src/etc/mtree/4.4BSD.dist")}
    for path, rec in read_metalog(out / "metalog", sysroot).items():
        attrs.setdefault(path, {}).update(rec)
    listed, report = set(), []
    for name in SETS:
        entries = set_list(out, name, arch)
        listed.update(e[2:] for e in entries)
        entries = [e for e in entries if e.startswith("./usr/lib/lib")] + \
                  [e for e in entries if not e.startswith("./usr/lib/lib")]
        spec, missing = ["#mtree"], []
        for e in entries:
            rel = e[2:]
            f = sysroot / rel
            if not (f.exists() or f.is_symlink()):
                missing.append(e)
                continue
            rec = attrs.get(rel, {})
            st = f.lstat()
            mode = rec.get("mode") if rec.get("mode", "").isdigit() else f"{st.st_mode & 0o7777:o}"
            owner = (f"uid={users.get(rec.get('uname', 'root'), 0)} gid={groups.get(rec.get('gname', 'wheel'), 0)} "
                     f"time={EPOCH}.0")
            if f.is_symlink():
                spec.append(f"{mtree_quote(e)} type=link {owner} mode=0755 link={mtree_quote(os.readlink(f))}")
            elif f.is_dir():
                spec.append(f"{mtree_quote(e)} type=dir {owner} mode={mode}")
            else:
                spec.append(f"{mtree_quote(e)} type=file {owner} mode={mode} contents={mtree_quote(str(f))}")
        (sets / f"{name}.mtree").write_text("\n".join(spec) + "\n")
        archive = sets / f"{name}{OSREV}.tgz"
        subprocess.run(["bsdtar", "-c", "-z", "--options", "gzip:!timestamp", "--format=ustar", "-f", str(archive),
                        f"@{sets / (name + '.mtree')}"], check=True)
        report.append(f"{name}: {len(entries) - len(missing)} of {len(entries)} entries, "
                      f"{archive.stat().st_size // 1024} KiB")
        (sets / f"{name}.missing").write_text("".join(m + "\n" for m in missing))
    sums = subprocess.run([str(HOST / "bin/sha256"), *(f"{name}{OSREV}.tgz" for name in SETS)], cwd=sets,
                          capture_output=True, text=True, check=True).stdout
    (sets / "SHA256").write_text(sums)
    installed = {str(p.relative_to(sysroot)) for p in sysroot.rglob("*")}
    # The etc list is no set: its files travel in base's var/sysmerge/etc.tgz.
    listed.update(e[2:] for e in set_list(out, "etc", arch))
    extra = sorted(installed - listed - {p for p in installed if p.startswith(("usr/include", "var/db"))})
    (sets / "extra").write_text("".join(f"./{e}\n" for e in extra))
    (sets / "checkflist").write_text("\n".join(report) + f"\ninstalled but in no list: {len(extra)} (sets/extra)\n")
    print((sets / "checkflist").read_text(), end="")


def mtree_quote(path: str) -> str:
    """A path in mtree(5) form: what is not printable or is a space, as \\ooo."""
    return "".join(c if c.isprintable() and c not in " \\#" else "".join(f"\\{b:03o}" for b in c.encode())
                   for c in path)


def ids_of(etc: Path) -> tuple:
    users = {l.split(":")[0]: int(l.split(":")[2]) for l in (etc / "master.passwd").read_text().splitlines()
             if l and not l.startswith("#")}
    groups = {l.split(":")[0]: int(l.split(":")[2]) for l in (etc / "group").read_text().splitlines()
              if l and not l.startswith("#")}
    return users, groups


STEPS = {"tree": step_tree, "host": step_host, "includes": step_includes, "obj": step_obj,
         "lib": step_lib, "base": step_base, "retry": step_retry, "image": step_image,
         "sets": step_sets, "etc": step_etc}
# `just world arm64` with no step: the base system built and installed into the sysroot.
# `make obj` first, as in the base system: include/Makefile has librpcsvc generate its
# headers, which then must be in that library's obj, where its sources are compiled.
DEFAULT = ("tree", "host", "obj", "includes", "lib", "base", "etc", "sets")


def case_sensitive(out: Path) -> None:
    """target/<arch> on a case-sensitive volume: the base system has names that differ only
    in case (libc's _Exit and _exit objects, terminfo's directories), which the host's file
    system folds into one. A sparse disk image beside it, made and attached the first time
    (hdiutil, as the user; `hdiutil detach target/<arch>` and removing the image undo it)."""
    if os.path.ismount(out):
        return
    image = out.parent / f"{out.name}.sparseimage"
    if not image.exists():
        subprocess.run(["hdiutil", "create", "-quiet", "-size", "60g", "-type", "SPARSE", "-fs",
                        "Case-sensitive APFS", "-volname", f"emibsd-{out.name}", str(image)], check=True)
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise SystemExit(f"world: {out} holds files and is not the case-sensitive volume; move them away")
    subprocess.run(["hdiutil", "attach", "-quiet", "-nobrowse", "-mountpoint", str(out), str(image)], check=True)


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in MACHINES:
        print(__doc__, file=sys.stderr)
        return 2
    arch = sys.argv[1]
    out = ROOT / "target" / arch
    case_sensitive(out)
    for name in sys.argv[2:] or DEFAULT:
        if name not in STEPS:
            print(f"world: no step {name}", file=sys.stderr)
            return 2
        STEPS[name](arch, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
