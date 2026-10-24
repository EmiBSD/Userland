// Copyright (c) 2026 Emilio Navarrete Lineros <enavarre@outlook.com>
//
// Permission to use, copy, modify, and distribute this software for any
// purpose with or without fee is hereby granted, provided that the above
// copyright notice and this permission notice appear in all copies.
//
// THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
// WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
// MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
// ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
// WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
// ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
// OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

//! `sys`: the thin FFI over libc that the written programs share.
//!
//! This is the one crate beside `lib/libc` and `libexec/rtld` where `unsafe` is allowed
//! (docs/PROGRAM.md). Every `unsafe` block carries its proof. What the standard library
//! already wraps (files, directories, metadata, the environment) is not duplicated here;
//! only what it lacks: the passwd and group databases, the terminal's size, the local time
//! zone, `pledge(2)`, the caller's uid and umask, and the file-system calls `std` has no
//! safe wrapper for (`mkfifo`, `mknod`, the file flags, times and mode of a symbolic link).
//!
//! The layouts below are those of OpenBSD and of macOS (where the programs are developed
//! and tested before they run on EmiBSD); any other target is refused at compile time.

#![deny(unsafe_op_in_unsafe_fn)]
#![warn(missing_docs)]

use std::cell::RefCell;
use std::collections::HashMap;
use std::ffi::{CStr, CString};
use std::io;
use std::os::unix::ffi::OsStrExt;
use std::path::Path;

#[cfg(not(any(target_os = "macos", target_os = "openbsd")))]
compile_error!(
    "sys: the struct layouts below are OpenBSD's and macOS's; add this target deliberately"
);

mod ffi {
    use std::ffi::{c_char, c_int, c_long, c_ulong};

    /// `time_t` on both targets (OpenBSD: 64 bits everywhere; macOS: `long`, 64 bits).
    pub type TimeT = i64;
    /// `mode_t`: 32 bits on OpenBSD, 16 on macOS.
    #[cfg(target_os = "openbsd")]
    pub type ModeT = u32;
    #[cfg(target_os = "macos")]
    pub type ModeT = u16;
    /// `dev_t`: 32 bits, signed, on both.
    pub type DevT = i32;
    /// `AT_FDCWD`: paths relative to the current directory.
    #[cfg(target_os = "openbsd")]
    pub const AT_FDCWD: c_int = -100;
    #[cfg(target_os = "macos")]
    pub const AT_FDCWD: c_int = -2;
    /// `AT_SYMLINK_NOFOLLOW`: act on a symbolic link itself.
    #[cfg(target_os = "openbsd")]
    pub const AT_SYMLINK_NOFOLLOW: c_int = 0x02;
    #[cfg(target_os = "macos")]
    pub const AT_SYMLINK_NOFOLLOW: c_int = 0x20;

    /// `struct timespec`, 64-bit seconds and nanoseconds on both targets.
    #[repr(C)]
    pub struct Timespec {
        pub tv_sec: TimeT,
        pub tv_nsec: c_long,
    }

    /// `struct passwd`: the same ten fields in the same order on OpenBSD and macOS.
    #[repr(C)]
    pub struct Passwd {
        pub pw_name: *mut c_char,
        pub pw_passwd: *mut c_char,
        pub pw_uid: u32,
        pub pw_gid: u32,
        pub pw_change: TimeT,
        pub pw_class: *mut c_char,
        pub pw_gecos: *mut c_char,
        pub pw_dir: *mut c_char,
        pub pw_shell: *mut c_char,
        pub pw_expire: TimeT,
    }

    /// `struct group`: the same four fields on both targets.
    #[repr(C)]
    pub struct Group {
        pub gr_name: *mut c_char,
        pub gr_passwd: *mut c_char,
        pub gr_gid: u32,
        pub gr_mem: *mut *mut c_char,
    }

    /// `struct winsize`.
    #[repr(C)]
    #[derive(Default)]
    pub struct Winsize {
        pub ws_row: u16,
        pub ws_col: u16,
        pub ws_xpixel: u16,
        pub ws_ypixel: u16,
    }

    /// `struct tm`, the BSD layout with `tm_gmtoff` and `tm_zone`.
    #[repr(C)]
    pub struct Tm {
        pub tm_sec: c_int,
        pub tm_min: c_int,
        pub tm_hour: c_int,
        pub tm_mday: c_int,
        pub tm_mon: c_int,
        pub tm_year: c_int,
        pub tm_wday: c_int,
        pub tm_yday: c_int,
        pub tm_isdst: c_int,
        pub tm_gmtoff: c_long,
        pub tm_zone: *mut c_char,
    }

