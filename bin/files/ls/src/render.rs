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

//! The renderers: names (one per line or in a grid), the long table (POSIX's shape to a
//! pipe, the modern one to a terminal), and the machine formats through `cli`.

use std::io::{self, Write};
use std::time::{SystemTime, UNIX_EPOCH};

use cli::text::{human_size, sanitize};
use cli::{Column, Output, Table, Value};

use crate::entry::Entry;
use crate::mode;
use crate::options::Config;
use crate::time;
use crate::walk::Listing;

pub struct Renderer<'a> {
    cfg: &'a Config,
    out: &'a mut dyn Write,
    /// Something was printed already: the next directory gets a blank line before its name.
    printed: bool,
    /// Directory names are printed when there is more than one listing to tell apart.
    name_dirs: bool,
    /// The machine formats collect every record and print once.
    records: Vec<Value>,
    now: i64,
}

impl<'a> Renderer<'a> {
    pub fn new(cfg: &'a Config, out: &'a mut dyn Write) -> Renderer<'a> {
        let dir_operands = cfg
            .operands
            .iter()
            .filter(|o| crate::walk::is_dir(o))
            .count();
        let name_dirs = cfg.recursive
            || cfg.operands.len() > 1
            || (dir_operands > 0 && cfg.operands.len() > dir_operands);
        Renderer {
            cfg,
            out,
            printed: false,
            name_dirs,
            records: Vec::new(),
            now: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map(|d| d.as_secs() as i64)
                .unwrap_or(0),
        }
    }

    fn machine(&self) -> bool {
        matches!(
            self.cfg.output,
            Output::Json | Output::Yaml | Output::Wide | Output::Custom(_)
        )
    }

    pub fn listing(&mut self, mut listing: Listing) -> io::Result<()> {
        for f in &listing.failed {
            let what = f.error.as_deref().unwrap_or("error");
            eprintln!("ls: {}: {}", f.name, what);
        }
        if let Some(e) = &listing.error {
            eprintln!("ls: {}: {}", listing.dir.as_deref().unwrap_or(""), e);
            return Ok(());
        }
        if self.machine() {
            let numeric = self.cfg.long.map(|l| l.numeric_ids).unwrap_or(false);
            self.records
                .extend(listing.entries.iter().map(|e| e.to_value(numeric)));
            return Ok(());
        }
        if let Some(dir) = &listing.dir {
            if self.name_dirs {
                if self.printed {
                    writeln!(self.out)?;
                }
                writeln!(self.out, "{}:", self.show(dir))?;
            }
        } else if listing.entries.is_empty() {
            return Ok(());
        }
        self.printed = true;
        for e in &mut listing.entries {
            e.read_target();
        }
        match self.cfg.output {
            Output::Table => self.table(&listing),
            _ => self.names(&listing),
        }
    }

    pub fn finish(&mut self) -> io::Result<()> {
        if !self.machine() {
            return Ok(());
        }
        let records = std::mem::take(&mut self.records);
        match &self.cfg.output {
            Output::Json => {
                let doc = Value::Map(vec![
                    ("apiVersion".into(), Value::Str("emibsd.org/v1".into())),
                    ("kind".into(), Value::Str("FileList".into())),
                    ("items".into(), Value::List(records)),
                ]);
                writeln!(self.out, "{}", doc.to_json(true))
            }
            Output::Yaml => {
                let doc = Value::Map(vec![
                    ("apiVersion".into(), Value::Str("emibsd.org/v1".into())),
                    ("kind".into(), Value::Str("FileList".into())),
                    ("items".into(), Value::List(records)),
                ]);
                write!(self.out, "{}", doc.to_yaml())
            }
            other => cli::render::render_records(other, &records, self.cfg.headers, self.out),
        }
    }

    /// A name as it reaches the terminal.
    fn show(&self, s: &str) -> String {
        if self.cfg.sanitize {
            sanitize(s)
        } else {
            s.to_string()
        }
    }

    fn decorated_name(&self, e: &Entry) -> String {
        let mut s = self.show(&e.name);
        if let Some(m) = &e.meta {
            if self.cfg.indicator_all {
                if let Some(c) = mode::indicator(m.mode) {
                    s.push(c);
                }
            } else if self.cfg.indicator_dirs && m.is_dir() {
                s.push('/');
            }
        }
        s
    }

    fn blocks_of(&self, e: &Entry) -> u64 {
        // st_blocks counts 512-byte units; shown in units of the block size, rounded up.
        let b = e.meta.map(|m| m.blocks).unwrap_or(0) * 512;
        b.div_ceil(self.cfg.block_size)
    }

    fn prefix(&self, e: &Entry, w_inode: usize, w_blocks: usize) -> String {
        let mut s = String::new();
        if self.cfg.inode {
            s.push_str(&format!(
                "{:>w$} ",
                e.meta.map(|m| m.ino).unwrap_or(0),
                w = w_inode
            ));
        }
        if self.cfg.blocks {
            s.push_str(&format!("{:>w$} ", self.blocks_of(e), w = w_blocks));
        }
        s
    }

    fn widths(&self, l: &Listing) -> (usize, usize) {
        let wi = l
            .entries
            .iter()
            .map(|e| e.meta.map(|m| m.ino).unwrap_or(0).to_string().len())
            .max()
            .unwrap_or(0);
        let wb = l
            .entries
            .iter()
            .map(|e| self.blocks_of(e).to_string().len())
            .max()
            .unwrap_or(0);
        (wi, wb)
    }

    fn total_line(&mut self, l: &Listing) -> io::Result<()> {
        // POSIX: the total of blocks, for directories, when -l or -s.
        if l.dir.is_some() && (self.cfg.long.is_some() || self.cfg.blocks) && !self.cfg.tty {
            let total: u64 = l.entries.iter().map(|e| self.blocks_of(e)).sum();
            writeln!(self.out, "total {total}")?;
        }
        Ok(())
    }

    fn names(&mut self, l: &Listing) -> io::Result<()> {
        let (wi, wb) = self.widths(l);
        self.total_line(l)?;
        let items: Vec<String> = l
            .entries
            .iter()
            .map(|e| format!("{}{}", self.prefix(e, wi, wb), self.decorated_name(e)))
            .collect();
        if self.cfg.single_column || !self.cfg.tty {
            for i in items {
                writeln!(self.out, "{i}")?;
            }
        } else {
            for line in cli::render::grid(&items, self.cfg.width) {
                writeln!(self.out, "{line}")?;
            }
        }
        Ok(())
    }

    fn table(&mut self, l: &Listing) -> io::Result<()> {
        let long = self.cfg.long.unwrap_or(crate::options::LongOptions {
            owner: true,
            numeric_ids: false,
            flags: false,
        });
        let (wi, wb) = self.widths(l);
        self.total_line(l)?;
        let posix = !self.cfg.tty;
        let mut cols: Vec<Column> = Vec::new();
        if self.cfg.inode {
            cols.push(Column::right("INODE"));
        }
        if self.cfg.blocks {
            cols.push(Column::right("BLOCKS"));
        }
        cols.push(Column::left("MODE"));
        cols.push(Column::right("LINKS"));
        if long.owner {
            cols.push(Column::left("OWNER"));
        }
        cols.push(Column::left("GROUP"));
        if long.flags {
            cols.push(Column::left("FLAGS"));
        }
        cols.push(Column::right("SIZE"));
        cols.push(Column::left(match self.cfg.time {
            crate::options::TimeField::Modified => "MODIFIED",
            crate::options::TimeField::Accessed => "ACCESSED",
            crate::options::TimeField::Changed => "CHANGED",
        }));
        cols.push(Column::left("NAME"));
        let mut t = Table::new(cols);
        // The device column: in POSIX's format "major, minor" shares the size column, both
        // numbers aligned among themselves.
        let w_major = l
            .entries
            .iter()
            .filter_map(|e| e.meta.filter(|m| m.is_device()))
            .map(|m| m.major_minor().0.to_string().len())
            .max()
            .unwrap_or(0);
        let w_minor = l
            .entries
            .iter()
            .filter_map(|e| e.meta.filter(|m| m.is_device()))
            .map(|m| m.major_minor().1.to_string().len())
            .max()
            .unwrap_or(0);
        for e in &l.entries {
            let Some(m) = &e.meta else { continue };
            let mut row = Vec::new();
            if self.cfg.inode {
                row.push(format!("{:>w$}", m.ino, w = wi));
            }
            if self.cfg.blocks {
                row.push(format!("{:>w$}", self.blocks_of(e), w = wb));
            }
            row.push(mode::strmode(m.mode));
            row.push(m.nlink.to_string());
            if long.owner {
                row.push(if long.numeric_ids {
                    m.uid.to_string()
                } else {
                    sys::user_name(m.uid).unwrap_or_else(|| m.uid.to_string())
                });
            }
            row.push(if long.numeric_ids {
                m.gid.to_string()
            } else {
                sys::group_name(m.gid).unwrap_or_else(|| m.gid.to_string())
            });
            if long.flags {
                let f = sys::flags_to_string(m.flags);
                row.push(if f.is_empty() { "-".into() } else { f });
            }
            row.push(if m.is_device() {
                let (maj, min) = m.major_minor();
                format!("{maj:>w1$}, {min:>w2$}", w1 = w_major, w2 = w_minor)
            } else if self.cfg.human {
                human_size(m.size)
            } else {
                m.size.to_string()
            });
            let secs = match self.cfg.time {
                crate::options::TimeField::Modified => m.mtime.0,
                crate::options::TimeField::Accessed => m.atime.0,
                crate::options::TimeField::Changed => m.ctime.0,
            };
            row.push(if posix {
                time::posix(secs, self.now)
            } else {
                time::iso(secs)
            });
            let mut name = self.decorated_name(e);
            if m.is_symlink() {
                if let Some(t) = &e.target {
                    name.push_str(" -> ");
                    name.push_str(&self.show(t));
                }
            }
            row.push(name);
            t.rows.push(row);
        }
        if posix {
            // POSIX's spacing: one blank between columns, owner and group padded on the
            // right with two blanks, as every ls since 4.4BSD prints it.
            self.posix_rows(&t, long)
        } else {
            t.render(self.cfg.headers, self.out)
        }
    }

    fn posix_rows(&mut self, t: &Table, long: crate::options::LongOptions) -> io::Result<()> {
        let n = t.columns.len();
        let mut widths = vec![0usize; n];
        for row in &t.rows {
            for (i, c) in row.iter().enumerate() {
                widths[i] = widths[i].max(c.chars().count());
            }
        }
        let owner_col = usize::from(self.cfg.inode) + usize::from(self.cfg.blocks) + 2;
        let group_col = owner_col + usize::from(long.owner);
        for row in &t.rows {
            let mut line = String::new();
            for (i, c) in row.iter().enumerate() {
                let last = i + 1 == n;
                let pad = widths[i] - c.chars().count();
                match t.columns[i].align {
                    cli::Align::Right => {
                        line.extend(std::iter::repeat_n(' ', pad));
                        line.push_str(c);
                    }
                    cli::Align::Left => {
                        line.push_str(c);
                        if !last {
                            line.extend(std::iter::repeat_n(' ', pad));
                        }
                    }
                }
                if !last {
                    line.push(' ');
                    if i == owner_col || i == group_col {
                        line.push(' ');
                    }
                }
            }
            writeln!(self.out, "{line}")?;
        }
        Ok(())
    }
}
