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

//! Walking the sources into operations, in the order the copier must perform them.
//!
//! The target operand decides the shape: an existing directory receives one tree per
//! source under its own name (`cp a b dir`); anything else is the copy itself (`cp a b`,
//! `cp -R dir newdir`). Each source is examined (following a symbolic link only when the
//! configuration says so), paired with its target, and the pair becomes an [`Op`]: a node
//! to copy, a directory to enter and later to leave (its mode and times are set on the way
//! out, after its contents, as `fts(3)`'s post-order visit let OpenBSD's `cp` do), or a
//! refusal with its reason. Refusals are records too: the rest is copied and the exit status
//! says so. A cycle under `-L` is detected by `(dev, ino)` of the directories being entered.

use std::collections::HashSet;
use std::fs::{self, Metadata};
use std::os::unix::fs::{FileTypeExt, MetadataExt};
use std::path::{Path, PathBuf};

use cli::os_error;

use crate::options::Config;

/// What `stat` said about a file, as the copier needs it.
#[derive(Debug, Clone, Copy)]
pub struct Meta {
    /// `file`, `dir`, `symlink`, `fifo`, `socket`, `char`, `block`.
    pub kind: &'static str,
    pub mode: u32,
    pub uid: u32,
    pub gid: u32,
    pub size: u64,
    pub rdev: u64,
    pub ino: u64,
    pub dev: u64,
    pub flags: u32,
    pub atime: (i64, u32),
    pub mtime: (i64, u32),
}

impl Meta {
    pub fn from_std(m: &Metadata) -> Meta {
        let ft = m.file_type();
        let kind = if ft.is_dir() {
            "dir"
        } else if ft.is_symlink() {
            "symlink"
        } else if ft.is_file() {
            "file"
        } else if ft.is_fifo() {
            "fifo"
        } else if ft.is_socket() {
            "socket"
        } else if ft.is_char_device() {
            "char"
        } else if ft.is_block_device() {
            "block"
        } else {
            "unknown"
        };
        Meta {
            kind,
            mode: m.mode(),
            uid: m.uid(),
            gid: m.gid(),
            size: m.size(),
            rdev: m.rdev(),
            ino: m.ino(),
            dev: m.dev(),
            flags: file_flags(m),
            atime: (m.atime(), m.atime_nsec() as u32),
            mtime: (m.mtime(), m.mtime_nsec() as u32),
        }
    }

    pub fn is_dir(&self) -> bool {
        self.kind == "dir"
    }

    fn same_file(&self, other: &Meta) -> bool {
        self.dev == other.dev && self.ino == other.ino
    }
}

#[cfg(test)]
mod tests {
    use super::under;
    use std::path::Path;

    #[test]
    fn the_last_component_is_read_as_openbsd_reads_it() {
        let d = Path::new("dst");
        assert_eq!(under(d, "src"), Path::new("dst/src"));
        assert_eq!(under(d, "a/b/src/"), Path::new("dst/src"));
        assert_eq!(under(d, "src/."), Path::new("dst"));
        assert_eq!(under(d, "src/./"), Path::new("dst"));
        assert_eq!(under(d, "src/sub/.."), Path::new("dst"));
        assert_eq!(under(d, "."), Path::new("dst"));
        assert_eq!(under(d, "/"), Path::new("dst"));
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

/// One step of the copy.
#[derive(Debug)]
pub enum Op {
    /// A file, link, FIFO, device or socket to copy over `existing`, if there is one.
    Node {
        source: PathBuf,
        target: PathBuf,
        meta: Meta,
        existing: Option<Meta>,
    },
    /// A directory whose contents follow; created unless `existing`.
    EnterDir {
        source: PathBuf,
        target: PathBuf,
        meta: Meta,
        existing: Option<Meta>,
    },
    /// The same directory, after its contents: time to give it its mode and times.
    LeaveDir {
        source: PathBuf,
        target: PathBuf,
        meta: Meta,
        created: bool,
    },
    /// Something that is not copied, and why.
    Refused {
        source: PathBuf,
        target: PathBuf,
        kind: &'static str,
        error: String,
    },
}

/// Which of the two forms of the command line this is.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Shape {
    /// `cp source target`: the target is the copy.
    ToTarget,
    /// `cp source ... directory`: each source goes under the directory by its own name.
    IntoDirectory,
}

/// How a failure to classify the target is reported.
pub enum ShapeError {
    /// Several sources and a target that is not a directory: the command line is wrong.
    Usage(String),
    /// The target could not be examined.
    Io(String),
}

fn stat(path: &Path, follow: bool) -> std::io::Result<Meta> {
    let m = if follow {
        fs::metadata(path)
    } else {
        fs::symlink_metadata(path)
    }?;
    Ok(Meta::from_std(&m))
}

/// `stat` of a source, following a link when asked and falling back to the link itself when
/// it dangles (so a broken link is copied as a link, as OpenBSD's `cp` does).
fn stat_source(path: &Path, follow: bool) -> std::io::Result<Meta> {
    match stat(path, follow) {
        Ok(m) => Ok(m),
        Err(e) if follow => stat(path, false).map_err(|_| e),
        Err(e) => Err(e),
    }
}

/// Decides the shape from the target operand.
pub fn shape(cfg: &Config) -> Result<Shape, ShapeError> {
    let target = Path::new(&cfg.target);
    match fs::metadata(target) {
        Ok(m) if m.is_dir() => Ok(Shape::IntoDirectory),
        Ok(_) => {
            if cfg.sources.len() > 1 {
                Err(ShapeError::Usage(format!(
                    "{}: not a directory",
                    cfg.target
                )))
            } else {
                Ok(Shape::ToTarget)
            }
        }
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
            if cfg.sources.len() > 1 {
                Err(ShapeError::Usage(format!(
                    "{}: {}",
                    cfg.target,
                    os_error(&e)
                )))
            } else {
                Ok(Shape::ToTarget)
            }
        }
        Err(e) => Err(ShapeError::Io(format!("{}: {}", cfg.target, os_error(&e)))),
    }
}

