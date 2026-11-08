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

The steps, in order (the first nine, through sets, when none is named):

  tree      target/<arch>/src: every inherited directory's src/ copied back to its path in
            the base system's tree, so each Makefile finds its neighbours where it expects
            them (${.CURDIR}/.., BSDSRCDIR); patches/ applied to the copy, src/ only read;
            __OpenBSD__ renamed __EmiBSD__ in the copy; the base system's name (OpenBSD to
            EmiBSD, in prose, messages, comments, identifiers and URLs) renamed in the
            inherited trees' text after the patches, never in the imported programs, and the
            version-control ids ($OpenBSD$, $Id$...) removed; copyright and licence notices,
            e-mail addresses, names of files that keep the old name, target triples and the
            ELF wire values stay; target/<arch>/rename-report.txt counts and lists them
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
  miniroot  target/<arch>/miniroot80.fs: the installer's ramdisk, as distrib/<arch>/ramdisk
            makes it (instbin crunched, the list run, makefs), padded to rd(4)'s size
  sets      target/<arch>/sets: base, comp, game and man as zstd archives, from the
            sysroot by distrib/sets/lists, the miniroot beside them, and their SHA256
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
                           Path.home() / "devel/emibsd/toolchains/llvm-23.1.4+emibsd.2-aarch64-apple-darwin-arm64/bin"))
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


def imported():
    """(directory, its pin, where it goes in the copied tree) of every imported program."""
    for status in sorted(BASE.rglob("STATUS")):
        d = status.parent
        if not status.read_text().startswith("imported"):
            continue
        with open(d / "UPSTREAM.toml", "rb") as fh:
            doc = tomllib.load(fh)
        yield d, doc["upstream"], doc["build"]["tree"]


def place_imported(view: Path) -> int:
    """Each imported program's pinned source (upstream/, `tools/upstream.py fetch`) and its
    build/ glue at its place in the copied tree, its patches applied there."""
    n = 0
    for d, up, where in imported():
        source = ROOT / "upstream" / up["repo"].rstrip("/").rsplit("/", 1)[-1]
        pin = source / ".pin"
        if not pin.exists() or pin.read_text().strip() != up["commit"]:
            raise SystemExit(f"tree: {d.relative_to(ROOT)}: upstream/ is not at its pin; just fetch first")
        dst = view / where
        for path in up["path"]:
            if (source / path).is_dir():
                shutil.copytree(source / path, dst / path, symlinks=True, dirs_exist_ok=True)
            else:
                dst.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / path, dst / path)
        shutil.copytree(d / "build", dst, dirs_exist_ok=True)
        for f in dst.rglob("*"):   # upstream/ is read-only; the copy is the build's
            if not f.is_symlink():
                f.chmod(f.stat().st_mode | stat.S_IWUSR)
        for patch in sorted((d / "patches").glob("*.patch")):
            subprocess.run(["patch", "-s", "-p1", "-F", "0", "-V", "none", "-t", "-N", "-d", str(dst),
                            "-i", str(patch)], check=True)
        n += 1
    return n


# --- the base system's name -------------------------------------------------------------
#
# In the userland the base system's name becomes EmiBSD in the copied tree (the user's
# decision of 2026-11-07: prose, messages, comments, identifiers and URLs; build time, in the
# copy, never by patch). Everything that is a fact about someone else is kept: copyright and
# licence notices, e-mail addresses, the names of files that exist with the old name, the
# target triples and Perl's architecture names, and the ELF wire values that the Kernel and
# the linker read by text (the note name, the .openbsd.* section names, the linker script's
# PT_OPENBSD_* names) until they move together. The version-control keywords are removed.

NAME_RE = re.compile(r"(?i)openbsd")
NAME_FORMS = {"OpenBSD": "EmiBSD", "openbsd": "emibsd", "OPENBSD": "EMIBSD", "openBSD": "emiBSD"}
KEYWORDS = "OpenBSD|NetBSD|FreeBSD|Id|Header"
ID_RE = re.compile(r"\$(" + KEYWORDS + r")(?::[ \t][^$\n]*)?\$")
# What can surround a version-control id on a line that holds nothing else.
COMMENT_ONLY = re.compile(r'^\s*(?:(?:/\*|\*/|//|#|\.\\"|\\"|dnl\b|--|;|\*|<!--|-->)\s*)*$')
DECL_RE = re.compile(
    r"^[ \t]*(?:static\s+)?(?:const\s+)?(?:volatile\s+)?char\s*(?:const\s*)?\*?\s*(\w+)\s*(?:\[\s*\])?"
    r"(?:\s*__\w+(?:\s*\(\([^)]*\)\))?)*\s*=\s*(?:\"[^\"\n]*\"\s*)+;[ \t]*\n", re.M)