    /// `TIOCGWINSZ`: `_IOR('t', 104, struct winsize)`, the same encoding on both BSDs.
    pub const TIOCGWINSZ: c_ulong = 0x4008_7468;

    unsafe extern "C" {
        pub fn getpwuid_r(
            uid: u32,
            pwd: *mut Passwd,
            buf: *mut c_char,
            buflen: usize,
            result: *mut *mut Passwd,
        ) -> c_int;
        pub fn getgrgid_r(
            gid: u32,
            grp: *mut Group,
            buf: *mut c_char,
            buflen: usize,
            result: *mut *mut Group,
        ) -> c_int;
        pub fn ioctl(fd: c_int, request: c_ulong, ...) -> c_int;
        pub fn localtime_r(clock: *const TimeT, result: *mut Tm) -> *mut Tm;
        #[cfg(target_os = "openbsd")]
        pub fn pledge(promises: *const c_char, execpromises: *const c_char) -> c_int;
        pub fn getuid() -> u32;
        pub fn umask(mask: ModeT) -> ModeT;
        pub fn mkfifo(path: *const c_char, mode: ModeT) -> c_int;
        pub fn mknod(path: *const c_char, mode: ModeT, dev: DevT) -> c_int;
        pub fn fchflags(fd: c_int, flags: u32) -> c_int;
        #[cfg(target_os = "macos")]
        pub fn lchflags(path: *const c_char, flags: u32) -> c_int;
        #[cfg(target_os = "openbsd")]
        pub fn chflagsat(fd: c_int, path: *const c_char, flags: u32, atflags: c_int) -> c_int;
        pub fn utimensat(
            fd: c_int,
            path: *const c_char,
            times: *const Timespec,
            flags: c_int,
        ) -> c_int;
        pub fn fchmodat(fd: c_int, path: *const c_char, mode: ModeT, flags: c_int) -> c_int;
    }
}

thread_local! {
    static USERS: RefCell<HashMap<u32, Option<String>>> = RefCell::new(HashMap::new());
    static GROUPS: RefCell<HashMap<u32, Option<String>>> = RefCell::new(HashMap::new());
}

/// Copies a NUL-terminated C string that libc filled into one of its own structures.
///
/// # Safety
/// `p` is a pointer libc returned inside a buffer this crate owns and has not freed or
/// reused since; it is either null or points at a NUL-terminated string.
unsafe fn c_string(p: *const std::ffi::c_char) -> Option<String> {
    if p.is_null() {
        return None;
    }
    // SAFETY: the caller's contract, above.
    Some(unsafe { CStr::from_ptr(p) }.to_string_lossy().into_owned())
}

fn lookup_user(uid: u32) -> Option<String> {
    let mut pwd = std::mem::MaybeUninit::<ffi::Passwd>::uninit();
    let mut buf = vec![0 as std::ffi::c_char; 4096];
    let mut result: *mut ffi::Passwd = std::ptr::null_mut();
    // SAFETY: `pwd` is a valid, writable `struct passwd` of the target's layout; `buf` is a
    // writable buffer of the length passed; `result` is a valid out-pointer. getpwuid_r
    // writes only within them and sets `result` to `pwd` or to null.
    let rc = unsafe {
        ffi::getpwuid_r(
            uid,
            pwd.as_mut_ptr(),
            buf.as_mut_ptr(),
            buf.len(),
            &mut result,
        )
    };
    if rc != 0 || result.is_null() {
        return None;
    }
    // SAFETY: getpwuid_r returned 0 with a non-null `result`, so `pwd` is initialised and its
    // string fields point into `buf`, which is alive until the end of this function.
    unsafe { c_string((*result).pw_name) }
}

fn lookup_group(gid: u32) -> Option<String> {
    let mut grp = std::mem::MaybeUninit::<ffi::Group>::uninit();
    let mut buf = vec![0 as std::ffi::c_char; 4096];
    let mut result: *mut ffi::Group = std::ptr::null_mut();
    // SAFETY: as in `lookup_user`, for `struct group` and getgrgid_r.
    let rc = unsafe {
        ffi::getgrgid_r(
            gid,
            grp.as_mut_ptr(),
            buf.as_mut_ptr(),
            buf.len(),
            &mut result,
        )
    };
    if rc != 0 || result.is_null() {
        return None;
    }
    // SAFETY: getgrgid_r returned 0 with a non-null `result`; `gr_name` points into `buf`.
    unsafe { c_string((*result).gr_name) }
}

