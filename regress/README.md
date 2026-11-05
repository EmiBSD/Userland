# regress

The integration battery: what no single program's tests can see. Boots EmiBSD in QEMU and runs scenarios across programs (login over the console, rc bringing up the network, an install from the ramdisk, ssh in, pf rules, a mail delivered), each also run on a reference system and compared, as the kernel's differential battery does.

| Directory | What |
|---|---|
| `scenarios/` | One directory per scenario: the steps, the expected lines, the comparison with a reference system. |
| `harness/` | Booting the images, driving the console, collecting and comparing. |

Nothing written yet.
