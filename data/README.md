# data

Data for everyone that no program owns, imported from its upstream like a program is (an UPSTREAM.toml per entry, to be written): the time zone database, locales, dictionaries, terminal types. A program's manual lives beside the program; `share/` as a tree is generated at install time, not kept. OpenBSD's share/, reduced.

| Directory | What |
|---|---|
| `zoneinfo/` | The IANA time zone database (tzdata; zic and zdump are usr/sbin/services). |
| `locale/` | Locale definitions and character maps. |
| `dict/` | The word lists spell(1) and look(1) read. |
| `termtypes/` | The terminal descriptions, source of terminfo (tic is usr/bin/docs). |
| `misc/` | Small tables of share/misc: ascii, airport codes, units, the magic of file(1) is in file itself. |

Nothing written yet.
