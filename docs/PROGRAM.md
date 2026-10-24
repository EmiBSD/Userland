# The contract of a program

Every program and library directory of this repository (`bin/`, `sbin/`, `usr/bin/`,
`usr/sbin/`, `libexec/`, `lib/`, `compiler/`) is one solution, laid out the same way.
`tools/layout.py` creates the skeleton; the people and agents who work on the program fill
it. There are two classes, told apart by the first word of `STATUS`.

## Written (from scratch, in Rust)

```
<group>/<name>/
├── STATUS            planned | defined | designed | implemented | shipped
├── DEFINITION.md     the functional design: what it does, scope, constraints, inputs,
│                     parameters, outputs, exit codes, signals, compatibility, the
│                     performance budget, the security history (CVEs of the reference)
├── DESIGN.md         the architecture: mermaid diagrams, concurrency model, threat model,
│                     security (pledge, unveil, privileges), decisions, dependencies
├── schemas/          the machine-readable contracts: output.v1.json, config.v1.json
│                     (what `-o json` / `-o yaml` emit; versioned, kubectl's apiVersion)
├── src/              the Rust sources, a Cargo package; unit tests beside the code
├── tests/            integration tests; property tests for every parser; stress/ on four
│                     CPUs for what serves many; cve/ one test per entry of the security
│                     history; golden/ the differential tests against OpenBSD's program
├── bench/            host benchmarks (harness = false) against OpenBSD's program on the
│                     same input; `just bench` prints the ratio
├── man/<name>.<n>    the manual, mdoc(7) source; HTML and Markdown are rendered from it
├── etc/              the default configuration installed under /etc, when it has one
├── DELIVERY.md       the install set, path, static or dynamic, owner and mode, MAKEDEV
└── justfile          `import` of tools/program.just
```

The order: **planned** (the skeleton; DEFINITION names the OpenBSD reference), **defined**
(DEFINITION complete; *Compatibility* is the section that matters most: what the rest of the
base system expects, the flags `rc` uses, the output another program parses, the exit codes
a script branches on), **designed** (DESIGN and schemas complete; the pledge and unveil
profile never relaxes what OpenBSD's program restricts), **implemented** (builds; unit,
integration, property, stress, cve and differential tests pass; bench within budget; the
manual complete with EXAMPLES; the package joined the workspace), **shipped** (DELIVERY
complete, `distrib/` installs it).

## Imported (compiled from upstream, never rewritten)

```
<group>/<name>/
├── STATUS            imported | imported-built | imported-shipped
├── UPSTREAM.toml     the pin: mirror, origin, path, commit or tag, version, licence, CPE
├── patches/          our patches, a numbered series, each with its reason in its header
├── build/            the glue: what is built, with which flags, against which libc and libtls
├── DEFINITION.md     what it gives us, what we build of it, compatibility, configuration we
│                     ship, the security history tracked against the upstream's CPE
├── DESIGN.md         the integration: pledge kept, privileges, concurrency as upstream has it
├── tests/            our integration: it builds against our libc, starts under our rc, and
│                     behaves as OpenBSD's binary (golden/); cve/ for what we patched
├── man/              the upstream manual; a change to it is one more patch
├── DELIVERY.md
└── justfile
```

The source itself lives under `upstream/`, gitignored and read-only, fetched by
`tools/upstream.py fetch` and verified against `UPSTREAM.toml` (commit for git, SHA-256 and
signature for a tarball); a build copies it to `target/`, applies `patches/`, builds there.
`upstream/.pin` must match the TOML or `just build` refuses. Most imports point at
`EmiBSD/OpenBSD-src` at the Kernel's pin (OpenSSH, LibreSSL, `unbound`, `smtpd`, `nvi`,
`mandoc`, ncurses, LLVM all live in that tree): one shared clone, one fetch. Moving an
import to a newer version is a `upstream:` commit that bumps the pin and lists the CVEs it
closes, as the kernel bumps its LZ pin.

## Rules

- A written program is written from scratch under its definition; OpenBSD's code is read
  for behaviour, never copied or translated. An imported one is never edited in place:
  patches only, and a patch needs a reason.
- Rust; `#![forbid(unsafe_code)]` at the crate root. `unsafe` only in `lib/libc`,
  `libexec/rtld` and `lib/crates/sys`, each site with a `// SAFETY:` proof. Miri on their
  host tests.

## The common grammar (the user's decision of 2026-10-24, taken with `ls`)

A written program is a query over records with a schema (`schemas/<record>.v1.json`); the
human and machine outputs are renderers of the same record, from the shared crate
`lib/crates/cli`, so the user learns the grammar once:

| | |
|---|---|
| `-o name` | one identifier per line (to a pipe) or in columns (to a terminal) |
| `-o table` | the classic columns; `--no-headers` drops the header line |
| `-o wide` | every field of the record as a table |
| `-o json`, `-o yaml` | the record, versioned (`apiVersion`) |
| `-o custom-columns=NAME:.name,SIZE:.size` | the fields you ask for |
| `--sort-by=.field`, `-r` | any field of the record, reversed |
| `--type=`, `--since=`, `--max-depth=` | filters, where the record has them |

POSIX's short flags keep their meaning (`ls -la` is `ls -la`). To a pipe, the output of a
POSIX-defined form (`ls -l`, `-1`, `-i`, `-s`) is POSIX's byte for byte, so the world's
scripts keep working. To a terminal, the defaults are modern: ISO 8601 dates, human sizes,
a header on tables. BSD extensions nobody remembers are not carried (`ls -m`, `-x`, `-T`);
what they did is `-o` or `--sort-by`. `-o` itself is the one conscious break with POSIX
XSI: it is the output selector, as in kubectl.

