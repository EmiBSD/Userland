# usr/bin/process-tools

Running things under a changed environment, priority or limit; the shell's helpers (the primitives are bin/processes).

Covers, from OpenBSD's base system at the pin (its path in OpenBSD's `src`):

- [`env`](env/) (usr.bin/env)
- [`nice`](nice/) (usr.bin/nice)
- [`nohup`](nohup/) (usr.bin/nohup)
- [`renice`](renice/) (usr.bin/renice)
- [`time`](time/) (usr.bin/time)
- [`timeout`](timeout/) (usr.bin/timeout)
- [`pkill`](pkill/) (usr.bin/pkill)
- [`top`](top/) (usr.bin/top)
- [`fstat`](fstat/) (usr.bin/fstat)
- [`true`](true/) (usr.bin/true)
- [`false`](false/) (usr.bin/false)
- [`yes`](yes/) (usr.bin/yes)
- [`seq`](seq/) (usr.bin/seq)
- [`jot`](jot/) (usr.bin/jot)
- [`printf`](printf/) (usr.bin/printf)
- [`printenv`](printenv/) (usr.bin/printenv)
- [`getopt`](getopt/) (usr.bin/getopt)
- [`getconf`](getconf/) (usr.bin/getconf)
- [`tee`](tee/) (usr.bin/tee)
- [`tty`](tty/) (usr.bin/tty)
- [`tsort`](tsort/) (usr.bin/tsort)
- [`apply`](apply/) (usr.bin/apply)

Each entry is a program directory laid out as `docs/PROGRAM.md` says.
