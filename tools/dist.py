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
"""The artifact of one architecture's install sets: dist/userland-<tag>-<arch>.tar.zst and its .sha256.

usage: dist.py <arch>...     build the sets of each architecture from HEAD's tag, from scratch,
                             and pack them

HEAD must carry a release tag, YEAR.MONTH.N (2026.11.0), and the tree no change to a tracked
file: a release is cut from a tagged commit. The build runs in a new worktree of that tag
under target/dist/<tag>, so nothing built before (an object compiled with older flags) reaches
it (upstream/, the imported programs' sources fetched by `just fetch`, is linked in), with
SOURCE_DATE_EPOCH the tag's commit time (world.py's default when it is unset): anyone
who builds the tag again gets the same sets and the same SHA256.

The tarball holds one directory, userland-<tag>-<arch>/, with the sets as world.py's sets step
made them (base80.tar.zst, comp, game, man), the installer's ramdisk miniroot80.fs (set into
the Kernel's bsd.RAMDISK with rdsetroot, it is bsd.rd), their SHA256 as a release lists them, and MANIFEST
(the tag, the commit, the architecture, the epoch, the base system's pin, the compiler, the sums,
what the sets still lack). Compressed as DevTools' artifacts are (zstd -19, the host's zstd).
Reproducible: entries sorted, mtime the epoch, root and wheel, modes 0644 and 0755. The worktree
is removed afterwards; dist/ keeps the artifact.
"""
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
ARCHS = ("arm64",)   # what world.py builds today; amd64 joins with its MACHINES entry
SETS = ("base", "comp", "game", "man")
OSREV = "80"
TAG = re.compile(r"^\d{4}\.\d{1,2}\.\d+$")


def run(*cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw).stdout.strip()


def release_tag() -> str:
    tags = [t for t in run("git", "-C", str(ROOT), "tag", "--points-at", "HEAD").splitlines() if TAG.match(t)]
    if len(tags) != 1:
        raise SystemExit("dist: HEAD carries no release tag YEAR.MONTH.N (git tag -a 2026.11.0 -m '...' first;"
                         " a release is cut from a tagged commit)" if not tags else f"dist: HEAD carries {tags}: one")
    changed = run("git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=no")
    if changed:
        raise SystemExit(f"dist: the tree has changes to tracked files; a release is HEAD's alone:\n{changed}")
    return tags[0]


def build(tag: str, arch: str) -> Path:
    """The sets of `arch` from a new worktree of `tag`; returns that worktree."""
    tree = ROOT / "target" / "dist" / tag
    if tree.exists():
        unmount(tree)
        run("git", "-C", str(ROOT), "worktree", "remove", "--force", str(tree))
    tree.parent.mkdir(parents=True, exist_ok=True)
    run("git", "-C", str(ROOT), "worktree", "add", "--detach", str(tree), tag)
    # The imported programs' sources (tools/upstream.py fetch, gitignored) are the main
    # checkout's: world.py checks each against its pin.
    (tree / "upstream").symlink_to(ROOT / "upstream")
    env = {k: v for k, v in os.environ.items() if k != "SOURCE_DATE_EPOCH"}   # the tag's own time
    log = tree / f"dist-{arch}.log"
    with open(log, "w") as fh:
        for cmd in (["just", "host-make"], ["just", "world", arch]):
            if subprocess.run(cmd, cwd=tree, env=env, stdout=fh, stderr=subprocess.STDOUT).returncode:
                raise SystemExit(f"dist: {' '.join(cmd)} failed for {arch}; see {log}")
    return tree


def unmount(tree: Path) -> None:
    for image in (tree / "target").glob("*.sparseimage"):
        mount = image.with_suffix("")
        if os.path.ismount(mount):
            run("hdiutil", "detach", "-quiet", str(mount))


