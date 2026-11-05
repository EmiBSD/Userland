# distrib

How a release is made, and what else is generated at release time: the install sets, the installer and its ramdisk, /usr/include from the libraries' exported headers, /usr/share from every program's manual plus data/.

| Directory | What |
|---|---|
| `sets/` | The install sets and their lists; the release version is YEAR.MONTH (docs/PROGRAM.md, Versions). |
| `installer/` | The installer, its ramdisk and the per-architecture media. |
| `include/` | /usr/include as include/Makefile assembles it: the C library's public headers (include/) and the kernel's, the ABI the kernel implements (sys/, headers only, without dev/microcode and dev/pci/drm, as that Makefile leaves them out). The libraries' own exported headers stay with each library. |
| `share/` | /usr/share's own trees: share/mk, the rules every Makefile of the base system includes, and the manuals' shared pages. |
| `kernel/` | The kernel's sources the userland compiles too, reached by the Makefiles' .PATH into sys/: bpf_filter for libpcap, pf_ruleset for pfctl, pf_osfp for tcpdump, ffs_subr and ffs_tables for fsck_ffs and fsdb, ext2fs_bswap for the ext2fs tools, syscalls for btrace, the three DRM device lists fw_update matches firmware with, and the DRM ioctls kdump decodes. |
| `build/` | The base system's build glue, which belongs to no program: the top Makefile and Makefile.cross, and the Makefile and Makefile.inc of each tree (bin/Makefile.inc makes every /bin program static). |

Nothing written yet.
