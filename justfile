# EmiBSD Userland: the recipes over the whole monorepo. Each program has its own justfile
# importing tools/program.just; these run across all of them.

# Progress: how many programs sit at each STATUS.
status:
    @find bin sbin usr libexec lib -name STATUS | xargs cat | sort | uniq -c | sort -rn

# Every program at a given status: `just at implemented`.
at s:
    @find bin sbin usr libexec lib -name STATUS | while read f; do [ "$(cat "$f")" = "{{s}}" ] && dirname "$f"; done | sort

# Regenerate the READMEs and the missing skeletons from the map (needs Kernel's reference tree).
layout src="../Kernel/reference/openbsd-src":
    python3 -I tools/layout.py {{src}} .

# Format, clippy and tests over the workspace (the packages that joined Cargo.toml).
check:
    cargo fmt --all -- --check
    cargo clippy --workspace -- -D warnings
    cargo test --workspace
