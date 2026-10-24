# cp

STATUS: see `STATUS`. EmiBSD's own `cp`, written from scratch under this definition (the
user's decision of 2026-10-23); its reference is POSIX.1-2024's `cp` and the BSD habits its
users have. No other system's code is read for it. The second program of the repository, and
the one that proved the common grammar fits an action, not only a query: every copy is a record.

## What it does

Copies files. `cp source target` makes `target` a copy of `source`; `cp source ... directory`
copies each source into an existing directory under its own name. A directory source is
copied, with everything below it, only with `-R`. Each source examined becomes one record
(`schemas/copy.v1.json`): source, target, type, bytes, and what happened to it (created,
replaced, merged, skipped, planned, failed), rendered as `-v` or `-o` asks.

## Scope

In: everything POSIX's `cp` does with the same short flags (`-R`, `-H -L -P`, `-f`, `-i`,
`-p`), the BSD `-a` and `-v`, the common grammar (`-o`, `--no-headers`), `--dry-run`, and
`--help` as text or as a record. Out, deliberately: the historic `-r` (it copied links and
special files wrongly; this one refuses it); GNU's `-n`, `-u`, `-l`,
`-s`, `--reflink`, `--backup`. Hard links are not preserved (`pax`'s and `tar`'s job).
Colour is out until the common grammar has a policy.

## Constraints

Root partition only, linked static: `cp` runs in single-user mode and on the installer's
ramdisk. No dependency outside the repository's own crates (`cli`, `sys`) and `std`. Writes
only where the operands say. Never follows a symbolic link it was not asked to follow. The
`pledge` profile is derived from the options: `dpath` only under `-R` (FIFOs and device
nodes), `chown` only under `-p`.

## Inputs

- Arguments: options, then at least two operands; the last is the target.
- Standard input: one line per question under `-i`.
- Environment: none read directly. The umask shapes the mode of what is created, as
  `open(2)` and `mkdir(2)` apply it.
- The terminal: whether standard output is one (a header on tables).
- Files: `stat` of every source and target, the contents of regular files, the target of
  every link copied, directory entries under `-R`. Nothing else is read.

## Parameters

| Flag | Argument | Meaning | Default |
|---|---|---|---|
| `-R`, `--recursive` | | directories with their trees; links as links; FIFOs and nodes recreated | off |
| `-H` / `-L` / `-P` | | with `-R`: follow command-line links / every link / none | `-P` |
| `-a`, `--archive` | | `-R -p -P` | |
| `-f`, `--force` / `-i`, `--interactive` | | remove an existing target first / ask before overwriting | write over it |
| `-p`, `--preserve` | | keep times, mode, owner, group, flags as permissions allow | off |
| `-v`, `--verbose` | | `source -> target` after each copy | quiet |
| `-o`, `--output` | `name` `table` `wide` `json` `yaml` `custom-columns=H:.p,...` | every copy as a record | none |
| `--dry-run` | | plan and report, write nothing | off |
| `--no-headers` | | no header on tables | pipe: none |
| `--help` | | the description; `-o json`/`yaml` as a record | |

Of `-f` and `-i` the last wins; of `-H`, `-L` and `-P` the last wins, and without `-R` all
three mean nothing (every link is followed). Fewer than two operands, or several sources
with a target that is not a directory, is a usage error.

## Outputs

- By default nothing on standard output. `-v`: `source -> target` per copy made (and per
  copy planned under `--dry-run`).
- `-o name`: the target of each copy, one per line. `-o table`: `SOURCE TARGET TYPE SIZE
  ACTION`, a header on a terminal. `-o wide`, `-o custom-columns`: through `cli`.
- `-o json`, `-o yaml`: `{apiVersion: emibsd.org/v1, kind: CopyList, items: [...]}`, one
  record per source examined, including the refused ones (`action: failed`, `error`).
