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

//! The record: one file as `schemas/entry.v1.json` describes it.

use std::fs::Metadata;
use std::os::unix::fs::MetadataExt;
use std::path::Path;

use cli::Value;

use crate::mode;
use crate::time;

/// What `stat` said about a file.
#[derive(Debug, Clone, Copy)]
pub struct Meta {
    pub mode: u32,
    pub nlink: u64,
    pub uid: u32,
    pub gid: u32,
    pub size: u64,
    pub blocks: u64,
    pub rdev: u64,
    pub ino: u64,
    pub dev: u64,
    pub flags: u32,
    pub atime: (i64, u32),
    pub mtime: (i64, u32),
    pub ctime: (i64, u32),
}

impl Meta {
    pub fn from_std(m: &Metadata) -> Meta {
        Meta {
            mode: m.mode(),
            nlink: m.nlink(),
            uid: m.uid(),
            gid: m.gid(),
            size: m.size(),
            blocks: m.blocks(),
            rdev: m.rdev(),
            ino: m.ino(),
            dev: m.dev(),
            flags: file_flags(m),
            atime: (m.atime(), m.atime_nsec() as u32),
            mtime: (m.mtime(), m.mtime_nsec() as u32),
            ctime: (m.ctime(), m.ctime_nsec() as u32),
        }
    }

    pub fn is_dir(&self) -> bool {
        self.mode & mode::S_IFMT == mode::S_IFDIR
    }

    pub fn is_symlink(&self) -> bool {
        self.mode & mode::S_IFMT == mode::S_IFLNK
    }

    pub fn is_device(&self) -> bool {
        matches!(self.mode & mode::S_IFMT, mode::S_IFCHR | mode::S_IFBLK)
    }

    /// The device number split as the BSDs encode it: major in bits 8..16, minor in the
    /// low byte and bits 16..32.
    pub fn major_minor(&self) -> (u32, u32) {
        let r = self.rdev as u32;
        ((r >> 8) & 0xff, (r & 0xff) | ((r >> 8) & 0xffff_ff00))
    }
}

#[cfg(target_os = "macos")]
fn file_flags(m: &Metadata) -> u32 {
    use std::os::macos::fs::MetadataExt as _;
    m.st_flags()
}

#[cfg(target_os = "openbsd")]
fn file_flags(m: &Metadata) -> u32 {
    use std::os::openbsd::fs::MetadataExt as _;
    m.st_flags()
}

#[cfg(not(any(target_os = "macos", target_os = "openbsd")))]
fn file_flags(_m: &Metadata) -> u32 {
    0
}

/// One file of a listing.
#[derive(Debug, Clone)]
pub struct Entry {
    /// The name as shown: the operand as given, or the directory entry's name.
    pub name: String,
    /// The path used to reach it.
    pub path: String,
    /// The directory it was listed in, empty for an operand.
    pub dir: String,
    /// The kind from the directory entry when `stat` was not needed.
    pub kind_hint: Option<&'static str>,
    pub meta: Option<Meta>,
    /// Why there is no `meta`.
    pub error: Option<String>,
    /// A symbolic link's target.
    pub target: Option<String>,
}

impl Entry {
    pub fn kind(&self) -> &'static str {
        match &self.meta {
            Some(m) => mode::kind_name(m.mode),
            None => self.kind_hint.unwrap_or("unknown"),
        }
    }

    /// Reads the link target, for a symlink that has not been read yet.
    pub fn read_target(&mut self) {
        if self.target.is_none() && self.meta.map(|m| m.is_symlink()).unwrap_or(false) {
            self.target = std::fs::read_link(Path::new(&self.path))
                .ok()
                .map(|p| p.to_string_lossy().into_owned());
        }
    }

    /// The record, `schemas/entry.v1.json`. `numeric_ids` leaves owner and group as numbers.
    pub fn to_value(&self, numeric_ids: bool) -> Value {
        let mut m: Vec<(String, Value)> = vec![
            ("name".into(), Value::Str(self.name.clone())),
            ("path".into(), Value::Str(self.path.clone())),
            ("dir".into(), Value::Str(self.dir.clone())),
            ("type".into(), Value::Str(self.kind().into())),
        ];
        match &self.meta {
            Some(s) => {
                let owner = if numeric_ids {
                    None
                } else {
                    sys::user_name(s.uid)
                };
                let group = if numeric_ids {
                    None
                } else {
                    sys::group_name(s.gid)
                };
                m.extend([
                    ("mode".into(), Value::Str(mode::strmode(s.mode))),
                    (
                        "perm".into(),
                        Value::Str(format!("{:04o}", s.mode & 0o7777)),
                    ),
                    ("nlink".into(), Value::UInt(s.nlink)),
                    ("uid".into(), Value::UInt(s.uid as u64)),
                    (
                        "owner".into(),
                        owner
                            .map(Value::Str)
                            .unwrap_or(Value::Str(s.uid.to_string())),
                    ),
                    ("gid".into(), Value::UInt(s.gid as u64)),
                    (
                        "group".into(),
                        group
                            .map(Value::Str)
                            .unwrap_or(Value::Str(s.gid.to_string())),
                    ),
                    ("size".into(), Value::UInt(s.size)),
                    ("blocks".into(), Value::UInt(s.blocks)),
                    ("flags".into(), Value::Str(sys::flags_to_string(s.flags))),
                    ("inode".into(), Value::UInt(s.ino)),
                    (
                        "atime".into(),
                        Value::Str(time::rfc3339(s.atime.0, s.atime.1)),
                    ),
                    (
                        "mtime".into(),
                        Value::Str(time::rfc3339(s.mtime.0, s.mtime.1)),
                    ),
                    (
                        "ctime".into(),
                        Value::Str(time::rfc3339(s.ctime.0, s.ctime.1)),
                    ),
                ]);
                if s.is_device() {
                    let (maj, min) = s.major_minor();
                    m.push(("major".into(), Value::UInt(maj as u64)));
                    m.push(("minor".into(), Value::UInt(min as u64)));
                }
                if s.is_symlink() {
                    m.push((
                        "target".into(),
                        self.target.clone().map(Value::Str).unwrap_or(Value::Null),
                    ));
                }
            }
            None => {
                m.push((
                    "error".into(),
                    self.error.clone().map(Value::Str).unwrap_or(Value::Null),
                ));
            }
        }
        Value::Map(m)
    }
}
