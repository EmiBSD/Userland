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

The steps, in order (all of them when none is named):

  host      the base system's own tools the build runs on the development host (rpcgen,
            yacc, lex, ...), built by the same make, into target/host/bin
  tree      target/<arch>/src: every inherited directory's src/ copied back to its path in
            the base system's tree, so each Makefile finds its neighbours where it expects
            them (${.CURDIR}/.., BSDSRCDIR); patches/ applied to the copy, src/ only read
  includes  target/<arch>/sysroot/usr/include, by include/Makefile's own targets
  csu       the C start-up objects into the sysroot's /usr/lib
  libc      libc.a, then the libraries the programs link
  programs  the programs, installed into the sysroot (DESTDIR)
  image     target/<arch>/ramdisk.ffs: the mtree skeleton, the programs, /etc from the
            tree, /dev by MAKEDEV's `ramdisk` target, made by the base system's makefs
            with the owners, modes and nodes the metalog recorded

make is target/host/bin/make (`just host-make`); the compiler is DevTools' clang, whose
default target is EmiBSD's (EMIBSD_LLVM_BIN). Nothing is installed on the host and nothing
is written outside target/.
"""
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "base"
TREES = ("etc", "data", "distrib")   # their entries keep their full paths under src/
LLVM = Path(os.environ.get("EMIBSD_LLVM_BIN",
                           Path.home() / "devel/emibsd/toolchains/llvm-23.1.4+emibsd.1-aarch64-apple-darwin/bin"))
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
    (out / "metalog").unlink(missing_ok=True)   # a new tree, a new record of what is installed
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
HOST_TOOLS = ("usr.bin/rpcgen", "usr.bin/yacc", "usr.bin/lex")


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
    return env


# The stand-ins for a build run by a user (tools/host): they record in the metalog what
# they cannot do (owners, groups, device nodes) instead of failing.
WRAPPERS = {"install": "install.sh", "chown": "chown.sh", "chgrp": "chgrp.sh", "mknod": "mknod.sh"}


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
        subprocess.run([str(HOST / "bin/make"), "-m", str(out / "src/share/mk"), f"CC={host_cc()}",
                        "NOMAN=1", "CRTBEGIN=", "CRTEND=", "LIBCRT0=", "LIBC=", "WARNINGS=no"],
                       cwd=out / "src" / tool, env=env, check=True)
        prog = Path(tool).name
        shutil.copy2(obj / prog, HOST / "bin" / prog)
        print(f"host: {HOST / 'bin' / prog}")
    host_makefs(out)


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


def step_csu(arch: str, out: Path) -> None:
    make(arch, out, "lib/csu", "all", "install")


# The libraries the programs link, in the order their own dependencies need.
LIBRARIES = ("lib/libc", "lib/libutil", "lib/libm", "lib/libz", "lib/libcurses", "lib/libkvm")


def step_libc(arch: str, out: Path) -> None:
    for lib in LIBRARIES:
        make(arch, out, lib, "all", "install", extra=("NOPIC=1", "NOPROFILE=1"))


# The first set: what a single-user boot of the ramdisk reaches (init, the shell, mounting,
# the file and system utilities a session at its prompt uses). WORLD_PROGRAMS overrides it.
PROGRAMS = (
    "sbin/init", "bin/ksh", "bin/cat", "bin/chmod", "bin/cp", "bin/date", "bin/dd", "bin/df",
    "bin/echo", "bin/ed", "bin/hostname", "bin/kill", "bin/ln", "bin/ls", "bin/mkdir", "bin/mv",
    "bin/ps", "bin/pwd", "bin/rm", "bin/rmdir", "bin/sleep", "bin/stty", "bin/sync",
    "sbin/dmesg", "sbin/mount", "sbin/mount_ffs", "sbin/reboot", "sbin/sysctl", "sbin/umount",
    "usr.bin/id", "usr.bin/uname",
)


def step_programs(arch: str, out: Path) -> None:
    # Static like the install media's programs: there is no ld.so in the image yet, and the
    # Makefiles of /usr/bin link dynamically.
    for prog in os.environ.get("WORLD_PROGRAMS", "").split() or PROGRAMS:
        make(arch, out, prog, "all", "install", extra=("LDSTATIC=-static",))


# What the ramdisk's /etc holds, from the tree (the arm64 files from etc/etc.<arch>), and
# the modes the base system's etc/Makefile installs them with.
ETC_FILES = {"etc/master.passwd": 0o600, "etc/group": 0o644, "etc/shells": 0o644,
             "etc/motd": 0o644, "etc/gettytab": 0o644, "etc/protocols": 0o644,
             "etc/services": 0o644, "etc/ksh.kshrc": 0o644, "etc/rc": 0o644,
             "etc/rc.conf": 0o644, "etc/netstart": 0o644, "etc/etc.<arch>/ttys": 0o644,
             "etc/etc.<arch>/login.conf": 0o644}
# The trees of the sysroot the ramdisk takes: the programs, not the headers and archives.
IMAGE_TREES = ("bin", "sbin", "usr/bin", "usr/sbin", "usr/libexec")


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
    modes = {}
    for src, mode in ETC_FILES.items():
        src = src.replace("<arch>", arch)
        dst = staging / "etc" / Path(src).name
        shutil.copy2(out / "src" / src, dst)
        dst.chmod(mode)
        modes[f"etc/{dst.name}"] = mode
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
    used = sum(p.lstat().st_size for p in staging.rglob("*") if p.is_file() and not p.is_symlink())
    cylinder = 2 * 768
    sectors = ((used * 2 // 512 + 16384) // cylinder + 1) * cylinder
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
# DevTools' (the comp set); games/ is not in the map yet.
BASE_TREES = ("bin", "libexec", "sbin", "usr.bin", "usr.sbin", "share")


# The base system's lld takes these by default when it targets the base system (its
# Driver.cpp, under __OpenBSD__): a version script may name symbols a library does not
# define (libc's Symbols.list names __data_start), and protected symbols stay preemptible.
# DevTools' lld for aarch64-emibsd does not yet; until it does (a DevTools matter), they are
# given to every link, and only to links, by a clang configuration file under target/.
LINK_DEFAULTS = ("--undefined-version", "--ignore-function-address-equality")
# Likewise the base system's clang leaves -Wpointer-sign off by default and upstream's turns
# it on: the Makefiles that build with -Werror (LibreSSL's) mix char and unsigned char
# pointers and expect no warning for it.
COMPILE_DEFAULTS = ("-Wno-pointer-sign",)


def link_config(out: Path) -> Path:
    cfg = out / "clang-link.cfg"
    cfg.write_text("".join(f"{flag}\n" for flag in COMPILE_DEFAULTS) +
                   "".join(f"$-Wl,{flag}\n" for flag in LINK_DEFAULTS))
    return cfg


def make_walk(arch: str, out: Path, directory: str, *targets: str) -> int:
    """make in `directory` and down its SUBDIR, each subdirectory in its own `obj` (made by
    `make obj`); -k, so one failure does not hide the next. Returns make's status."""
    m = MACHINES[arch]
    sysroot = out / "sysroot"
    cfg = link_config(out)
    cc = f"{LLVM}/clang --config={cfg} --target={m['triple']} --sysroot={sysroot}"
    args = [str(HOST / "bin/make"), "-k", f"-j{os.cpu_count()}", "-m", str(out / "src/share/mk"),
            f"BSDSRCDIR={out / 'src'}", f"BSDOBJDIR={out / 'obj'}", f"DESTDIR={sysroot}",
            f"CC={cc}", f"CXX={LLVM}/clang++ --config={cfg} --target={m['triple']} --sysroot={sysroot}",
            f"CPP={cc} -E", f"LD={LLVM}/ld.lld", f"AR={LLVM}/llvm-ar", f"RANLIB={LLVM}/llvm-ranlib",
            f"NM={LLVM}/llvm-nm", f"OBJCOPY={LLVM}/llvm-objcopy", f"STRIP={LLVM}/llvm-strip",
            f"HOSTCC={host_cc()}", "NOMAN=1", *targets]
    env = make_env(arch, out)
    return subprocess.run(args, cwd=out / "src" / directory, env=env).returncode


