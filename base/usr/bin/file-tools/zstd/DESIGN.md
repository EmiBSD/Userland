# zstd: the integration

- **Privileges and pledge.** As upstream has it: no pledge(2) or unveil(2) of ours; the
  program runs as its user and touches only the files it is given.
- **Concurrency.** Upstream's: with `-T`, worker threads over libpthread; one thread by
  default.
- **Where it runs.** `/usr/bin` in the base set (dynamic, as `usr/` is); the installer's
  ramdisk carries the decompressor crunched into `instbin`.