MACRO_RE = re.compile(r"^[ \t]*(?:__\w*RCSID|__FBSDID|__IDSTRING|__SCCSID)\s*\((?:[^;\n]|\n)*?\)\s*;?[ \t]*\n", re.M)
IDENT_RE = re.compile(r"^[ \t]*#\s*(?:ident|pragma\s+ident)\s+\"[^\"\n]*\"[ \t]*\n", re.M)
LICENCE_WORDS = re.compile(r"PROVIDED|WARRANT|(?i:Redistribution|permission notice|endorse or promote)")
LICENCE_FILE = re.compile(r"(?i)licen[cs]e|copying|copyright")
LINE_COMMENT = re.compile(r'^\s*(?:\.?\\"|#|//|dnl\b|;|--)')
EMAIL_RE = re.compile(r"[\w.+%-]+@[\w.-]*\w")
URL_RE = re.compile(r"(?i)(?:(?:https?|ftp)://[^\s\"'<>)\]|]+|(?<![\w@.-])(?:[\w-]+\.)*openbsd\.(?:org|com|net)(?:/[^\s\"'<>)\]|]*)?)")
# ABI wire values: section names, the note's name string where it is written (\0 follows) or
# described (@nn), and the linker script's segment types, which lld reads by text.
WIRE_RE = re.compile(r"(?i)(?<![\w.])\.(?:note\.)?openbsd\.(?!(?:org|com|net)\b)[\w.*-]+|OpenBSD(?=\\{1,2}0|@nn)")
SCRIPT_RE = re.compile(r"\b(?:PT|PF)_OPENBSD_\w+")
# "first appeared in OpenBSD 2.1" is a true statement about where the code came from.
HISTORY_RE = re.compile(r"OpenBSD(?= \d+\.\d)")
MDOC_OX = ('\tcase MDOC_Ox:\n\t\tos = "EmiBSD";\n',
           '\tcase MDOC_Ox:\n\t\t/* a version after .Ox says where code first appeared; bare, it is this system */\n'
           '\t\tos = n->child == NULL ? "EmiBSD" : "OpenBSD";\n')
# Data that describes other systems is not EmiBSD's text: OS fingerprints of remote hosts,
# the magic of other systems' formats (EmiBSD's own binaries carry the old note name), the
# autoconf and libtool host tables (the packages are configured for an "openbsd" host), the
# registered MIB modules, the history calendar, the mdoc macro package's system names.
DATA_RE = re.compile(
    r"^etc/pf\.os$|^usr\.bin/file/magdir/|(^|/)(config\.guess|config\.sub|ltmain\.sh|configure|aclocal\.m4)$"
    r"|(^|/)(libtool|lt\w+)\.m4$|^share/snmp/OPENBSD-[\w-]+\.txt$|^usr\.bin/calendar/calendars/calendar\.openbsd$"
    r"|^share/tmac/mdoc/doc-common$")
# Nothing EmiBSD runs or tells a user may send mail to the base system's project: a contact
# address at its hosts becomes the same local part at emibsd.org; a person's address in a
# copyright, a licence, an AUTHORS section or a credit comment stays.
ROLE_RE = re.compile(r"(?i)(bugs|security|misc|tech|ports|dmesg|announce|majordomo|www|webmaster|"
                     r"source-changes|ports-changes|advocacy|hackers|office|owner-[\w+.-]+|bugs-[\w+.-]+)")
OLD_HOST_RE = re.compile(r"(?i)(?:[\w-]+\.)*openbsd\.(?:org|com|net)")
SOURCE_SUFFIXES = (".c", ".h", ".y", ".l", ".sh", ".pl", ".pm", ".py", ".awk", ".S", ".s", ".m4", ".cc")
COMMENT_LINE = re.compile(r'^\s*(?:/\*|\*|//|#|\.\\"|dnl\b|;|--)')
PROSE_WORDS = re.compile(r"(?i)\b(send|mail|report|write|contact|mailing)\b")
# The base system's CVS servers (anoncvs@...:/cvs) are not mail and have no counterpart: the
# instruction or the example goes, and where the text needs a sentence it says where the
# sources are. Exact texts of the original; the build stops if one moved.
CVS_EDITS = {
    "usr.bin/cvs/cvsintro.7": (
        ("from local mirror anoncvs.nl.openbsd.org:\n",
         "from a CVS repository (the sources are on GitHub,\n"
         "https://github.com/EmiBSD, and are not served by CVS):\n"),
        ("$ cvs -d anoncvs@anoncvs.nl.openbsd.org:/cvs checkout -P src",
         "$ cvs -d /path/to/repository checkout -P src"),
        ("$ cvs -d anoncvs@anoncvs.nl.openbsd.org:/cvs update -Pd",
         "$ cvs -d /path/to/repository update -Pd"),
    ),
    "share/man/man8/release.8": (
        ("See\n.Lk https://www.openbsd.org/anoncvs.html\nfor instructions on fetching the sources for the first time.\n",
         "The sources are on GitHub:\n.Lk https://github.com/EmiBSD .\n"),
    ),
    "usr.sbin/config/config.8": (
        ("deraadt@i386.openbsd.org:/usr/src", "user@build.example.org:/usr/src"),
    ),
}
KEPT_LISTED = ("abi",)
# A key file's name inside a line, and a set-list line that is just that file.
KEY_RE = re.compile(r"openbsd-[\w${}()+ -]*?\.pub")
KEY_LIST_RE = re.compile(r"^\./etc/signify/openbsd-(\d+)-(\w+)\.pub\s*$")


