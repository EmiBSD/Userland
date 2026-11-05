# distrib/kernel

The kernel's sources the userland compiles too, reached by the Makefiles' .PATH into sys/: bpf_filter for libpcap, pf_ruleset for pfctl, pf_osfp for tcpdump, ffs_subr and ffs_tables for fsck_ffs and fsdb, ext2fs_bswap for the ext2fs tools, syscalls for btrace, the three DRM device lists fw_update matches firmware with, and the DRM ioctls kdump decodes.

Programs of this group:

- `bpf_filter.c` (sys/net/bpf_filter.c)
- `pf_ruleset.c` (sys/net/pf_ruleset.c)
- `pf_osfp.c` (sys/net/pf_osfp.c)
- `ffs_subr.c` (sys/ufs/ffs/ffs_subr.c)
- `ffs_tables.c` (sys/ufs/ffs/ffs_tables.c)
- `ext2fs_bswap.c` (sys/ufs/ext2fs/ext2fs_bswap.c)
- `syscalls.c` (sys/kern/syscalls.c)
- `amdgpu_devlist.h` (sys/dev/pci/drm/amd/amdgpu/amdgpu_devlist.h)
- `i915_devlist.h` (sys/dev/pci/drm/i915/i915_devlist.h)
- `radeon_devlist.h` (sys/dev/pci/drm/radeon/radeon_devlist.h)
- `i915_drm.h` (sys/dev/pci/drm/include/uapi/drm/i915_drm.h)
- `drm.h` (sys/dev/pci/drm/include/uapi/drm/drm.h)
- `drm_mode.h` (sys/dev/pci/drm/include/uapi/drm/drm_mode.h)

Inherited: `src/` holds these at their paths in the base system's tree, at the pin of `UPSTREAM.toml`.
