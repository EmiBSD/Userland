# cli

STATUS: see `STATUS`. No counterpart elsewhere: the reference is its users' needs, `ls` first
(2026-10-24) and `cp` second, the same day. Written from scratch; the one library every
written program links.

## What it does

Gives a written program the common grammar (docs/PROGRAM.md, "The common grammar") as code,
so the user learns it once and the program writes none of it:

- **`Command`**: the program declared once (name, summary, synopsis, options with their
  type and exclusive group, output formats, schema, exit codes, examples, environment,
  notes). From it: the parser with typed values, `--help` as text, `--help -o json|yaml` as
  a `CommandHelp` record, the usage line, `name: message` diagnostics, the shared exit codes.
- **`Value`**: the record, an ordered dynamically typed value with its own JSON and YAML
  writers and a JSON reader (RFC 8259 whole: every escape, surrogate pairs, numbers as
  `Int`, `UInt` or `Float`; an error names its line and column), paths (`.a.b`), the order
  `--sort-by` uses.
- **`Output`, `render`**: `-o name|table|wide|json|yaml|custom-columns=`, the aligned table,
  the grid of columns a terminal gets.
- **`text`**: display width, the sanitising of names for a terminal, human sizes, durations
  and sizes a human types.
- **`os_error`**: the text of `strerror(3)` without std's `(os error N)`.

## Scope

In: everything above. Out, until a second user asks: filters over records (`--where`), a
colour policy, `wcwidth` (needs `data/locale`), configuration files as `Value`, syslog for
the daemons, a `pledge` profile derived from the declaration (today each program derives its
own), a `#[derive(Command)]` (a `const` table does the same without a proc-macro; revisited
when thirty programs repeat it).

## Constraints

`#![forbid(unsafe_code)]`; `std` only, no dependency: JSON and YAML are written here so no
program needs `serde`. Linked into every program of `bin/` and `sbin/`, so it stays small.
Everything it prints to standard error has the program's name first.

## Inputs

The process's arguments (`Command::from_env`), and the file each `--request` names (read
whole while parsing, at most 1 MiB of UTF-8, so a program that pledges before parsing keeps
`rpath`); never standard input, which is the data's. Nothing else: the environment and the
terminal are the program's to read (`sys` has the width).

**The request** (docs/PROGRAM.md, "The request"): `--request=FILE`, or the document inline
when the value starts with `{`, is a JSON object whose keys are `Given::key` (the long name
when there is one, else the letter) and `operands`. `parse` lowers it to the words it spells,
`--long=value` or `-x value` in the document's order, a flag for `true` and nothing for
`false`, a `List` from an array or the comma form, an `Int` from a number or a string, the
other kinds from a string; and lexes and types those words like any others, where
`--request` stood, so the groups, the last-wins rule and every value's diagnostic are the
option's own. The documents' operands come first, in order, then the command line's. A
document that is not JSON (`--request: line 3, column 7: ...`), an unknown key, a value of
the wrong shape, a nested `request`, or a file that cannot be read is a usage error, exit 2.

## Parameters

The API, in `man/cli.3` and the crate's doc comments. Option types a `Command` may declare:

| Kind | The parser checks | The value arrives as |
|---|---|---|
| `Flag` | nothing | `Typed::Flag` |
| `Str(PLACEHOLDER)` | nothing | `Typed::Str` |
| `Choice(PLACEHOLDER, &[..])` | one of the set | `Typed::Choice(&'static str)` |
| `List(PLACEHOLDER, &[..])` | comma-separated, each of the set, at least one | `Typed::List` |
| `Int {name, min, max}` | a whole number within bounds | `Typed::Int(i64)` |
| `Duration(PLACEHOLDER)` | `7d`, `12h`, `30m`, `45s`, seconds | `Typed::Duration(u64)` seconds |
| `Size(PLACEHOLDER)` | `512`, `4K`, `10M`, `1G` | `Typed::Size(u64)` bytes |
| `Path(PLACEHOLDER)` | not empty | `Typed::Path` |
| `Field(PLACEHOLDER)` | `.a.b`, letters, digits, `_`, `-` | `Typed::Field` without the dot |
| `Format` | one of the `-o` renderers | `Typed::Format(Output)` |

## Outputs

`--help`: the text, or the `CommandHelp` record (`schemas/command-help.v1.json`). A wrong
command line: `name: message` and the usage line on standard error, exit 2. `warn` and
`report`: `name: message`, `name: subject: error`.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | `exit::OK`: everything asked was done |
| 1 | `exit::FAILURE`: something could not be done; the rest was |
| 2 | `exit::USAGE`: the command line was wrong; nothing was done |

## Signals and failure behaviour

None of its own. Writers return `io::Result`; a closed pipe is the program's to treat as
quiet success.

## Compatibility

Every written program; a breaking change here is `Change: breaking` and a migration of
every user in the same commit (the workspace builds as one). The `CommandHelp` schema is
versioned apart: a field added is compatible, a field removed or retyped is `v2`.

## Performance budget

Parsing is not measured. `Value::to_json` of a hundred thousand records (an `ls -R -o json`
of `/usr`) must not dominate the walk: measured with `ls`'s bench.

## Security history

No CVE: no upstream. The class it guards against is the terminal: `text::sanitize` is what
keeps a hostile file name from driving it (`ls -q`'s default).

| CVE | Class | Here |
|---|---|---|
| none | terminal escape injection through printed names | `text::sanitize`; `ls`'s `tests/cve/escape.rs` (pending) |

## Open questions

- `display_width` counts characters, not columns, until `data/locale` gives `wcwidth`.
- `Value` holds `String`s: non-UTF-8 names arrive lossy. A `Bytes` variant is the fix when a
  program needs it.
- Filters, colour, configuration files, syslog, the derived `pledge` profile: see Scope.
