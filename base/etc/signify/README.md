# EmiBSD's signify public keys

The public halves of the keys that sign EmiBSD's releases, one file each, as `signify(1)`
reads them (a comment line and the key line):

| File | Signs |
|---|---|
| `emibsd-80-base.pub` | the base sets of release 8.0; the installer verifies the sets with it |
| `emibsd-80-fw.pub` | the firmware of release 8.0 |
| `emibsd-80-pkg.pub` | the packages of release 8.0 |
| `emibsd-80-syspatch.pub` | the syspatch updates of release 8.0 |
| `emibsd-81-base.pub` | the base sets of release 8.1 |

The private halves belong to the maintainer and are never in a repository. A new release
adds its next key here, as `emibsd-NN-<purpose>.pub`; the keys are public and are never
edited once published.

`tools/world.py` installs these files in place of the inherited tree's `etc/signify/`
(the base system's own keys are removed from the copy), so the sets, the installer's
ramdisk and every program that names a key (`install.sub`, `syspatch`, `fw_update`,
`sysupgrade`, `pkg_add`) refer to these. A reference to a key EmiBSD does not have is
dropped from the lists, not renamed to a file that would not exist.
