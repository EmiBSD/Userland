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

//! The program's one declaration, and the command line turned into a [`Config`] whose fields
//! cannot contradict each other.
//!
//! [`COMMAND`] is the only place `ls` says what it accepts: from it `cli` derives the parser
//! (values arrive typed), `--help` as text and as a record, the usage line and the error
//! prefix. The POSIX short flags keep their meaning; the common grammar adds `-o`,
//! `--sort-by`, `--type`, `--since`, `--max-depth`, `--no-headers`, `--flags`. Where the
//! classic `ls` keeps twenty integers that override each other in a `switch`, the mutually
//! exclusive flags here collapse into enums: the last one given wins, and `-l` always beats
//! `-g`.

use std::io::IsTerminal;

use cli::{Command, Kind, OptSpec, Output, Parsed, Typed};

const KINDS: &[&str] = &["file", "dir", "symlink", "fifo", "socket", "char", "block"];

/// The program's own description: `--help` prints it as text, `--help -o json` as a record.
pub const COMMAND: Command = Command {
    name: "ls",
    summary: "list directory contents",
    synopsis: "[-1AacdFghiklnpqRrSstuHL] [-o format] [--sort-by=.field] [--type=t,...] [--since=duration] [--max-depth=n] [--no-headers] [--flags] [file ...]",
    options: &[
        OptSpec::value(Some('o'), Some("output"), Kind::Format, "what to print")
            .in_group("format"),
        OptSpec::flag(Some('1'), None, "one name per line").in_group("format"),
        OptSpec::flag(Some('C'), None, "names in columns").in_group("format"),
        OptSpec::flag(
            Some('l'),
            None,
            "the long table: mode, links, owner, group, size, time, name",
        )
        .in_group("format"),
        OptSpec::flag(Some('g'), None, "the long table without the owner").in_group("format"),
        OptSpec::flag(
            Some('n'),
            None,
            "the long table with numeric owner and group",
        )
        .in_group("format"),
        OptSpec::value(
            None,
            Some("sort-by"),
            Kind::Field(".FIELD"),
            "sort by any field of the record (.name, .size, .mtime, .atime, .ctime, .mode, .owner, ...)",
        )
        .in_group("sort"),
        OptSpec::flag(Some('t'), None, "sort by time, newest first").in_group("sort"),
        OptSpec::flag(Some('S'), None, "sort by size, largest first").in_group("sort"),
        OptSpec::flag(Some('r'), Some("reverse"), "reverse the order"),
        OptSpec::flag(
            Some('c'),
            None,
            "use the time of last status change for sorting and the table",
        )
        .in_group("time"),
        OptSpec::flag(
            Some('u'),
            None,
            "use the time of last access for sorting and the table",
        )
        .in_group("time"),
        OptSpec::flag(
            Some('a'),
            Some("all"),
            "include entries whose name begins with a dot, and . and ..",
        )
        .in_group("hidden"),
        OptSpec::flag(
            Some('A'),
            Some("almost-all"),
            "include dot entries except . and .. (always on for root)",
        )
        .in_group("hidden"),
        OptSpec::flag(
            Some('d'),
            Some("directory"),
            "list a directory itself, not its contents",
        )
        .in_group("depth"),
        OptSpec::flag(Some('R'), Some("recursive"), "list subdirectories recursively").in_group("depth"),
        OptSpec::value(
            None,
            Some("max-depth"),
            Kind::Int {
                name: "N",
                min: 0,
                max: 1024,
            },
            "with -R, descend at most N levels",
        ),
        OptSpec::value(
            None,
            Some("type"),
            Kind::List("T,...", KINDS),
            "only entries of these kinds",
        ),
        OptSpec::value(
            None,
            Some("since"),
            Kind::Duration("DURATION"),
            "only entries modified within the last 7d, 12h, 30m, 45s",
        ),
        OptSpec::flag(
            Some('F'),
            None,
            "append / to directories, * to executables, @ to symlinks, = to sockets, | to FIFOs",
        ),
        OptSpec::flag(Some('p'), None, "append / to directories"),
        OptSpec::flag(Some('i'), None, "print the inode number"),
        OptSpec::flag(Some('s'), None, "print the blocks used, in BLOCKSIZE units"),
        OptSpec::flag(Some('k'), None, "blocks of 1024 bytes for -s and total"),
        OptSpec::flag(
            Some('h'),
            Some("human"),
            "sizes with K, M, G suffixes (default on a terminal)",
        )
        .bsd(),
        OptSpec::flag(
            None,
            Some("flags"),
            "show the file flags of chflags(1) in the table",
        ),
        OptSpec::flag(
            Some('H'),
            None,
            "follow symbolic links named on the command line",
        )
        .in_group("follow"),
        OptSpec::flag(Some('L'), None, "follow all symbolic links").in_group("follow"),
        OptSpec::flag(
            Some('q'),
            None,
            "print ? for non-printable characters (default on a terminal)",
        ),
        OptSpec::flag(None, Some("no-headers"), "no header line on tables"),
    ],
    outputs: &[
        ("name", "one name per line to a pipe, columns on a terminal"),
        ("table", "the long listing; POSIX's byte for byte to a pipe"),
        ("wide", "every field of the record as a table"),
        ("json", "a FileList document: apiVersion, kind, items"),
        ("yaml", "the same document as YAML"),
        (
            "custom-columns=NAME:.name,SIZE:.size",
            "the fields you choose",
        ),
    ],
    schema: Some("bin/files/ls/schemas/entry.v1.json"),
    exit_codes: &[
        (0, "every operand was listed"),
        (
            1,
            "an operand or an entry could not be listed, or standard output failed",
        ),
    ],
    examples: &[
        ("ls -l", "the classic long listing"),
        (
            "ls -o json | jq '.items[].size'",
            "sizes without parsing columns",
        ),
        (
            "ls --sort-by=.mtime -r --since=7d",
            "what changed this week, oldest first",
        ),
        (
            "ls -o custom-columns=NAME:.name,OWNER:.owner,MODE:.perm",
            "three fields of your choice",
        ),
        (
            "ls --help -o json",
            "this description as a record, for a tool or an agent",
        ),
    ],
    environment: &[
        (
            "BLOCKSIZE",
            "the unit of -s and of the total line, 512 unless -k",
        ),
        (
            "COLUMNS",
            "the width for columns, else the terminal's, else 80",
        ),
        ("TZ", "the zone dates are shown in"),
    ],
    notes: "To a pipe the output of -l, -1, -i and -s is POSIX's, so scripts keep working; to a terminal, dates are ISO 8601, sizes human-readable and tables carry a header. Of a group of exclusive options the last one given wins, except that -l beats -g.",
};

