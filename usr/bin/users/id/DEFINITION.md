# id

STATUS: see `STATUS`. Reference for behaviour: OpenBSD's `usr.bin/id`, manual id(1).
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

## Open questions
