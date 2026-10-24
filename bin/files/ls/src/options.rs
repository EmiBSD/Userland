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

//! The command line, turned into a [`Config`] whose fields cannot contradict each other.
//!
//! The POSIX short flags keep their meaning; the common grammar adds `-o`, `--sort-by`,
//! `--type`, `--since`, `--max-depth`, `--no-headers`, `--flags`. Where OpenBSD's `ls`
//! keeps twenty integers that override each other in a `switch`, the mutually exclusive
//! flags here collapse into enums: the last one given wins, and `-l` always beats `-g`.

use std::io::IsTerminal;

use cli::text::parse_duration;
use cli::{Help, OptDoc, Output, Spec};

pub const USAGE: &str = "usage: ls [-1AacdFghiklnpqRrSstuHL] [-o format] [--sort-by=.field] [--type=t,...]\n          [--since=duration] [--max-depth=n] [--no-headers] [--flags] [file ...]";

const fn opt(
    short: Option<char>,
    long: Option<&'static str>,
    value: Option<&'static str>,
    doc: &'static str,
) -> OptDoc {
    OptDoc {
        short,
        long,
        value,
        doc,
        choices: &[],
        group: None,
    }
}

const fn grouped(
    short: Option<char>,
    long: Option<&'static str>,
    doc: &'static str,
    group: &'static str,
) -> OptDoc {
    OptDoc {
        short,
        long,
        value: None,
        doc,
        choices: &[],
        group: Some(group),
    }
}

