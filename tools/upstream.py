#!/usr/bin/env python3
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
                yield d, tomllib.load(fh)["upstream"]


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