class Rename:
    """The state of one rename pass: the counts, the kept occurrences, the report."""

    def __init__(self, view: Path):
        self.view = view
        self.renamed = {"url": 0, "other": 0}
        self.kept = {"licence": 0, "email": 0, "abi": 0, "data": 0, "history": 0, "odd-case": 0}
        self.listed = {k: [] for k in KEPT_LISTED}
        self.ids = {"line": 0, "declaration": 0, "keyword": 0}
        self.ids_by_kind = {}
        self.files = 0
        self.latin1 = 0
        self.keys = []   # EmiBSD's public keys installed in place of the base system's
        self.key_refs = []   # where a reference to a key was changed
        self.key_dropped = []   # list lines for a key EmiBSD does not have
        self.cvs = []   # CVS servers and examples removed or made neutral
        self.contacts = {}   # address -> files, renamed to emibsd.org
        self.ambiguous = []   # personal addresses in prose that asks the reader to write
        self.data_files = {}   # file -> occurrences of the name kept in it
        self.paths = []   # (old, new) of every file and directory renamed

    def count_id(self, found: str, where: str) -> None:
        self.ids[where] += 1
        self.ids_by_kind[found] = self.ids_by_kind.get(found, 0) + 1

    def strip_declarations(self, text: str) -> str:
        """Remove the declarations that only hold a version-control id, when nothing else
        refers to what they declare."""
        def drop(m, name=None):
            body = m.group(0)
            found = [i.group(1) for i in ID_RE.finditer(body)]
            if not found or "copyright" in body.lower():
                return body
            if name is not None and len(re.findall(r"\b%s\b" % re.escape(name), text)) != 1:
                return body
            for f in found:
                self.count_id(f, "declaration")
            return ""
        text = DECL_RE.sub(lambda m: drop(m, m.group(1)), text)
        text = MACRO_RE.sub(drop, text)
        return IDENT_RE.sub(drop, text)

    def licence_lines(self, lines: list, name: str) -> list:
        """Per line: is it part of a copyright or licence notice."""
        n = len(lines)
        if LICENCE_FILE.search(name):
            return [True] * n
        flag = ["copyright" in line.lower() or bool(LICENCE_WORDS.search(line)) for line in lines]
        i = 0
        while i < n:   # a comment block that holds a Copyright line is licence through its end
            line = lines[i]
            start = i
            if "/*" in line and "*/" not in line.split("/*", 1)[1]:
                while i < n - 1 and "*/" not in lines[i]:
                    i += 1
            elif LINE_COMMENT.match(line):
                while i < n - 1 and LINE_COMMENT.match(lines[i + 1]):
                    i += 1
            else:
                i += 1
                continue
            # From the first Copyright line: what precedes it in the block (a version id) is not.
            first = next((j for j in range(start, i + 1) if "copyright" in lines[j].lower()), None)
            if first is not None:
                for j in range(first, i + 1):
                    flag[j] = True
            i += 1
        return flag

    def strip_ids(self, lines: list, licence: list) -> tuple:
        out, out_licence = [], []
        for line, lic in zip(lines, licence):
            if lic or not ID_RE.search(line):
                out.append(line)
                out_licence.append(lic)
                continue
            found = [m.group(1) for m in ID_RE.finditer(line)]
            rest = ID_RE.sub("", line)
            if COMMENT_ONLY.match(rest):
                for f in found:
                    self.count_id(f, "line")
                if rest.count("/*") != rest.count("*/"):   # an unbalanced delimiter stays
                    out.append(rest.rstrip())
                    out_licence.append(False)
                continue
            for f in found:
                self.count_id(f, "keyword")
            out.append(rest)
            out_licence.append(False)
        return out, out_licence

    def spans(self, line: str, script: bool) -> tuple:
        """(start, end, category) of what is kept on a line, the earlier category winning,
        and the spans of its URLs."""
        urls = [(m.start(), m.end()) for m in URL_RE.finditer(line)]
        found = []

        def add(m, cat):
            if not any(m.start() < e and s < m.end() for s, e, _ in found):
                found.append((m.start(), m.end(), cat))
        for m in EMAIL_RE.finditer(line):
            if NAME_RE.search(m.group(0)):
                add(m, "email")
        for m in WIRE_RE.finditer(line):
            add(m, "abi")
        if script:
            for m in SCRIPT_RE.finditer(line):
                add(m, "abi")
        if not line.lstrip().startswith(".Os"):
            for m in HISTORY_RE.finditer(line):
                add(m, "history")
        return found, urls

    def contact_mail(self, line: str, where: str, number: int, section: str, source: bool, man: bool) -> str:
        """The addresses at the old hosts that a program, a message or a reader's instructions
        use become the same local part at emibsd.org."""
        if "@" not in line:
            return line

        def fix(m):
            local, _, host = m.group(0).rpartition("@")
            if not OLD_HOST_RE.fullmatch(host):
                return m.group(0)
            comment = bool(COMMENT_LINE.match(line))
            contact = bool(ROLE_RE.fullmatch(local)) or where.startswith("distrib/notes/") or \
                (source and not comment and not re.search(r"\w\s*<" + re.escape(m.group(0)) + ">", line)) or \
                (man and section != "AUTHORS" and re.match(r"\s*\.(?:Mt|Aq)\b", line) is not None
                 and not re.match(r"\s*\.An\b", line))
            if not contact:
                if PROSE_WORDS.search(line) and not comment:
                    self.ambiguous.append(f"{where}:{number}: {m.group(0)}")
                return m.group(0)
            new = f"{local}@emibsd.org"
            self.contacts.setdefault(new, set()).add(where)
            return new
        return EMAIL_RE.sub(fix, line)

    def rename_line(self, line: str, licence: bool, where: str, number: int, script: bool,
                    section: str = "", source: bool = False, man: bool = False) -> str:
        if not licence or "copyright" not in line.lower():   # a role address in a notice is still a contact
            line = self.contact_mail(line, where, number, section, source, man)
        if not NAME_RE.search(line):
            return line
        if licence:
            self.kept["licence"] += len(NAME_RE.findall(line))
            return line
        found, urls = self.spans(line, script)
        for m in KEY_RE.finditer(line):
            self.key_refs.append(f"{where}:{number}: {line.strip()[:120]}")
        out, last = [], 0
        for m in NAME_RE.finditer(line):
            cat = next((c for s, e, c in found if s <= m.start() < e), None)
            if cat:
                self.kept[cat] += 1
                if cat in self.listed:
                    self.listed[cat].append(f"{where}:{number}: {line.strip()[:120]}")
                continue
            new = NAME_FORMS.get(m.group(0))
            if new is None:
                self.kept["odd-case"] += 1
                continue
            out.append(line[last:m.start()])
            out.append(new)
            last = m.end()
            self.renamed["url" if any(s <= m.start() < e for s, e in urls) else "other"] += 1
        out.append(line[last:])
        return "".join(out)

    def file(self, path: Path) -> None:
        data = path.read_bytes()
        if b"\0" in data or not re.search(rb"(?i)openbsd|\$(?:NetBSD|FreeBSD|Id|Header)", data):
            return
        where = path.relative_to(self.view).as_posix()
        try:
            coding = "utf-8"
            text = data.decode(coding)
        except UnicodeDecodeError:
            coding = "latin-1"   # an old 8-bit text: every byte maps back to itself
            text = data.decode(coding)
            self.latin1 += 1
        self.files += 1
        text = self.strip_declarations(text)
        lines = text.split("\n")
        lines, licence = self.strip_ids(lines, self.licence_lines(lines, path.name))
        if "/lists/" in f"/{where}":   # a set list names no key that EmiBSD does not have
            keep = []
            for l, lic in zip(lines, licence):
                m = KEY_LIST_RE.match(l)
                if m and m.groups() not in self.have:
                    self.key_dropped.append(f"{where}: {l.strip()}")
                else:
                    keep.append((l, lic))
            lines, licence = [k[0] for k in keep], [k[1] for k in keep]
        sections, section = [], ""
        for l in lines:
            if l.startswith(".Sh "):
                section = l[4:].strip().strip('"')
            sections.append(section)
        source = path.suffix in SOURCE_SUFFIXES
        man = re.search(r"\.\d\w*$", path.name) is not None
        if DATA_RE.search(where):
            lines = [l if "copyright" in l.lower() else self.contact_mail(l, where, i + 1, sections[i], source, man)
                     for i, (l, lic) in enumerate(zip(lines, licence))]
            count = sum(len(NAME_RE.findall(l)) for l in lines)
            if count:
                self.data_files[where] = count
                self.kept["data"] += count
            new = "\n".join(lines).encode(coding)
            if new != data:
                path.write_bytes(new)
            return
        script = path.name.startswith("ld.script") or path.suffix in (".ld", ".lds")
        lines = [self.rename_line(l, lic, where, i + 1, script, sections[i], source, man)
                 for i, (l, lic) in enumerate(zip(lines, licence))]
        new = "\n".join(lines).encode(coding)
        if new != data:
            path.write_bytes(new)

    def cvs_edits(self) -> None:
        for name, edits in CVS_EDITS.items():
            f = self.view / name
            text = f.read_text()
            for old, new in edits:
                if text.count(old) != 1:
                    raise SystemExit(f"tree: {name} no longer holds the text the CVS edit expects")
                text = text.replace(old, new)
                self.cvs.append(f"{name}: {old.strip().splitlines()[0][:100]}")
            f.write_text(text)

    def install_keys(self) -> None:
        """EmiBSD signs with its own keys (base/etc/signify): the base system's are removed
        from the copy and ours take their place under etc/signify."""
        target = self.view / "etc/signify"
        for old in sorted(target.glob("openbsd-*.pub")):
            old.unlink()
        for key in sorted((BASE / "etc/signify").glob("*.pub")):
            shutil.copyfile(key, target / key.name)
            self.keys.append(key.name)
        self.have = {re.fullmatch(r"emibsd-(\d+)-(\w+)\.pub", k).groups() for k in self.keys}

    def tree(self) -> None:
        self.install_keys()
        self.cvs_edits()
        for dirpath, dirs, files in os.walk(self.view):
            dirs.sort()
            for name in sorted(files):
                f = Path(dirpath) / name
                if not f.is_symlink():
                    self.file(f)
        self.mandoc_ox()
        self.rename_paths()

    def rename_paths(self) -> None:
        """Files and directories named after the old name get the new one, bottom up, as the
        text that refers to them has: the installed names follow. A symbolic link's own text
        follows too."""
        def renamed(name):
            return NAME_RE.sub(lambda m: NAME_FORMS.get(m.group(0), m.group(0)), name)
        for dirpath, dirs, files in os.walk(self.view, topdown=False):
            for entry in sorted(dirs + files):
                new = renamed(entry)
                if new == entry:
                    continue
                old = Path(dirpath) / entry
                if (Path(dirpath) / new).exists() or (Path(dirpath) / new).is_symlink():
                    raise SystemExit(f"tree: {old.relative_to(self.view)} would replace {new}")
                os.rename(old, Path(dirpath) / new)
                self.paths.append((old.relative_to(self.view).as_posix(), new))
        for dirpath, dirs, files in os.walk(self.view):
            for entry in sorted(dirs + files):
                link = Path(dirpath) / entry
                if link.is_symlink() and NAME_RE.search(os.readlink(link)):
                    target = renamed(os.readlink(link))
                    link.unlink()
                    link.symlink_to(target)

    def mandoc_ox(self) -> None:
        """mandoc prints .Ox as the system's name when bare and as OpenBSD when a version
        follows (HISTORY sections), so the manuals stay true: one line in mandoc's copy."""
        f = self.view / "usr.bin/mandoc/mdoc_validate.c"
        text = f.read_text()
        if text.count(MDOC_OX[0]) != 1:
            raise SystemExit("tree: mandoc's .Ox handling is not where the rename expects it")
        f.write_text(text.replace(*MDOC_OX))

    def report(self, out: Path) -> str:
        """Write target/<arch>/rename-report.txt; return its one-line summary."""
        r = ["rename-report: OpenBSD -> EmiBSD in the inherited trees' copy", ""]
        r.append(f"files read with the name or an id: {self.files}")
        r.append(f"renamed: {sum(self.renamed.values())} (URLs and host names {self.renamed['url']}, "
                 f"everything else {self.renamed['other']})")
        r.append("kept, by category:")
        for k, v in self.kept.items():
            r.append(f"  {k}: {v}")
        r.append("version-control ids removed:")
        for k, v in self.ids.items():
            r.append(f"  {k}: {v}")
        for k in sorted(self.ids_by_kind):
            r.append(f"  keyword {k}: {self.ids_by_kind[k]}")
        r.append("")
        r.append(f"== kept: ABI wire values, pending Kernel and DevTools ({len(self.listed['abi'])})")
        r.extend(self.listed["abi"])
        r.append("")
        r.append(f"== signify keys installed ({len(self.keys)})")
        r.extend(self.keys)
        r.append("")
        r.append(f"== references to a key, renamed ({len(self.key_refs)})")
        r.extend(self.key_refs)
        r.append("")
        r.append(f"== set-list lines for a key EmiBSD does not have, dropped ({len(self.key_dropped)})")
        r.extend(self.key_dropped)
        r.append("")
        r.append(f"== contact addresses renamed to emibsd.org ({len(self.contacts)})")
        for addr in sorted(self.contacts):
            r.append(f"{addr}: {', '.join(sorted(self.contacts[addr])[:6])}"
                     + (f" (+{len(self.contacts[addr]) - 6} more)" if len(self.contacts[addr]) > 6 else ""))
        r.append("")
        r.append(f"== personal addresses in prose that asks the reader to write, kept ({len(self.ambiguous)})")
        r.extend(self.ambiguous)
        r.append("")
        r.append(f"== CVS servers (anoncvs) removed or made neutral ({len(self.cvs)})")
        r.extend(self.cvs)
        r.append("")
        r.append(f"== data about other systems, kept as they are ({len(self.data_files)} files)")
        r.extend(f"{n} {f}" for f, n in sorted(self.data_files.items()))
        r.append("")
        r.append(f"== files and directories renamed ({len(self.paths)})")
        r.extend(f"{old} -> {new}" for old, new in sorted(self.paths))
        r.append("")
        r.append(f"== files read as Latin-1 text, not UTF-8: {self.latin1}")
        (out / "rename-report.txt").write_text("\n".join(r) + "\n")
        return (f"{sum(self.renamed.values())} renamed, {sum(self.kept.values())} kept, "
                f"{sum(self.ids.values())} ids removed")


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
    # The base system's name, after the patches (they match the original text) and before the
    # imported programs are placed (third party, never rewritten).
    rename = Rename(view)
    rename.tree()
    summary = rename.report(out)
    m = place_imported(view)
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
    print(f"tree: {n} inherited entries and {m} imported in {view}; __OpenBSD__ renamed in {renamed} files; name: {summary}")


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
    host_crunchgen(arch, out)


