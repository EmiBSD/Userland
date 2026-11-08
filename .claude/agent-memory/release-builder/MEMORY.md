# release-builder: lessons across runs

One line per lesson, appended at the end; task state goes in HANDOFF.md
(`.claude/rules/subagents.md`, "Memory"). Committed with the tree.

- A from-scratch `just dist arm64` takes about 25 minutes; two in a row about 50. Two builds of 2026.11.0 were identical; sums change between tags because the epoch is the tag's commit time.
- What made builds differ once, if it comes back: SOURCE_DATE_EPOCH unset, sort -R unseeded, DWARF 5 MD5s of checkout paths, makefs times and disklabel uid, gzip/zstd headers with times (see the reproducible-sets commits).
- The sets' sums in SHA256 differ from a `just world` in the main checkout: that build's epoch is HEAD's, not the tag's; compare dist with dist only.
- A published tag is never cut again: a defect found after publication is a new tag (2026.11.1 and on).
- 2026.11.2: two builds identical, install-check PASS; second build plus check about 35 minutes after the first.
- 2026.11.3: two builds identical, install-check PASS; miniroot80.fs is plain-text searchable with strings -a (check install.sub there); target/arm64 in the main checkout is a stale tree, not the dist's.
