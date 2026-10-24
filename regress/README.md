# regress

The integration battery: what no single program's tests can see. Boots EmiBSD in QEMU and runs scenarios across programs (login over the console, rc bringing up the network, an install from the ramdisk, ssh in, pf rules, a mail delivered), each also run on OpenBSD at the pin and compared, as the kernel's diff-openbsd does. OpenBSD's regress/ is not in the clone; its scenarios are read as the reference for what to cover (the kernel's N11 organic battery draws on the same source).

| Directory | What |
|---|---|
| `scenarios/` | One directory per scenario: the steps, the expected lines, the OpenBSD comparison. |
| `harness/` | Booting the images, driving the console, collecting and comparing. |

Nothing written yet.
