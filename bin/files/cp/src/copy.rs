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

//! Performing one operation, and saying what happened as a [`Record`].
//!
//! What OpenBSD's `cp` knows and this one keeps, without its shape: a new file gets the
//! source's mode shaped by the umask with the set-id bits dropped (kept only when the owner
//! and group match and `-p` is off); an existing file is written over and keeps its mode and
//! owner; `-f` removes it first; `-i` asks; runs of zero bytes become holes; a directory is
//! created writable for its owner and gets its real mode after its contents; with `-p` the
//! times go first, then the owner (a refusal drops the set-id bits silently), then the mode,
//! then the file flags; a symbolic link is copied as a link, a FIFO and a device node are
//! recreated under `-R`, a socket cannot be copied.

use std::fs::{self, File, FileTimes, OpenOptions};
use std::io::{self, BufRead, Read, Seek, SeekFrom, Write};
use std::os::fd::AsRawFd;
use std::os::unix::fs::{DirBuilderExt, OpenOptionsExt, PermissionsExt, fchown, lchown, symlink};
use std::path::{Path, PathBuf};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use cli::os_error;

use crate::options::{Config, Overwrite};
use crate::walk::{Meta, Op};

/// What happened to one source, `schemas/copy.v1.json`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Action {
    /// The target did not exist and does now.
    Created,
    /// The target existed and holds the source's contents now.
    Replaced,
    /// An existing directory received the tree below the source.
    Merged,
    /// `-i` was answered with anything but `y`.
    Skipped,
    /// `--dry-run`: what would have been done.
    Planned,
    /// Not copied; `error` says why.
    Failed,
}

impl Action {
    pub fn name(self) -> &'static str {
        match self {
            Action::Created => "created",
            Action::Replaced => "replaced",
            Action::Merged => "merged",
            Action::Skipped => "skipped",
            Action::Planned => "planned",
            Action::Failed => "failed",
        }
    }
}

/// One copy, done or not.
#[derive(Debug, Clone)]
pub struct Record {
    pub source: PathBuf,
    pub target: PathBuf,
    /// The source's kind: `file`, `dir`, `symlink`, `fifo`, `char`, `block`, `socket`.
    pub kind: &'static str,
    /// Bytes written, for a file.
    pub size: Option<u64>,
    pub action: Action,
    /// The complete diagnostic, without the program's name, when `Failed`.
    pub error: Option<String>,
}

impl Record {
    fn new(source: &Path, target: &Path, kind: &'static str, action: Action) -> Record {
        Record {
            source: source.to_path_buf(),
            target: target.to_path_buf(),
            kind,
            size: None,
            action,
            error: None,
        }
    }

    fn failed(source: &Path, target: &Path, kind: &'static str, error: String) -> Record {
        Record {
            error: Some(error),
            ..Record::new(source, target, kind, Action::Failed)
        }
    }

    pub fn to_value(&self) -> cli::Value {
        use cli::Value;
        let mut m = vec![
            (
                "source".into(),
                Value::Str(self.source.display().to_string()),
            ),
            (
                "target".into(),
                Value::Str(self.target.display().to_string()),
            ),
            ("type".into(), Value::Str(self.kind.into())),
            ("action".into(), Value::Str(self.action.name().into())),
        ];
        if let Some(n) = self.size {
            m.push(("size".into(), Value::UInt(n)));
        }
        if let Some(e) = &self.error {
            m.push(("error".into(), Value::Str(e.clone())));
        }
        Value::Map(m)
    }
}

const BUF: usize = 64 * 1024;
const SET_ID: u32 = 0o6000;
const STICKY: u32 = 0o1000;

/// Performs operations in order, with the process's identity read once.
pub struct Copier<'a> {
    cfg: &'a Config,
    uid: u32,
    umask: u32,
    buf: Vec<u8>,
}