def manifest(tag: str, arch: str, tree: Path, epoch: str, sums: str) -> str:
    commit = run("git", "-C", str(tree), "rev-parse", "HEAD")
    pin = next((l.split('"')[1] for l in (tree / "base/distrib/share/UPSTREAM.toml").read_text().splitlines()
                if l.startswith("commit")), "unknown")
    out = tree / "target" / arch
    llvm = run(str(Path(os.environ.get("EMIBSD_LLVM_BIN", Path.home() /
                    "devel/emibsd/toolchains/llvm-23.1.4+emibsd.1-aarch64-apple-darwin/bin")) / "clang"), "--version")
    missing = {s: len([l for l in (out / f"sets/{s}.missing").read_text().splitlines() if l]) for s in SETS}
    return "".join([
        f"tag: {tag}\n", f"commit: {commit}\n", f"arch: {arch}\n", f"source_date_epoch: {epoch}\n",
        f"base system pin: {pin}\n", f"compiler: {llvm.splitlines()[0]}\n", "\n",
        f"miniroot: miniroot{OSREV}.fs, an FFS image of {(out / f'sets/miniroot{OSREV}.fs').stat().st_size} bytes "
        "for rd(4) (rdsetroot into the Kernel's bsd.RAMDISK)\n",
        "\n", "sets (SHA256):\n", sums, "\n",
        "entries of each set's list the build does not make yet:\n",
        *(f"{s}: {n}\n" for s, n in missing.items()),
    ])


def pack(tag: str, arch: str, tree: Path) -> Path:
    out = tree / "target" / arch
    epoch = run("git", "-C", str(tree), "log", "-1", "--format=%ct")
    sums = (out / "sets/SHA256").read_text()
    name = f"userland-{tag}-{arch}"
    files = [(f"{s}{OSREV}.tar.zst", (out / f"sets/{s}{OSREV}.tar.zst").read_bytes()) for s in SETS]
    miniroot = out / f"sets/miniroot{OSREV}.fs"
    if not miniroot.exists():
        raise SystemExit(f"dist: {arch} has no miniroot{OSREV}.fs (world.py's miniroot step)")
    files.append((miniroot.name, miniroot.read_bytes()))
    files += [("SHA256", sums.encode()), ("MANIFEST", manifest(tag, arch, tree, epoch, sums).encode())]
    DIST.mkdir(exist_ok=True)
    tarball = DIST / f"{name}.tar.zst"
    if shutil.which("zstd") is None:
        raise SystemExit("dist: zstd not found (the user's install, as DevTools' dist uses)")
    zstd = subprocess.Popen(["zstd", "-19", "-T0", "-q", "-f", "-o", str(tarball)], stdin=subprocess.PIPE)
    with tarfile.open(fileobj=zstd.stdin, mode="w|", format=tarfile.USTAR_FORMAT) as tar:
        def entry(path, kind, size=0):
            info = tarfile.TarInfo(path)
            info.type, info.size, info.mtime = kind, size, int(epoch)
            info.uid = info.gid = 0
            info.uname, info.gname = "root", "wheel"
            info.mode = 0o755 if kind == tarfile.DIRTYPE else 0o644
            return info
        tar.addfile(entry(name, tarfile.DIRTYPE))
        for path, data in sorted(files):
            tar.addfile(entry(f"{name}/{path}", tarfile.REGTYPE, len(data)), io.BytesIO(data))
    zstd.stdin.close()
    if zstd.wait() != 0:
        raise SystemExit("dist: zstd failed")
    digest = hashlib.sha256(tarball.read_bytes()).hexdigest()
    (DIST / f"{tarball.name}.sha256").write_text(f"{digest}  {tarball.name}\n")
    return tarball


def main() -> int:
    archs = sys.argv[1:]
    if not archs or any(a not in ARCHS for a in archs):
        print(__doc__, file=sys.stderr)
        return 2
    tag = release_tag()
    for arch in archs:
        tree = build(tag, arch)
        tarball = pack(tag, arch, tree)
        print((DIST / f"{tarball.name}.sha256").read_text(), end="")
        print((tree / "target" / arch / "sets/SHA256").read_text(), end="")
        unmount(tree)
        run("git", "-C", str(ROOT), "worktree", "remove", "--force", str(tree))
        shutil.rmtree(tree, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
