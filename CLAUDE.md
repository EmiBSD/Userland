# EmiBSD Userland

The monorepo of EmiBSD's userland: the programs, libraries and configuration above the
Kernel (`../Kernel`, GitHub `EmiBSD/Kernel`). Phase 3 of the project. Since the user's
decision of 2026-11-04 its base is **inherited**: OpenBSD's base system at LandingZone's pin,
in this repository's layout, changed only by patches; the programs **written from scratch in
Rust** grow from it one at a time. The first written programs (`cli`, `sys`, `ls`, `cp`)
were a proof of concept: their code is on the `experimental` branch (read it with `git show
experimental:<path>`), their documents stay in `main` at `designed`, and `main` has no Rust
code, no `Cargo.toml` and no toolchain pin until a written program is implemented again.
The process of a written program (the user's decisions of 2026-10-23, that nothing is ported,
2026-10-24 and 2026-10-25): the reference manual and code are read to write a program's specification
(DEFINITION.md: what each parameter does, how the output is formatted, the exit codes) and,
while implementing, to resolve what the specification leaves open and to check a behaviour;
the specification stays the contract, the code takes the behaviour and never the structure
or the text (nothing is copied or translated), and the repository names another system only
where code under its copyright is compiled, the inherited and imported classes. The written programs owe
nothing to anyone, in fact and in appearance.

Everything in this repository (code, comments, docs, commits, every Markdown file) is in
English, and no conversation is quoted verbatim: a decision is recorded by its date and its
substance, in English. The user is answered in Spanish.

## Non-negotiables

- `README.md` ("Rules") and `docs/PROGRAM.md` (the contract of a program, the common grammar,
  linking, versions) are the rules; this file points at them. `.claude/rules/rust.md` is
  the practice under them: how Rust is written here, with the compressed list for agents.
- Three classes: **inherited** (the base system's C at the pin, in our layout, patches only),
  **imported** (a third-party upstream, `UPSTREAM.toml` pin, patches, never rewritten) and
  **written** (from scratch, Rust, `#![forbid(unsafe_code)]`). The inherited class is decided
  but not built yet: `tools/layout.py` still writes those skeletons as written programs at
  `planned` (README, "Open"). `unsafe` only in `base/lib/libc`, `base/libexec/rtld`
  and `base/lib/crates/sys`, each site with a `// SAFETY:` proof.
- **One grammar**: a program is a query over records (or an action whose steps are records)
  with a schema; one `Command` declares its options with their types and `cli` derives the
  parser, `--help` (text and `-o json`), usage, diagnostics and exit codes 0/1/2; `-o`
  selects the renderer; `--request` takes the whole invocation as one JSON document (file or
  inline, never stdin) lowered to the same parser, `--show-request` prints it, `--help -o json`
  publishes the keys, and under `-o json` every diagnostic is a `Diagnostic` record on stderr
  (`severity`, `code` = errno name, `subject`), so a person and a machine drive every program
  the same way. POSIX short
  flags keep their meaning and the POSIX forms to a pipe are the standard's byte for byte; to
  a terminal the defaults are modern.
- `bin/` and `sbin/` static (`src/build.rs`), `usr/` and `libexec/` dynamic.
- Semver per program with the `Change: breaking|feature|fix` trailer the `commit-msg` hook
  enforces (`just setup`); `YEAR.MONTH` for releases. No GPL. Nothing installed and nothing
  downloaded without the user's OK; `../Kernel/reference/openbsd-src` and `upstream/` are
  read-only, read with `git show` or `sed -n`, never from inside.
- Commit on the user's explicit go-ahead, push only when the user asks for a push; never
  push otherwise.

## Directory map

```
base/                                  the system that is built, the BSD trees:
  bin/ sbin/ usr/bin usr/sbin libexec/   the programs, grouped by purpose
  lib/crates/cli lib/crates/sys          the shared crates: the grammar; the FFI
  lib/ data/ etc/ distrib/              libraries, data, /etc, the release (the toolchains are DevTools')
regress/                               the integration battery against a reference system
docs/PROGRAM.md                        the contract (generated from tools/layout.py)
tools/                                 layout.py, version.py, upstream.py, cve.py, program.just
.claude/agents .claude/rules           the subagents and their contract (subagents.md)
```

## Working

`PATH=/opt/homebrew/opt/rustup/bin:$PATH`; `just check` at the root (fmt, clippy `-D
warnings`, tests, once a written program brings the workspace back); `just lint`, `just test`, `just man` in a program's directory; `just
status` for the progress numbers. A program is made by the roles of
`.claude/rules/subagents.md`: `surveyor` (the standard's facts), `designer` (DEFINITION, DESIGN,
schemas), `implementer` (src, tests, manual), `reviewer`, `integrator`; `mechanical` for the
same change over many programs. The main session launches them one by one with the Agent
tool and gives each the six items of the launching prompt.