/// Which time of the record `-t` sorts by and the table shows.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TimeField {
    Modified,
    Accessed,
    Changed,
}

/// The order of a listing.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Sort {
    Name,
    Size,
    Time,
    /// `--sort-by=.field`.
    Field(String),
}

/// Which hidden entries appear.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Hidden {
    None,
    /// `-A`: dotfiles but not `.` and `..`.
    AlmostAll,
    /// `-a`: everything.
    All,
}

/// Whether a symbolic link is followed when its target is examined.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Follow {
    Never,
    /// `-H`: only the operands (POSIX's default when neither `-d`, `-F` nor `-l`).
    CommandLine,
    /// `-L`.
    Always,
}

/// What the long table shows beyond POSIX's columns.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct LongOptions {
    pub owner: bool,
    pub numeric_ids: bool,
    pub flags: bool,
}

const LONG_DEFAULT: LongOptions = LongOptions {
    owner: true,
    numeric_ids: false,
    flags: false,
};

/// A kind of file `--type` can select.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TypeFilter {
    File,
    Dir,
    Symlink,
    Fifo,
    Socket,
    Char,
    Block,
}

impl TypeFilter {
    /// From one of [`KINDS`], which the parser already checked.
    fn of(s: &str) -> TypeFilter {
        match s {
            "file" => TypeFilter::File,
            "dir" => TypeFilter::Dir,
            "symlink" => TypeFilter::Symlink,
            "fifo" => TypeFilter::Fifo,
            "socket" => TypeFilter::Socket,
            "char" => TypeFilter::Char,
            _ => TypeFilter::Block,
        }
    }
}

/// Everything the walk and the renderers need, consistent by construction.
#[derive(Debug, Clone)]
pub struct Config {
    pub operands: Vec<String>,
    pub output: Output,
    /// The output goes to a terminal: modern defaults, columns, `?` for controls.
    pub tty: bool,
    pub width: usize,
    pub long: Option<LongOptions>,
    pub single_column: bool,
    pub headers: bool,
    pub sort: Sort,
    pub reverse: bool,
    pub time: TimeField,
    pub hidden: Hidden,
    pub recursive: bool,
    pub max_depth: Option<usize>,
    pub directory: bool,
    pub follow: Follow,
    pub indicator_all: bool,
    pub indicator_dirs: bool,
    pub inode: bool,
    pub blocks: bool,
    pub block_size: u64,
    pub human: bool,
    pub sanitize: bool,
    pub types: Vec<TypeFilter>,
    pub since_seconds: Option<u64>,
}

