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

//! A program declared once. The [`Command`] names every option with its type; from that one
//! table come the parser (values arrive converted and checked), `--help` as text, `--help
//! -o json` as a `CommandHelp` record (so a tool, an agent or an MCP server reads what the
//! program accepts without parsing prose; the user's decision of 2026-10-24), the usage line,
//! the `name: message` prefix of every diagnostic, and the exit codes every program shares.
//!
//! No program declares `--help`: every command has it, and `--help -o json` renders the
//! description in the format `-o` names, wherever `-o` was given.

use std::fmt;
use std::process::ExitCode;

use crate::args::{self, ArgError};
use crate::render::Output;
use crate::text::{parse_duration, parse_size};
use crate::value::Value;

/// The exit codes every written program shares. A program may define more above 2 and
/// list them in its [`Command::exit_codes`].
pub mod exit {
    /// Everything asked was done.
    pub const OK: u8 = 0;
    /// Something asked could not be done: an operand failed, output failed; the rest was done.
    pub const FAILURE: u8 = 1;
    /// The command line was wrong: an unknown option, a missing operand, a value of the wrong
    /// type. Nothing was done.
    pub const USAGE: u8 = 2;
}

/// The type of an option's value: what the parser checks and converts, what `--help` shows.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Kind {
    /// No value.
    Flag,
    /// Any text; the placeholder `--help` shows (`FILE`, `PATTERN`).
    Str(&'static str),
    /// One of a fixed set; the placeholder and the set.
    Choice(&'static str, &'static [&'static str]),
    /// One or more of a fixed set, comma-separated.
    List(&'static str, &'static [&'static str]),
    /// A whole number within bounds.
    Int {
        /// The placeholder, `N`.
        name: &'static str,
        /// The smallest value accepted.
        min: i64,
        /// The largest value accepted.
        max: i64,
    },
    /// A duration a human types (`7d`, `12h`, `30m`, `45s`, plain seconds), as seconds.
    Duration(&'static str),
    /// A size a human types (`512`, `4K`, `10M`, `1G`), as bytes.
    Size(&'static str),
    /// A path; only emptiness is refused here, the file system says the rest.
    Path(&'static str),
    /// A field path into the record, `.name` or `.meta.size`.
    Field(&'static str),
    /// `-o`: one of the renderers of [`Output`].
    Format,
}

/// The value of an option as the parser hands it over: already of the declared [`Kind`].
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Typed {
    /// A flag has no value.
    Flag,
    /// [`Kind::Str`].
    Str(String),
    /// [`Kind::Choice`]: the choice, as spelled in the declaration.
    Choice(&'static str),
    /// [`Kind::List`]: the choices, in the order given.
    List(Vec<&'static str>),
    /// [`Kind::Int`].
    Int(i64),
    /// [`Kind::Duration`], in seconds.
    Duration(u64),
    /// [`Kind::Size`], in bytes.
    Size(u64),
    /// [`Kind::Path`].
    Path(String),
    /// [`Kind::Field`], without its leading dot.
    Field(String),
    /// [`Kind::Format`].
    Format(Output),
}

impl Typed {
    /// The text of a `Str`, `Path` or `Field`, or the choice of a `Choice`.
    pub fn text(&self) -> Option<&str> {
        match self {
            Typed::Str(s) | Typed::Path(s) | Typed::Field(s) => Some(s),
            Typed::Choice(c) => Some(c),
            _ => None,
        }
    }
}

/// Where an option comes from: `--help` groups the options by it, so a user sees at a glance
/// what POSIX gives every system, what the BSDs have beyond it and is kept so their scripts
/// and habits work, what is this program's own, and what is the grammar every EmiBSD program
/// shares (the user's decision of 2026-10-24). No section names another system's program:
/// the origin is the flag's, never the code's, which is written here.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Origin {
    /// Defined by POSIX for this utility.
    Posix,
    /// A flag the BSD systems have beyond POSIX, kept for compatibility with their scripts.
    Bsd,
    /// EmiBSD's own, this program's: a filter, a flag no other system has.
    Emibsd,
    /// The common grammar every EmiBSD program shares, the shape of the output: `-o`,
    /// `--sort-by`, `--no-headers`, `--help`.
    Grammar,
}

/// The long names `cli` recognises as the common grammar's.
const GRAMMAR: &[&str] = &["output", "sort-by", "no-headers", "help"];

const fn str_eq(a: &str, b: &str) -> bool {
    let (a, b) = (a.as_bytes(), b.as_bytes());
    if a.len() != b.len() {
        return false;
    }
    let mut i = 0;
    while i < a.len() {
        if a[i] != b[i] {
            return false;
        }
        i += 1;
    }
    true
}

impl Origin {
    /// The name `--help -o json` prints.
    pub fn name(self) -> &'static str {
        match self {
            Origin::Posix => "posix",
            Origin::Bsd => "bsd",
            Origin::Emibsd => "emibsd",
            Origin::Grammar => "grammar",
        }
    }

    fn heading(self) -> &'static str {
        match self {
            Origin::Posix => "options (POSIX):",
            Origin::Bsd => "options (BSD compatibility):",
            Origin::Emibsd => "options (EmiBSD extensions):",
            Origin::Grammar => "options (EmiBSD common grammar, the output):",
        }
    }

    /// The default for a declaration: one of the grammar's long names is the grammar's
    /// whatever its short form; otherwise a short flag is POSIX's unless said otherwise and
    /// a long-only option is EmiBSD's (POSIX has no long options).
    const fn default_for(short: Option<char>, long: Option<&'static str>) -> Origin {
        if let Some(l) = long {
            let mut i = 0;
            while i < GRAMMAR.len() {
                if str_eq(l, GRAMMAR[i]) {
                    return Origin::Grammar;
                }
                i += 1;
            }
        }
        if short.is_some() {
            Origin::Posix
        } else {
            Origin::Emibsd
        }
    }
}

/// One option of a [`Command`].
#[derive(Debug, Clone, Copy)]
pub struct OptSpec {
    /// The short form, `l` for `-l`.
    pub short: Option<char>,
    /// The long form, `sort-by` for `--sort-by`.
    pub long: Option<&'static str>,
    /// Its value's type.
    pub kind: Kind,
    /// What it does, one sentence.
    pub doc: &'static str,
    /// The group of mutually exclusive options it belongs to, if any; the program decides
    /// which wins (usually the last), the help tells a tool not to combine them.
    pub group: Option<&'static str>,
    /// Where it comes from.
    pub origin: Origin,
}

impl OptSpec {
    /// An option without a value.
    pub const fn flag(short: Option<char>, long: Option<&'static str>, doc: &'static str) -> Self {
        OptSpec {
            short,
            long,
            kind: Kind::Flag,
            doc,
            group: None,
            origin: Origin::default_for(short, long),
        }
    }

    /// An option with a value of `kind`.
    pub const fn value(
        short: Option<char>,
        long: Option<&'static str>,
        kind: Kind,
        doc: &'static str,
    ) -> Self {
        OptSpec {
            short,
            long,
            kind,
            doc,
            group: None,
            origin: Origin::default_for(short, long),
        }
    }

    /// The same option, in an exclusive group.
    pub const fn in_group(self, group: &'static str) -> Self {
        OptSpec {
            group: Some(group),
            ..self
        }
    }

    /// The same option, a BSD flag beyond POSIX kept for compatibility.
    pub const fn bsd(self) -> Self {
        OptSpec {
            origin: Origin::Bsd,
            ..self
        }
    }

    /// The same option, EmiBSD's own (a short flag POSIX does not define, like `-o`).
    pub const fn emibsd(self) -> Self {
        OptSpec {
            origin: Origin::Emibsd,
            ..self
        }
    }

    /// The name a program matches on: the long form when there is one, else the short.
    pub fn key(&self) -> &'static str {
        match (self.long, self.short) {
            (Some(l), _) => l,
            (None, Some(c)) => short_key(c),
            (None, None) => "",
        }
    }

    fn dashed(&self, as_given: &str) -> String {
        if as_given.chars().count() == 1 {
            format!("-{as_given}")
        } else {
            format!("--{as_given}")
        }
    }
}

/// A one-character `&'static str` for a printable ASCII option letter.
fn short_key(c: char) -> &'static str {
    const PRINTABLE: &str = "!\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~";
    let i = c as usize;
    if (0x21..=0x7e).contains(&i) {
        &PRINTABLE[i - 0x21..i - 0x20]
    } else {
        "?"
    }
}

/// One option as given, with its value already typed.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Given {
    /// The short form of the option it matched.
    pub short: Option<char>,
    /// The long form of the option it matched.
    pub long: Option<&'static str>,
    /// Its value.
    pub value: Typed,
}

impl Given {
    /// The name a program matches on: the long form when the option has one (`"output"`
    /// for both `-o` and `--output`), else the short one as text (`"l"`).
    pub fn key(&self) -> &'static str {
        match (self.long, self.short) {
            (Some(l), _) => l,
            (None, Some(c)) => short_key(c),
            (None, None) => "",
        }
    }
}

/// A command line accepted by a [`Command`].
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Parsed {
    /// The options in the order given, typed.
    pub given: Vec<Given>,
    /// Everything after the options.
    pub operands: Vec<String>,
    /// `--help` was given.
    pub help: bool,
}

impl Parsed {
    /// The last `-o` given, if any.
    pub fn output(&self) -> Option<Output> {
        self.given.iter().rev().find_map(|g| match &g.value {
            Typed::Format(o) => Some(o.clone()),
            _ => None,
        })
    }

    /// Whether the option `key` names was given at all.
    pub fn has(&self, key: &str) -> bool {
        self.given.iter().any(|g| g.key() == key)
    }

    /// The value of the last occurrence of the option `key` names.
    pub fn last(&self, key: &str) -> Option<&Typed> {
        self.given
            .iter()
            .rev()
            .find(|g| g.key() == key)
            .map(|g| &g.value)
    }
}

/// A program's whole declaration.
#[derive(Debug, Clone, Copy)]
pub struct Command {
    /// `ls`.
    pub name: &'static str,
    /// One line.
    pub summary: &'static str,
    /// The synopsis, without the program name.
    pub synopsis: &'static str,
    /// Every option; `--help` is implied.
    pub options: &'static [OptSpec],
    /// The `-o` formats: `(name, what it prints)`.
    pub outputs: &'static [(&'static str, &'static str)],
    /// The record schema `-o json` follows, as a path in the repository.
    pub schema: Option<&'static str>,
    /// Exit codes and their meaning; 2 (the command line was wrong) is implied.
    pub exit_codes: &'static [(i32, &'static str)],
    /// `(command, what it shows)`.
    pub examples: &'static [(&'static str, &'static str)],
    /// Environment variables read: `(name, effect)`.
    pub environment: &'static [(&'static str, &'static str)],
    /// What a human should know besides the options.
    pub notes: &'static str,
}

const HELP_DOC: &str = "this description; with -o json or -o yaml, as a record";

impl Command {
    fn find(&self, name: &str) -> Option<&'static OptSpec> {
        let mut chars = name.chars();
        match (chars.next(), chars.next()) {
            (Some(c), None) => self.options.iter().find(|o| o.short == Some(c)),
            _ => self.options.iter().find(|o| o.long == Some(name)),
        }
    }

    fn classify(&self, name: &str) -> Option<bool> {
        match self.find(name) {
            Some(o) => Some(o.kind != Kind::Flag),
            None if name == "help" => Some(false),
            None => None,
        }
    }

    /// Parses `args` (without the program name): the options come back typed and checked,
    /// or the first error, already worded.
    pub fn parse<I: IntoIterator<Item = String>>(&self, args: I) -> Result<Parsed, ArgError> {
        let raw = args::lex(args, |n| self.classify(n))?;
        let mut out = Parsed {
            operands: raw.operands,
            ..Parsed::default()
        };
        for o in raw.opts {
            let Some(spec) = self.find(&o.name) else {
                // Only the implied --help reaches here: `classify` refused everything else.
                out.help = true;
                continue;
            };
            let value = convert(&spec.kind, o.value, &spec.dashed(&o.name))?;
            out.given.push(Given {
                short: spec.short,
                long: spec.long,
                value,
            });
        }
        Ok(out)
    }

    /// Parses the process's own arguments and handles what every program handles alike:
    /// `--help` prints the description (in the format `-o` named, if any) and the program
    /// exits 0; a wrong command line gets `name: message` and the usage line on standard
    /// error and the program exits 2. Returns the exit code to end with in those cases.
    pub fn from_env(&self) -> Result<Parsed, ExitCode> {
        self.run(std::env::args().skip(1))
    }

    /// [`Command::from_env`] over any arguments.
    pub fn run<I: IntoIterator<Item = String>>(&self, args: I) -> Result<Parsed, ExitCode> {
        match self.parse(args) {
            Ok(p) if p.help => {
                print!("{}", self.help(&p.output().unwrap_or(Output::Table)));
                Err(ExitCode::SUCCESS)
            }
            Ok(p) => Ok(p),
            Err(e) => {
                eprintln!("{}: {e}", self.name);
                eprintln!("{}", self.usage());
                Err(ExitCode::from(exit::USAGE))
            }
        }
    }

    /// `name: message` on standard error.
    pub fn warn(&self, message: impl fmt::Display) {
        eprintln!("{}: {message}", self.name);
    }

    /// `name: subject: error` on standard error, the shape of every per-operand failure.
    pub fn report(&self, subject: impl fmt::Display, error: impl fmt::Display) {
        eprintln!("{}: {subject}: {error}", self.name);
    }

    /// The usage line(s): `usage: name synopsis`, each line of a multi-line synopsis (the
    /// forms of the command) prefixed with the name, each wrapped at 80 columns.
    pub fn usage(&self) -> String {
        let mut lines: Vec<String> = Vec::new();
        for (i, form) in self.synopsis.lines().enumerate() {
            let prefix = if i == 0 {
                format!("usage: {} ", self.name)
            } else {
                format!("       {} ", self.name)
            };
            let indent = " ".repeat(prefix.len());
            lines.push(prefix);
            for word in synopsis_words(form) {
                let cur = lines.last_mut().expect("one line");
                let sep = if cur.ends_with(' ') { "" } else { " " };
                if cur.len() + sep.len() + word.len() > 80 && !cur.trim().is_empty() {
                    lines.push(format!("{indent}{word}"));
                } else {
                    cur.push_str(sep);
                    cur.push_str(&word);
                }
            }
        }
        lines.join("\n")
    }

    fn flag_column(o: &OptSpec) -> String {
        let mut f = String::new();
        if let Some(c) = o.short {
            f.push('-');
            f.push(c);
        }
        if let Some(l) = o.long {
            if !f.is_empty() {
                f.push_str(", ");
            }
            f.push_str("--");
            f.push_str(l);
        }
        if let Some(v) = placeholder(&o.kind) {
            f.push(' ');
            f.push_str(v);
        }
        f
    }

    /// The text a terminal gets: the options in four sections, POSIX's, BSD compatibility,
    /// EmiBSD's own, the common grammar (`--help` among the last).
    pub fn text(&self) -> String {
        let mut s = format!("{}: {}\n\n{}\n", self.name, self.summary, self.usage());
        let help_col = "--help".to_string();
        let width = self
            .options
            .iter()
            .map(|o| Self::flag_column(o).len())
            .chain(std::iter::once(help_col.len()))
            .max()
            .unwrap_or(0)
            .min(28);
        for origin in [Origin::Posix, Origin::Bsd, Origin::Emibsd, Origin::Grammar] {
            let mine: Vec<&OptSpec> = self.options.iter().filter(|o| o.origin == origin).collect();
            if mine.is_empty() && origin != Origin::Grammar {
                continue;
            }
            s.push('\n');
            s.push_str(origin.heading());
            s.push('\n');
            for o in mine {
                let mut doc = o.doc.to_string();
                let ch = choices(&o.kind);
                if !ch.is_empty() {
                    doc.push_str(&format!(" [{}]", ch.join(" | ")));
                }
                if let Kind::Int { min, max, .. } = o.kind {
                    doc.push_str(&format!(" [{min}..{max}]"));
                }
                s.push_str(&option_lines(&Self::flag_column(o), &doc, width));
            }
            if origin == Origin::Grammar {
                s.push_str(&option_lines(&help_col, HELP_DOC, width));
            }
        }
        if !self.outputs.is_empty() {
            s.push_str("\noutput formats (-o):\n");
            for (n, d) in self.outputs {
                s.push_str(&format!("  {n:<16}  {d}\n"));
            }
        }
        if !self.environment.is_empty() {
            s.push_str("\nenvironment:\n");
            for (n, d) in self.environment {
                s.push_str(&format!("  {n:<16}  {d}\n"));
            }
        }
        s.push_str("\nexit status:\n");
        for (c, d) in self.all_exit_codes() {
            s.push_str(&format!("  {c:<3} {d}\n"));
        }
        if !self.examples.is_empty() {
            s.push_str("\nexamples:\n");
            for (c, d) in self.examples {
                s.push_str(&format!("  {c}\n      {d}\n"));
            }
        }
        if !self.notes.is_empty() {
            s.push('\n');
            s.push_str(self.notes);
            if !self.notes.ends_with('\n') {
                s.push('\n');
            }
        }
        if let Some(schema) = self.schema {
            s.push_str(&format!(
                "\nschema of -o json: {schema}\n--help -o json prints this description as a record.\n"
            ));
        }
        s
    }

    fn all_exit_codes(&self) -> Vec<(i32, &'static str)> {
        let mut v: Vec<(i32, &'static str)> = self.exit_codes.to_vec();
        if !v.iter().any(|(c, _)| *c == exit::USAGE as i32) {
            v.push((
                exit::USAGE as i32,
                "the command line was wrong; nothing was done",
            ));
        }
        v
    }

    /// The description as a record, `kind: CommandHelp`
    /// (`lib/crates/cli/schemas/command-help.v1.json`).
    pub fn value(&self) -> Value {
        let s = |x: &str| Value::Str(x.to_string());
        let option = |short: Option<char>,
                      long: Option<&str>,
                      kind: &Kind,
                      doc: &str,
                      group: Option<&str>,
                      origin: Origin| {
            let mut m = vec![
                (
                    "short".into(),
                    short
                        .map(|c| Value::Str(format!("-{c}")))
                        .unwrap_or(Value::Null),
                ),
                (
                    "long".into(),
                    long.map(|l| Value::Str(format!("--{l}")))
                        .unwrap_or(Value::Null),
                ),
                ("type".into(), s(kind_name(kind))),
                ("origin".into(), s(origin.name())),
                ("takesValue".into(), Value::Bool(*kind != Kind::Flag)),
                (
                    "value".into(),
                    placeholder(kind).map(&s).unwrap_or(Value::Null),
                ),
                ("description".into(), s(doc)),
            ];
            let ch = choices(kind);
            if !ch.is_empty() {
                m.push((
                    "choices".into(),
                    Value::List(ch.iter().map(|c| s(c)).collect()),
                ));
            }
            if let Kind::Int { min, max, .. } = kind {
                m.push(("min".into(), Value::Int(*min)));
                m.push(("max".into(), Value::Int(*max)));
            }
            if let Some(g) = group {
                m.push(("exclusiveGroup".into(), s(g)));
            }
            Value::Map(m)
        };
        let mut options: Vec<Value> = self
            .options
            .iter()
            .map(|o| option(o.short, o.long, &o.kind, o.doc, o.group, o.origin))
            .collect();
        options.push(option(
            None,
            Some("help"),
            &Kind::Flag,
            HELP_DOC,
            None,
            Origin::Grammar,
        ));
        let pairs = |xs: &[(&str, &str)], k1: &str, k2: &str| {
            Value::List(
                xs.iter()
                    .map(|(a, b)| Value::Map(vec![(k1.to_string(), s(a)), (k2.to_string(), s(b))]))
                    .collect(),
            )
        };
        Value::Map(vec![
            ("apiVersion".into(), s("emibsd.org/v1")),
            ("kind".into(), s("CommandHelp")),
            ("name".into(), s(self.name)),
            ("summary".into(), s(self.summary)),
            (
                "synopsis".into(),
                s(&self
                    .synopsis
                    .lines()
                    .map(|l| format!("{} {l}", self.name))
                    .collect::<Vec<_>>()
                    .join("\n")),
            ),
            ("options".into(), Value::List(options)),
            ("outputs".into(), pairs(self.outputs, "name", "description")),
            ("schema".into(), self.schema.map(&s).unwrap_or(Value::Null)),
            (
                "exitCodes".into(),
                Value::List(
                    self.all_exit_codes()
                        .iter()
                        .map(|(c, d)| {
                            Value::Map(vec![
                                ("code".into(), Value::Int(*c as i64)),
                                ("meaning".into(), s(d)),
                            ])
                        })
                        .collect(),
                ),
            ),
            (
                "environment".into(),
                pairs(self.environment, "name", "effect"),
            ),
            ("examples".into(), pairs(self.examples, "command", "shows")),
            ("notes".into(), s(self.notes.trim())),
        ])
    }

    /// The help in the format `-o` asked: text for `name` and `table`, the record for the rest.
    pub fn help(&self, output: &Output) -> String {
        match output {
            Output::Json => self.value().to_json(true) + "\n",
            Output::Yaml => self.value().to_yaml(),
            _ => self.text(),
        }
    }
}

/// One option of the help text: the flag column, then the description wrapped at 80 columns
/// with the continuation lines under the description.
fn option_lines(flags: &str, doc: &str, width: usize) -> String {
    let indent = width + 4;
    let room = 80usize.saturating_sub(indent).max(20);
    let mut out = String::new();
    let mut first = true;
    let mut line = String::new();
    let flush = |line: &mut String, out: &mut String, first: &mut bool| {
        if *first {
            out.push_str(&format!("  {flags:<width$}  {line}\n"));
            *first = false;
        } else {
            out.push_str(&format!("{}{line}\n", " ".repeat(indent)));
        }
        line.clear();
    };
    for word in doc.split(' ') {
        if !line.is_empty() && line.len() + 1 + word.len() > room {
            flush(&mut line, &mut out, &mut first);
        }
        if !line.is_empty() {
            line.push(' ');
        }
        line.push_str(word);
    }
    if !line.is_empty() || first {
        flush(&mut line, &mut out, &mut first);
    }
    out
}

/// Splits a synopsis into words, keeping each bracketed group (`[-o format]`) whole.
fn synopsis_words(synopsis: &str) -> Vec<String> {
    let mut words = Vec::new();
    let mut cur = String::new();
    let mut depth = 0i32;
    for c in synopsis.chars() {
        match c {
            '[' | '{' | '(' => depth += 1,
            ']' | '}' | ')' => depth -= 1,
            _ => {}
        }
        if c == ' ' && depth <= 0 {
            if !cur.is_empty() {
                words.push(std::mem::take(&mut cur));
            }
        } else {
            cur.push(c);
        }
    }
    if !cur.is_empty() {
        words.push(cur);
    }
    // `source ...` is one word: the ellipsis never starts a line.
    let mut glued: Vec<String> = Vec::with_capacity(words.len());
    for w in words {
        match glued.last_mut() {
            Some(prev) if w == "..." => {
                prev.push(' ');
                prev.push_str(&w);
            }
            _ => glued.push(w),
        }
    }
    glued
}

fn placeholder(kind: &Kind) -> Option<&'static str> {
    match kind {
        Kind::Flag => None,
        Kind::Str(n)
        | Kind::Choice(n, _)
        | Kind::List(n, _)
        | Kind::Duration(n)
        | Kind::Size(n)
        | Kind::Path(n)
        | Kind::Field(n) => Some(n),
        Kind::Int { name, .. } => Some(name),
        Kind::Format => Some("FORMAT"),
    }
}