/// The program's own description: `--help` prints it as text, `--help -o json` as a record.
pub const HELP: Help = Help {
    name: "ls",
    summary: "list directory contents",
    synopsis: "[-1AacdFghiklnpqRrSstuHL] [-o format] [--sort-by=.field] [--type=t,...] [--since=duration] [--max-depth=n] [--no-headers] [--flags] [file ...]",
    options: &[
        OptDoc {
            short: Some('o'),
            long: Some("output"),
            value: Some("FORMAT"),
            doc: "what to print",
            choices: &[
                "name",
                "table",
                "wide",
                "json",
                "yaml",
                "custom-columns=NAME:.path,...",
            ],
            group: Some("format"),
        },
        grouped(Some('1'), None, "one name per line", "format"),
        grouped(Some('C'), None, "names in columns", "format"),
        grouped(
            Some('l'),
            None,
            "the long table: mode, links, owner, group, size, time, name",
            "format",
        ),
        grouped(
            Some('g'),
            None,
            "the long table without the owner",
            "format",
        ),
        grouped(
            Some('n'),
            None,
            "the long table with numeric owner and group",
            "format",
        ),
        opt(
            None,
            Some("sort-by"),
            Some(".FIELD"),
            "sort by any field of the record (.name, .size, .mtime, .atime, .ctime, .mode, .owner, ...)",
        ),
        grouped(Some('t'), None, "sort by time, newest first", "sort"),
        grouped(Some('S'), None, "sort by size, largest first", "sort"),
        opt(Some('r'), Some("reverse"), None, "reverse the order"),
        grouped(
            Some('c'),
            None,
            "use the time of last status change for sorting and the table",
            "time",
        ),
        grouped(
            Some('u'),
            None,
            "use the time of last access for sorting and the table",
            "time",
        ),
        opt(
            Some('a'),
            Some("all"),
            None,
            "include entries whose name begins with a dot, and . and ..",
        ),
        opt(
            Some('A'),
            Some("almost-all"),
            None,
            "include dot entries except . and .. (always on for root)",
        ),
        opt(
            Some('d'),
            Some("directory"),
            None,
            "list a directory itself, not its contents",
        ),
        opt(
            Some('R'),
            Some("recursive"),
            None,
            "list subdirectories recursively",
        ),
        opt(
            None,
            Some("max-depth"),
            Some("N"),
            "with -R, descend at most N levels",
        ),
        OptDoc {
            short: None,
            long: Some("type"),
            value: Some("T,..."),
            doc: "only entries of these kinds",
            choices: &["file", "dir", "symlink", "fifo", "socket", "char", "block"],
            group: None,
        },
        opt(
            None,
            Some("since"),
            Some("DURATION"),
            "only entries modified within the last 7d, 12h, 30m, 45s",
        ),
        opt(
            Some('F'),
            None,
            None,
            "append / to directories, * to executables, @ to symlinks, = to sockets, | to FIFOs",
        ),
        opt(Some('p'), None, None, "append / to directories"),
        opt(Some('i'), None, None, "print the inode number"),
        opt(
            Some('s'),
            None,
            None,
            "print the blocks used, in BLOCKSIZE units",
        ),
        opt(
            Some('k'),
            None,
            None,
            "blocks of 1024 bytes for -s and total",
        ),
        opt(
            Some('h'),
            Some("human"),
            None,
            "sizes with K, M, G suffixes (default on a terminal)",
        ),
        opt(
            None,
            Some("flags"),
            None,
            "show the file flags of chflags(1) in the table",
        ),
        grouped(
            Some('H'),
            None,
            "follow symbolic links named on the command line",
            "follow",
        ),
        grouped(Some('L'), None, "follow all symbolic links", "follow"),
        opt(
            Some('q'),
            None,
            None,
            "print ? for non-printable characters (default on a terminal)",
        ),
        opt(None, Some("no-headers"), None, "no header line on tables"),
        opt(
            None,
            Some("help"),
            None,
            "this description; with -o json or -o yaml, as a record",
        ),
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
            "an operand or an entry could not be listed, or the options were wrong",
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

const SPEC: Spec = Spec {
    short_flags: "1ACacdFghiklnpqRrSstuHL",
    short_with_value: "o",
    long_flags: &[
        "no-headers",
        "flags",
        "help",
        "all",
        "almost-all",
        "recursive",
        "directory",
        "human",
        "reverse",
    ],
    long_with_value: &["output", "sort-by", "type", "since", "max-depth"],
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
    fn parse(s: &str) -> Result<TypeFilter, String> {
        Ok(match s {
            "file" | "f" => TypeFilter::File,
            "dir" | "d" | "directory" => TypeFilter::Dir,
            "symlink" | "l" | "link" => TypeFilter::Symlink,
            "fifo" | "p" | "pipe" => TypeFilter::Fifo,
            "socket" | "s" => TypeFilter::Socket,
            "char" | "c" => TypeFilter::Char,
            "block" | "b" => TypeFilter::Block,
            _ => {
                return Err(format!(
                    "--type: `{s}` is not file, dir, symlink, fifo, socket, char or block"
                ));
            }
        })
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

/// Why the command line was not accepted.
pub enum Usage {
    /// `--help`, in the output format given with it.
    Help(Output),
    Error(String),
}

impl Config {
    pub fn from_args<I: IntoIterator<Item = String>>(args: I) -> Result<Config, Usage> {
        let parsed = SPEC.parse(args).map_err(|e| Usage::Error(e.to_string()))?;
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
            hidden: if is_root() {
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
        let mut help = false;
        for opt in parsed.opts {
            let v = opt.value.as_deref().unwrap_or("");
            match opt.name.as_str() {
                "1" => {
                    c.output = Output::Name;
                    c.single_column = true;
                    c.long = None;
                    output_explicit = true;
                }
                "C" => {
                    c.output = Output::Name;
                    c.single_column = false;
                    c.long = None;
                    output_explicit = true;
                }
                "l" => {
                    c.output = Output::Table;
                    let numeric = c.long.map(|l| l.numeric_ids).unwrap_or(false);
                    c.long = Some(LongOptions {
                        owner: true,
                        numeric_ids: numeric,
                        flags: c.long.map(|l| l.flags).unwrap_or(false),
                    });
                    long_wins = true;
                    output_explicit = true;
                }
                "g" => {
                    c.output = Output::Table;
                    let prev = c.long.unwrap_or(LongOptions {
                        owner: true,
                        numeric_ids: false,
                        flags: false,
                    });
                    c.long = Some(LongOptions {
                        owner: long_wins,
                        ..prev
                    });
                    output_explicit = true;
                }
                "n" => {
                    c.output = Output::Table;
                    let prev = c.long.unwrap_or(LongOptions {
                        owner: true,
                        numeric_ids: false,
                        flags: false,
                    });
                    c.long = Some(LongOptions {
                        numeric_ids: true,
                        ..prev
                    });
                    output_explicit = true;
                }
                "o" | "output" => {
                    c.output = Output::parse(v).map_err(Usage::Error)?;
                    if c.output == Output::Table && c.long.is_none() {
                        c.long = Some(LongOptions {
                            owner: true,
                            numeric_ids: false,
                            flags: false,
                        });
                    }
                    output_explicit = true;
                }
                "a" | "all" => c.hidden = Hidden::All,
                "A" | "almost-all" => c.hidden = Hidden::AlmostAll,
                "c" => c.time = TimeField::Changed,
                "u" => c.time = TimeField::Accessed,
                "d" | "directory" => {
                    c.directory = true;
                    c.recursive = false;
                }
                "R" | "recursive" => {
                    c.recursive = true;
                    c.directory = false;
                }
                "F" => c.indicator_all = true,
                "p" => c.indicator_dirs = true,
                "H" => {
                    c.follow = Follow::CommandLine;
                    follow_explicit = true;
                }
                "L" => {
                    c.follow = Follow::Always;
                    follow_explicit = true;
                }
                "h" | "human" => c.human = true,
                "i" => c.inode = true,
                "s" => c.blocks = true,
                "k" => c.block_size = 1024,
                "q" => c.sanitize = true,
                "r" | "reverse" => c.reverse = true,
                "S" => c.sort = Sort::Size,
                "t" => c.sort = Sort::Time,
                "sort-by" => c.sort = Sort::Field(v.trim_start_matches('.').to_string()),
                "no-headers" => c.headers = false,
                "flags" => {
                    let prev = c.long.unwrap_or(LongOptions {
                        owner: true,
                        numeric_ids: false,
                        flags: false,
                    });
                    c.long = Some(LongOptions {
                        flags: true,
                        ..prev
                    });
                    if c.output == Output::Name && !output_explicit {
                        c.output = Output::Table;
                    }
                }
                "type" => {
                    for t in v.split(',').filter(|s| !s.is_empty()) {
                        c.types.push(TypeFilter::parse(t).map_err(Usage::Error)?);
                    }
                }
                "since" => c.since_seconds = Some(parse_duration(v).map_err(Usage::Error)?),
                "max-depth" => {
                    c.max_depth = Some(v.parse().map_err(|_| {
                        Usage::Error(format!("--max-depth: `{v}` is not a number"))
                    })?);
                    if !c.directory {
                        c.recursive = true;
                    }
                }
                "help" => help = true,
                other => return Err(Usage::Error(format!("unknown option -- {other}"))),
            }
        }
        if help {
            // `--help -o json` and `-o json --help` alike: the format wherever it was given.
            return Err(Usage::Help(c.output));
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
        Ok(c)
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
    if let Ok(cols) = std::env::var("COLUMNS") {
        if let Ok(n) = cols.trim().parse::<usize>() {
            if n > 0 {
                return n;
            }
        }
    }
    if tty {
        if let Some(n) = sys::terminal_columns() {
            return n;
        }
    }
    80
}

fn block_size_from_env() -> u64 {
    // BLOCKSIZE: a number, optionally with a K, M or G suffix, between 512 and 1G as
    // getbsize(3) allows; anything else is 512.
    let Ok(s) = std::env::var("BLOCKSIZE") else {
        return 512;
    };
    let s = s.trim();
    let (num, mult) = match s.chars().last() {
        Some('k' | 'K') => (&s[..s.len() - 1], 1024u64),
        Some('m' | 'M') => (&s[..s.len() - 1], 1024 * 1024),
        Some('g' | 'G') => (&s[..s.len() - 1], 1024 * 1024 * 1024),
        _ => (s, 1),
    };
    match num.parse::<u64>() {
        Ok(n) if (512..=1024 * 1024 * 1024).contains(&(n * mult)) => n * mult,
        _ => 512,
    }
}

fn is_root() -> bool {
    // Root sees dotfiles without -A, as OpenBSD's ls does. std has no getuid; the
    // environment's USER is a proxy good enough for the listing's default.
    std::env::var("USER").map(|u| u == "root").unwrap_or(false)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cfg(s: &str) -> Config {
        Config::from_args(s.split_whitespace().map(String::from))
            .ok()
            .expect("parses")
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
        assert!(Config::from_args(["--type=zzz".to_string()]).is_err());
        assert!(Config::from_args(["-Z".to_string()]).is_err());
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
