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

//! Walking the operands into listings.
//!
//! The operands that are not directories form the first listing; each directory operand,
//! and with `-R` each directory below it, forms one more, in sorted order. `stat` is called
//! only when something needs it: with none of `-l`, `-i`, `-s`, `-F`, `-p`, a sort other
//! than by name or a machine format, a directory is listed from its entries alone, which is
//! what keeps `ls` of a hundred thousand files cheap. Errors are entries too: a listing with
//! an unreadable operand still prints the rest, and the exit status says so.

use std::collections::HashSet;
use std::fs;
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::entry::{Entry, Meta};
use crate::mode;
use crate::options::{Config, Follow, Hidden, Sort, TypeFilter};

/// One group of entries printed together.
pub struct Listing {
    /// The directory's path, or `None` for the operands that are not directories.
    pub dir: Option<String>,
    /// An error listing the directory itself.
    pub error: Option<String>,
    pub entries: Vec<Entry>,
    /// Entries that failed are kept, with their error, so the caller can print them.
    pub failed: Vec<Entry>,
}

impl Listing {
    pub fn had_errors(&self) -> bool {
        self.error.is_some() || !self.failed.is_empty()
    }
}

fn now() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

fn kind_hint(ft: &fs::FileType) -> &'static str {
    use std::os::unix::fs::FileTypeExt;
    if ft.is_dir() {
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
    }
}

fn stat(path: &str, follow: bool) -> Result<Meta, String> {
    let r = if follow {
        fs::metadata(path)
    } else {
        fs::symlink_metadata(path)
    };
    r.map(|m| Meta::from_std(&m)).map_err(|e| os_error(&e))
}

fn os_error(e: &std::io::Error) -> String {
    // The text of strerror(3), without the "(os error N)" std appends.
    let s = e.to_string();
    match s.find(" (os error") {
        Some(i) => s[..i].to_string(),
        None => s,
    }
}

fn type_matches(e: &Entry, types: &[TypeFilter]) -> bool {
    if types.is_empty() {
        return true;
    }
    let k = e.kind();
    types.iter().any(|t| match t {
        TypeFilter::File => k == "file",
        TypeFilter::Dir => k == "dir",
        TypeFilter::Symlink => k == "symlink",
        TypeFilter::Fifo => k == "fifo",
        TypeFilter::Socket => k == "socket",
        TypeFilter::Char => k == "char",
        TypeFilter::Block => k == "block",
    })
}

fn since_matches(e: &Entry, since: Option<u64>, now: i64) -> bool {
    match (since, &e.meta) {
        (None, _) => true,
        (Some(s), Some(m)) => m.mtime.0 >= now - s as i64,
        (Some(_), None) => false,
    }
}

/// Sorts entries as the configuration asks; errors keep their place at the end.
fn sort_entries(entries: &mut [Entry], cfg: &Config) {
    let key_time = |m: Meta| match cfg.time {
        crate::options::TimeField::Modified => m.mtime,
        crate::options::TimeField::Accessed => m.atime,
        crate::options::TimeField::Changed => m.ctime,
    };
    match &cfg.sort {
        Sort::Name => entries.sort_by(|a, b| a.name.as_bytes().cmp(b.name.as_bytes())),
        Sort::Size => entries.sort_by(|a, b| {
            let sa = a.meta.map(|m| m.size).unwrap_or(0);
            let sb = b.meta.map(|m| m.size).unwrap_or(0);
            sb.cmp(&sa)
                .then_with(|| a.name.as_bytes().cmp(b.name.as_bytes()))
        }),
        Sort::Time => entries.sort_by(|a, b| {
            let ta = a.meta.map(key_time).unwrap_or((0, 0));
            let tb = b.meta.map(key_time).unwrap_or((0, 0));
            tb.cmp(&ta)
                .then_with(|| a.name.as_bytes().cmp(b.name.as_bytes()))
        }),
        Sort::Field(field) => {
            let numeric = cfg.long.map(|l| l.numeric_ids).unwrap_or(false);
            let mut keyed: Vec<(cli::Value, Entry)> = entries
                .iter()
                .cloned()
                .map(|e| (e.to_value(numeric), e))
                .collect();
            keyed.sort_by(|(va, ea), (vb, eb)| {
                let o = match (va.get(field), vb.get(field)) {
                    (Some(x), Some(y)) => x.sort_cmp(y),
                    (Some(_), None) => std::cmp::Ordering::Less,
                    (None, Some(_)) => std::cmp::Ordering::Greater,
                    (None, None) => std::cmp::Ordering::Equal,
                };
                o.then_with(|| ea.name.as_bytes().cmp(eb.name.as_bytes()))
            });
            for (slot, (_, e)) in entries.iter_mut().zip(keyed) {
                *slot = e;
            }
        }
    }
    if cfg.reverse {
        entries.reverse();
    }
}

