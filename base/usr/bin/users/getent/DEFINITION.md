# getent

STATUS: see `STATUS`. EmiBSD's own `getent`, written from scratch under this definition (the
user's decision of 2026-10-23): this document is the specification, written from POSIX where
the standard defines the program and from the behaviour the tradition settled; the code is
written from this document alone.

## What it does

## Scope

What is in, what is out, and why.

## Constraints

Root partition only (static) or not; privileges; what it may never do.

## Inputs

Arguments, standard input, environment variables, files it reads, configuration.

## Parameters

| Flag | Argument | Meaning | Default |
|---|---|---|---|

## Outputs

Human output; `-o json` / `-o yaml` (`schemas/output.v1.json`); what goes to stderr.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success |

## Signals and failure behaviour

SIGHUP, SIGTERM, SIGINT; disk full, permission denied, interrupted.

## Compatibility

What the rest of the base system expects of this program: who calls it (rc, other
programs, the installer), with which flags, which output they parse, which exit codes they
branch on. Nothing here changes without checking every caller.

## Performance budget

The measure that matters for this program and its floor: never slower than a reference
system's getent on the same machine and input (`bench/`, `just bench`).

## Security history

The CVEs of the programs of this name on other systems, each with its class
and what makes it impossible here (a type, a check, the language) or the test in
`tests/cve/` that proves it.

| CVE | Class | Here |
|---|---|---|

## Open questions

