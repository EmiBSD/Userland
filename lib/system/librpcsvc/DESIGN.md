# librpcsvc: design

## Architecture

```mermaid
flowchart LR
    A[input] --> B[librpcsvc] --> C[output]
```

## Concurrency

The model (single-threaded, a process per privilege or connection as OpenBSD's daemons do,
a thread pool, an event loop); what is shared and how; whether and how it uses more than one
core. What serves many has stress tests in `tests/stress/` on four CPUs.

## Threat model

Which inputs are hostile (the network, a user's file, an argument from root), what an
attacker gains from each failure, and what bounds it.

## Security

`pledge(2)` promises, `unveil(2)` paths, privilege separation, setuid. Never less than
OpenBSD's librpcsvc(3) restricts.

## Data

The schemas in `schemas/`; their versions; who consumes them.

## Decisions

Numbered, each with its reason and what was rejected.

## Dependencies

Crates used, each with why; the allowlist governs.
