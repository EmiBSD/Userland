# implementer: lessons across runs

One line per lesson, appended at the end; task state goes in HANDOFF.md
(`.claude/rules/subagents.md`, "Memory"). Committed with the tree.
- tools/version.py: while MAJOR is 0, `Change: feature` bumps PATCH (0.2.1 -> 0.2.2), not MINOR; every commit that touches a package's src/ needs its own bump, so N commits mean N bumps.
- The worktree guard refuses Bash with heredocs of code, multi-git chains or long `python3 -c` edits: write scratch files with Write, edit sources with Edit, one plain git command per call.
- Parsing and printing f64 (str::parse, `{:?}`) costs ~60-75 KB in a static release binary: a Value::Float or JSON reader shows up in every program's DELIVERY size.
- A hand-rolled property test is only trusted after a mutation: break the code under test in one place by sed, see the property fail, restore.