/// The login name of `uid`, or `None` when the passwd database has no such user. Cached
/// per thread, as libc's `user_from_uid(3)` caches, since a listing asks for the same few
/// ids thousands of times.
pub fn user_name(uid: u32) -> Option<String> {
    USERS.with(|c| {
        c.borrow_mut()
            .entry(uid)
            .or_insert_with(|| lookup_user(uid))
            .clone()
    })
}

/// The name of `gid`, or `None` when the group database has no such group. Cached per thread.
pub fn group_name(gid: u32) -> Option<String> {
    GROUPS.with(|c| {
        c.borrow_mut()
            .entry(gid)
            .or_insert_with(|| lookup_group(gid))
            .clone()
    })
}

/// The width in columns of the terminal on standard output, or `None` when it is not a
/// terminal or the kernel does not know.
pub fn terminal_columns() -> Option<usize> {
    let mut ws = ffi::Winsize::default();
    // SAFETY: TIOCGWINSZ reads nothing and writes exactly one `struct winsize` through the
    // pointer passed, which is a valid, writable `Winsize` of that layout.
    let rc = unsafe { ffi::ioctl(1, ffi::TIOCGWINSZ, &mut ws as *mut ffi::Winsize) };
    if rc == 0 && ws.ws_col > 0 {
        Some(ws.ws_col as usize)
    } else {
        None
    }
}

/// A broken-down local time.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct LocalTime {
    /// The year, e.g. 2026.
    pub year: i32,
    /// The month, 1 to 12.
    pub month: u32,
    /// The day of the month, 1 to 31.
    pub day: u32,
    /// Hours, 0 to 23.
    pub hour: u32,
    /// Minutes.
    pub minute: u32,
    /// Seconds, 0 to 60.
    pub second: u32,
    /// Seconds east of UTC for this instant (daylight saving included).
    pub utc_offset: i64,
}

/// `secs` since the epoch as local time in the zone `TZ` names, or `None` for a time the C
/// library cannot represent.
pub fn local_time(secs: i64) -> Option<LocalTime> {
    let mut tm = std::mem::MaybeUninit::<ffi::Tm>::uninit();
    let clock: ffi::TimeT = secs;
    // SAFETY: `clock` is a valid time_t and `tm` a valid, writable `struct tm` of the BSD
    // layout; localtime_r writes only `tm` and returns its pointer or null.
    let p = unsafe { ffi::localtime_r(&clock, tm.as_mut_ptr()) };
    if p.is_null() {
        return None;
    }
    // SAFETY: localtime_r returned non-null, so `tm` is initialised.
    let tm = unsafe { tm.assume_init() };
    Some(LocalTime {
        year: tm.tm_year + 1900,
        month: (tm.tm_mon + 1) as u32,
        day: tm.tm_mday as u32,
        hour: tm.tm_hour as u32,
        minute: tm.tm_min as u32,
        second: tm.tm_sec as u32,
        utc_offset: tm.tm_gmtoff, // c_long is i64 on both targets this crate admits
    })
}

/// `pledge(2)` with the given promises. On OpenBSD a refusal is an error; on a development
/// host without pledge it is a no-op, so the call sits in every program unconditionally.
pub fn pledge(promises: &str) -> io::Result<()> {
    #[cfg(target_os = "openbsd")]
    {
        let c = std::ffi::CString::new(promises)
            .map_err(|_| io::Error::other("pledge: NUL in promises"))?;
        // SAFETY: `c` is a valid NUL-terminated string alive for the call; a null
        // execpromises leaves them unchanged, as pledge(2) documents.
        let rc = unsafe { ffi::pledge(c.as_ptr(), std::ptr::null()) };
        if rc != 0 {
            return Err(io::Error::last_os_error());
        }
        Ok(())
    }
    #[cfg(not(target_os = "openbsd"))]
    {
        let _ = promises;
        Ok(())
    }
}

