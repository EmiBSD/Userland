# distrib/include

/usr/include as include/Makefile assembles it: the C library's public headers (include/) and the kernel's, the ABI the kernel implements (sys/, headers only, without dev/microcode and dev/pci/drm, as that Makefile leaves them out). The libraries' own exported headers stay with each library.

Programs of this group:

- `include` (include)
- `crypto` (sys/crypto)
- `ddb` (sys/ddb)
- `dev` (sys/dev)
- `isofs` (sys/isofs)
- `miscfs` (sys/miscfs)
- `msdosfs` (sys/msdosfs)
- `net` (sys/net)
- `netinet` (sys/netinet)
- `netinet6` (sys/netinet6)
- `netmpls` (sys/netmpls)
- `net80211` (sys/net80211)
- `nfs` (sys/nfs)
- `ntfs` (sys/ntfs)
- `scsi` (sys/scsi)
- `sys` (sys/sys)
- `ufs` (sys/ufs)
- `uvm` (sys/uvm)
- `include` (sys/arch/<arch>/include)

Inherited: `src/` holds these at their paths in the base system's tree, at the pin of `UPSTREAM.toml`.
