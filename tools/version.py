#!/usr/bin/env python3
"""Versions of the programs (docs/PROGRAM.md, "Versions").

usage: version.py check-commit <message file>   the commit-msg hook: a change to a program's
                                                 code carries a `Change:` trailer and the bump
                                                 it calls for
       version.py changelog <program dir>        CHANGELOG.md from the commits' trailers

Written programs: semver in src/Cargo.toml. `Change: breaking` bumps MAJOR (MINOR while
MAJOR is 0, as Cargo reads 0.y.z), `Change: feature` bumps MINOR (PATCH while MAJOR is 0),
`Change: fix` bumps PATCH. Imported programs: `version` in UPSTREAM.toml, the upstream's
version plus our patch level as build metadata (`9.9+emibsd.2`); a change to patches/ or
build/ raises the patch level, a pin bump changes the base. Stdlib only.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRAILER = re.compile(r"^Change:\s*(breaking|feature|fix)\s*$", re.M)
CODE_DIRS = ("src/", "patches/", "build/")
CODE_FILES = ("UPSTREAM.toml",)


def git(*args, check=True):
    r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)
    if check and r.returncode:
        raise SystemExit(f"version: git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def program_of(path: str):
    """The program directory (holds STATUS) a repository path belongs to, or None."""
    p = Path(path)
    for parent in [p] + list(p.parents):
        if (ROOT / parent / "STATUS").exists() and parent != Path("."):
            return parent
    return None


def is_code(path: str, prog: Path) -> bool:
    rel = str(Path(path).relative_to(prog))
    return rel.startswith(CODE_DIRS) or rel in CODE_FILES


def parse_semver(s: str):
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-[0-9A-Za-z.-]+)?(?:\+([0-9A-Za-z.-]+))?$", s.strip())
    if not m:
        raise SystemExit(f"version: `{s}` is not MAJOR.MINOR.PATCH[-pre][+meta]")
    return int(m[1]), int(m[2]), int(m[3]), m[4] or ""


def version_in(text: str, path: str) -> str:
    m = re.search(r'^version\s*=\s*"([^"]*)"', text, re.M)
    if not m:
        raise SystemExit(f"version: {path}: no `version = \"...\"` line")
    return m[1]


def staged(path: Path) -> str:
    return git("show", f":{path}", check=False)


def committed(path: Path) -> str:
    return git("show", f"HEAD:{path}", check=False)


def expected_bump(old, kind):
    major, minor, patch, _ = old
    if major == 0:
        return {"breaking": (0, minor + 1, 0), "feature": (0, minor, patch + 1), "fix": (0, minor, patch + 1)}[kind]
    return {"breaking": (major + 1, 0, 0), "feature": (major, minor + 1, 0), "fix": (major, minor, patch + 1)}[kind]


def check_commit(msg_file: str) -> int:
    message = Path(msg_file).read_text()
    kinds = TRAILER.findall(message)
    files = [f for f in git("diff", "--cached", "--name-only").splitlines() if f]
    touched = {}
    for f in files:
        prog = program_of(f)
        if prog and is_code(f, prog):
            touched.setdefault(prog, []).append(f)
    if not touched:
        if kinds:
            print("version: `Change:` trailer on a commit that changes no program's code: dropped from the check")
        return 0
    if not kinds:
        names = ", ".join(str(p) for p in touched)
        print(f"version: the commit changes the code of {names} and carries no `Change: breaking|feature|fix` trailer")
        return 1
    if len(set(kinds)) > 1:
        print(f"version: one `Change:` kind per commit, found {sorted(set(kinds))}")
        return 1
    kind = kinds[0]
    errors = 0
    for prog in touched:
        status = (ROOT / prog / "STATUS").read_text().strip()
        if status.startswith("imported"):
            path = prog / "UPSTREAM.toml"
            new_text = staged(path)
            if not new_text:
                print(f"version: {prog}: imported, but no UPSTREAM.toml staged")
                errors += 1
                continue
            new, old_text = version_in(new_text, str(path)), committed(path)
            old = version_in(old_text, str(path)) if old_text else ""
            if new == old:
                print(f"version: {prog}: UPSTREAM.toml version unchanged ({new or 'empty'}); raise the patch level (+emibsd.N) or the base")
                errors += 1
            continue
        path = prog / "src" / "Cargo.toml"
        new_text = staged(path)
        if not new_text:
            print(f"version: {prog}: code changed but src/Cargo.toml is not in the commit (version lives there)")
            errors += 1
            continue
        new = parse_semver(version_in(new_text, str(path)))
        old_text = committed(path)
        if not old_text:
            if new[:3] != (0, 1, 0):
                print(f"version: {prog}: a new package starts at 0.1.0, not {'.'.join(map(str, new[:3]))}")
                errors += 1
            continue
        old = parse_semver(version_in(old_text, str(path)))
        want = expected_bump(old, kind)
        if new[:3] != want:
            print(f"version: {prog}: `Change: {kind}` on {'.'.join(map(str, old[:3]))} calls for "
                  f"{'.'.join(map(str, want))}, Cargo.toml says {'.'.join(map(str, new[:3]))}")
            errors += 1
    return 1 if errors else 0


def changelog(prog_dir: str) -> int:
    prog = Path(prog_dir).resolve().relative_to(ROOT)
    log = git("log", "--format=%H%x00%s%x00%b%x00%ad", "--date=short", "--", str(prog / "src"), str(prog / "patches"),
              str(prog / "build"), str(prog / "UPSTREAM.toml"))
    entries = []
    for rec in log.split("\n"):
        if not rec.strip():
            continue
        parts = rec.split("\x00")
        if len(parts) < 4:
            continue
        sha, subject, body, date = parts[0], parts[1], parts[2], parts[3]
        m = TRAILER.search(body)
        if not m:
            continue
        status = (ROOT / prog / "STATUS").read_text().strip()
        vpath = prog / ("UPSTREAM.toml" if status.startswith("imported") else "src/Cargo.toml")
        text = git("show", f"{sha}:{vpath}", check=False)
        ver = version_in(text, str(vpath)) if text else "?"
        entries.append((ver, date, m[1], subject, sha[:12]))
    out = [f"# {prog.name}: changelog", "", "Generated by `tools/version.py changelog` from the `Change:` trailers; do not edit.", ""]
    current = None
    for ver, date, kind, subject, sha in entries:
        if ver != current:
            out += [f"## {ver}", ""]
            current = ver
        out.append(f"- {date} {kind}: {subject} ({sha})")
    (ROOT / prog / "CHANGELOG.md").write_text("\n".join(out) + "\n")
    print(f"version: {prog}/CHANGELOG.md: {len(entries)} entries")
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "check-commit":
        sys.exit(check_commit(sys.argv[2]))
    if len(sys.argv) == 3 and sys.argv[1] == "changelog":
        sys.exit(changelog(sys.argv[2]))
    print(__doc__)
    sys.exit(2)
