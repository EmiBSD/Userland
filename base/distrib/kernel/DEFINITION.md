# distrib/kernel (inherited)

STATUS: see `STATUS`. Files of the base system that belong to no program, at the pin of
`UPSTREAM.toml`, in this layout (the user's decision of 2026-11-04): `src/` holds OpenBSD's
`sys/net/bpf_filter.c`, `sys/net/pf_ruleset.c`, `sys/net/pf_osfp.c`, `sys/ufs/ffs/ffs_subr.c`, `sys/ufs/ffs/ffs_tables.c`, `sys/ufs/ext2fs/ext2fs_bswap.c`, `sys/kern/syscalls.c`, `sys/dev/pci/drm/amd/amdgpu/amdgpu_devlist.h`, `sys/dev/pci/drm/i915/i915_devlist.h`, `sys/dev/pci/drm/radeon/radeon_devlist.h`, `sys/dev/pci/drm/include/uapi/drm/i915_drm.h`, `sys/dev/pci/drm/include/uapi/drm/drm.h`, `sys/dev/pci/drm/include/uapi/drm/drm_mode.h`, `sys/conf/files`, `sys/arch/arm64/conf/files.arm64`, `sys/arch/amd64/conf/files.amd64`, `sys/scsi/files.scsi`, `sys/dev/acpi/files.acpi`, `sys/dev/adb/files.adb`, `sys/dev/ata/files.ata`, `sys/dev/atapiscsi/files.atapiscsi`, `sys/dev/cardbus/files.cardbus`, `sys/dev/dec/files.dec`, `sys/dev/efi/files.efi`, `sys/dev/eisa/files.eisa`, `sys/dev/fdt/files.fdt`, `sys/dev/gpio/files.gpio`, `sys/dev/hid/files.hid`, `sys/dev/hil/files.hil`, `sys/dev/i2c/files.i2c`, `sys/dev/isa/files.isa`, `sys/dev/isa/files.isapnp`, `sys/dev/mii/files.mii`, `sys/dev/ofw/files.ofw`, `sys/dev/onewire/files.onewire`, `sys/dev/pci/drm/files.drm`, `sys/dev/pci/files.agp`, `sys/dev/pci/files.pci`, `sys/dev/pckbc/files.pckbc`, `sys/dev/pcmcia/files.pcmcia`, `sys/dev/pv/files.pv`, `sys/dev/rasops/files.rasops`, `sys/dev/sbus/files.sbus`, `sys/dev/sdmmc/files.sdmmc`, `sys/dev/sun/files.sun`, `sys/dev/tc/files.tc`, `sys/dev/usb/dwc2/files.dwc2`, `sys/dev/usb/files.usb`, `sys/dev/wscons/files.wscons`, `sys/dev/wsfont/files.wsfont`, each at its own path in that tree, byte for byte and every notice kept whole,
rewritten from the pin by `tools/layout.py` and never edited by hand. What we change is a
patch under `patches/`.

## What it is for here

## Patches

The series under `patches/`, each with its reason in its header: none today.
