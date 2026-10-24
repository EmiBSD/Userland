#!/usr/bin/env python3
"""The CVE history of a program from NVD, as rows for DEFINITION.md's Security history.

usage: cve.py <program dir> [--since YEAR] [--json]

Reads the CPE: `[security] cpe` of UPSTREAM.toml for an imported program, or the
`cpe = "vendor:product"` line of a written program's DEFINITION.md (the CPE of its namesakes,
e.g. `cpe = "openbsd:openbsd"` with a `cve-keyword = "grep"` to narrow). Queries NVD's API 2.0
(network; set NVD_API_KEY for the higher rate limit), caches the raw answer under
target/cve/<program>.json, and prints Markdown rows: CVE, year, CVSS, class (the CWE), summary.
Stdlib only. Run only with the user's OK: it uses the network.
"""
import json
import os
import re
import sys
import time
import tomllib
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://services.nvd.nist.gov/rest/json/cves/2.0"


def cpe_of(prog: Path):
    up = prog / "UPSTREAM.toml"
    if up.exists():
        with open(up, "rb") as fh:
            data = tomllib.load(fh)
        return data.get("security", {}).get("cpe", ""), data["upstream"].get("version", ""), ""
    text = (prog / "DEFINITION.md").read_text()
    m = re.search(r'^cpe\s*=\s*"([^"]+)"', text, re.M)
    k = re.search(r'^cve-keyword\s*=\s*"([^"]+)"', text, re.M)
    return (m[1] if m else ""), "", (k[1] if k else prog.name)


def fetch(params: dict) -> dict:
    out, start = {"vulnerabilities": []}, 0
    headers = {"User-Agent": "EmiBSD-Userland tools/cve.py"}
    if os.environ.get("NVD_API_KEY"):
        headers["apiKey"] = os.environ["NVD_API_KEY"]
    while True:
        q = dict(params, startIndex=start, resultsPerPage=200)
        req = urllib.request.Request(API + "?" + urllib.parse.urlencode(q), headers=headers)
        with urllib.request.urlopen(req, timeout=60) as r:
            page = json.load(r)
        out["vulnerabilities"] += page.get("vulnerabilities", [])
        start += page.get("resultsPerPage", 0)
        if start >= page.get("totalResults", 0) or not page.get("resultsPerPage"):
            return out
        time.sleep(6 if "apiKey" not in headers else 0.6)   # NVD's public rate limit


def rows(data: dict, since: int):
    for v in data["vulnerabilities"]:
        c = v["cve"]
        cid, year = c["id"], int(c["published"][:4])
        if year < since:
            continue
        desc = next((d["value"] for d in c.get("descriptions", []) if d["lang"] == "en"), "")
        metrics = c.get("metrics", {})
        score = ""
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            if key in metrics:
                score = str(metrics[key][0]["cvssData"]["baseScore"])
                break
        cwes = [d["value"] for w in c.get("weaknesses", []) for d in w.get("description", []) if d["value"].startswith("CWE")]
        yield cid, year, score, ", ".join(sorted(set(cwes))) or "?", desc.replace("|", "\\|").strip()


def main(argv) -> int:
    if not argv or argv[0].startswith("-"):
        print(__doc__)
        return 2
    prog = Path(argv[0]).resolve()
    since = int(argv[argv.index("--since") + 1]) if "--since" in argv else 0
    cpe, version, keyword = cpe_of(prog)
    if not cpe:
        print(f"cve: {prog.relative_to(ROOT)}: no CPE (UPSTREAM.toml [security] cpe, or `cpe = \"vendor:product\"` in DEFINITION.md)")
        return 1
    vendor, product = cpe.split(":", 1)
    match = f"cpe:2.3:a:{vendor}:{product}:{version or '*'}:*:*:*:*:*:*:*" if vendor != "openbsd" or product != "openbsd" \
        else f"cpe:2.3:o:openbsd:openbsd:*:*:*:*:*:*:*:*"
    params = {"virtualMatchString": match}
    if keyword:
        params["keywordSearch"] = keyword
    cache = ROOT / "target" / "cve" / f"{prog.name}.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    data = fetch(params)
    cache.write_text(json.dumps(data, indent=1))
    if "--json" in argv:
        print(cache)
        return 0
    print(f"<!-- {len(data['vulnerabilities'])} entries from NVD for {match}{' keyword ' + keyword if keyword else ''}; cached in {cache.relative_to(ROOT)} -->")
    print("| CVE | Year | CVSS | Class | Summary | Here |")
    print("|---|---|---|---|---|---|")
    for cid, year, score, cwe, desc in sorted(rows(data, since), key=lambda r: r[0]):
        print(f"| {cid} | {year} | {score} | {cwe} | {desc[:160]} | |")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
