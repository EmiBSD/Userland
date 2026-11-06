# install-checker: lessons across runs

One line per lesson, appended at the end; task state goes in HANDOFF.md
(`.claude/rules/subagents.md`, "Memory"). Committed with the tree.

- A passing check takes about 25 s to the installer's prompt, 115 s for the install and 45 s for the disk's boot to a shell; the lock wait comes before.
- Expected noise, not failures: after halt the Kernel traps into ddb ("Unknown kernel exception 0x00") once the disks are synced; rc's reorder_libs and the ssh-agent relink fail without comp's compiler; "unported: coredump" while saving the configuration; kvm_mkdb cannot open /dev/ksyms.
- "Continue without verification?" is expected (the sets are not signed); "Use sets found here anyway?" is a failure (INSTALL.<arch> missing from the medium).
- The install must not be cut short: the disk has no /bsd unless QEMU lives until "halted by root" plus a settle (the tool waits 60 s).
- The lock at /tmp/emibsd/ci.lock is often held by the Kernel's agents for half an hour; wait, never remove it.
