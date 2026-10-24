# jpath

STATUS: see `STATUS`. EmiBSD's own `jpath`, written from scratch under this definition (the
user's decision of 2026-10-24): a program of the user's own, with no counterpart in any
reference tree. Its specification comes from RFC 9535 (JSONPath: Query Expressions for
JSON), whose JSON is RFC 8259's, the same language ECMA-404 defines; and from the common
grammar (docs/PROGRAM.md), whose `-o json` documents it exists to filter. The reference
texts are in `reference/` (its README says which and under what terms). This document is
the specification the code will be written from.

## What it does

Selects nodes of a JSON document with a JSONPath query and prints them: what XPath is to
XML, `jpath` is to JSON (the user's words of 2026-10-24: "similar a xpath pero con json").
The document comes from a file operand or from standard input, so the `-o json` output of
every written program can be filtered in a pipeline:

```
ls -lo json | jpath '$.items[?@.size > 1000000].name'
```

The query is RFC 9535's: the root `$`, child and descendant segments, the name, wildcard,
index, slice and filter selectors, the five standard functions. The result is the RFC's
nodelist, each node with its value and its Normalized Path (RFC 9535, Section 2.7), rendered
as `-o` asks.

## Scope

In: RFC 9535 complete, as the query language; one document per query from a file or from
standard input; the common grammar's renderers over the nodelist. Out, by the user's
decision of 2026-10-24 ("yo solo necesito filtrar los resultados de un json con jpath para
obtener el resultado"): any transformation or construction of new values, any pipe or
function language beyond the RFC's filter expressions, any state. `jpath` is a query, not a
language. What the survey and the design must still settle is in Open questions.

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
system's jpath on the same machine and input (`bench/`, `just bench`).

## Security history

The CVEs of the programs of this name on other systems, each with its class
and what makes it impossible here (a type, a check, the language) or the test in
`tests/cve/` that proves it.

| CVE | Class | Here |
|---|---|---|

## Open questions

- The document `-o json` emits for a nodelist (so `jpath | jpath` chains): the values
  alone, or records of Normalized Path and value, with `apiVersion` and `kind` like every
  other written program's.
- Several JSON documents in one input (one per line, as event-emitting programs write): the
  RFC covers one document; apply the query to each, or refuse.
- The exit code when the query selects nothing: 0 with empty output, or 1 so a script can
  branch (the common grammar's 1 is "something could not be done").
- How much of RFC 9535's function-extension type system the first version carries.

- No counterpart elsewhere: the specification is written from the standards the program
  implements and from the common grammar; there is no reference implementation to survey.
