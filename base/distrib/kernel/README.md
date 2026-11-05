# distrib/kernel

The kernel's sources the userland compiles too, reached by the Makefiles' .PATH into sys/: bpf_filter for libpcap, pf_ruleset for pfctl, pf_osfp for tcpdump, ffs_subr and ffs_tables for fsck_ffs and fsdb, ext2fs_bswap for the ext2fs tools, syscalls for btrace.

Programs of this group:

- `bpf_filter.c` (sys/net/bpf_filter.c)
- `pf_ruleset.c` (sys/net/pf_ruleset.c)
- `pf_osfp.c` (sys/net/pf_osfp.c)
- `ffs_subr.c` (sys/ufs/ffs/ffs_subr.c)
- `ffs_tables.c` (sys/ufs/ffs/ffs_tables.c)
- `ext2fs_bswap.c` (sys/ufs/ext2fs/ext2fs_bswap.c)
- `syscalls.c` (sys/kern/syscalls.c)

Inherited: `src/` holds these at their paths in the base system's tree, at the pin of `UPSTREAM.toml`.
