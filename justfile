# EmiBSD Userland: the recipes over the whole monorepo. Each program has its own justfile
# importing tools/program.just; these run across all of them.

trees := "base"

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

# The base system's make(1) built for the development host from its inherited src/, into target/host/bin/make.
host-make:
    sh tools/host/bootstrap-make.sh

# Build the inherited base system for EmiBSD (tools/world.py): `just world arm64`, or some steps of it.
world arch="arm64" *steps:
    python3 -I tools/world.py {{arch}} {{steps}}

# What `just world` builds from (network): KERNEL.toml's release and the imported programs' sources.
fetch-build:
    python3 -I tools/upstream.py fetch --build

# Built from scratch in a worktree of HEAD's tag: dist/userland-<tag>-<arch>.tar.zst and .sha256.
# A release's artifact of the install sets, one per architecture (`just dist arm64`).
dist +archs:
    python3 -I tools/dist.py {{archs}}

# The maintainer's, from the main session (it uses the private key): SHA256.sig over the
# artifact's SHA256 with EmiBSD's base key, after the build is proven and before the release.
sign +archs:
    python3 -I tools/dist.py --sign {{archs}}

# A release's manual as man.emibsd.org, from its artifact in dist/ and EmiBSD's host mandoc;
# `just man-site <tag> --publish` uploads it (the main session's, after the release).
man-site tag *flags:
    python3 -I tools/man-site.py {{tag}} {{flags}}

# An internal check, never a release's medium (OS makes those): a throwaway ISO from the two
# releases, an install in QEMU under /tmp/emibsd/ci.lock, the installed disk booted to a shell.
install-check tag arch="arm64":
    python3 -I tools/install-check.py {{tag}} {{arch}}

# The same check on the sets of `just world` (target/<arch>/sets), before any tag is made.
install-check-world arch="arm64":
    python3 -I tools/install-check.py --world {{arch}}

# The maintainer's, from the main session (it publishes); a later architecture is added to it.
# The GitHub release of the sets from a tagged commit, every artifact in dist/ for it.
release tag:
    sh tools/release.sh {{tag}}

# Format, clippy and tests over the workspace; the root Cargo.toml comes back with the first written program.
check:
    #!/bin/sh
    set -e
    if [ ! -f Cargo.toml ]; then echo "check: no written program in the tree: nothing for cargo"; exit 0; fi
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

# cargo-audit and cargo-deny are `cargo install`ed tools, outside the repository: installed only with the user's OK.
# Advisories against our crate dependencies (RustSec) and the licence and duplicate policy.
audit:
    #!/bin/sh
    if command -v cargo-audit >/dev/null; then cargo audit; else echo "audit: cargo-audit not installed (cargo install cargo-audit, with the user's OK)"; fi
    if command -v cargo-deny >/dev/null; then cargo deny check; else echo "audit: cargo-deny not installed (cargo install cargo-deny, with the user's OK)"; fi

# The CVE history of one program from NVD, as rows for DEFINITION.md's Security history (network).
cve dir:
    python3 -I tools/cve.py {{dir}}