**One declaration per program** (the user's decision of 2026-10-24, taken with `cli` 0.2 and
`cp`): a `Command` in `src/options.rs` names every option once, with its type (`Flag`,
`Str`, `Choice`, `List`, `Int {min, max}`, `Duration`, `Size`, `Path`, `Field`, `Format`).
From that one table `cli` derives the parser (values arrive converted and checked, the
error already worded, as in `ls: --max-depth: 'x' is not a whole number` with the value
in backticks), `--help` as text,
`--help -o json` as a `CommandHelp` record (`lib/crates/cli/schemas/command-help.v1.json`,
with the type of every option, so an agent can drive the program without reading prose), the
usage line, and the `name: message` prefix of every diagnostic. No program declares `--help`
or writes a `parse::<usize>()` of its own. Every option carries its origin, and `--help`
shows the options in four sections, POSIX's, BSD compatibility (flags the BSDs have beyond
POSIX, kept so their scripts work), EmiBSD's own for this program, and the common grammar
every program shares (`-o`, `--sort-by`, `--no-headers`,
`--help`; `origin` in the record), so a user tells at a glance what works everywhere, what
is this program's, and what is the same in every EmiBSD program: `cli` knows the grammar's
names; a short flag is POSIX's unless the declaration says `.bsd()` or `.emibsd()`; a
long-only option is EmiBSD's. The exit codes are shared: **0** everything asked
was done, **1** something could not be done and the rest was, **2** the command line was
wrong and nothing was done; a program may define more above 2 and lists them in its
`Command`. An action is a stream of records too: `cp` makes one record per source examined,
with `action` saying what happened (created, replaced, merged, skipped, planned, failed);
`-v` and `-o` are two renderings of the same records, and `--dry-run` produces them without
the effect. The `pledge` promises follow the options (`cp` adds `dpath` under `-R` and
`chown` under `-p`); `cli` may grow a general form of that.
- A new crate dependency needs the user's OK and a row in the allowlist (to be written with
  the first program). Fuzzing: property tests on stable (`cargo-fuzz` needs nightly).
- Performance: a commit that moves a benchmark more than 10 % carries `Bench:` lines and a
  reason, or stops (the kernel's decision 43).
- Security: three layers. What the program forbids itself (pledge, unveil, privileges,
  verified by running its tests on EmiBSD, where a violation kills the process); the CVE
  history of the reference or upstream (a table in DEFINITION, a test per entry in
  `tests/cve/`); and our dependencies (`cargo audit`, `cargo deny` in `just check`, pending).
- The manual's source is mdoc(7), the format of the system; `mandoc -T markdown` and
  `-T html` render it for the site. EXAMPLES is not optional.
- Every file starts with the author's ISC block (`LICENSE`).
- `just status` at the root counts the STATUS files; that count is the progress of the
  userland, as `cargo xtask lz status` is the kernel's.

## Linking (the user's decision of 2026-10-24)

OpenBSD's rule, kept: the programs of `bin/` and `sbin/` are linked **statically**, so
they run with only the root partition mounted, in single-user mode and on the installer's
ramdisk, without `/usr/lib` or `ld.so`; everything under `usr/` and `libexec/` is dynamic,
so a fix in a shared library reaches every program that links it. A `bin/` or `sbin/`
program carries `src/build.rs` emitting `cargo:rustc-link-arg-bins=-static` when the target
is OpenBSD (no flag on the development host, where static linking does not exist); the
toolchain's `crt-static` replaces it if `compiler/rust` finds the OpenBSD target respects
it. `DELIVERY.md` says `static` or `dynamic` and the measured size. The installer's ramdisk
does not pay `std` once per program: `distrib/installer` builds `bin/` and `sbin/` into one
multi-call crate, the Rust form of `crunchgen(8)`.

## Versions (the user's decision of 2026-10-23)

Two levels, because they answer two questions.

- **A program: semver, `MAJOR.MINOR.PATCH`**, because a program has interfaces others depend
  on (flags, `-o json`, exit codes, its configuration format) and the question its users ask
  is "does it break me?". `MAJOR` rises when a flag, an exit code, a schema (`output.v1` to
  `v2`) or the configuration format is removed or changed; `MINOR` when something is added;
  `PATCH` when something is fixed with nothing visible changed. A written program's version
  is `version` in `src/Cargo.toml`, starting at `0.1.0`; while `MAJOR` is 0, Cargo's reading
  applies: `breaking` bumps `MINOR`, `feature` and `fix` bump `PATCH`. An imported program's
  version is `version` in `UPSTREAM.toml`: the upstream's, plus our patch level as build
  metadata (`9.9+emibsd.2`); a new patch raises the level, a pin bump changes the base.
- **The system: calendar, `YEAR.MONTH`** (`2027.04`), the release `distrib/` builds, like
  OpenBSD's release every six months with the date said. The question there is "how old is
  what I run?". It is a level apart from the `EmiBSD 8.0` the kernel shows userland, which
  does not move while the ABI is OpenBSD's.

The rule, mechanical: a commit that changes a program's code (`src/`; for an import
`patches/`, `build/` or `UPSTREAM.toml`) carries one trailer, `Change: breaking`, `Change:
feature` or `Change: fix`, and the version it carries is the bump that trailer calls for.
`tools/version.py check-commit` runs as the `commit-msg` hook (`just setup` installs
`.githooks/`) and refuses the commit otherwise; a commit that touches only tests, manuals or
docs needs no trailer and no bump. `CHANGELOG.md` of a program is generated from those
trailers by `just changelog`, never written by hand. A schema carries its own `apiVersion`,
raised only when the JSON stops being compatible, and that raise is `breaking` by
definition.