/// Where `-p` sets the attributes: an open file, or a path not followed (a link).
enum At<'f> {
    Fd(&'f File),
    Link(&'f Path),
}

impl<'a> Copier<'a> {
    pub fn new(cfg: &'a Config) -> Copier<'a> {
        Copier {
            cfg,
            uid: sys::getuid(),
            umask: sys::umask(),
            buf: vec![0; BUF],
        }
    }

    /// Performs `op`. Returns the record it produced, if any, and whether a directory just
    /// entered should be descended into.
    pub fn perform(&mut self, op: Op) -> (Option<Record>, bool) {
        match op {
            Op::Refused {
                source,
                target,
                kind,
                error,
            } => (Some(Record::failed(&source, &target, kind, error)), false),
            Op::Node {
                source,
                target,
                meta,
                existing,
            } => (Some(self.node(&source, &target, &meta, existing)), false),
            Op::EnterDir {
                source,
                target,
                meta,
                existing,
            } => self.enter_dir(&source, &target, &meta, existing),
            Op::LeaveDir {
                source,
                target,
                meta,
                created,
            } => (self.leave_dir(&source, &target, &meta, created), false),
        }
    }

    fn node(
        &mut self,
        source: &Path,
        target: &Path,
        meta: &Meta,
        existing: Option<Meta>,
    ) -> Record {
        if self.cfg.dry_run {
            let mut r = Record::new(source, target, meta.kind, Action::Planned);
            if meta.kind == "file" {
                r.size = Some(meta.size);
            }
            return r;
        }
        let exists = existing.is_some();
        let done = if exists {
            Action::Replaced
        } else {
            Action::Created
        };
        let result = match meta.kind {
            "symlink" => self.copy_link(source, target, meta, exists),
            "fifo" if self.cfg.recursive => self.recreate(target, meta, exists, |t, m| {
                sys::mkfifo(t, m.mode & 0o7777)
                    .map_err(|e| format!("mkfifo: {}: {}", t.display(), os_error(&e)))
            }),
            "char" | "block" if self.cfg.recursive => {
                self.recreate(target, meta, exists, |t, m| {
                    sys::mknod(t, m.mode, m.rdev)
                        .map_err(|e| format!("mknod: {}: {}", t.display(), os_error(&e)))
                })
            }
            "socket" => Err(format!("{}: Operation not supported", source.display())),
            _ => self.copy_file(source, target, meta, exists),
        };
        match result {
            Ok(Some(size)) => Record {
                size,
                ..Record::new(source, target, meta.kind, done)
            },
            Ok(None) => Record::new(source, target, meta.kind, Action::Skipped),
            Err(e) => Record::failed(source, target, meta.kind, e),
        }
    }

    /// `Ok(Some(bytes))` copied, `Ok(None)` skipped by `-i`, `Err` with the diagnostic.
    fn copy_file(
        &mut self,
        source: &Path,
        target: &Path,
        meta: &Meta,
        exists: bool,
    ) -> Result<Option<Option<u64>>, String> {
        let mut from =
            File::open(source).map_err(|e| format!("{}: {}", source.display(), os_error(&e)))?;
        let mut exists = exists;
        if exists {
            match self.cfg.overwrite {
                Overwrite::Ask if !self.ask(target) => return Ok(None),
                Overwrite::Force => {
                    let _ = fs::remove_file(target);
                    exists = false;
                }
                _ => {}
            }
        }
        let to = if exists {
            OpenOptions::new().write(true).truncate(true).open(target)
        } else {
            // The source's mode without the set-id bits, shaped by the umask as open(2) does.
            OpenOptions::new()
                .write(true)
                .create(true)
                .truncate(true)
                .mode(meta.mode & 0o777)
                .open(target)
        }
        .map_err(|e| format!("{}: {}", target.display(), os_error(&e)))?;
        let mut to = to;
        let written = self.transfer(&mut from, &mut to, source, target)?;
        if self.cfg.preserve {
            self.set_attributes(meta, At::Fd(&to), target)?;
        } else if !exists && meta.mode & SET_ID != 0 && meta.uid == self.uid {
            // A set-id file copied by its owner into the same group keeps the bits; the
            // umask shapes them as it shaped the rest.
            let st = to
                .metadata()
                .map_err(|e| format!("{}: {}", target.display(), os_error(&e)))?;
            if std::os::unix::fs::MetadataExt::gid(&st) == meta.gid {
                to.set_permissions(fs::Permissions::from_mode(meta.mode & 0o7777 & !self.umask))
                    .map_err(|e| format!("{}: {}", target.display(), os_error(&e)))?;
            }
        }
        Ok(Some(Some(written)))
    }

    /// Reads `from` into `to`, 64 KB at a time; a block of zeros becomes a hole when the
    /// target is a regular file, and the length is fixed at the end so a trailing hole counts.
    fn transfer(
        &mut self,
        from: &mut File,
        to: &mut File,
        source: &Path,
        target: &Path,
    ) -> Result<u64, String> {
        let holes = to.metadata().map(|m| m.is_file()).unwrap_or(false);
        let mut total: u64 = 0;
        let mut pending_hole = false;
        loop {
            let n = match from.read(&mut self.buf) {
                Ok(0) => break,
                Ok(n) => n,
                Err(e) if e.kind() == io::ErrorKind::Interrupted => continue,
                Err(e) => return Err(format!("{}: {}", source.display(), os_error(&e))),
            };
            let chunk = &self.buf[..n];
            if holes && chunk.iter().all(|&b| b == 0) {
                to.seek(SeekFrom::Current(n as i64))
                    .map_err(|e| format!("{}: {}", target.display(), os_error(&e)))?;
                pending_hole = true;
            } else {
                to.write_all(chunk)
                    .map_err(|e| format!("{}: {}", target.display(), os_error(&e)))?;
                pending_hole = false;
            }
            total += n as u64;
        }
        if pending_hole {
            to.set_len(total)
                .map_err(|e| format!("{}: {}", target.display(), os_error(&e)))?;
        }
        Ok(total)
    }

    fn copy_link(
        &mut self,
        source: &Path,
        target: &Path,
        meta: &Meta,
        exists: bool,
    ) -> Result<Option<Option<u64>>, String> {
        if exists && self.cfg.overwrite == Overwrite::Ask && !self.ask(target) {
            return Ok(None);
        }
        let dest = fs::read_link(source)
            .map_err(|e| format!("readlink: {}: {}", source.display(), os_error(&e)))?;
        if exists {
            fs::remove_file(target)
                .map_err(|e| format!("unlink: {}: {}", target.display(), os_error(&e)))?;
        }
        symlink(&dest, target)
            .map_err(|e| format!("symlink: {}: {}", dest.display(), os_error(&e)))?;
        if self.cfg.preserve {
            self.set_attributes(meta, At::Link(target), target)?;
        }
        Ok(Some(None))
    }

    /// A FIFO or a device node: removed if it exists, made anew by `make`, attributes set.
    fn recreate(
        &mut self,
        target: &Path,
        meta: &Meta,
        exists: bool,
        make: impl Fn(&Path, &Meta) -> Result<(), String>,
    ) -> Result<Option<Option<u64>>, String> {
        if exists && self.cfg.overwrite == Overwrite::Ask && !self.ask(target) {
            return Ok(None);
        }
        if exists {
            fs::remove_file(target)
                .map_err(|e| format!("unlink: {}: {}", target.display(), os_error(&e)))?;
        }
        make(target, meta)?;
        if self.cfg.preserve {
            self.set_attributes(meta, At::Link(target), target)?;
        }
        Ok(Some(None))
    }

    fn enter_dir(
        &mut self,
        source: &Path,
        target: &Path,
        meta: &Meta,
        existing: Option<Meta>,
    ) -> (Option<Record>, bool) {
        if self.cfg.dry_run {
            return (
                Some(Record::new(source, target, "dir", Action::Planned)),
                true,
            );
        }
        if existing.is_some() {
            return (
                Some(Record::new(source, target, "dir", Action::Merged)),
                true,
            );
        }
        // Writable for its owner while it is filled, whatever the source's mode; the real
        // mode is set on the way out, unshaped by the umask.
        match fs::DirBuilder::new()
            .mode(meta.mode & 0o7777 | 0o700)
            .create(target)
        {
            Ok(()) => (
                Some(Record::new(source, target, "dir", Action::Created)),
                true,
            ),
            Err(e) => (
                Some(Record::failed(
                    source,
                    target,
                    "dir",
                    format!("{}: {}", target.display(), os_error(&e)),
                )),
                false,
            ),
        }
    }

    fn leave_dir(
        &mut self,
        source: &Path,
        target: &Path,
        meta: &Meta,
        created: bool,
    ) -> Option<Record> {
        if self.cfg.dry_run {
            return None;
        }
        let result = if self.cfg.preserve {
            File::open(target)
                .map_err(|e| format!("{}: {}", target.display(), os_error(&e)))
                .and_then(|dir| self.set_attributes(meta, At::Fd(&dir), target))
        } else if created {
            fs::set_permissions(target, fs::Permissions::from_mode(meta.mode & 0o7777))
                .map_err(|e| format!("chmod: {}: {}", target.display(), os_error(&e)))
        } else {
            Ok(())
        };
        result
            .err()
            .map(|e| Record::failed(source, target, "dir", e))
    }

    /// `-p`: times, owner and group, mode, file flags, in that order, as permissions allow.
    fn set_attributes(&self, meta: &Meta, at: At<'_>, target: &Path) -> Result<(), String> {
        let mut mode = meta.mode & 0o7777;
        let times = FileTimes::new()
            .set_accessed(timestamp(meta.atime))
            .set_modified(timestamp(meta.mtime));
        let r = match at {
            At::Fd(f) => f.set_times(times),
            At::Link(p) => sys::set_times_nofollow(p, meta.atime, meta.mtime),
        };
        r.map_err(|e| format!("update times: {}: {}", target.display(), os_error(&e)))?;
        // Owner before mode: a chown clears the set-id bits on the BSDs, and a refusal
        // (not root) drops them from the copy without a word, as cp(1) documents.
        let r = match at {
            At::Fd(f) => fchown(f, Some(meta.uid), Some(meta.gid)),
            At::Link(p) => lchown(p, Some(meta.uid), Some(meta.gid)),
        };
        if let Err(e) = r {
            if e.kind() != io::ErrorKind::PermissionDenied {
                return Err(format!("chown: {}: {}", target.display(), os_error(&e)));
            }
            mode &= !(SET_ID | STICKY);
        }
        let r = match at {
            At::Fd(f) => f.set_permissions(fs::Permissions::from_mode(mode)),
            At::Link(p) => match sys::set_mode_nofollow(p, mode) {
                // A link has no mode of its own on some file systems; nothing to keep.
                Err(e) if e.kind() == io::ErrorKind::Unsupported => Ok(()),
                r => r,
            },
        };
        r.map_err(|e| format!("chmod: {}: {}", target.display(), os_error(&e)))?;
        let r = match at {
            At::Fd(f) => sys::set_flags_fd(f.as_raw_fd(), meta.flags),
            At::Link(p) => sys::set_flags_nofollow(p, meta.flags),
        };
        // A file system without flags (NFS) refuses; that loses nothing when there were none.
        if let Err(e) = r
            && !(e.kind() == io::ErrorKind::Unsupported && meta.flags == 0)
        {
            return Err(format!("chflags: {}: {}", target.display(), os_error(&e)));
        }
        Ok(())
    }

    /// `-i`: `overwrite target? ` on standard error; `y` or `Y` first means yes.
    fn ask(&self, target: &Path) -> bool {
        eprint!("overwrite {}? ", target.display());
        let _ = io::stderr().flush();
        let mut line = String::new();
        if io::stdin().lock().read_line(&mut line).is_err() {
            return false;
        }
        matches!(line.chars().next(), Some('y' | 'Y'))
    }
}

fn timestamp((secs, nanos): (i64, u32)) -> SystemTime {
    if secs >= 0 {
        UNIX_EPOCH + Duration::new(secs as u64, nanos)
    } else {
        UNIX_EPOCH - Duration::new(secs.unsigned_abs(), 0) + Duration::from_nanos(nanos as u64)
    }
}