def host_crunchgen(arch: str, out: Path) -> None:
    """crunchgen(8) for the host, which links the installer's programs into one instbin and,
    as `crunchgen -h` (crunchide), hides each one's symbols in its ELF object: the target's
    ELF definitions from the tree (elf.h, sys/exec_elf.h, the machine's ELF size), and
    MACHINE, which names an obj.<machine> directory, the target's."""
    inc = HOST / "include-crunchgen"
    if inc.exists():
        shutil.rmtree(inc)
    (inc / "sys").mkdir(parents=True)
    (inc / "machine").mkdir()
    shutil.copy2(out / "src/include/elf.h", inc / "elf.h")
    shutil.copy2(out / "src/sys/sys/exec_elf.h", inc / "sys/exec_elf.h")
    size = re.search(r"#define\s+ARCH_ELFSIZE\s+(\d+)",
                     (out / f"src/sys/arch/{MACHINES[arch]['MACHINE']}/include/exec.h").read_text()).group(1)
    (inc / "machine/exec.h").write_text(f"#define ARCH_ELFSIZE {size}\n")
    obj = HOST / "obj/usr.sbin/crunchgen"
    obj.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(HOST / "bin/make"), "-m", str(out / "src/share/mk"),
                    f"CC={host_cc()} -I{inc} -DMACHINE='\"{MACHINES[arch]['MACHINE']}\"'",
                    "NOMAN=1", "CRTBEGIN=", "CRTEND=", "LIBCRT0=", "LIBC=", "WARNINGS=no"],
                   cwd=out / "src/usr.sbin/crunchgen", env=dict(os.environ, MAKEOBJDIR=str(obj)), check=True)
    shutil.copy2(obj / "crunchgen", HOST / "bin/crunchgen")
    print(f"host: {HOST / 'bin/crunchgen'}")


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
                    "NOMAN=1", "CRTBEGIN=", "CRTEND=", "LIBCRT0=", "LIBC=", f"DPADD={lib}", f"LDADD={lib}",
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