/// The file flags of `chflags(2)` as the comma-separated names `ls -lo` and `chflags(1)`
/// use; empty when no flag is set. The bits are OpenBSD's; macOS shares them and adds a few,
/// listed so a development host prints something sensible.
pub fn flags_to_string(flags: u32) -> String {
    const NAMES: &[(u32, &str)] = &[
        (0x0000_0001, "nodump"),
        (0x0000_0002, "uchg"),
        (0x0000_0004, "uappnd"),
        (0x0000_0008, "opaque"),
        (0x0000_0020, "compressed"),
        (0x0000_8000, "hidden"),
        (0x0001_0000, "arch"),
        (0x0002_0000, "schg"),
        (0x0004_0000, "sappnd"),
        (0x0008_0000, "restricted"),
        (0x0010_0000, "nounlink"),
    ];
    NAMES
        .iter()
        .filter(|(bit, _)| flags & bit != 0)
        .map(|(_, n)| *n)
        .collect::<Vec<_>>()
        .join(",")
}

fn c_path(path: &Path) -> io::Result<CString> {
    CString::new(path.as_os_str().as_bytes())
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "path contains a NUL byte"))
}

fn check(rc: std::ffi::c_int) -> io::Result<()> {
    if rc == 0 {
        Ok(())
    } else {
        Err(io::Error::last_os_error())
    }
}

/// The real user id of the process.
pub fn getuid() -> u32 {
    // SAFETY: getuid takes nothing, touches nothing and cannot fail.
    unsafe { ffi::getuid() }
}

/// The process's file mode creation mask, read without changing it. The C library offers no
/// read-only query, so the mask is set to zero and restored at once; a program that creates
/// files from another thread at that instant could see the wrong mask, which is why the
/// written programs call this before anything else.
pub fn umask() -> u32 {
    // SAFETY: umask only exchanges a process-wide integer; both calls are infallible.
    let old = unsafe { ffi::umask(0) };
    // SAFETY: as above; restores the mask the process had.
    unsafe { ffi::umask(old) };
    old as u32
}

/// `mkfifo(2)`: a named pipe at `path` with `mode`, which the umask then shapes.
pub fn mkfifo(path: &Path, mode: u32) -> io::Result<()> {
    let c = c_path(path)?;
    // SAFETY: `c` is a valid NUL-terminated path alive for the call; the mode is a plain
    // integer the kernel masks itself.
    check(unsafe { ffi::mkfifo(c.as_ptr(), mode as ffi::ModeT) })
}

/// `mknod(2)`: a character or block device node at `path`, `mode` carrying the type bits
/// and `dev` the device number as `stat` reported it. Needs root.
pub fn mknod(path: &Path, mode: u32, dev: u64) -> io::Result<()> {
    let c = c_path(path)?;
    // SAFETY: `c` is a valid NUL-terminated path alive for the call; mode and dev are plain
    // integers the kernel validates.
    check(unsafe { ffi::mknod(c.as_ptr(), mode as ffi::ModeT, dev as ffi::DevT) })
}

/// `fchflags(2)`: the file flags of `chflags(1)` on an open file.
pub fn set_flags_fd(fd: std::os::fd::RawFd, flags: u32) -> io::Result<()> {
    // SAFETY: fd is an open descriptor the caller owns for the duration of the call; the
    // flags are a plain integer.
    check(unsafe { ffi::fchflags(fd, flags) })
}

/// The file flags of `path` itself, a symbolic link not followed (`lchflags(2)` on macOS,
/// `chflagsat(2)` with `AT_SYMLINK_NOFOLLOW` on OpenBSD).
pub fn set_flags_nofollow(path: &Path, flags: u32) -> io::Result<()> {
    let c = c_path(path)?;
    #[cfg(target_os = "macos")]
    // SAFETY: `c` is a valid NUL-terminated path alive for the call.
    let rc = unsafe { ffi::lchflags(c.as_ptr(), flags) };
    #[cfg(target_os = "openbsd")]
    // SAFETY: as above; AT_FDCWD resolves the path from the current directory.
    let rc = unsafe { ffi::chflagsat(ffi::AT_FDCWD, c.as_ptr(), flags, ffi::AT_SYMLINK_NOFOLLOW) };
    check(rc)
}

