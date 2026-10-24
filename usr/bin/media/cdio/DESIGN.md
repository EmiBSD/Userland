# cdio: design

## Architecture

```mermaid
flowchart LR
    A[input] --> B[cdio] --> C[output]
```

## Security

`pledge(2)` promises, `unveil(2)` paths, privilege separation, setuid. Never less than
OpenBSD's cdio(1) restricts.

## Data

The schemas in `schemas/`; their versions; who consumes them.

## Decisions

Numbered, each with its reason and what was rejected.

## Dependencies

Crates used, each with why; the allowlist governs.
