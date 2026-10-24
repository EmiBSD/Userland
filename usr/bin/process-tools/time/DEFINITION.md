# time

STATUS: see `STATUS`. Reference for behaviour: OpenBSD's `usr.bin/time`, manual time(1).
Written from scratch under this definition; not a port (the user's decision of 2026-10-23).

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

The measure that matters for this program and its floor: never slower than OpenBSD's
time on the same machine and input (`bench/`, `just bench`).

## Security history

The CVEs and errata of OpenBSD's time (and of what it derives from), each with its class
and what makes it impossible here (a type, a check, the language) or the test in
`tests/cve/` that proves it.

| CVE | Class | Here |
|---|---|---|

## Open questions