/// The target of a source under the directory form: the directory plus the source's last
/// component, read from the text as OpenBSD's `cp` does (never through `Path::file_name`,
/// which drops a trailing `.`). A source whose last component is `.` or `..` (`src/.`,
/// `src/./`, `..`) goes to the directory itself, so `cp -R src/. dir` fills `dir`.
fn under(dir: &Path, source: &str) -> PathBuf {
    let trimmed = source.trim_end_matches('/');
    let last = trimmed.rsplit('/').next().unwrap_or(trimmed);
    match last {
        "" | "." | ".." => dir.to_path_buf(),
        name => dir.join(name),
    }
}

/// Walks every source and hands each operation to `sink`, which says whether to go on
/// below a directory it was asked to enter.
pub fn walk(cfg: &Config, shape: Shape, sink: &mut dyn FnMut(Op) -> bool) {
    let target = Path::new(&cfg.target);
    let mut entered: HashSet<(u64, u64)> = HashSet::new();
    for s in &cfg.sources {
        let source = Path::new(s);
        let dst = match shape {
            Shape::ToTarget => target.to_path_buf(),
            Shape::IntoDirectory => under(target, s),
        };
        match stat_source(source, cfg.follow_operand()) {
            Ok(meta) => visit(cfg, source.to_path_buf(), dst, meta, &mut entered, sink),
            Err(e) => {
                sink(Op::Refused {
                    source: source.to_path_buf(),
                    target: dst,
                    kind: "unknown",
                    error: format!("{s}: {}", os_error(&e)),
                });
            }
        }
    }
}

fn visit(
    cfg: &Config,
    source: PathBuf,
    target: PathBuf,
    meta: Meta,
    entered: &mut HashSet<(u64, u64)>,
    sink: &mut dyn FnMut(Op) -> bool,
) {
    let existing = stat(&target, true).ok();
    if let Some(t) = &existing {
        if t.same_file(&meta) {
            sink(Op::Refused {
                error: format!(
                    "{} and {} are identical (not copied).",
                    target.display(),
                    source.display()
                ),
                source,
                target,
                kind: meta.kind,
            });
            return;
        }
        if !meta.is_dir() && t.is_dir() {
            sink(Op::Refused {
                error: format!(
                    "cannot overwrite directory {} with non-directory {}",
                    target.display(),
                    source.display()
                ),
                source,
                target,
                kind: meta.kind,
            });
            return;
        }
    }
    if !meta.is_dir() {
        sink(Op::Node {
            source,
            target,
            meta,
            existing,
        });
        return;
    }
    if !cfg.recursive {
        sink(Op::Refused {
            error: format!("{} is a directory (not copied).", source.display()),
            source,
            target,
            kind: "dir",
        });
        return;
    }
    if existing.is_some_and(|t| !t.is_dir()) {
        sink(Op::Refused {
            error: format!("{}: Not a directory", target.display()),
            source,
            target,
            kind: "dir",
        });
        return;
    }
    if !entered.insert((meta.dev, meta.ino)) {
        sink(Op::Refused {
            error: format!("{}: directory causes a cycle", source.display()),
            source,
            target,
            kind: "dir",
        });
        return;
    }
    let created = existing.is_none();
    let descend = sink(Op::EnterDir {
        source: source.clone(),
        target: target.clone(),
        meta,
        existing,
    });
    if descend {
        match fs::read_dir(&source) {
            Ok(rd) => {
                let mut names: Vec<_> = rd.filter_map(|e| e.ok().map(|e| e.file_name())).collect();
                names.sort();
                for name in names {
                    let child = source.join(&name);
                    let child_target = target.join(&name);
                    match stat_source(&child, cfg.follow_below()) {
                        Ok(m) => visit(cfg, child, child_target, m, entered, sink),
                        Err(e) => {
                            sink(Op::Refused {
                                error: format!("{}: {}", child.display(), os_error(&e)),
                                source: child,
                                target: child_target,
                                kind: "unknown",
                            });
                        }
                    }
                }
            }
            Err(e) => {
                sink(Op::Refused {
                    error: format!("{}: {}", source.display(), os_error(&e)),
                    source: source.clone(),
                    target: target.clone(),
                    kind: "dir",
                });
            }
        }
        sink(Op::LeaveDir {
            source,
            target,
            meta,
            created,
        });
    }
    entered.remove(&(meta.dev, meta.ino));
}
