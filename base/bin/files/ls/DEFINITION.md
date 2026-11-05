# ls

STATUS: see `STATUS`. EmiBSD's own `ls`, written from scratch under this definition (the
user's decision of 2026-10-23); its reference is POSIX.1-2024's `ls` and the BSD habits its
users have; this document is the specification the code was written from. The first program
of the repository, and
the one that set the common grammar (docs/PROGRAM.md).

## What it does

Lists files. Each operand that is not a directory is one record; each directory operand is
listed as its entries, and with `-R` so is every directory below. A record is the file as
`schemas/entry.v1.json` describes it: name, path, type, mode, owner, group, size, blocks,
flags, inode, the three times, the device numbers, a symlink's target. The records are
filtered, sorted and rendered as `-o` asks: names, the classic long table, every field,
JSON, YAML or the columns the user chooses.

## Scope

In: everything POSIX's `ls` does, with the same short flags; the common grammar (`-o`,
`--sort-by`, `--type`, `--since`, `--max-depth`, `--no-headers`); `--help` as text or as a
record. Out, deliberately: the BSD `-m` (comma stream), `-x` (columns across), `-T` (full
time), `-f` (unsorted), `-o` as file flags: what they did is `-o`, `--sort-by` or `--flags`.
Colour is out until the common grammar has a colour policy. No `-X`, `--group-directories-
first` or other GNU additions.

## Constraints

Root partition only, linked static: `ls` must run in single-user mode and on the installer's
ramdisk. No dependency outside the repository's own crates (`cli`, `sys`) and `std`. Reads
the file system and the passwd database; writes only standard output and error. Never
follows a symbolic link it was not asked to follow.

## Inputs

- Arguments: options, then operands; no operand means `.`.
- Environment: `BLOCKSIZE` (unit of `-s` and `total`, 512 unless `-k`), `COLUMNS` (width of
  the grid), `TZ` (the zone of the dates). Root's `-A` default comes from `getuid`.
- The terminal: whether standard output is one (the defaults below) and its width.
- Files: directory entries and `stat` of each, `readlink` of symbolic links, the passwd and
  group databases. Nothing else is read.

## Parameters

| Flag | Argument | Meaning | Default |
|---|---|---|---|
| `-o`, `--output` | `name` `table` `wide` `json` `yaml` `custom-columns=H:.p,...` | the renderer | `name` |
| `-1` / `-C` | | one per line / grid | pipe: `-1`; terminal: `-C` |
| `-l` / `-g` / `-n` | | long table / without owner / numeric ids | |
| `--sort-by` | `.field` | order by any field of the record | by name |
| `-t` / `-S` | | by time, newest first / by size, largest first | |
| `-r`, `--reverse` | | reverse the order | |
| `-c` / `-u` | | the change / access time instead of modification | modification |
| `-a` / `-A` | | hidden entries, with / without `.` and `..` | none; root: `-A` |
| `-d` | | the directory itself | |
| `-R` | | recurse | |
| `--max-depth` | `N` | with `-R`, how deep | unlimited |
| `--type` | `file,dir,symlink,fifo,socket,char,block` | keep only these kinds | all |
| `--since` | `7d`, `12h`, `30m`, `45s` | modified within this long | all |
| `-F` / `-p` | | type indicators / `/` on directories | |
| `-i` / `-s` / `-k` | | inode / blocks / blocks of 1024 | |
| `-h`, `--human` | | sizes with K, M, G | terminal: on |
| `--flags` | | file flags in the table | |
| `-H` / `-L` | | follow links on the command line / everywhere | POSIX's rule |
| `-q` | | `?` for non-printable characters | terminal: on |
| `--no-headers` | | no header on tables | pipe: no headers |
| `--help` | | the description; `-o json`/`yaml` as a record | |

Of a group of exclusive options the last one wins, except that `-l` beats `-g`. `-d` turns
`-R` off and `-R` turns `-d` off, whichever came last.

## Outputs

- `name` to a pipe: one name per line. To a terminal: a grid down the page, as wide as the
  terminal allows; one column when two do not fit.
- `table` to a pipe: POSIX's long format, byte for byte as the standard specifies it (`total N`
  first for a directory; mode, links, owner, group padded with two blanks, size or
  `major, minor`, the date as `Mon dd HH:MM` within six months and `Mon dd  YYYY` beyond
  or in the future, the name, ` -> target`). To a terminal: a header, ISO 8601 dates, human
  sizes, no `total`.
- `wide`: every field as a table. `custom-columns`: the fields named.
- `json`, `yaml`: `{apiVersion: emibsd.org/v1, kind: FileList, items: [...]}`, one record per
  entry across every directory listed, each with its `dir`.
- Several listings: a blank line and `dir:` before each, when there is more than one operand
  or `-R`; never for a single directory operand.
- Standard error: `ls: <name>: <strerror>` per entry or operand that failed; the rest is
  listed.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | every operand and entry was listed |
| 1 | an operand or an entry could not be listed, or standard output failed; the rest was listed |
| 2 | the command line was wrong (an unknown option, a value of the wrong type); nothing was listed |

## Signals and failure behaviour

No signal handling of its own: SIGINT and SIGTERM end it. A closed pipe (`ls | head`) ends
the output quietly with status 0. Permission denied on a directory lists what can be read
and reports the directory; a dangling link is listed as the link; a cycle under `-R -L` is
reported once and not entered. Output is buffered and flushed at the end of each listing.

## Compatibility

Who depends on `ls` in the base system: shell scripts everywhere (`ls -1`, `ls -l | awk`),
the installer's `install.sub`, `security(8)`'s nightly report, `rc.d` scripts, every user's
muscle memory. What they expect is POSIX's output to a pipe, and that is kept byte for
byte: `tests/golden` lists a fixed tree with every POSIX form through this `ls` and through
a reference system's, and the outputs must match. The three conscious breaks: `-o` is the
output selector (the BSD `-o` showed file flags; `--flags` does now), to a terminal the
defaults are modern, and a wrong command line exits 2 where the tradition exits 1 (the
shared convention of docs/PROGRAM.md; a script that branches on
"non-zero" sees no difference). No script sees a terminal.

## Performance budget

Two measures against a reference system's `ls` on the same image (`bench/`, `just bench`):
`ls` of a directory of 100,000 files, which must stay free of `stat` (names and `d_type`
only), and `ls -lR /usr`. Floor: never slower. Memory: one listing in memory at a time;
`-R` does not hold the tree.

## Security history

No `ls` has a CVE of its own. The family's known problem is the terminal: a file name carrying
an escape sequence reaches the screen and drives it. That is why `-q` is the terminal
default and why a listing to a terminal never prints a control character. `tests/cve/`
carries it as a test without a number.

| CVE | Class | Here |
|---|---|---|
| none | terminal escape injection via file names (the family's recurring report) | `-q` default on a terminal; `cli::text::sanitize`; `tests/cve/escape.rs` |

## Open questions

- Non-UTF-8 file names are shown lossy (U+FFFD); the record should carry the bytes too.
- `display_width` counts characters, not columns: East Asian wide characters misalign the
  grid until `data/locale` gives `wcwidth`.
- Missing for `implemented`: `tests/golden` against a reference system's `ls` (needs the EmiBSD image),
  `bench/` with its two measures, `tests/cve/escape.rs`, and the manual's EXAMPLES. The code,
  its unit and integration tests, clippy and fmt are done on the development host (macOS).