# The installer's ramdisk image: rd(4)'s size in the kernel that boots it (the Kernel's
# bsd.RAMDISK, 65536 sectors), which the image is padded to exactly.
MINIROOT_SECTORS = 65536


def step_miniroot(arch: str, out: Path) -> None:
    """target/<arch>/miniroot80.fs: the installer's ramdisk as distrib/<arch>/ramdisk's mr.fs
    target makes it, without the kernel (OS sets the image into the Kernel's bsd.RAMDISK with
    rdsetroot): instbin crunched by crunchgen from distrib/special, then the list run by
    distrib/miniroot's runlist.sh into a staging tree laid out by its mtree.conf, then makefs.
    The host's tools are the tree's (crunchgen, mtree, pwd_mkdb, tic, makefs); MAKEDEV's
    nodes and every owner go through the stand-ins' metalog. The image is the same in every
    build of one commit: makefs takes the epoch for its times and labels."""
    rd = f"distrib/{arch}/ramdisk"
    src, sysroot = out / "src", out / "sysroot"
    for d in ("distrib/special", "distrib/special/zstd", rd):
        make_walk(arch, out, d, "obj")
    if make_walk(arch, out, "distrib/special/libstubs") or make_walk(arch, out, rd, "instbin"):
        raise SystemExit(f"miniroot: instbin did not build ({rd})")
    objdir = (src / rd / "obj").resolve()
    staging = out / "miniroot"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()
    log = out / "miniroot-metalog"
    log.unlink(missing_ok=True)
    env = make_env(arch, out)
    env.update(WORLD_METALOG=str(log), MAKEDEV_PARTITIONS="16")
    utils = src / "distrib/miniroot"
    # -U, the -u of the recipe that exits 0 once every mismatch is corrected: in a new tree
    # every directory is one.
    subprocess.run([str(HOST / "bin/mtree"), "-def", str(utils / "mtree.conf"), "-p", str(staging), "-U"],
                   env=env, check=True, stdout=subprocess.DEVNULL)
    # runlist.sh's script, with MAKEDEV run as the image step runs it: from a copy whose PATH
    # line leads to the stand-ins, by bash (the base system's sh has `echo -n` and `local`).
    makedev = src / f"etc/etc.{arch}/MAKEDEV"
    runner = out / "MAKEDEV.build"
    runner.write_text(makedev.read_text().replace("\nPATH=/sbin:/usr/sbin:/bin:/usr/bin\n",
                                                  f"\nPATH={HOST / 'bin'}:/bin:/usr/bin\n"))
    script = subprocess.run(["awk", "-f", str(utils / "list2sh.awk"), str(src / rd / "list")],
                            capture_output=True, text=True, check=True).stdout
    old = "(cd ${TARGDIR}; cd dev; sh MAKEDEV ramdisk)"
    assert script.count(old) == 1, "the list's MAKEDEV line moved"
    script = script.replace(old, f"(cd ${{TARGDIR}}; cd dev; /bin/bash {runner} ramdisk)")
    env.update(CURDIR=str(src / rd), OBJDIR=str(objdir), OSrev=OSREV, TARGDIR=str(staging),
               UTILS=str(utils), RELEASEDIR="", DESTDIR=str(sysroot))
    subprocess.run(["sh", "-e"], input=script, text=True, env=env, check=True, stdout=subprocess.DEVNULL)
    (staging / "instbin").unlink()
    # The table makefs's lstat reads: mtree.conf's directories, then what the metalog
    # recorded (chmod, chown, MAKEDEV's nodes); the rest is root's and wheel's.
    users, groups = ids_of(utils)
    attrs = {path: dict(keys) for path, keys in mtree_entries(utils / "mtree.conf")}
    for path, rec in read_metalog(log, staging).items():
        attrs.setdefault(path, {}).update(rec)
    lines = []
    for path, rec in sorted(attrs.items()):
        f = staging / path
        if not (f.exists() or f.is_symlink()):
            continue
        st = f.lstat()
        mode = int(rec["mode"], 8) if rec.get("mode", "").isdigit() else st.st_mode & 0o7777
        kind = {"char": "c", "block": "b"}.get(rec.get("type", ""), "d" if f.is_dir() else "f")
        lines.append(f"{mode:o} {users.get(rec.get('uname', 'root'), 0)} {groups.get(rec.get('gname', 'wheel'), 0)} "
                     f"{kind} {rec.get('major', 0)} {rec.get('minor', 0)} {path}")
    table = out / "miniroot-attrs"
    table.write_text("\n".join(lines) + "\n")
    disktab = out / "miniroot-disktab"
    tracks, sectors = 2, 256
    disktab.write_text(
        f"rdroot|ramdiskroot|RAM-disk root FS image:\\\n"
        f"\t:dt=rdroot:se#512:nc#{MINIROOT_SECTORS // (tracks * sectors)}:nt#{tracks}:ns#{sectors}:\\\n"
        f"\t:ta=4.2BSD:oa#0:pa#{MINIROOT_SECTORS}:fa#512:ba#4096:\\\n"
        f"\t:oc#0:pc#{MINIROOT_SECTORS}:\n")
    image = out / f"miniroot{OSREV}.fs"
    image.unlink(missing_ok=True)
    subprocess.run([str(HOST / "bin/makefs"), "-T", EPOCH, "-o", "disklabel=rdroot,minfree=0,density=4096",
                    str(image), str(staging)],
                   env=dict(os.environ, WORLD_STAGING=str(staging), WORLD_ATTRS=str(table),
                            WORLD_DISKTAB=str(disktab), SOURCE_DATE_EPOCH=EPOCH), check=True)
    size, want = image.stat().st_size, MINIROOT_SECTORS * 512
    if size > want:
        raise SystemExit(f"miniroot: {image} is {size} bytes, more than rd(4)'s {want}")
    with open(image, "r+b") as fh:
        fh.truncate(want)
    print(f"miniroot: {image} ({want} bytes, {len(lines)} entries with attributes)")


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
# Other settings a directory needs, for that directory only: crunchgen's instbin.mk links
# with bsd.own.mk's NOPIE_LDFLAGS, -nopie, a spelling the base system's clang and lld
# accept and DevTools' do not; -no-pie is the same option in both.
DIR_VARS = {f"distrib/{arch}/ramdisk": ("NOPIE_LDFLAGS=-no-pie",) for arch in ("arm64", "amd64")}


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
            *DIR_VARS.get(directory, ()),
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
            # The packages' autoconf tables are data about other systems and stay as they are
            # (the rename keeps them), so the host they are told is the one they know.
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
    # The imported programs, which no SUBDIR of the base system names.
    places = [where for _, _, where in imported()]
    bad = [w for w in places if make_walk(arch, out, w, "obj") or make_walk(arch, out, w) or
           make_walk(arch, out, w, "install")]
    failed += bad
    print(f"base: imported: {len(places) - len(bad)} of {len(places)} built and installed")
    failed += install_from_kernel(arch, out)
    (out / "failed").write_text("".join(f"{d}\n" for d in failed))
    print(f"base: {len(failed)} failed, listed in {out / 'failed'}")


