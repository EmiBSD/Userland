# mechanical: lessons across runs

One line per lesson, appended at the end; task state goes in HANDOFF.md
(`.claude/rules/subagents.md`, "Memory"). Committed with the tree.
- tools/world.py rename pass: a partial keep-list for names (Perl OpenBSD:: dir, triples) breaks the build in pkg_add's Makefile; rename all or keep all, and read Latin-1 files as latin-1 or identifiers split across files (isakmpd).
- A full 'just world arm64' takes about 15 minutes of wall time; the Bash tool may report waits as much longer, check 'date'. Worktree hook refuses loops and heredoc python: put scripts in the scratchpad and run them.
- Kernel-ABI headers installed from the Kernel's include/ are un-renamed: run world.py's Rename over the copies or libc's init.c (AUX_emibsd_*) stops compiling; the result equals the tree-renamed headers byte for byte.
- The Kernel's MANUAL.toml listed syscalls 295-297 (__semctl, shmctl, msgctl) as absent with empty names while its sys/syscall.h defines them: the build's by-name-and-number check catches it; report to the Kernel, never loosen the check.
- Agent worktree hook: no shell variables in commands, no python heredocs, no `git -C` into other trees; a worktree's upstream/ can be a symlink to a private scratchpad copy so fetch_kernel can unpack without writing the main checkout's.
- `just layout` needs an absolute reference path from a worktree (the default ../Kernel is wrong there) and also regenerates unrelated drift (installer patch list, jpath DEFINITION): git checkout those back.
