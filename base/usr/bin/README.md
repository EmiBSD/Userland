# usr/bin

The commands a user runs once /usr is mounted (209).

| Directory | What |
|---|---|
| `text/` | Filters and transformers of text streams. |
| `records/` | Querying the records the written programs emit (`-o json`); EmiBSD's own, no counterpart elsewhere. |
| `editors/` | Editors and the pager. |
| `file-tools/` | Finding, describing and installing files (the basic operations are bin/files). |
| `process-tools/` | Running things under a changed environment, priority or limit; the shell's helpers (the primitives are bin/processes). |
| `users/` | Logging in, identities, who is on the machine, talking to them. |
| `network-clients/` | Network clients a user runs. |
| `development/` | Build tools, source generators, version control and tracing. |
| `docs/` | Manual pages and terminal descriptions. |
| `calc/` | Calculators and calendars. |
| `mail/` | Reading and sending mail from the command line. |
| `scheduling/` | Running things later. |
| `media/` | Audio, MIDI, radio and CD. |
| `system-info/` | What machine this is, how it is doing, and small system chores. |
| `crypto/` | Certificates, signatures and keys from the command line. |
| `yp-clients/` | Querying the YP/NIS directory (its servers are usr/sbin/yp). |
| `misc/` | What fits nowhere else. |

Each entry is a group; each group's README lists its programs.