def install_from_kernel(arch: str, out: Path) -> list:
    """What the base system takes from the Kernel's release (KERNEL.toml, fetched by
    `just fetch`): the boot loader, in /usr/mdec as the base system's own Makefile installs
    its loader (root, bin, 555). Returns what could not be installed."""
    with open(ROOT / "KERNEL.toml", "rb") as fh:
        k = tomllib.load(fh)["kernel"]
    where = ROOT / "upstream/kernel" / k["release"]
    pin = where / ".pin"
    if arch not in k["sha256"] or not pin.exists() or pin.read_text().strip() != k["commit"]:
        print(f"base: kernel {k['release']}: {arch} not fetched or not pinned (just fetch)")
        return [f"KERNEL.toml {k['release']} {arch}"]
    for name in k["take"]:
        subprocess.run([str(HOST / "bin/install"), "-c", "-o", "root", "-g", "bin", "-m", "555",
                        str(where / f"kernel-{k['release']}-{arch}" / name), str(out / "sysroot/usr/mdec" / name)],
                       env=make_env(arch, out), check=True)
    print(f"base: kernel {k['release']}: {', '.join(k['take'])} installed in /usr/mdec")
    return []


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
    """The install sets, as distrib/sets/maketars makes them (one archive per set, from
    DESTDIR, in its list's order with the libraries first), with the owners, groups and modes
    the metalog and the mtree specification give, not the building user's: bsdtar reads an
    mtree description of each entry. Compressed with zstd (level 19), not gzip as the base
    system's are: <set>80.tar.zst, which the installer reads once the base system carries
    zstd (an import), pax runs it and install.sub names the sets so. Every entry's time is
    the epoch and zstd's frame has none, so the archives are the same in every build of one
    commit; SHA256 is the base system's sha256 over them, as a release lists them.
    distrib/sets/checkflist's comparison of the lists with DESTDIR is written to
    sets/checkflist."""
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
        archive = sets / f"{name}{OSREV}.tar.zst"
        subprocess.run(["bsdtar", "-c", "--zstd", "--options", "zstd:compression-level=19", "--format=ustar", "-f", str(archive),
                        f"@{sets / (name + '.mtree')}"], check=True)
        report.append(f"{name}: {len(entries) - len(missing)} of {len(entries)} entries, "
                      f"{archive.stat().st_size // 1024} KiB")
        (sets / f"{name}.missing").write_text("".join(m + "\n" for m in missing))
    # The installer's ramdisk and the installation notes travel with the sets, as a release
    # lists them.
    released = [f"{name}{OSREV}.tar.zst" for name in SETS]
    if (out / f"miniroot{OSREV}.fs").exists():
        shutil.copy2(out / f"miniroot{OSREV}.fs", sets / f"miniroot{OSREV}.fs")
        released.append(f"miniroot{OSREV}.fs")
    # The installation notes, EmiBSD's own: the installer asks before it takes sets from a
    # directory without them.
    notes = BASE / f"distrib/installer/notes/INSTALL.{arch}"
    if notes.exists():
        shutil.copy2(notes, sets / notes.name)
        released.append(notes.name)
    sums = subprocess.run([str(HOST / "bin/sha256"), *released], cwd=sets,
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
         "sets": step_sets, "etc": step_etc, "miniroot": step_miniroot}
# `just world arm64` with no step: the base system built and installed into the sysroot.
# `make obj` first, as in the base system: include/Makefile has librpcsvc generate its
# headers, which then must be in that library's obj, where its sources are compiled.
DEFAULT = ("tree", "host", "obj", "includes", "lib", "base", "etc", "miniroot", "sets")


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