def step_obj(arch: str, out: Path) -> None:
    (out / "obj").mkdir(parents=True, exist_ok=True)
    for d in ("lib",) + BASE_TREES:
        make_walk(arch, out, d, "obj")


def step_lib(arch: str, out: Path) -> None:
    """lib/ as the base system's Makefile.cross does it: csu and libc built and installed
    first (every shared library links against them), then the rest, built and installed."""
    for first in ("lib/csu", "lib/libc"):
        if make_walk(arch, out, first) or make_walk(arch, out, first, "install"):
            raise SystemExit(f"lib: {first} failed")
    status = make_walk(arch, out, "lib")
    status = make_walk(arch, out, "lib", "install") or status
    print(f"lib: make exited {status}")


def step_base(arch: str, out: Path) -> None:
    for d in BASE_TREES:
        status = make_walk(arch, out, d)
        status = make_walk(arch, out, d, "install") or status
        print(f"base: {d}: make exited {status}")


STEPS = {"tree": step_tree, "host": step_host, "includes": step_includes, "csu": step_csu,
         "libc": step_libc, "programs": step_programs, "image": step_image,
         "obj": step_obj, "lib": step_lib, "base": step_base}


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
    for name in sys.argv[2:] or STEPS:
        if name not in STEPS:
            print(f"world: no step {name}", file=sys.stderr)
            return 2
        STEPS[name](arch, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
