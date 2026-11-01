# Rust in the userland: the practices

How Rust is written in this repository, for people and for the agents of
`.claude/rules/subagents.md`. Adapted on 2026-10-25 from the user's "Manual de buenas
prácticas en Rust" to what this repository has already decided; where the manual and a
decision differed, the decision won and the difference is noted. The rules stay authoritative
in `README.md` ("Rules") and `docs/PROGRAM.md`; this file is the practice under them, and
follows them when they change. The last section is the compressed list an agent reads first.

Five ideas order the rest:

1. **The type is the documentation.** A value with a constraint carries it in its type: a
   newtype, an enum, a `NonZero`. What the compiler can refuse is not checked at run time.
2. **Errors are values.** A function that can fail returns `Result`; a program's diagnostics
   go through `cli`; `panic!` is for a broken invariant of the program, never for bad input
   or a refusal of the system.
3. **`unsafe` lives in one place.** Every program and `cli` carry `#![forbid(unsafe_code)]`;
   `unsafe` only in `base/lib/crates/sys` (and, outside the workspace, `base/lib/libc` and
   `base/libexec/rtld`), each site with a `// SAFETY:` proof, only for what `std` lacks.
4. **The specification, not the reference.** A written program comes from its DEFINITION.md
   alone; the reference's code is read to write the definition, never to write the code.
5. **The tool decides, not taste.** `rustfmt` formats, `clippy -D warnings` reviews, the
   `commit-msg` hook checks the trailer and the bump; a discussion of style ends in
   configuration, once.

## Organisation

The workspace is `Cargo.toml` at the root; a program's package is `src/` under its directory
and joins `members` when its STATUS reaches `implemented` (`docs/PROGRAM.md`, "Written").

- **One `Command`, one `main.rs`, modules by domain.** `src/options.rs` holds the `Command`
  and the `Config` built from the parsed options; `main.rs` pledges, parses through `cli`,
  runs and maps the result to `cli::exit`; the work is in modules named for what they do
  (`walk.rs`, `entry.rs`, `copy.rs`, `render.rs`), never `types.rs`, `utils.rs`,
  `helpers.rs`. `ls` and `cp` are the pattern; read the neighbour before making a new one.
- **Two shared crates and no third without a decision.** `cli` is the grammar, the record and
  the renderers; `sys` is the FFI. A program depends on those two and on `std`. A program's
  need that neither covers is an addition to `cli` or `sys`, with its reason, in its own
  commit; a new crate from outside the repository is the user's decision (`docs/PROGRAM.md`,
  Rules) and goes in the allowlist of dependencies. Today the workspace has no external
  dependency at all, and that is the state to keep.
- **Visibility is the minimum.** Everything is private until something needs it; `pub(crate)`
  inside a crate; `pub` only in `cli` and `sys`, where it is a contract that semver covers.
  A program's modules export to `main.rs` and nothing else.
- **The toolchain is pinned** (`rust-toolchain.toml`: stable, one version, `rustfmt`,
  `clippy`, `rust-src`); a bump is its own commit and the user's decision. No nightly, not
  even for a tool: what needs nightly (`cargo-fuzz`, `miri` on the host) is not used; property
  tests on stable replace fuzzing (`docs/PROGRAM.md`, Rules).
- **Edition 2024** everywhere, inherited from `[workspace.package]`; `edition.workspace =
  true`, `license.workspace = true`, `authors.workspace = true` in every package.
- **`Cargo.lock` is committed.** Features are not used in the programs: a program is one
  behaviour, and what differs by target is `#[cfg(target_os = ...)]` in `sys`.
- **The release profile is the workspace's** (`strip`, `lto`, one codegen unit); a program
  does not override it. `bin/` and `sbin/` are static through `src/build.rs`
  (`docs/PROGRAM.md`, Linking); `DELIVERY.md` records the measured size.

## Types and ownership

An invalid state must not be representable.

- **Newtypes for identities** that would otherwise be the same integer: a uid, a gid, a file
  descriptor, a depth. One line, and a uid cannot be passed where a gid went. Derive `Copy`
  when the inside is `Copy`.
