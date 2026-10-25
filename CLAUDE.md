# EmiBSD Userland

The monorepo of EmiBSD's own userland: the programs, libraries and configuration above the
Kernel (`../Kernel`, GitHub `EmiBSD/Kernel`), **written from scratch in Rust** under one
contract. Phase 3 of the project: until the kernel's redesign closes at N9, EmiBSD runs an
inherited base system unmodified; this repository is where the system that replaces it is
written. The process (the user's decisions of 2026-10-23, "no vamos a migrar", and
2026-10-24): the reference manual and code are read only to write a program's specification
(DEFINITION.md: what each parameter does, how the output is formatted, the exit codes); the
implementation is written from the specification alone, never from that code; and the
repository names another system only where code under its copyright is compiled, the
imported class. The written programs owe nothing to anyone, in fact and in appearance.

Everything in this repository (code, comments, docs, commits) is in English. The user is
answered in Spanish.

## Non-negotiables

- `README.md` ("Rules") and `docs/PROGRAM.md` (the contract of a program, the common grammar,
  linking, versions) are the rules; this file points at them.
- Two classes: **written** (from scratch, Rust, `#![forbid(unsafe_code)]`) and **imported**
  (`UPSTREAM.toml` pin, patches, never rewritten). `unsafe` only in `lib/libc`, `libexec/rtld`
  and `lib/crates/sys`, each site with a `// SAFETY:` proof.
- **One grammar**: a program is a query over records (or an action whose steps are records)
  with a schema; one `Command` declares its options with their types and `cli` derives the
  parser, `--help` (text and `-o json`), usage, diagnostics and exit codes 0/1/2; `-o`
  selects the renderer; `--request` takes the whole invocation as one JSON document (file or
  inline, never stdin) lowered to the same parser, `--show-request` prints it, `--help -o json`
  publishes the keys, so a person and a machine drive every program the same way. POSIX short
  flags keep their meaning and the POSIX forms to a pipe are the standard's byte for byte; to
  a terminal the defaults are modern.
- `bin/` and `sbin/` static (`src/build.rs`), `usr/` and `libexec/` dynamic.
- Semver per program with the `Change: breaking|feature|fix` trailer the `commit-msg` hook
  enforces (`just setup`); `YEAR.MONTH` for releases. No GPL. Nothing installed and nothing
  downloaded without the user's OK; `../Kernel/reference/openbsd-src` and `upstream/` are
  read-only, read with `git show` or `sed -n`, never from inside.
- Commit on the user's "dale", push on "súbelo"; never push otherwise.

## Directory map

```
bin/ sbin/ usr/bin usr/sbin libexec/   the programs, the BSD trees, grouped by purpose
lib/crates/cli lib/crates/sys          the shared crates: the grammar; the FFI
lib/ compiler/ data/ etc/ distrib/     libraries, the toolchains (imported), data, /etc, the release
regress/                               the integration battery against a reference system
docs/PROGRAM.md                        the contract (generated from tools/layout.py)
tools/                                 layout.py, version.py, upstream.py, cve.py, program.just
.claude/agents .claude/rules           the subagents and their contract (subagents.md)
```

## Working

`PATH=/opt/homebrew/opt/rustup/bin:$PATH`; `just check` at the root (fmt, clippy `-D
warnings`, tests); `just lint`, `just test`, `just man` in a program's directory; `just
status` for the progress numbers. A program is made by the roles of
`.claude/rules/subagents.md`: `surveyor` (the standard's facts), `designer` (DEFINITION, DESIGN,
schemas), `implementer` (src, tests, manual), `reviewer`, `integrator`; `mechanical` for the
same change over many programs. The main session launches them one by one with the Agent
tool and gives each the six items of the launching prompt.