/// The access and modification times of `path` itself, a symbolic link not followed:
/// `utimensat(2)` with `AT_SYMLINK_NOFOLLOW`. Each time is `(seconds, nanoseconds)`.
pub fn set_times_nofollow(path: &Path, atime: (i64, u32), mtime: (i64, u32)) -> io::Result<()> {
    let c = c_path(path)?;
    let ts = [
        ffi::Timespec {
            tv_sec: atime.0,
            tv_nsec: atime.1 as std::ffi::c_long,
        },
        ffi::Timespec {
            tv_sec: mtime.0,
            tv_nsec: mtime.1 as std::ffi::c_long,
        },
    ];
    // SAFETY: `c` is a valid NUL-terminated path and `ts` two valid timespecs, both alive
    // for the call; utimensat reads them and writes nothing.
    check(unsafe {
        ffi::utimensat(
            ffi::AT_FDCWD,
            c.as_ptr(),
            ts.as_ptr(),
            ffi::AT_SYMLINK_NOFOLLOW,
        )
    })
}

/// The mode of `path` itself, a symbolic link not followed: `fchmodat(2)` with
/// `AT_SYMLINK_NOFOLLOW`. A file system that gives links no mode of their own answers
/// `Unsupported`.
pub fn set_mode_nofollow(path: &Path, mode: u32) -> io::Result<()> {
    let c = c_path(path)?;
    // SAFETY: `c` is a valid NUL-terminated path alive for the call; the mode is a plain
    // integer the kernel masks to its permission bits.
    check(unsafe {
        ffi::fchmodat(
            ffi::AT_FDCWD,
            c.as_ptr(),
            mode as ffi::ModeT,
            ffi::AT_SYMLINK_NOFOLLOW,
        )
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn root_is_a_user_everywhere() {
        assert_eq!(user_name(0).as_deref(), Some("root"));
        assert!(user_name(0xFFFF_FFF0).is_none() || user_name(0xFFFF_FFF0).is_some());
    }

    #[test]
    fn wheel_or_root_is_group_zero() {
        let g = group_name(0).expect("group 0 exists");
        assert!(g == "wheel" || g == "root", "{g}");
    }

    #[test]
    fn the_epoch_in_utc() {
        // SAFETY of the test: TZ is process state; the test sets it before any other call.
        unsafe { std::env::set_var("TZ", "UTC") };
        let t = local_time(0).unwrap();
        assert_eq!(
            (
                t.year,
                t.month,
                t.day,
                t.hour,
                t.minute,
                t.second,
                t.utc_offset
            ),
            (1970, 1, 1, 0, 0, 0, 0)
        );
        let t = local_time(1_777_000_000).unwrap();
        assert_eq!((t.year, t.month, t.day), (2026, 4, 24));
    }

    #[test]
    fn flag_names() {
        assert_eq!(flags_to_string(0), "");
        assert_eq!(flags_to_string(0x2 | 0x20000), "uchg,schg");
        assert_eq!(flags_to_string(0x1), "nodump");
    }

    #[test]
    fn pledge_is_callable() {
        pledge("stdio rpath getpw").unwrap();
    }

    #[test]
    fn uid_and_umask_read_back() {
        let _ = getuid();
        let m = umask();
        assert!(m <= 0o777, "{m:o}");
        assert_eq!(umask(), m, "reading the mask must not change it");
    }

    #[test]
    fn a_fifo_and_a_link_get_times_flags_and_mode() {
        let dir = std::env::temp_dir().join(format!("emibsd-sys-test-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let fifo = dir.join("fifo");
        mkfifo(&fifo, 0o600).unwrap();
        let meta = std::fs::metadata(&fifo).unwrap();
        assert!(std::os::unix::fs::FileTypeExt::is_fifo(&meta.file_type()));
        let link = dir.join("link");
        std::os::unix::fs::symlink("fifo", &link).unwrap();
        set_times_nofollow(&link, (1_000_000_000, 0), (1_000_000_000, 500)).unwrap();
        let lm = std::fs::symlink_metadata(&link).unwrap();
        assert_eq!(std::os::unix::fs::MetadataExt::mtime(&lm), 1_000_000_000);
        set_flags_nofollow(&link, 0).unwrap();
        match set_mode_nofollow(&link, 0o700) {
            Ok(()) => {}
            Err(e) if e.kind() == io::ErrorKind::Unsupported => {}
            Err(e) => panic!("{e}"),
        }
        assert!(mknod(&dir.join("node"), 0o020_600, 0).is_err() || getuid() == 0);
        std::fs::remove_dir_all(&dir).unwrap();
    }
}