impl Config {
    /// From a command line `COMMAND` accepted: every value is already of its type, so
    /// nothing here can fail.
    pub fn from_parsed(parsed: Parsed) -> Config {
        let tty = std::io::stdout().is_terminal();
        let mut c = Config {
            operands: parsed.operands,
            output: Output::Name,
            tty,
            width: terminal_width(tty),
            long: None,
            single_column: !tty,
            headers: tty,
            sort: Sort::Name,
            reverse: false,
            time: TimeField::Modified,
            hidden: if sys::getuid() == 0 {
                Hidden::AlmostAll
            } else {
                Hidden::None
            },
            recursive: false,
            max_depth: None,
            directory: false,
            follow: Follow::CommandLine,
            indicator_all: false,
            indicator_dirs: false,
            inode: false,
            blocks: false,
            block_size: block_size_from_env(),
            human: tty,
            sanitize: tty,
            types: Vec::new(),
            since_seconds: None,
        };
        let mut follow_explicit = false;
        let mut long_wins = false; // -l always overrides -g
        let mut output_explicit = false;
        for g in parsed.given {
            match (g.key(), g.value) {
                ("1", _) => {
                    c.output = Output::Name;
                    c.single_column = true;
                    c.long = None;
                    output_explicit = true;
                }
                ("C", _) => {
                    c.output = Output::Name;
                    c.single_column = false;
                    c.long = None;
                    output_explicit = true;
                }
                ("l", _) => {
                    c.output = Output::Table;
                    c.long = Some(LongOptions {
                        owner: true,
                        ..c.long.unwrap_or(LONG_DEFAULT)
                    });
                    long_wins = true;
                    output_explicit = true;
                }
                ("g", _) => {
                    c.output = Output::Table;
                    c.long = Some(LongOptions {
                        owner: long_wins,
                        ..c.long.unwrap_or(LONG_DEFAULT)
                    });
                    output_explicit = true;
                }
                ("n", _) => {
                    c.output = Output::Table;
                    c.long = Some(LongOptions {
                        numeric_ids: true,
                        ..c.long.unwrap_or(LONG_DEFAULT)
                    });
                    output_explicit = true;
                }
                ("output", Typed::Format(o)) => {
                    c.output = o;
                    if c.output == Output::Table && c.long.is_none() {
                        c.long = Some(LONG_DEFAULT);
                    }
                    output_explicit = true;
                }
                ("all", _) => c.hidden = Hidden::All,
                ("almost-all", _) => c.hidden = Hidden::AlmostAll,
                ("c", _) => c.time = TimeField::Changed,
                ("u", _) => c.time = TimeField::Accessed,
                ("directory", _) => {
                    c.directory = true;
                    c.recursive = false;
                }
                ("recursive", _) => {
                    c.recursive = true;
                    c.directory = false;
                }
                ("F", _) => c.indicator_all = true,
                ("p", _) => c.indicator_dirs = true,
                ("H", _) => {
                    c.follow = Follow::CommandLine;
                    follow_explicit = true;
                }
                ("L", _) => {
                    c.follow = Follow::Always;
                    follow_explicit = true;
                }
                ("human", _) => c.human = true,
                ("i", _) => c.inode = true,
                ("s", _) => c.blocks = true,
                ("k", _) => c.block_size = 1024,
                ("q", _) => c.sanitize = true,
                ("reverse", _) => c.reverse = true,
                ("S", _) => c.sort = Sort::Size,
                ("t", _) => c.sort = Sort::Time,
                ("sort-by", Typed::Field(f)) => c.sort = Sort::Field(f),
                ("no-headers", _) => c.headers = false,
                ("flags", _) => {
                    c.long = Some(LongOptions {
                        flags: true,
                        ..c.long.unwrap_or(LONG_DEFAULT)
                    });
                    if c.output == Output::Name && !output_explicit {
                        c.output = Output::Table;
                    }
                }
                ("type", Typed::List(kinds)) => {
                    c.types.extend(kinds.iter().map(|k| TypeFilter::of(k)));
                }
                ("since", Typed::Duration(secs)) => c.since_seconds = Some(secs),
                ("max-depth", Typed::Int(n)) => {
                    c.max_depth = Some(n as usize);
                    if !c.directory {
                        c.recursive = true;
                    }
                }
                // The declaration and this match name the same options; a value of another
                // type cannot arrive, since `cli` checked it against the declared kind.
                _ => {}
            }
        }
        // POSIX: without -d, -F or -l, a symbolic link operand is followed; with any of them,
        // the link itself is listed, unless -H or -L said otherwise.
        if !follow_explicit && (c.directory || c.indicator_all || c.long.is_some()) {
            c.follow = Follow::Never;
        }
        // A table to a pipe is POSIX's long format: no human sizes unless asked, no header.
        if !tty {
            c.headers = false;
        }
        c
    }

