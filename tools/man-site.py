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
"""A release's manual as a web site, man.emibsd.org (the user's decision of 2026-11-07).

usage: man-site.py <tag> [--publish]     render target/man-site/<tag>/ from the release's
                                         artifact; with --publish, upload it

The pages come from the artifact dist/userland-<tag>-arm64.tar.zst (checked against its .sha256
and its SHA256.sig with emibsd-80-base.pub): the mdoc and man sources under usr/share/man/ in
its four sets (man80 holds sections 1, 4, 5, 7 and 8; comp80 2, 3 and 9; game80 6; base80 a
few). A page is kept when it is machine-independent or arm64's (man4/arm64/); the other
architectures' subdirectories are dropped. An arm64 page whose name a machine-independent
page already has is published as arm64/<name>.<section>.

Each page is rendered by EmiBSD's own mandoc, the host build in target/host/bin (makewhatis
is mandoc under another name; `just world arm64 tree host` builds it from the renamed tree),
with `-T html -O man=%N.%S,style=mandoc.css -I os="EmiBSD <version>"`. The object key is
<name>.<section> exactly as the inherited links name it (getentropy.2), with no .html. The site
also carries the tree's mandoc.css and an index.html listing every page by section.

--publish uploads to the R2 bucket emibsd-man with the aws CLI, from the main session only (it
is a publication; subagents are refused). The credentials are shell assignments in the file
EMIBSD_R2_CREDS names (~/emibsd-keys/emibsd-r2): sourced by a shell, never read here, never
printed. The pages go up first with Content-Type `text/html; charset=utf-8` (aws would guess
binary from `.1`) and Cache-Control max-age=300, then mandoc.css, then index.html, and only
then are the keys no longer in the site deleted, so the root never answers 404. Finally
https://man.emibsd.org/getentropy.2 must answer 200 with text/html.
"""
import hashlib
import html
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = ROOT / "target/host/bin"
BUCKET = "emibsd-man"
SITE = "https://man.emibsd.org"
ARCH = "arm64"
SETS = ("base", "comp", "game", "man")
OSREV = "80"
VERSION = "8.0"
PAGE = re.compile(r"^usr/share/man/man([1-9])(?:/([a-z0-9]+))?/([^/]+)\.([1-9][a-z]*)$")
SECTIONS = {"1": "General commands", "2": "System calls", "3": "Library functions",
            "4": "Device drivers", "5": "File formats", "6": "Games", "7": "Miscellaneous",
            "8": "System administration", "9": "Kernel internals"}


def artifact(tag: str) -> Path:
    """The release's tarball, unpacked into a temporary directory, its sums and signature checked."""
    tarball = ROOT / "dist" / f"userland-{tag}-{ARCH}.tar.zst"
    sums = tarball.with_name(tarball.name + ".sha256")
    if not tarball.exists() or not sums.exists():
        raise SystemExit(f"man-site: no {tarball.relative_to(ROOT)} and its .sha256 (just dist, or the release's download)")
    if hashlib.sha256(tarball.read_bytes()).hexdigest() != sums.read_text().split()[0]:
        raise SystemExit(f"man-site: {tarball.name} does not match its .sha256")
    work = Path(tempfile.mkdtemp(prefix="man-site-"))
    zstd = subprocess.Popen(["zstd", "-dcq", str(tarball)], stdout=subprocess.PIPE)
    with tarfile.open(fileobj=zstd.stdout, mode="r|") as tar:
        tar.extractall(work, filter="data")
    zstd.wait()
    top = work / tarball.name.removesuffix(".tar.zst")
    subprocess.run(["signify", "-C", "-q", "-p", str(ROOT / "base/etc/signify/emibsd-80-base.pub"),
                    "-x", "SHA256.sig"], cwd=top, check=True)
    return top


