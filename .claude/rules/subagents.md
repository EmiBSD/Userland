# Subagents: the common contract

The repository's subagents are defined in `.claude/agents/*.md`, adapted on 2026-10-24 from
the Kernel's set-up (its `.claude/rules/subagents.md`, in force there since 2026-10-10) to
the way a userland program is made: surveyed, defined and designed, implemented, reviewed,
integrated. Every definition points here; this file is the part they share. The rules it
summarises stay authoritative in `README.md` ("Rules") and `docs/PROGRAM.md` (the contract
of a program, the common grammar, linking, versions); when they change, this file follows.

## Roles

| Agent | Model | Worktree | Memory | Writes | Use it for |
|---|---|---|---|---|---|
| `surveyor` | opus | no | yes | scratchpad | read-only inventory of an OpenBSD program before it is defined: what it does, every flag and its meaning, exit codes, who in the base system calls it and with what, what it parses and prints, its CVE history, what `std`, `cli` and `sys` lack for it; facts with `file:line`, never a design |
| `designer` | fable | yes | yes | branch (documents) | DEFINITION.md, DESIGN.md, `schemas/`, the manual's SYNOPSIS and DESCRIPTION of one program from the survey; STATUS to `defined` then `designed`; proposes the decisions the user must take, never takes them, never writes code |
| `implementer` | opus | yes | yes | branch | `src/`, `tests/`, the manual's EXAMPLES, DELIVERY.md of a designed program, on `cli` and `sys`; the additions those two crates need for it (a `Kind`, a libc call), each with its reason; one program per run |
| `mechanical` | sonnet | yes | yes | branch | the same change over many programs (a `cli` API moved, a rule's wording in every DEFINITION), tests added to an existing program, a manual's lint, `tools/layout.py` regeneration, an import's `UPSTREAM.toml`, `build/` and patch series once the pin is decided |
| `reviewer` | opus | no | no | nothing | read-only review of a branch: behaviour against DEFINITION.md and OpenBSD's manual, POSIX byte for byte to a pipe, `forbid(unsafe_code)`, the `pledge` profile no weaker than OpenBSD's, no C copied or translated, tests that assert behaviour, the `Change:` trailer and the version bump, the manual complete |
| `integrator` | opus | yes | yes | branch | merge agent branches, resolve the shared files (`Cargo.toml` members, `Cargo.lock`, READMEs, `docs/PROGRAM.md` through `tools/layout.py`, agent memories), finish a stopped agent's work from its `HANDOFF.md`, `just check` and `just status` |

Mechanical vs delicate (the user's split, 2026-10-03): when unsure, it is delicate (opus).
Design is Fable's (the user's decision of 2026-10-16: Fable for planning only, as a subagent,
so the main session stays on Opus); the designer writes documents, never `src/`. Concurrency:
at most 4 agents run at the same time; the main session launches each one with the Agent
tool and sees every plan and every commit; there is no batch workflow (the user's decision of
2026-10-10: a migration driven by a session, never by a Workflow).

Effort (the user's decision, 2026-10-19): every definition fixes `effort` in its frontmatter,
so a run never inherits the main session's level: `medium` for `mechanical` and `surveyor`
(their value is completeness), `high` for the rest. The launching session may raise one run
to `xhigh` when the task justifies it (a program over 3,000 lines of reference C, a
security-sensitive program: anything setuid, anything that parses the network, anything that
writes `/etc`) and says so in the prompt; it never lowers one.

Turns: the read-only roles carry `maxTurns` as a spending stop (`reviewer` 300, `surveyor`
300). At the limit Claude Code returns the output marked partial; the launching session
resumes the run once with `SendMessage` if the work is worth finishing; a second partial
return is a stop: the user decides. The worktree roles carry none: a stop in the middle of
their work leaves commits unmade.

Guard hook: the writing roles (`designer`, `implementer`, `mechanical`, `integrator`) carry a
`PreToolUse` hook, `.claude/hooks/agent-guard.sh`, that refuses before it runs: `git push`,
`git commit --amend`, a force of anything, any write under `upstream/` or under a `reference/`
tree (the Kernel's OpenBSD clone, read with `git show`, never from inside), a `cd` into
either, `cargo install`, `rustup`, `brew`, `pip`, `npm`, and `curl` or `wget` (nothing is
installed and nothing is downloaded without the user's OK; `tools/upstream.py fetch` is the
one sanctioned download and runs from the main session). A refusal is a "STOP" like any
other: the agent reports it, never routes around it. It is a belt against a slip, not a wall.

Reviews (the user's decision of 2026-10-22, kept): one `reviewer` run per program before its
merge; its findings go back to the **same** implementer with `SendMessage`, never to a fresh
agent; a second review only when the first found something blocking, or when the program is
security-sensitive (setuid, network input, `/etc`). The main session checks every other fix
itself and writes that check in the merge message.

## Memory (`memory: project`)

An agent with memory keeps `.claude/agent-memory/<agent>/MEMORY.md`: lessons that outlive one
run (an idiom that took two attempts, a `cli` pattern that fits a kind of program, a clippy
lint and its fix, a mandoc pitfall), one line each, in English, appended at the end. It is
committed with the tree; a worktree agent's lines travel on its branch and merge by git's
`union` driver (`.gitattributes`); whoever merges drops exact duplicates. Task state
(branches, hashes, what is left) goes in `HANDOFF.md` in the scratchpad, never in memory. The
`reviewer` has none on purpose: fresh eyes.

## What the launching prompt must give

The definitions are generic; the prompt of each launch supplies the specifics:

1. the program(s) and the scope: the directory (`bin/files/cp`), the STATUS it starts at and
   the one it must reach, what is explicitly out;
2. the base commit or the branch to merge first;
3. the scratchpad directory for `HANDOFF.md`, the survey and logs;
4. what else runs on the machine at the same time (in this repository and in the Kernel's);
5. any authorisation the user gave for this launch, quoted ("dale" and what it answered);
6. the block "Rules that apply to this work": the 10-15 lines that bind the task (the common
   grammar's points that matter for it, the POSIX forms that must match byte for byte, the
   `pledge` promises OpenBSD's program uses, what is forbidden) and the files the agent reads
   whole: always `docs/PROGRAM.md` and this file; the reviewer reads `README.md` too.

A prompt that misses one of these gets a question back, not a guess.

## Setup in a worktree

- The main checkout is the first line of `git worktree list --porcelain`:
  `MAIN=$(git worktree list --porcelain | sed -n '1s/^worktree //p')`. `upstream/` (fetched
  sources, gitignored) lives only there: `ln -s "$MAIN/upstream" upstream` when an import is
  the work, unlinked before the worktree is removed. The OpenBSD reference is the Kernel's
  clone, `$MAIN/../Kernel/reference/openbsd-src`, read with
  `git -C <that path> show HEAD:bin/cp/cp.c`; never `cd` into it, never write there.
- `PATH=/opt/homebrew/opt/rustup/bin:$PATH` before `cargo` or `just`. Install nothing. The
  worktree has its own `target/`; the main checkout's is never used.
- `just setup` once, so the `commit-msg` hook runs (it is `core.hooksPath`, shared by the
  worktrees of one repository; check with `git config core.hooksPath`).
- Read the "Rules that apply to this work" block of your prompt and the files it names
  before writing anything.

## While working

- Author block: every file starts with the author's ISC block (`LICENSE`; copy the header of
  `lib/crates/cli/src/lib.rs`). Everything in the repository is in English.
- A written program is written from scratch under its DEFINITION; OpenBSD's code is read for
  behaviour, never copied or translated. A program parses nothing itself: its `Command`
  declares the options with their types and `cli` does the rest (`docs/PROGRAM.md`, "The
  common grammar"). `#![forbid(unsafe_code)]`; `unsafe` only in `lib/crates/sys` with a
  `// SAFETY:` proof, and only for what `std` lacks.
- Commit early: each piece that passes `just lint` and `just test` in the program's directory
  is committed at once. `<scope>: <imperative summary>`; the body says what and why; a
  commit that changes `src/` carries `Change: breaking|feature|fix` and the version bump it
  calls for (the hook refuses it otherwise); then the session's `Co-Authored-By:` line. A
  breaking change to `cli` or `sys` migrates every user in the same commit (the workspace
  builds as one). Never push, never amend, never touch `main`, never `git add -A` or
  `git add .`: add paths by name.
- Nothing heavy while another agent compiles the same workspace is not a concern here (each
  worktree has its own `target/`); `just check` at the root is the integrator's and the
  implementer's last step before handing back, not every commit's.
- Read cheaply: `grep`, `sed -n 'a,bp'`, long output redirected to scratchpad files. The
  program's reference C and its manual are still read completely, in ranges.
- Behaviour: to a pipe, the POSIX forms are OpenBSD's byte for byte; to a terminal, the
  common grammar's defaults. A behaviour that cannot be kept is reported with the evidence,
  never silently changed.

## Stopping

- A "STOP" refusal or a permission denial: stop at once, commit nothing more, report it.
- Anything that is the user's decision: a crate dependency, a download, an install, anything
  outside the repository, a change to `docs/PROGRAM.md`'s rules, a bump of
  `rust-toolchain.toml` or of an `UPSTREAM.toml` pin, a flag or exit code that leaves POSIX,
  a scope change: stop and hand back with the question.
- Low on context: stop in a committed state, update `HANDOFF.md` (done with hashes, left,
  the tests' counts), then hand back naming its path.

## Final report

Branch and tip, commits in order, the evidence (`just lint` and `just test` output, test
counts before and after, `just status` line, the release size for DELIVERY), the STATUS
reached, deviations from the DEFINITION or from OpenBSD's behaviour with their reason, what is
left, the `HANDOFF.md` path.
