# EmiBSD Userland: the recipes over the whole monorepo. Each program has its own justfile
# importing tools/program.just; these run across all of them.

trees := "bin sbin usr libexec lib compiler"

# Progress: how many programs sit at each STATUS (written: planned..shipped; imported: imported..).
status:
    @find {{trees}} -name STATUS | xargs cat | sort | uniq -c | sort -rn

# Every program at a given status: `just at implemented`, `just at imported`.
at s:
    @find {{trees}} -name STATUS | while read f; do [ "$(cat "$f")" = "{{s}}" ] && dirname "$f"; done | sort

# Fetch and verify every upstream named by an UPSTREAM.toml (shared clones under upstream/).
fetch:
    python3 -I tools/upstream.py fetch

# Check every fetched upstream against its pin.
fetch-check:
    python3 -I tools/upstream.py check

# Regenerate the READMEs and the skeletons still at planned/imported (needs Kernel's reference tree).
layout src="../Kernel/reference/openbsd-src":
    python3 -I tools/layout.py {{src}} .

# Format, clippy and tests over the workspace (the packages that joined Cargo.toml).
check:
    cargo fmt --all -- --check
    cargo clippy --workspace -- -D warnings
    cargo test --workspace

# Install the repository's git hooks (commit-msg: the Change: trailer and the version bump).
setup:
    git config core.hooksPath .githooks
    @echo "hooks: core.hooksPath = .githooks"

# Regenerate CHANGELOG.md of one program from its commits' Change: trailers.
changelog dir:
    python3 -I tools/version.py changelog {{dir}}