- **Enums instead of booleans and strings.** `enum Action { Created, Replaced, Merged,
  Skipped, Planned, Failed }`, as `cp`'s record has it, not `replaced: bool`. A `match` on
  a type of this repository has no `_` arm, so a new variant breaks the build where it must.
- **Borrow in parameters, own in returns.** Take `&str`, `&[u8]`, `&Path`, `&Value`; return
  `String`, `Vec<T>`, `PathBuf`, `Value`. Take a `String` by value only to keep it.
- **`clone()` is a decision, not a reflex.** Written to quiet the borrow checker, it hides an
  ownership problem; written in a loop over records, it is a silent benchmark regression
  (`docs/PROGRAM.md`, Rules: more than 10 % stops the commit).
- **`Option` for absence, `Result` for failure.** Never `-1`, `0`, `""` or `None` where an
  error happened; a record's missing field is absent, not a placeholder.
- **Lifetimes only when the compiler asks.** A struct that wants a lifetime usually wants to
  own its data; lifetimes on structs spread.
- **`Rc<RefCell<T>>` and `Arc<Mutex<T>>` are the last resort.** One owner with borrows, or an
  index into a `Vec`, almost always exists. `sys` keeps its lookup caches in a thread-local
  `RefCell`, the one place that pattern is at home.
- **`Cow<'_, str>`** for text that sometimes changes and sometimes passes through (a name
  sanitised for a terminal): no allocation when nothing changed.
- **Derives:** `Debug` always; `Clone`, `PartialEq`, `Eq`, `Hash` when they mean something;
  `Default` only when the empty value is valid; `Copy` only for small, trivial types.
- **`#[must_use]`** on a function whose ignored result is almost always a bug: a builder's
  step, a guard, a `Result` returned for information.
- **Integers convert with `From` and `TryFrom`,** never with `as` where those exist:
  `u64::from(uid)` cannot truncate; `n as usize` can, silently. `as` stays for what has no
  other spelling (a `char` to its code point, a C field whose width `sys` owns), and there it
  says why. The code written before this rule has such casts; they go when their file is
  next touched, not in a sweep (`mechanical` may do the sweep when the user asks).

## Errors and diagnostics

The manual's `thiserror` and `anyhow` are not used: the crate that plays both roles here is
`cli`, and a program has no error type of its own unless it carries data a renderer needs.

- **A fallible function returns `Result`;** `?` propagates. A `match` that only re-wraps is
  noise: `map_err` or a `From` impl.
- **The diagnostic is `cli`'s.** A program hands `COMMAND.report(subject, error)` the
  `io::Error` itself, never its text, so the errno name travels into the `Diagnostic` record
  (`docs/PROGRAM.md`, Diagnostics); `warn` for what did not stop the work; `usage_error` for
  its own usage errors, exit 2. The text form is `name: subject: message` and nobody formats
  it by hand.
- **The exit code is the summary**, computed once in `main`: 0 everything asked was done; 1
  something was not and the rest was; 2 the command line was wrong and nothing was done; more
  only if the `Command` declares them. An action's failure is also in its record (`cp`'s
  `action: failed` with `error`), so a machine reading `-o json` does not need stderr.
- **`unwrap()` outside tests does not exist.** `expect("...")` only for an invariant the code
  itself guarantees, and the message says why it holds (`expect("two operands")` after the
  parser enforced the count), never what went wrong. Today's code has two such sites, both
  with their reason; that is the budget.
- **`panic!` is not control flow.** Invalid input, an absent file, a permission denied, a
  broken pipe are `Err`. `unreachable!()` only when the compiler cannot see it and the
  comment says why.
- **The `errno` is read at the syscall**, in `sys`, with `io::Error::last_os_error()` before
  any other call can overwrite it; a program compares `raw_os_error()` or `kind()`, never
  the text.