/// Reads one directory into entries, applying the hidden-file and type filters.
fn read_dir(
    dir: &str,
    cfg: &Config,
    need_stat: bool,
    now: i64,
) -> Result<(Vec<Entry>, Vec<Entry>), String> {
    let rd = fs::read_dir(dir).map_err(|e| os_error(&e))?;
    let mut entries = Vec::new();
    let mut failed = Vec::new();
    let join = |name: &str| {
        if dir == "/" {
            format!("/{name}")
        } else {
            format!("{dir}/{name}")
        }
    };
    if cfg.hidden == Hidden::All {
        for (name, path) in [(".", dir.to_string()), ("..", join(".."))] {
            let mut e = Entry {
                name: name.into(),
                path,
                dir: dir.into(),
                kind_hint: Some("dir"),
                meta: None,
                error: None,
                target: None,
            };
            if need_stat {
                match stat(&e.path, true) {
                    Ok(m) => e.meta = Some(m),
                    Err(err) => e.error = Some(err),
                }
            }
            entries.push(e);
        }
    }
    for item in rd {
        let item = match item {
            Ok(i) => i,
            Err(e) => {
                failed.push(Entry {
                    name: dir.into(),
                    path: dir.into(),
                    dir: dir.into(),
                    kind_hint: None,
                    meta: None,
                    error: Some(os_error(&e)),
                    target: None,
                });
                continue;
            }
        };
        let name = item.file_name().to_string_lossy().into_owned();
        if name.starts_with('.') && cfg.hidden == Hidden::None {
            continue;
        }
        let path = join(&name);
        let hint = item.file_type().ok().map(|ft| kind_hint(&ft));
        let mut e = Entry {
            name,
            path,
            dir: dir.into(),
            kind_hint: hint,
            meta: None,
            error: None,
            target: None,
        };
        if need_stat {
            let follow = cfg.follow == Follow::Always;
            match stat(&e.path, follow) {
                Ok(m) => e.meta = Some(m),
                Err(err) => {
                    // A dangling link under -L: show the link itself, as ls does.
                    match stat(&e.path, false) {
                        Ok(m) if follow => e.meta = Some(m),
                        _ => e.error = Some(err),
                    }
                }
            }
            e.read_target();
        }
        if e.error.is_some() {
            failed.push(e);
        } else if type_matches(&e, &cfg.types) && since_matches(&e, cfg.since_seconds, now) {
            entries.push(e);
        }
    }
    Ok((entries, failed))
}

/// Walks the operands and hands every listing to `sink`, in the order `ls` prints them.
pub fn walk(cfg: &Config, sink: &mut dyn FnMut(Listing)) {
    let now = now();
    let need_stat = cfg.needs_stat();
    let operands: Vec<String> = if cfg.operands.is_empty() {
        vec![".".into()]
    } else {
        cfg.operands.clone()
    };
    let mut files = Vec::new();
    let mut failed = Vec::new();
    let mut dirs: Vec<Entry> = Vec::new();
    for op in &operands {
        let follow = cfg.follow != Follow::Never;
        let mut e = Entry {
            name: op.clone(),
            path: op.clone(),
            dir: String::new(),
            kind_hint: None,
            meta: None,
            error: None,
            target: None,
        };
        match stat(op, follow) {
            Ok(m) => e.meta = Some(m),
            Err(err) => match stat(op, false) {
                Ok(m) if follow => e.meta = Some(m), // a dangling link: the link itself
                _ => e.error = Some(err),
            },
        }
        e.read_target();
        if e.error.is_some() {
            failed.push(e);
        } else if e.meta.map(|m| m.is_dir()).unwrap_or(false) && !cfg.directory {
            dirs.push(e);
        } else if type_matches(&e, &cfg.types) && since_matches(&e, cfg.since_seconds, now) {
            files.push(e);
        }
    }
    sort_entries(&mut files, cfg);
    sort_entries(&mut dirs, cfg);
    failed.sort_by(|a, b| a.name.cmp(&b.name));
    if !files.is_empty() || !failed.is_empty() {
        sink(Listing {
            dir: None,
            error: None,
            entries: files,
            failed,
        });
    }
    let mut seen: HashSet<(u64, u64)> = HashSet::new();
    for d in dirs {
        if let Some(m) = d.meta {
            seen.insert((m.dev, m.ino));
        }
        descend(&d.path, 0, cfg, need_stat, now, &mut seen, sink);
    }
}

fn descend(
    dir: &str,
    depth: usize,
    cfg: &Config,
    need_stat: bool,
    now: i64,
    seen: &mut HashSet<(u64, u64)>,
    sink: &mut dyn FnMut(Listing),
) {
    let recurse_stat = need_stat || cfg.recursive;
    let (mut entries, failed) = match read_dir(dir, cfg, recurse_stat, now) {
        Ok(x) => x,
        Err(e) => {
            sink(Listing {
                dir: Some(dir.into()),
                error: Some(e),
                entries: Vec::new(),
                failed: Vec::new(),
            });
            return;
        }
    };
    sort_entries(&mut entries, cfg);
    let subdirs: Vec<(String, Option<(u64, u64)>)> =
        if cfg.recursive && cfg.max_depth.map(|d| depth < d).unwrap_or(true) {
            entries
                .iter()
                .filter(|e| e.name != "." && e.name != "..")
                .filter(|e| match e.meta {
                    Some(m) => {
                        m.is_dir()
                            && (cfg.follow == Follow::Always
                                || !e.kind_hint.map(|k| k == "symlink").unwrap_or(false))
                    }
                    None => e.kind_hint == Some("dir"),
                })
                .map(|e| (e.path.clone(), e.meta.map(|m| (m.dev, m.ino))))
                .collect()
        } else {
            Vec::new()
        };
    sink(Listing {
        dir: Some(dir.into()),
        error: None,
        entries,
        failed,
    });
    for (sub, id) in subdirs {
        if let Some(id) = id {
            if !seen.insert(id) {
                sink(Listing {
                    dir: Some(sub.clone()),
                    error: Some("directory causes a cycle".into()),
                    entries: Vec::new(),
                    failed: Vec::new(),
                });
                continue;
            }
        }
        descend(&sub, depth + 1, cfg, need_stat, now, seen, sink);
    }
}

/// Whether `path` names a directory operand (for the header rule: a lone directory operand
/// prints no `dir:` line).
pub fn is_dir(path: &str) -> bool {
    fs::metadata(Path::new(path))
        .map(|m| m.mode() & mode::S_IFMT == mode::S_IFDIR)
        .unwrap_or(false)
}

use std::os::unix::fs::MetadataExt;