    /// Whether the walk needs `stat` of every entry, or names and types suffice.
    pub fn needs_stat(&self) -> bool {
        self.long.is_some()
            || self.inode
            || self.blocks
            || self.indicator_all
            || self.indicator_dirs
            || self.sort != Sort::Name
            || self.since_seconds.is_some()
            || !matches!(self.output, Output::Name)
    }
}

fn terminal_width(tty: bool) -> usize {
    if let Some(n) = std::env::var("COLUMNS")
        .ok()
        .and_then(|c| c.trim().parse::<usize>().ok())
        .filter(|n| *n > 0)
    {
        return n;
    }
    if let Some(n) = sys::terminal_columns().filter(|_| tty) {
        return n;
    }
    80
}

fn block_size_from_env() -> u64 {
    // BLOCKSIZE: a number, optionally with a K, M or G suffix, between 512 and 1G as
    // getbsize(3) allows; anything else is 512.
    let Ok(s) = std::env::var("BLOCKSIZE") else {
        return 512;
    };
    match cli::text::parse_size(&s) {
        Ok(n) if (512..=1024 * 1024 * 1024).contains(&n) => n,
        _ => 512,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cfg(s: &str) -> Config {
        Config::from_parsed(
            COMMAND
                .parse(s.split_whitespace().map(String::from))
                .expect("parses"),
        )
    }

    fn refused(s: &str) -> bool {
        COMMAND
            .parse(s.split_whitespace().map(String::from))
            .is_err()
    }

    #[test]
    fn l_beats_g_whatever_the_order() {
        assert!(cfg("-lg").long.unwrap().owner);
        assert!(cfg("-gl").long.unwrap().owner);
        assert!(!cfg("-g").long.unwrap().owner);
        assert!(cfg("-gn").long.unwrap().numeric_ids);
        assert!(!cfg("-gn").long.unwrap().owner);
    }

    #[test]
    fn the_last_format_wins() {
        let c = cfg("-l -1");
        assert_eq!(c.output, Output::Name);
        assert!(c.single_column);
        assert!(c.long.is_none());
        let c = cfg("-1 -l");
        assert_eq!(c.output, Output::Table);
        let c = cfg("-l -o json");
        assert_eq!(c.output, Output::Json);
    }

    #[test]
    fn d_and_r_exclude_each_other_and_follow_rules() {
        let c = cfg("-R -d");
        assert!(c.directory && !c.recursive);
        assert_eq!(c.follow, Follow::Never);
        let c = cfg("-d -R");
        assert!(c.recursive && !c.directory);
        assert_eq!(cfg("").follow, Follow::CommandLine);
        assert_eq!(cfg("-l").follow, Follow::Never);
        assert_eq!(cfg("-lH").follow, Follow::CommandLine);
        assert_eq!(cfg("-L").follow, Follow::Always);
    }

    #[test]
    fn times_sorts_and_filters() {
        assert_eq!(cfg("-c").time, TimeField::Changed);
        assert_eq!(cfg("-cu").time, TimeField::Accessed);
        assert_eq!(cfg("-S").sort, Sort::Size);
        assert_eq!(cfg("--sort-by=.mtime").sort, Sort::Field("mtime".into()));
        assert_eq!(
            cfg("--type=dir,symlink").types,
            [TypeFilter::Dir, TypeFilter::Symlink]
        );
        assert_eq!(cfg("--since=2h").since_seconds, Some(7200));
        assert_eq!(cfg("--max-depth=2").max_depth, Some(2));
        assert!(cfg("--max-depth=2").recursive);
        assert!(refused("--type=zzz"));
        assert!(refused("--max-depth=x"));
        assert!(refused("--since=3y"));
        assert!(refused("-o xml"));
        assert!(refused("-Z"));
    }

    #[test]
    fn stat_is_needed_only_when_something_uses_it() {
        assert!(!cfg("").needs_stat());
        assert!(cfg("-l").needs_stat());
        assert!(cfg("-t").needs_stat());
        assert!(cfg("-F").needs_stat());
        assert!(cfg("-o json").needs_stat());
    }
}
