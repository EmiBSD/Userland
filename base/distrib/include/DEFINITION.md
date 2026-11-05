# distrib/include (inherited)

STATUS: see `STATUS`. Files of the base system that belong to no program, at the pin of
`UPSTREAM.toml`, in this layout (the user's decision of 2026-11-04): `src/` holds OpenBSD's
`include`, `sys/crypto`, `sys/ddb`, `sys/dev`, `sys/isofs`, `sys/miscfs`, `sys/msdosfs`, `sys/net`, `sys/netinet`, `sys/netinet6`, `sys/netmpls`, `sys/net80211`, `sys/nfs`, `sys/ntfs`, `sys/scsi`, `sys/sys`, `sys/ufs`, `sys/uvm`, `sys/arch/arm64/include`, `sys/arch/amd64/include`, each at its own path in that tree, byte for byte and every notice kept whole,
rewritten from the pin by `tools/layout.py` and never edited by hand. What we change is a
patch under `patches/`.

## What it is for here

## Patches

The series under `patches/`, each with its reason; none today.