def pages(top: Path) -> dict:
    """{key: mdoc source bytes} for every page kept, from the four sets."""
    found, arch_pages = {}, {}
    for s in SETS:
        zstd = subprocess.Popen(["zstd", "-dcq", str(top / f"{s}{OSREV}.tar.zst")], stdout=subprocess.PIPE)
        with tarfile.open(fileobj=zstd.stdout, mode="r|") as tar:
            for member in tar:
                m = PAGE.match(member.name.removeprefix("./"))
                if not m or not (member.isfile() or member.islnk()):
                    continue
                sec, arch, name, ext = m.groups()
                if arch not in (None, ARCH):
                    continue
                if member.isfile():
                    data = tar.extractfile(member).read()
                else:   # a hard link: the target came earlier in the archive
                    data = found.get(("link", member.linkname.removeprefix("./")))
                    if data is None:
                        continue
                found[("link", member.name.removeprefix("./"))] = data
                (arch_pages if arch else found)[f"{name}.{ext}"] = data
        zstd.wait()
    site = {k: v for k, v in found.items() if isinstance(k, str)}
    for key, data in arch_pages.items():
        site[f"{ARCH}/{key}" if key in site else key] = data
    return site


def render(tag: str, site: dict, out: Path) -> None:
    with tempfile.TemporaryDirectory() as bindir:
        mandoc = Path(bindir) / "mandoc"   # mandoc's multi-call binary goes by its name
        mandoc.symlink_to(HOST / "makewhatis")
        for key, source in sorted(site.items()):
            page = out / key
            page.parent.mkdir(parents=True, exist_ok=True)
            css = "../mandoc.css" if "/" in key else "mandoc.css"
            r = subprocess.run([str(mandoc), "-T", "html",
                                "-O", f"man=%N.%S,style={css}", "-I", f"os=EmiBSD {VERSION}"],
                               input=source, capture_output=True)
            if not r.stdout:
                raise SystemExit(f"man-site: mandoc failed on {key}: {r.stderr.decode(errors='replace')[:200]}")
            page.write_bytes(r.stdout)
    shutil.copy(ROOT / "target/arm64/src/usr.bin/mandoc/mandoc.css", out / "mandoc.css")
    aliases = alias_pages(out, site)
    unlink_missing(out, set(site) | set(aliases))
    by_section = {}
    for key in site:
        by_section.setdefault(key.rsplit(".", 1)[1][0], []).append(key)
    (out / "index.html").write_text(index_page(tag, out, by_section, len(site), aliases))


NAME = re.compile(r'id="NAME".*?(?=class="Nd")', re.S)
NM = re.compile(r'<code class="Nm">([^<]+)</code>')
XR = re.compile(r'<a class="Xr" href="([^"#]+)"[^>]*>(.*?)</a>', re.S)


def alias_pages(out: Path, site: dict) -> dict:
    """{alias key: page key}: every other name a page's NAME section gives (clock_settime in
    clock_gettime.2). The base system ships one file per page and man(1) finds the others in
    mandoc.db; on the site each other name is a small page that sends the reader to the page."""
    aliases = {}
    for key in sorted(site):
        if "/" in key:
            continue
        ext = key.rsplit(".", 1)[1]
        m = NAME.search((out / key).read_text(errors="replace"))
        for name in NM.findall(m.group(0)) if m else ():
            alias = f"{html.unescape(name).strip()}.{ext}"
            if alias not in site and alias not in aliases and "/" not in alias and alias.strip("."):
                aliases[alias] = key
    for alias, key in aliases.items():
        (out / alias).write_text(
            '<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">'
            f'<meta http-equiv="refresh" content="0; url={html.escape(key)}">'
            f'<link rel="canonical" href="{html.escape(key)}"><title>{html.escape(alias)}</title></head>'
            f'<body><p><a href="{html.escape(key)}">{html.escape(alias)} is documented in '
            f'{html.escape(key)}</a>.</p></body></html>\n')
    return aliases


def unlink_missing(out: Path, keys: set) -> None:
    """A cross-reference to a page the release does not have (a package's, X11's) is text, not a 404."""
    for key in keys:
        page = out / key
        text = page.read_text(errors="replace")
        new = XR.sub(lambda m: m.group(0) if (m.group(1) if "/" not in key else "../" + m.group(1)).removeprefix("../") in keys
                     else f'<span class="Xr">{m.group(2)}</span>', text)
        if new != text:
            page.write_text(new)