- **`let _ =` only on the way out**, where nothing can be done (a flush at exit, a best-effort
  remove in a test's `Drop`), and with the reason beside it when it is not obvious.
- **`BrokenPipe` on stdout is silence**, never a diagnostic: the reader went away. The
  program stops producing output at the first one; the exit code is the one its DEFINITION
  states (a query ends with 0, an action with 1 if it still had work to report), and the
  code follows the DEFINITION on every path, not only the first.

## `unsafe` and `sys`

The manual's "zero `unsafe`, `nix` and `signal-hook` instead" is adapted: this repository
writes its own libc and its own loader, and depends on nothing from outside, so the audited
`unsafe` is ours, in one crate.

- **Programs and `cli`: `#![forbid(unsafe_code)]`**, forbid and not deny, so no `#[allow]`
  can reopen it. A program that seems to need `unsafe` needs a call `std` lacks: it asks
  `sys` for it, in its own commit, with the reason in the commit and in `sys`'s DEFINITION.
- **`sys`: the minimum, each site proven.** `#![deny(unsafe_op_in_unsafe_fn)]`; every
  `unsafe` block is preceded by `// SAFETY:` stating what the pointer, the length and the
  layout are and why the call cannot break them; a safe `pub fn` wraps each call so no
  `unsafe` escapes the crate. `sys` duplicates nothing `std` already wraps safely (files,
  directories, metadata, the environment, processes): only what `std` lacks (the passwd and
  group databases, the terminal, local time, `pledge`, uid and umask, `mkfifo`, `mknod`, the
  flags, times and mode of a symbolic link).
- **Layouts are declared per target** (`openbsd`, the Kernel's ABI; `macos`, the development
  host) and any other target is a `compile_error!`: a wrong `struct` layout is undefined
  behaviour that no test catches.
- **What `std` already does safely is used from `std`:** `std::process::Command` for a
  child process (`process_group`, `current_dir`, `Stdio::from`), `OwnedFd` and `BorrowedFd`
  for descriptors, `std::os::unix::fs` for modes, owners and symbolic links.
- **`fork` without `exec`, `pre_exec`, a signal handler of our own, `transmute`,
  `static mut`: none of these exist** in any crate. A signal is observed, not handled: a
  program that needs one asks `sys` for a flag-setting registration and reads the flag in
  its loop. `EINTR` is retried at the call.
- **Miri on `sys`'s host tests** when it is available (`docs/PROGRAM.md`, Rules); it is a
  tool outside the repository and runs only with the user's OK.

## Text, bytes and paths

Nothing on a Unix system is UTF-8 by right: file names, arguments, environment variables and
other processes' output are bytes.

| Data | Right type | Wrong type |
|---|---|---|
| A path | `Path`, `PathBuf` | `String` |
| An argument, an environment variable | `OsStr`, `OsString` | `String` |
| A file's or a pipe's content | `&[u8]`, `Vec<u8>` | `String` |
| Text the program itself produced | `&str`, `String` | `&[u8]` |
| A string to or from C (`sys` only) | `CStr`, `CString` | `&str` with `as_ptr` |

- **`OsStrExt::as_bytes` and `from_bytes`** are the bridge between `OsStr` and `&[u8]`,
  without a copy.
- **Never `to_str().unwrap()`** on a `Path` or an `OsStr`. To show a name,
  `to_string_lossy()` through `cli::text::sanitize` (the terminal default: no control
  character reaches the terminal); to operate on it, the bytes.
- **Lossy conversion is a visible decision**, made once, at the renderer, for a person's
  eyes; never before the bytes reach another program, a file or a record field that a
  machine reads back.
- **Sorting bytes with `cmp` is `LC_ALL=C`**, and that is what a pipe gets; a locale
  collation is a decision the DEFINITION records.
- **A parser works on `&[u8]`** when its grammar is ASCII (an option, a request's JSON
  syntax); `str` only once the text is known to be text.

## Concurrency and signals

The code is synchronous and single-threaded until a measurement says otherwise. `ls` lists,
`cp` copies, one thing at a time; DESIGN.md's "Concurrency" section says so in one line when
there is nothing to say.

- **`std::thread::scope`** when there is parallel work over borrowed data; no `'static` and
  no `Arc` only to satisfy `spawn`.
- **Channels before locks** (`std::sync::mpsc`); a `Mutex` only for small shared state, the
  critical section a few lines, no I/O inside; `lock()`'s `PoisonError` is handled or
  propagated, never unwrapped.
- **`Send` and `Sync` are derived, never implemented**: an `unsafe impl` cannot be written.
- **What serves many has `tests/stress/`** on four CPUs (`just stress`,
  `EMIBSD_NCPU=4`); the DESIGN names the model (threads, a pool, a process per client) and
  what bounds it.
- **No `async`, no runtime.** A program that must multiplex sockets is a decision the user
  takes in its DESIGN; nothing in the workspace today needs it.
- **`pledge` first, then everything else.** The promises are the least the program needs,
  called before the first argument is read, widened only by an option that needs it
  (`cp -R` adds `dpath`, `-p` adds `chown`); on the development host the call is a no-op
  with the same signature. A violation on EmiBSD kills the process: the tests run there
  verify the profile.

## Performance

Measure first, then change only what the measurement named. Most of a program's time goes to
allocations, not instructions; most of its size goes to what it pulls from `std`.

- **`bench/` against a reference system's program on the same input**, `just bench` prints
  the ratio; the budget is in DEFINITION.md. A commit that moves a benchmark more than 10 %
  carries `Bench:` lines and a reason, or stops (`docs/PROGRAM.md`, Rules).
- **Allocations out of the loop:** `Vec::with_capacity` when the size is known; a buffer
  reused with `clear()`; `push_str` on an existing `String` instead of a chain of `format!`.
  Stdout is a `BufWriter` over the locked handle, flushed once.
- **Iterators over indices:** `for x in &v` and the adaptors compile without bounds checks;
  `v[i]` in a loop adds them. `chunks`, `windows`, `split` cover the C patterns.
- **Slices on the hot path, owned values on the cold one:** a record is built once; what
  renders it borrows.
- **Generics on the hot path, `dyn` on the cold one:** `&mut dyn Write` for an output is
  right; a `Box<dyn Fn>` inside a lexer's loop is not.
- **`#[inline]` only with evidence**; the compiler decides well.
- **Size is a measurement too.** A `f64` parse or print costs 60 to 75 KB in a static
  binary (the implementer's memory); a `Value` number is kept as text for that reason.
  DELIVERY.md records the release size; a jump has a reason.
- **Start-up is performance:** nothing read before it is known to be needed; a program
  called in a loop by a script pays its initialisation every time.

## API and documentation (`cli` and `sys`)

The two shared crates are libraries with users; the Rust API Guidelines apply, and these are
the points most often missed.

- **Conversion names mean one thing:** `as_` borrows for free, `to_` copies, `into_`
  consumes. An `into_` that clones or an `as_` that allocates confuses everyone.
- **Take generic, return concrete:** `impl AsRef<Path>`, `impl Into<String>`, `impl
  fmt::Display` in parameters; a named type or `impl Iterator<Item = T>` in returns.
- **Implement the standard traits that apply:** `Display` for what a person reads, `Debug`
  always, `Error` for errors, `FromStr` for what parses, `From` for lossless conversions.
  `Diagnosable` is `cli`'s trait for what a diagnostic needs; a new error carrier implements
  it rather than formatting itself.
- **Doc on everything `pub`** (`#![warn(missing_docs)]`, both crates): one summary line, a
  paragraph, `# Errors` when it returns `Result`, `# Panics` when it can, `# Safety` on an
  `unsafe fn`. Examples in the doc are doctests and run under `cargo test`; a `cli` API
  that a program calls has one.
- **`//!` at the top of every file**, after the ISC block: what the module holds and how it
  relates to its neighbours; it is the first thing a reader sees.
- **A breaking change to `cli` or `sys` migrates every user in the same commit**
  (`subagents.md`); the workspace builds as one, and the trailer is `Change: breaking`.
- **The manual is mdoc(7)**, `man/<name>.<n>`; `mandoc -T lint` clean; EXAMPLES is not
  optional. The manual and `--help` say the same thing, from the same `Command`.

## Tests

Each layer has its kind of test; the ones nobody writes, the property and the differential
tests, are the ones `docs/PROGRAM.md` demands for `implemented`.

| Kind | Where | What it covers |
|---|---|---|
| Unit | `#[cfg(test)] mod tests` in the same file | one function, with access to the private |
| Integration | `tests/cli.rs`, the binary on a temporary tree, output to a pipe | the program from outside: bytes, exit code, stderr |
| Doctests | the examples in `///` of `cli` and `sys` | that the documented use still compiles and holds |
| Property | hand-rolled on stable, beside the parser | invariants: `--show-request` round trip, a renderer's escaping, `parse(print(x)) == x` |
| Golden | `tests/golden/`, run on EmiBSD against the reference | the POSIX forms byte for byte, the exit codes |
| Stress | `tests/stress/`, four CPUs | what serves many, under load |
| CVE | `tests/cve/`, one per entry of the security history | that the class of bug is impossible or caught |

- **One test per behaviour, named as a sentence:** `dash_l_to_a_pipe_is_posix_byte_for_byte`,
  not `test_l_2`. A test asserts bytes and codes, not that the program "ran".
- **No real I/O in a unit test:** what touches the file system or a process takes a trait or
  a `&mut dyn Write`, and the test passes a buffer. An integration test makes its own
  temporary tree, named with the process id, and removes it in `Drop`.
- **A hand-rolled property test is trusted only after a mutation** (the implementer's
  memory): break the code under test in one place, see the property fail, restore.
- **Every fixed bug leaves a test that failed before the fix**, in the same commit.
- **`cargo test` stays under a minute locally**; what is slow is `#[ignore]` with its reason
  and runs by name.
- **The differential battery is `regress/`** against a reference system, with the harness and
  the scenarios there; a program's own golden cases are its `tests/golden/`. A new edge case
  found is a new case there before the fix.

## Tools and the gate

`just check` at the root is the gate: `cargo fmt --all -- --check`, `cargo clippy --workspace
-- -D warnings`, `cargo test --workspace`; `just lint` and `just test` in a program's
directory are the same for one package, and every commit passes them (`subagents.md`,
"While working"). The `commit-msg` hook (`just setup`) checks the `Change:` trailer and the
version bump.

- **Formatting is `rustfmt`'s defaults**; there is no `rustfmt.toml`, and adding one is a
  decision with a written reason.
- **Clippy is `-D warnings` on the default set.** The manual's `[workspace.lints]` table
  (`pedantic`, `unwrap_used = "deny"`, `missing_docs`) is not in `Cargo.toml` today: it is
  a change to the workspace's rules, the user's decision, proposed below. Until then the
  rules of this file are read, not enforced, except by the reviewer.
- **`#[allow]` always with `reason = "..."`**; an `allow` without a reason is a finding.
  Today there is none in the workspace.
- **`cargo audit` and `cargo deny` are `just audit`**, tools installed outside the repository
  (`README.md`, "Open"), run when installed; `cargo geiger`, `cargo hack`, `cargo
  semver-checks`, `cargo llvm-cov`, `cargo udeps` are not installed and nothing installs
  them without the user's OK. The guard hook refuses `cargo install` to the agents.
- **`just man`** renders the manual; **`just status`** counts the STATUS files; **`just
  changelog`** writes the CHANGELOG from the trailers, never by hand.

## Dependencies and licences

Every dependency is someone else's code compiled, trusted and carried, with its licence.

- **`std` first, the two shared crates second, nothing third without the user's OK.** The
  workspace has no external crate today. Before proposing one: does `std` cover it, what
  does `cargo tree` say it drags in, who maintains it and when was the last release. The
  proposal goes in the hand-back, not in a commit.
- **Licences:** ISC is ours (`LICENSE`); MIT, Apache-2.0, BSD-2 and BSD-3, Zlib, Unicode-3.0
  acceptable for a dependency; MPL-2.0 with a reason; GPL and LGPL never, not even for a
  build tool that links (`README.md`, Rules). `deny.toml` is to be written with the first
  dependency, when `cargo deny` is installed.
- **Versions with a caret and the lockfile committed**; `cargo update` is its own commit with
  the lockfile's diff reviewed.
- **No `build.rs` that downloads or compiles C**; the one `build.rs` a program has emits the
  static-link argument and nothing else.
- **No procedural macros** in the programs: `serde_derive`, `syn`, `quote` double the build
  of a small crate; `cli`'s `Value` and its JSON are hand-written for that reason.

## Style and readability

`rustfmt` decides the format; this is what it cannot decide.

- **Names by the language's convention:** `snake_case`, `CamelCase`, `SCREAMING_SNAKE_CASE`;
  no Hungarian prefixes and no C abbreviations (`buf` yes, `pbuf` no; `fd` yes, `nfd` no).
- **A function fits on a screen.** Two hundred lines and five levels of nesting are a C
  function in Rust clothes; split by responsibility, not by length.
- **Early return and `let ... else`:** `let Some(x) = m.get(k) else { return Err(..) };`
  instead of an `if let` that nests the whole body. `if let ... &&` chains (edition 2024)
  where they replace a nested `if`.
- **`match` without `_` on our own types**; `_` only on foreign or `#[non_exhaustive]` types.
- **Comments say why, the code says what.** `// POSIX: -l to a pipe prints the epoch's
  month, not ISO` yes; `// increment i` no. A comment that explains confusing code is a
  signal to rewrite the code.
- **No loose `TODO`.** What is left is in `HANDOFF.md` or in DEFINITION's open questions;
  the code carries no promises.
- **Order in a file:** the ISC block, `//!`, `use` grouped by origin (std, the repository's
  crates, the crate's own), constants, public types and their `impl`, private types, free
  functions, `mod tests`.
- **One `impl` per responsibility**, with a `// --- rendering ---` separator when a type is
  large, before splitting it into traits.
- **Everything in English:** code, comments, docs, commits, the manual.

## From the specification, with the reference at hand

Nothing is ported (the user's decision of 2026-10-23, "no vamos a migrar"): the DEFINITION,
DESIGN and `schemas/` are the contract, and the reference's manual and code are read to write
them and, while implementing (the user's decision of 2026-10-25), to settle what they leave
open and to check a behaviour, with `git show`, never from inside the tree. What is taken is
the behaviour; the structure and the text are not: nothing is copied or translated, a gap
settled from the reference becomes a DEFINITION line, and nothing in the repository names
the reference system for a written program. When the C is open beside the Rust, these are
the shapes that replace its own:

| In the C | Here |
|---|---|
| a global, a `static` in a function | a field of the state struct passed by `&mut`, or a `Config` |
| `setjmp`/`longjmp`, `goto cleanup` | `Result` and `?`; a guard with `Drop` |
| a tagged `union`, an `int` kind with `#define`s | an `enum` with data |
| `char *` with a length, `strlcpy` into a `MAXPATHLEN` buffer | `&[u8]`, `&OsStr`, `PathBuf` |
| `-1` and `errno` | `io::Result` with the error from the call |
| a linked list of entries | a `Vec` with indices |
| `switch` on flag letters into twenty ints | the `Command`'s typed options and a `Config` |
| `#ifdef` per platform | `sys`, with `#[cfg(target_os)]` and `compile_error!` |

- **The DEFINITION is the test oracle.** Each observable behaviour it states (a byte of
  output, an exit code, a file touched) is a test before it is code; the program is done when
  the tests pass, not when it "looks right".
- **A behaviour that cannot be kept is reported with the evidence**, never silently changed;
  a flag or an exit code that leaves POSIX is the user's decision.
- **A reference's bug is a DEFINITION line**, under Compatibility, with the case that shows
  it and the decision: reproduce (scripts depend on it) or correct (nobody does).
- **Overflow is an error, not a wrap.** `checked_add`, `saturating_add` or `wrapping_add`
  chosen by the case and said; never `as` to dodge the lint.

## Proposed to the user (not in force until decided)

The manual asks for three things this repository does not have. Each is a change to the
workspace's rules, so each is a decision, listed here so it is not lost:

1. `[workspace.lints]` in the root `Cargo.toml` with `[lints] workspace = true` in every
   package: `rust.unsafe_code = "forbid"` would have to be per-crate (`sys` is exempt), so
   the table would carry `missing_docs = "warn"`, `unreachable_pub = "warn"`,
   `clippy.unwrap_used = "deny"`, `clippy.expect_used = "warn"`, `clippy.panic = "warn"`,
   `clippy.cast_possible_truncation = "warn"`, and `clippy.pedantic = "warn"` with its
   exceptions named. The current code passes the first five; `pedantic` and the cast lint
   would need a `mechanical` pass first.
2. `deny.toml` with the licence allowlist above, once `cargo deny` is installed (the user's
   OK, `README.md` "Open").
3. The `as` casts already in `cli`, `sys`, `ls` and `cp` replaced by `From` and `TryFrom`
   where lossless or checked conversions exist, as one `mechanical` run.

## The rules, compressed (for agents)

Read this list before writing; the sections above are the reasons.

### Before writing
- Read the neighbouring module (`ls`, `cp`, the crate you touch) and follow its structure and
  names. Read `docs/PROGRAM.md` and `.claude/rules/subagents.md` whole.
- A written program comes from its DEFINITION.md, DESIGN.md and `schemas/`; the reference's
  manual and code are read with `git show` to settle what they leave open and to check a
  behaviour, never copied or translated, and nothing names the reference system.
- Each behaviour the DEFINITION states becomes a test before it becomes code.
- If you think you need `unsafe`, stop: propose the `std` call or the `sys` addition instead.
- If you think you need a crate from outside, stop: hand back the question.

### While writing
- `#![forbid(unsafe_code)]` at the crate root of every program and of `cli`; `sys` only, with
  `// SAFETY:` at every site and a safe wrapper around each.
- `Result` and `?` for every failure; the diagnostic through `COMMAND.report`, `warn` or
  `usage_error`, with the `io::Error` itself so the errno name travels; exit codes 0, 1, 2
  computed once in `main`.
- `unwrap()` only in tests; `expect()` only for an invariant the code guarantees, the message
  saying why it holds.
- Paths, arguments and the environment are `Path`, `OsStr`, `&[u8]`; lossy conversion once,
  at the renderer, through `cli::text::sanitize`.
- Enums with data instead of booleans and strings; `match` without `_` on our own types.
- `From` and `TryFrom` for integers, not `as`, where they exist.
- `clone()` never to silence the borrow checker; change the ownership.
- `pledge` before the first argument is read, the least the options need.
- Single-threaded unless DESIGN.md says otherwise; no `async`; no signal handler of our own.
- Stdout through a locked `BufWriter`; `BrokenPipe` is silence, stops the output, and exits
  as the DEFINITION says on every path.
- Doc on everything `pub` of `cli` and `sys`, `//!` at the top of every file, the ISC block
  first; comments say why. Everything in English.

### Before each commit
- `just lint` and `just test` in the program's directory; `just check` at the root before
  handing back.
- A commit that changes `src/` carries `Change: breaking|feature|fix` and the version bump it
  calls for; a `cli` or `sys` breaking change migrates every user in the same commit.
- Every fixed bug leaves a test that failed before the fix, in the same commit.
- Add paths by name; never `git add -A`, never amend, never push.

### Never
- `unsafe` outside `sys`; `fork` without `exec`, `pre_exec`, `static mut`, `transmute`,
  `unsafe impl Send`.
- `panic!` as error handling; `to_str().unwrap()` on a `Path` or `OsStr`.
- `#[allow(...)]` without `reason = "..."`.
- A `TODO` in the code; a promise lives in `HANDOFF.md`.
- A crate, a tool, a toolchain bump or a `docs/PROGRAM.md` rule changed without the user's
  decision.
