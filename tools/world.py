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
  programs  the programs, installed into target/<arch>/root

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
    n = 0
    for d, paths in inherited():
        tree = d.relative_to(BASE).parts[0] in TREES
        if tree:
            shutil.copytree(d / "src", view, symlinks=True, dirs_exist_ok=True)
        else:
            shutil.copytree(d / "src", view / paths[0], symlinks=True, dirs_exist_ok=True)
        for patch in sorted((d / "patches").glob("*.patch")):
            where = view if tree else view / paths[0]
            subprocess.run(["patch", "-s", "-p1", "-d", str(where), "-i", str(patch)], check=True)
        n += 1
    print(f"tree: {n} inherited entries in {view}")


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


# The host's install(8) and chown(8) stand-ins for a build run by a user (tools/host).
WRAPPERS = {"install": "install.sh", "chown": "chown.sh"}


def step_host(arch: str, out: Path) -> None:
    """Each tool by its own Makefile, for the host: no target start-up files or libc."""
    (HOST / "bin").mkdir(parents=True, exist_ok=True)
    for name, script in WRAPPERS.items():
        link = HOST / "bin" / name
        link.unlink(missing_ok=True)
        link.symlink_to(ROOT / "tools/host" / script)
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


def mtree_dirs(spec: Path) -> list:
    """The directories an mtree(8) specification lists (etc/mtree/4.4BSD.dist), in order:
    the skeleton OpenBSD's `make distrib-dirs` lays out before anything is installed."""
    stack, dirs = [], []
    for line in spec.read_text().splitlines():
        word = line.split("#", 1)[0].split()
        if not word or word[0].startswith("/"):
            continue
        if word[0] == "..":
            stack.pop()
            continue
        if word[0] == ".":
            continue
        stack.append(word[0])
        dirs.append("/".join(stack))
    return dirs


def distrib_dirs(out: Path, root: Path) -> None:
    for d in mtree_dirs(out / "src/etc/mtree/4.4BSD.dist"):
        (root / d).mkdir(parents=True, exist_ok=True)


def step_includes(arch: str, out: Path) -> None:
    sysroot = out / "sysroot"
    distrib_dirs(out, sysroot)
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


STEPS = {"tree": step_tree, "host": step_host, "includes": step_includes, "csu": step_csu,
         "libc": step_libc, "programs": step_programs}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in MACHINES:
        print(__doc__, file=sys.stderr)
        return 2
    arch = sys.argv[1]
    out = ROOT / "target" / arch
    for name in sys.argv[2:] or STEPS:
        if name not in STEPS:
            print(f"world: no step {name}", file=sys.stderr)
            return 2
        STEPS[name](arch, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
