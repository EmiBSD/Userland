# The contract of a program

Every program and library directory of this repository (`bin/`, `sbin/`, `usr/bin/`,
`usr/sbin/`, `libexec/`, `lib/`) is one solution, laid out the same way. `tools/layout.py`
creates the skeleton; the people and agents who work on the program fill it, in this order.

```
<group>/<name>/
├── STATUS            one word: planned | defined | designed | implemented | shipped
├── DEFINITION.md     the functional design: what it does, scope, constraints, inputs,
│                     parameters, outputs, exit codes, signals, compatibility
├── DESIGN.md         the architecture: mermaid diagrams, security (pledge, unveil,
│                     privileges), decisions with their reasons, dependencies
├── schemas/          the machine-readable contracts: output.v1.json, config.v1.json
│                     (what `-o json` / `-o yaml` emit; versioned, kubectl's apiVersion)
├── src/              the Rust sources, a Cargo package; unit tests beside the code
├── tests/            integration tests, property tests for every parser, and golden/,
│                     the differential tests: the same input to ours and to OpenBSD's
├── man/<name>.<n>    the manual, mdoc(7) source; HTML and Markdown are rendered from it
├── etc/              the default configuration installed under /etc, when it has one
├── DELIVERY.md       the install set, path, static or dynamic, owner and mode, MAKEDEV
└── justfile          `import` of tools/program.just: build, test, lint, man, status
```

## The order

1. **planned**: the skeleton exists. `DEFINITION.md` names the OpenBSD program and manual
   that are the reference for behaviour.
2. **defined**: `DEFINITION.md` is complete. Its *Compatibility* section is the one that
   matters most: what the rest of the base system expects of this program (the flags `rc`
   calls it with, the output another program parses, the exit codes a script branches on).
   The base system is an ecosystem; a program that works but breaks `netstart` is a failure.
3. **designed**: `DESIGN.md` and `schemas/` are complete; the security section says which
   `pledge(2)` promises and `unveil(2)` paths the program lives under, and whether it
   separates privileges or runs setuid. Nothing OpenBSD's program restricts may be relaxed.
4. **implemented**: `src/` builds, the unit, integration, property and differential tests
   pass, `man/` is complete with EXAMPLES. The package joined the workspace `Cargo.toml`.
5. **shipped**: `DELIVERY.md` is complete and `distrib/` installs it.

## Rules

- Written from scratch under the definition; OpenBSD's code is read for behaviour, never
  copied or translated (the user's decision of 2026-10-23).
- Rust; `#![forbid(unsafe_code)]` at the crate root. `unsafe` only in `lib/libc` and
  `libexec/rtld`, each site with a `// SAFETY:` proof.
- A new dependency needs the user's OK and a row in the allowlist (to be written with the
  first program).
- The manual's source is mdoc(7), the format of the system; `mandoc -T markdown` and
  `-T html` render it for the site. EXAMPLES is not optional.
- Every file starts with the author's ISC block (`LICENSE`).
- `just status` at the root counts the STATUS files; that count is the progress of the
  userland, as `cargo xtask lz status` is the kernel's.
