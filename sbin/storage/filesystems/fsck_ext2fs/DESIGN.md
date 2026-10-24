# fsck_ext2fs: design

## Architecture

```mermaid
flowchart LR
    A[input] --> B[fsck_ext2fs] --> C[output]
```

## Security

`pledge(2)` promises, `unveil(2)` paths, privilege separation, setuid. Never less than
OpenBSD's fsck_ext2fs(8) restricts.

## Data

The schemas in `schemas/`; their versions; who consumes them.

## Decisions

Numbered, each with its reason and what was rejected.

## Dependencies

Crates used, each with why; the allowlist governs.