ND = re.compile(r'<span class="Nd"[^>]*>(.*?)</span>', re.S)
TAG = re.compile(r"<[^>]+>")

# The index's own look: mandoc.css styles the pages, not a list of them.
INDEX_CSS = """
:root { color-scheme: light dark; --bg: #fbfbfa; --fg: #1d1d1f; --muted: #6b6b70;
  --line: #e4e4e2; --link: #0b57d0; --chip: #f0f0ee; --hi: #fff6d6; }
@media (prefers-color-scheme: dark) { :root { --bg: #161618; --fg: #ececee; --muted: #9a9aa2;
  --line: #2c2c30; --link: #8ab4f8; --chip: #222226; --hi: #3a3320; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg);
  font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
header { position: sticky; top: 0; z-index: 1; background: var(--bg);
  border-bottom: 1px solid var(--line); padding: 16px 24px 12px; }
h1 { margin: 0; font-size: 22px; font-weight: 650; letter-spacing: -0.01em; }
.sub { margin: 2px 0 12px; color: var(--muted); font-size: 13px; }
.bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
#q { flex: 1 1 260px; max-width: 420px; padding: 7px 11px; font: inherit; color: var(--fg);
  background: var(--chip); border: 1px solid var(--line); border-radius: 8px; outline: none; }
#q:focus { border-color: var(--link); }
nav a { display: inline-block; padding: 4px 10px; border-radius: 999px; background: var(--chip);
  color: var(--fg); text-decoration: none; font-size: 13px; }
nav a:hover { color: var(--link); }
main { padding: 8px 24px 48px; max-width: 1400px; }
h2 { font-size: 16px; margin: 28px 0 8px; padding-bottom: 6px; border-bottom: 1px solid var(--line); }
h2 span { color: var(--muted); font-weight: 400; }
ul { list-style: none; margin: 0; padding: 0; display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 2px 24px; }
li { padding: 3px 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
li a { color: var(--link); text-decoration: none; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13.5px; }
li a:hover { text-decoration: underline; }
li .s { color: var(--muted); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
li .d { color: var(--muted); }
li.hit { background: var(--hi); border-radius: 4px; }
.none { color: var(--muted); display: none; margin-top: 24px; }
footer { color: var(--muted); font-size: 12px; padding: 0 24px 32px; }
@media (max-width: 600px) { header, main, footer { padding-left: 16px; padding-right: 16px; }
  ul { grid-template-columns: 1fr; } }
"""

# Filter by name or description as you type; / focuses the box.
INDEX_JS = """
const q = document.getElementById('q'), items = [...document.querySelectorAll('li')];
const groups = [...document.querySelectorAll('section')], none = document.querySelector('.none');
function filter() {
  const v = q.value.trim().toLowerCase();
  for (const li of items) li.hidden = v !== '' && !li.dataset.k.includes(v);
  let shown = 0;
  for (const g of groups) { const n = g.querySelectorAll('li:not([hidden])').length; g.hidden = n === 0; shown += n; }
  none.style.display = shown ? 'none' : 'block';
}
q.addEventListener('input', filter);
document.addEventListener('keydown', e => { if (e.key === '/' && document.activeElement !== q) { e.preventDefault(); q.focus(); } });
"""


