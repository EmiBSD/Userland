# sys

STATUS: see `STATUS`. No OpenBSD counterpart: it wraps the libc calls the written programs
need and `std` lacks. Written from scratch with `ls` (2026-10-24) and extended with `cp`.

## What it does

The thin FFI over libc the written programs share, and the one crate beside `lib/libc` and
`libexec/rtld` where `unsafe` is allowed, every site with a `// SAFETY:` proof: the passwd
and group databases (`user_name`, `group_name`, cached), the terminal's width
(`terminal_columns`), local time (`local_time`), `pledge`, the caller's identity (`getuid`,
`umask`), and the file-system calls `std` has no safe wrapper for (`mkfifo`, `mknod`,
`set_flags_fd`, `set_flags_nofollow`, `set_times_nofollow`, `set_mode_nofollow`), plus
`flags_to_string` for `chflags(1)`'s names.

## Scope

In: what a written program asks libc that `std` does not wrap. Out: anything `std` wraps
(files, directories, metadata, `chown`, `set_times`, `set_permissions`, the environment),
which is used directly; anything with a safe crate of its own in the repository.

## Constraints

Targets: OpenBSD and macOS (the development host); any other is a compile error, because
the `#[repr(C)]` layouts (`passwd`, `group`, `winsize`, `tm`, `timespec`) and the constants
(`TIOCGWINSZ`, `AT_FDCWD`, `AT_SYMLINK_NOFOLLOW`, `mode_t`'s width) are those two systems'.
`#![deny(unsafe_op_in_unsafe_fn)]`; no `static mut`; the caches are thread-local.

## Inputs

The calls' arguments; `TZ` through `localtime_r`.

## Parameters

The API, in `man/sys.3` and the doc comments. Every function returns `io::Result` or
`Option`; none panics on a libc failure.

## Outputs

None of its own.

## Exit codes

None: a library.

## Signals and failure behaviour

`pledge` on a host without it is a no-op, so the call sits in every program
unconditionally; on OpenBSD a refusal is an error the program reports before doing anything.

## Compatibility

Every written program that needs libc. A change here is `Change:` on this crate; the
struct layouts must match the kernel's ABI, which is OpenBSD's and does not move.

## Performance budget

`user_name`/`group_name` are cached per thread: an `ls -l` of a hundred thousand entries
makes a handful of lookups. Not otherwise measured.

## Security history

No CVE: no upstream. The risk is the FFI itself; each `unsafe` block states the invariant
and who upholds it, and the host tests exercise every call (Miri on them is pending).

| CVE | Class | Here |
|---|---|---|
| none | a wrong struct layout reading past a buffer | the layouts are per target and refused elsewhere; `tests` read root and group 0 |

## Open questions

- Miri over the host tests, as docs/PROGRAM.md asks.
- `umask()` reads by setting and restoring: a program that creates files from another thread
  at that instant could see the wrong mask; the programs call it first.