- Standard error: `cp: <what>: <why>` per failure (`nope: No such file or directory`,
  `a and a are identical (not copied).`, `src is a directory (not copied).`, `cannot overwrite
  directory d with non-directory f`, `x: directory causes a cycle`, `update times: t: ...`),
  and the `-i` question `overwrite target? `.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | everything was copied (a `-i` answered no is not a failure) |
| 1 | something could not be copied, or standard output failed; the rest was copied |
| 2 | the command line was wrong; nothing was copied |

## Signals and failure behaviour

No signal handling of its own: SIGINT and SIGTERM end it, and a file half written stays
half written, as with every `cp`. A closed pipe on the records ends the output quietly. Disk
full and permission denied are per-file failures: reported, the rest is copied, exit 1. A
directory that cannot be created is reported and its tree skipped. Under `-L`, a link that
leads back to a directory being copied is reported once as a cycle and not entered. A
dangling link is copied as a link, even under `-L`.

## Compatibility

Who depends on `cp` in the base system: the installer (`install.sub` copies sets and
configuration), `rc` and `rc.d` scripts, `sysmerge`, `security(8)`, every Makefile's
`install` fallback, every user's muscle memory. What they expect: the POSIX flags with their
meaning, silence on success, exit 0 or 1, the modes and times that `-p` and `-R` give. All
kept; the conscious additions (`-o`, `--dry-run`, long flags, exit 2 for a wrong command
line) touch no script that was correct. The visible differences from the traditional `cp`,
all in failure paths: a socket among the sources is a failure (exit 1) here, where the
tradition warns and exits 0; a directory that cannot be created, and a directory source over
a target that is not a directory, are per-source failures here (reported, the rest copied,
exit 1) where the tradition aborts at once with exit 1; and `-r` is refused instead of
discouraged. `tests/golden` copies a fixed tree with every POSIX form through this `cp` and
through a reference system's and compares the resulting trees (`ls -lR`, contents).

## Performance budget

Two measures against a reference system's `cp` on the same image (`bench/`, `just bench`): one 1 GB
file (the 64 KB loop, holes skipped), and `cp -R` of a tree of 100,000 small files (one
`stat` per source, one per target, the directory read once). Floor: never slower. Memory: one
64 KB buffer and the path stack; the tree is never held.

## Security history

No `cp` has a CVE of its own. The family's known problems are the ones this
definition closes by construction: a set-user-ID copy made by someone else (the bits are
dropped unless owner and group match), a directory created world-writable while it is
filled (created owner-writable only, its real mode set after), a symbolic link followed
during `-R` into a tree the user did not name (`-P` is the default), and a target replaced
through a link under `-f` (the link is unlinked, never written through).

| CVE | Class | Here |
|---|---|---|
| none | set-id bits carried to a copy owned by another user | `copy.rs`: dropped unless `uid == getuid()` and the groups match; `tests/cve/setid.rs` (pending) |
| none | symlink followed during recursion into an unnamed tree | `-P` default under `-R`; `tests/cli.rs` `recursion_keeps_links_by_default_and_follows_with_l` |

## Open questions

- A failed write of the records is reported and exits 1 (disk full, I/O error), but a closed
  or read-only standard output is not: Rust's `std` swallows `EBADF` on stdout, so
  `cp -v a b >&-` exits 0 with nothing printed. Detecting it would need the descriptor
  outside `std`; whether that is worth an `unsafe` line in `sys` is open.

- `tests/golden` against a reference system's `cp` needs the EmiBSD image; `bench/` its two measures;
  `tests/cve/setid.rs` a second user to run as. Until then STATUS stays `designed`: the code,
  its unit and integration tests, clippy and fmt are done on the development host (macOS).
- Hard links: a `--hard-links` that keeps them by `(dev, ino)` would be cheap with the record
  model; not in POSIX's `cp`, left out until someone needs it.
- Copying across file systems carries flags that the target may not support; `-p` reports
  the refusal when flags were set. Whether to downgrade that to a note is
  open.
- The 64 KB buffer is the file system's largest block; `copy_file_range`-like kernel copies would be
  a `sys` addition when the kernel offers one.