def index_page(tag: str, out: Path, by_section: dict, count: int, aliases: dict) -> str:
    """index.html: every page by section, with its one-line description, filtered as one types."""
    nav, body = [], []
    others = {}
    for alias, key in aliases.items():
        others.setdefault(key, []).append(alias.rsplit(".", 1)[0])
    for sec in sorted(by_section):
        title = SECTIONS.get(sec, "")
        nav.append(f'<a href="#s{sec}">{sec} {html.escape(title)}</a>')
        rows = []
        for key in sorted(by_section[sec], key=str.lower):
            m = ND.search((out / key).read_text(errors="replace"))
            desc = html.unescape(TAG.sub("", m.group(1))).strip() if m else ""
            name, ext = key.rsplit(".", 1)
            keywords = " ".join([name, *others.get(key, []), desc]).lower()
            rows.append(f'<li data-k="{html.escape(keywords)}"><a href="{html.escape(key)}">'
                        f'{html.escape(name)}</a><span class="s">({html.escape(ext)})</span>'
                        f'{" <span class=d>&mdash; " + html.escape(desc) + "</span>" if desc else ""}</li>')
        body.append(f'<section><h2 id="s{sec}">Section {sec} <span>{html.escape(title)}</span></h2>\n<ul>\n'
                    + "\n".join(rows) + "\n</ul></section>")
    return ('<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<title>EmiBSD {VERSION} manual pages</title>\n<style>{INDEX_CSS}</style>\n</head>\n<body>\n'
            f'<header><h1>EmiBSD {VERSION} manual pages</h1>\n'
            f'<p class="sub">Userland {html.escape(tag)} &middot; {count} pages &middot; on a system: <code>man ls</code></p>\n'
            '<div class="bar"><input id="q" type="search" placeholder="Filter by name or description  ( / )" '
            'autocomplete="off" aria-label="Filter the manual pages">\n'
            f'<nav aria-label="Sections">{" ".join(nav)}</nav></div></header>\n<main>\n'
            + "\n".join(body) + '\n<p class="none">No page matches.</p>\n</main>\n'
            '<footer>Rendered by EmiBSD&rsquo;s mandoc from the release&rsquo;s sets.</footer>\n'
            f'<script>{INDEX_JS}</script>\n</body>\n</html>\n')


def publish(out: Path) -> None:
    creds = os.environ.get("EMIBSD_R2_CREDS", str(Path.home() / "emibsd-keys/emibsd-r2"))
    if not Path(creds).exists():
        raise SystemExit("man-site: no R2 credentials file (EMIBSD_R2_CREDS)")
    meta = ["--cache-control", "max-age=300", "--only-show-errors"]
    steps = [
        ["s3", "sync", ".", f"s3://{BUCKET}", "--exclude", "index.html", "--exclude", "mandoc.css",
         "--content-type", "text/html; charset=utf-8", *meta],
        ["s3", "cp", "mandoc.css", f"s3://{BUCKET}/mandoc.css", "--content-type", "text/css; charset=utf-8", *meta],
        ["s3", "cp", "index.html", f"s3://{BUCKET}/index.html", "--content-type", "text/html; charset=utf-8", *meta],
        ["s3", "sync", ".", f"s3://{BUCKET}", "--delete", "--exclude", "index.html", "--exclude", "mandoc.css",
         "--content-type", "text/html; charset=utf-8", *meta],
    ]
    for step in steps:
        # The credentials reach aws through a shell that sources the file; nothing here reads it.
        subprocess.run(["sh", "-c", 'set -a; . "$0"; set +a; export AWS_DEFAULT_REGION=auto '
                        'AWS_ENDPOINT_URL="$R2_ENDPOINT" AWS_PAGER=; exec aws "$@"', creds, *step],
                       cwd=out, check=True)
    r = subprocess.run(["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code} %{content_type}",
                        f"{SITE}/getentropy.2"], capture_output=True, text=True)
    print(f"man-site: {SITE}/getentropy.2 -> {r.stdout}")
    if not r.stdout.startswith("200 text/html"):
        raise SystemExit("man-site: the published page does not answer 200 text/html")


def main() -> int:
    args = sys.argv[1:]
    if not args or len(args) > 2 or (len(args) == 2 and args[1] != "--publish"):
        print(__doc__, file=sys.stderr)
        return 2
    tag = args[0]
    if not (HOST / "makewhatis").exists():
        raise SystemExit("man-site: no target/host/bin/makewhatis (just host-make; just world arm64 tree host)")
    top = artifact(tag)
    try:
        site = pages(top)
    finally:
        shutil.rmtree(top.parent, ignore_errors=True)
    out = ROOT / "target/man-site" / tag
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    render(tag, site, out)
    print(f"man-site: {len(site)} pages in {out.relative_to(ROOT)}")
    if args[1:] == ["--publish"]:
        publish(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
