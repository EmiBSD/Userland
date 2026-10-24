# EmiBSD Userland

The monorepo of EmiBSD's own userland: the programs, libraries and configuration that run
above the [Kernel](https://github.com/EmiBSD/Kernel). Phase 3 of the project: until the
kernel's redesign closes at N9, EmiBSD runs OpenBSD's base system unmodified; this repository
is where the system that replaces it is written.

## Layout

Grouped by what each part does, not by where it installs (OpenBSD's `bin/`, `sbin/`,
`usr.bin/`, `usr.sbin/` split by install path; that split, root partition only and linked
static or not, is a build attribute here). Every directory's `README.md` says what it is for
and which programs of OpenBSD's base system (at the pin of `Kernel/reference/PINNED.md`) it
covers, so nothing is forgotten and nothing is listed twice.

```
core-utilities/
├── shell            The shells and the terminal line they run on.
├── files            Listing, copying, moving, finding and describing files.
├── text             Filters and transformers of text streams.
├── editors          Editors and pagers.
├── process          Running, timing, listing and signalling processes; the shell's small helpers.
├── users            Logging in, identities, who is on the machine, talking to them.
├── net-clients      Network clients a user runs.
├── calc             Calculators and calendars.
├── mail             Reading and sending mail from the command line.
├── media            Audio, MIDI, radio and CD control.
├── docs             Manual pages and terminal descriptions.
├── scheduling       Running things later.
├── system-info      What machine this is and how it is set up.
└── misc             What fits nowhere else.
system-libraries/
├── libc             The C library, its start-up files and threads.
├── rtld             The run-time linker.
├── crypto           Cryptography and authentication libraries.
├── terminal         Terminal handling and line editing.
├── system           The rest of the system libraries.
└── include          The headers installed under /usr/include.
development-tools/
├── compiler         The compiler, the linker and the C++ runtime.
├── build            Build tools and source generators.
└── debug            Tracing and inspecting running programs and the kernel.
system-services/
├── storage          Disks, partitions, file systems, mounts, swap and backup.
├── network          Interfaces, addresses, routes, the packet filter, DHCP and name resolution.
├── routing          Routing daemons and their control programs.
├── daemons          Servers: web, mail, time, DNS, LDAP, logging, cron, inetd.
├── vpn              IPsec, IKE, PPP and L2TP.
├── auth             Authentication back ends, RADIUS and tokens.
├── crypto-tools     Certificates, signatures and keys from the command line.
├── nfs-rpc          NFS and the RPC services.
├── yp               The YP/NIS directory service.
├── hardware         Talking to the kernel about devices: sysctl, dmesg, consoles, buses, power, sensors.
├── monitoring       Statistics and accounting.
├── accounts         Users, groups and the system databases built from them.
├── print            Printing.
├── virtualization   vmm(4)'s daemon and control program, and the guest-host channel.
└── packages         Packages, firmware, patches and upgrades.
init/
├── init             Process 1 and how the system goes down.
└── rc               The start-up scripts and their control; terminals and login prompts.
base-config/
└── etc              OpenBSD's etc/ apart from the rc scripts (init/rc).
distrib/
├── sets             The install sets and their lists.
├── installer        The installer, its ramdisk and the per-architecture media.
└── share            zoneinfo, locale, dictionaries, terminal types: data for everyone.
```

The lists are the map to what OpenBSD's base system provides, not a porting list: the
programs written here are EmiBSD's own.

New code is ISC (`LICENSE`).