const FORMATS: &[&str] = &[
    "name",
    "table",
    "wide",
    "json",
    "yaml",
    "custom-columns=NAME:.path,...",
];

fn choices(kind: &Kind) -> &'static [&'static str] {
    match kind {
        Kind::Choice(_, c) | Kind::List(_, c) => c,
        Kind::Format => FORMATS,
        _ => &[],
    }
}

fn kind_name(kind: &Kind) -> &'static str {
    match kind {
        Kind::Flag => "flag",
        Kind::Str(_) => "string",
        Kind::Choice(..) => "choice",
        Kind::List(..) => "list",
        Kind::Int { .. } => "int",
        Kind::Duration(_) => "duration",
        Kind::Size(_) => "size",
        Kind::Path(_) => "path",
        Kind::Field(_) => "field",
        Kind::Format => "format",
    }
}

fn invalid(option: &str, message: String) -> ArgError {
    ArgError::Invalid {
        option: option.to_string(),
        message,
    }
}

fn one_of(set: &[&str]) -> String {
    set.join(", ")
}

/// Converts the raw value of an option to its declared type, or says what is wrong with it.
fn convert(kind: &Kind, raw: Option<String>, option: &str) -> Result<Typed, ArgError> {
    let Some(v) = raw else {
        return Ok(Typed::Flag);
    };
    Ok(match kind {
        Kind::Flag => Typed::Flag,
        Kind::Str(_) => Typed::Str(v),
        Kind::Choice(_, set) => match set.iter().find(|c| **c == v) {
            Some(c) => Typed::Choice(c),
            None => {
                return Err(invalid(
                    option,
                    format!("`{v}` is not one of {}", one_of(set)),
                ));
            }
        },
        Kind::List(_, set) => {
            let mut out = Vec::new();
            for part in v.split(',').filter(|p| !p.is_empty()) {
                match set.iter().find(|c| **c == part) {
                    Some(c) => out.push(*c),
                    None => {
                        return Err(invalid(
                            option,
                            format!("`{part}` is not one of {}", one_of(set)),
                        ));
                    }
                }
            }
            if out.is_empty() {
                return Err(invalid(
                    option,
                    format!("no value; one or more of {}", one_of(set)),
                ));
            }
            Typed::List(out)
        }
        Kind::Int { min, max, .. } => {
            let n: i64 = v
                .trim()
                .parse()
                .map_err(|_| invalid(option, format!("`{v}` is not a whole number")))?;
            if n < *min || n > *max {
                return Err(invalid(
                    option,
                    format!("`{v}` is not between {min} and {max}"),
                ));
            }
            Typed::Int(n)
        }
        Kind::Duration(_) => Typed::Duration(parse_duration(&v).map_err(|m| invalid(option, m))?),
        Kind::Size(_) => Typed::Size(parse_size(&v).map_err(|m| invalid(option, m))?),
        Kind::Path(_) => {
            if v.is_empty() {
                return Err(invalid(option, "an empty path".into()));
            }
            Typed::Path(v)
        }
        Kind::Field(_) => {
            let f = v.trim_start_matches('.');
            let ok = !f.is_empty()
                && f.chars()
                    .all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '_' | '-'));
            if !ok {
                return Err(invalid(
                    option,
                    format!("`{v}` is not a field path like .name or .meta.size"),
                ));
            }
            Typed::Field(f.to_string())
        }
        Kind::Format => Typed::Format(Output::parse(&v).map_err(|m| invalid(option, m))?),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    const X: Command = Command {
        name: "x",
        summary: "does x",
        synopsis: "[-a] [-o format] [--max-depth=n] [--type=t,...] [--since=d] [file ...]",
        options: &[
            OptSpec::flag(Some('a'), Some("all"), "everything"),
            OptSpec::value(Some('o'), Some("output"), Kind::Format, "the format")
                .in_group("format"),
            OptSpec::flag(Some('1'), None, "one per line").in_group("format"),
            OptSpec::value(
                None,
                Some("max-depth"),
                Kind::Int {
                    name: "N",
                    min: 0,
                    max: 64,
                },
                "how deep",
            ),
            OptSpec::value(
                None,
                Some("type"),
                Kind::List("T,...", &["file", "dir"]),
                "kinds",
            ),
            OptSpec::value(
                None,
                Some("since"),
                Kind::Duration("DURATION"),
                "how recent",
            ),
            OptSpec::value(None, Some("sort-by"), Kind::Field(".FIELD"), "the order"),
            OptSpec::value(None, Some("limit"), Kind::Size("SIZE"), "the size"),
            OptSpec::value(
                Some('m'),
                Some("mode"),
                Kind::Choice("MODE", &["fast", "slow"]),
                "the mode",
            )
            .bsd(),
        ],
        outputs: &[("json", "the record")],
        schema: Some("schemas/x.v1.json"),
        exit_codes: &[(0, "ok"), (1, "an error")],
        examples: &[("x -a", "all of it")],
        environment: &[("TZ", "the zone")],
        notes: "a note",
    };

    fn parse(s: &str) -> Result<Parsed, ArgError> {
        X.parse(s.split_whitespace().map(String::from))
    }

    #[test]
    fn typed_values_and_keys() {
        let p = parse(
            "-a1 -ojson --max-depth=3 --type=dir,file --since 2h --sort-by=.size --limit 10M -m slow f",
        )
        .unwrap();
        let keys: Vec<_> = p.given.iter().map(|g| g.key()).collect();
        assert_eq!(
            keys,
            [
                "all",
                "1",
                "output",
                "max-depth",
                "type",
                "since",
                "sort-by",
                "limit",
                "mode"
            ]
        );
        assert_eq!(p.given[2].value, Typed::Format(Output::Json));
        assert_eq!(p.given[3].value, Typed::Int(3));
        assert_eq!(p.given[4].value, Typed::List(vec!["dir", "file"]));
        assert_eq!(p.given[5].value, Typed::Duration(7200));
        assert_eq!(p.given[6].value, Typed::Field("size".into()));
        assert_eq!(p.given[7].value, Typed::Size(10 * 1024 * 1024));
        assert_eq!(p.given[8].value, Typed::Choice("slow"));
        assert_eq!(p.operands, ["f"]);
        assert_eq!(p.output(), Some(Output::Json));
        assert!(p.has("all") && !p.has("help"));
        assert_eq!(p.last("mode").and_then(Typed::text), Some("slow"));
    }

    #[test]
    fn wrong_values_are_refused_with_the_option_named() {
        let e = |s: &str| parse(s).unwrap_err().to_string();
        assert_eq!(e("--max-depth=x"), "--max-depth: `x` is not a whole number");
        assert_eq!(
            e("--max-depth=99"),
            "--max-depth: `99` is not between 0 and 64"
        );
        assert_eq!(e("--type=dir,zzz"), "--type: `zzz` is not one of file, dir");
        assert_eq!(e("-m x"), "-m: `x` is not one of fast, slow");
        assert!(e("--since=3y").starts_with("--since: `3y`"));
        assert!(e("-o xml").starts_with("-o: `xml` is not one of name, table"));
        assert_eq!(e("-z"), "unknown option -- z");
    }

    #[test]
    fn help_is_implied_and_takes_the_format_given_anywhere() {
        let p = parse("-o yaml --help").unwrap();
        assert!(p.help);
        assert_eq!(p.output(), Some(Output::Yaml));
        let t = X.text();
        assert!(
            t.starts_with("x: does x\n\nusage: x [-a] [-o format]"),
            "{t}"
        );
        assert!(t.contains("--max-depth N        how deep [0..64]"), "{t}");
        assert!(
            t.lines().all(|l| l.len() <= 80 || l.starts_with("usage")),
            "{t}"
        );
        assert!(
            t.contains("  -o, --output FORMAT  the format [name | table | wide | json | yaml |\n                       custom-columns=NAME:.path,...]\n"),
            "{t}"
        );
        assert!(t.contains("  --help "), "{t}");
        assert!(t.contains("  2   the command line was wrong"), "{t}");
        let v = X.value();
        assert_eq!(v.get(".kind").unwrap().to_cell(), "CommandHelp");
        let opts = match v.get(".options") {
            Some(Value::List(l)) => l.clone(),
            _ => panic!("options"),
        };
        assert_eq!(opts.len(), 10); // nine declared plus --help
        assert_eq!(opts[3].get("type").unwrap().to_cell(), "int");
        assert_eq!(opts[0].get("origin").unwrap().to_cell(), "posix");
        assert_eq!(opts[1].get("origin").unwrap().to_cell(), "grammar");
        assert_eq!(
            opts[3].get("origin").unwrap().to_cell(),
            "emibsd",
            "long-only is EmiBSD's"
        );
        assert_eq!(opts[8].get("origin").unwrap().to_cell(), "bsd");
        assert_eq!(
            opts[6].get("origin").unwrap().to_cell(),
            "grammar",
            "--sort-by"
        );
        assert_eq!(
            opts[9].get("origin").unwrap().to_cell(),
            "grammar",
            "--help"
        );
        assert_eq!(opts[3].get("max").unwrap().to_cell(), "64");
        assert_eq!(opts[1].get("exclusiveGroup").unwrap().to_cell(), "format");
        assert_eq!(opts[9].get("long").unwrap().to_cell(), "--help");
        let j = X.help(&Output::Json);
        assert!(j.contains("\"short\": \"-o\""), "{j}");
        assert!(
            X.help(&Output::Yaml)
                .starts_with("apiVersion: emibsd.org/v1\nkind: CommandHelp\n")
        );
    }

    #[test]
    fn usage_wraps_at_eighty_columns_keeping_groups_whole() {
        const LONG: Command = Command {
            synopsis: "[-1AacdFghiklnpqRrSstuHL] [-o format] [--sort-by=.field] [--type=t,...] [--since=duration] [--max-depth=n] [--no-headers] [--flags] [file ...]",
            ..X
        };
        let u = LONG.usage();
        let lines: Vec<&str> = u.lines().collect();
        assert!(lines.len() >= 2, "{u}");
        assert!(lines.iter().all(|l| l.len() <= 80), "{u}");
        assert!(lines[0].starts_with("usage: x [-1AacdFghiklnpqRrSstuHL] [-o format]"));
        assert!(lines[1].starts_with("         ["), "{u}");
        assert_eq!(X.usage(), format!("usage: x {}", X.synopsis));
        const TWO: Command = Command {
            synopsis: "[-a] source target\n[-a] source ... directory",
            ..X
        };
        assert_eq!(
            TWO.usage(),
            "usage: x [-a] source target\n       x [-a] source ... directory"
        );
        assert_eq!(
            TWO.value().get(".synopsis").unwrap().to_cell(),
            "x [-a] source target\nx [-a] source ... directory"
        );
    }

    #[test]
    fn run_handles_help_and_errors() {
        assert!(X.run(["-a".to_string()]).is_ok());
        assert_eq!(X.run(["--help".to_string()]), Err(ExitCode::SUCCESS));
        assert_eq!(X.run(["-z".to_string()]), Err(ExitCode::from(exit::USAGE)));
    }
}
