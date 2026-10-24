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
//! The POSIX short flags keep their meaning (`-R -H -L -P -f -i -p`), OpenBSD's `-a` and `-v`
//! too; the common grammar adds `-o` (every copy as a record), `--dry-run` and
//! `--no-headers`. `-f` and `-i` undo each other, the last one wins; `-H`, `-L` and `-P`
//! likewise, and mean nothing without `-R`.

use std::io::IsTerminal;

use cli::{Command, Kind, OptSpec, Output, Parsed, Typed};

/// The program's own description: `--help` prints it as text, `--help -o json` as a record.
pub const COMMAND: Command = Command {
    name: "cp",
    summary: "copy files and directories",
    synopsis: "[-afipv] [-R [-H | -L | -P]] [-o format] [--dry-run] source target\n[-afipv] [-R [-H | -L | -P]] [-o format] [--dry-run] source ... directory",
    options: &[
        OptSpec::flag(
            Some('R'),
            Some("recursive"),
            "copy directories with everything below; symbolic links are copied as links and special files recreated",
        ),
        OptSpec::flag(
            Some('H'),
            None,
            "with -R, follow the symbolic links named on the command line only",
        )
        .in_group("follow"),
        OptSpec::flag(Some('L'), None, "with -R, follow every symbolic link").in_group("follow"),
        OptSpec::flag(
            Some('P'),
            None,
            "with -R, follow no symbolic link (the default)",
        )
        .in_group("follow"),
        OptSpec::flag(Some('a'), Some("archive"), "the same as -R -p -P"),
        OptSpec::flag(
            Some('f'),
            Some("force"),
            "remove an existing target before copying, without asking",
        )
        .in_group("overwrite"),
        OptSpec::flag(
            Some('i'),
            Some("interactive"),
            "ask on standard error before overwriting; a reply starting with y copies",
        )
        .in_group("overwrite"),
        OptSpec::flag(
            Some('p'),
            Some("preserve"),
            "keep the times, mode, owner, group and file flags, as far as permissions allow",
        ),
        OptSpec::flag(
            Some('v'),
            Some("verbose"),
            "print `source -> target` after each copy",
        ),
        OptSpec::value(
            Some('o'),
            Some("output"),
            Kind::Format,
            "print every copy as a record: the targets (name), a table, every field (wide), json, yaml or custom columns",
        ),
        OptSpec::flag(
            None,
            Some("dry-run"),
            "plan and report every copy, write nothing",
        ),
        OptSpec::flag(None, Some("no-headers"), "no header line on tables"),
    ],
    outputs: &[
        ("name", "the target of each copy, one per line"),
        ("table", "SOURCE TARGET TYPE SIZE ACTION"),
        ("wide", "every field of the record as a table"),
        ("json", "a CopyList document: apiVersion, kind, items"),
        ("yaml", "the same document as YAML"),
        (
            "custom-columns=SRC:.source,DST:.target",
            "the fields you choose",
        ),
    ],
    schema: Some("bin/files/cp/schemas/copy.v1.json"),
    exit_codes: &[
        (0, "everything was copied"),
        (1, "something could not be copied; the rest was"),
    ],
    examples: &[
        ("cp foo bar", "a copy of foo named bar"),
        ("cp *.txt /tmp", "the files into a directory"),
        ("cp -R junk /tmp", "a directory and everything below it"),
        (
            "cp -a src dst",
            "an archive: the tree, links as links, times and modes kept",
        ),
        (
            "cp -R --dry-run -o json src dst",
            "what would be copied, as records, without writing",
        ),
        ("cp -Rv src dst | wc -l", "how many things were copied"),
    ],
    environment: &[],
    notes: "Without -R every symbolic link is followed and a directory is refused. An existing target file keeps its mode, owner and group; a new one gets the source's mode shaped by the umask, set-user-ID and set-group-ID bits dropped unless the owner matches. Regions of zero bytes are written as holes.",
};

/// Which symbolic links are followed under `-R`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Follow {
    /// `-P`: none, the default with `-R`.
    Never,
    /// `-H`: only the operands.
    CommandLine,
    /// `-L`: every one; also the rule without `-R`.
    Always,
}

/// What happens when the target exists.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Overwrite {
    /// Open it and write over it, keeping its mode and owner.
    Replace,
    /// `-f`: remove it first.
    Force,
    /// `-i`: ask.
    Ask,
}

/// Everything the walk, the copier and the reporter need, consistent by construction.
#[derive(Debug, Clone)]
pub struct Config {
    /// The sources, in order.
    pub sources: Vec<String>,
    /// The last operand.
    pub target: String,
    pub recursive: bool,
    pub follow: Follow,
    pub overwrite: Overwrite,
    pub preserve: bool,
    pub verbose: bool,
    /// `-o`: records instead of silence.
    pub output: Option<Output>,
    pub dry_run: bool,
    /// A header on tables: on a terminal unless `--no-headers`.
    pub headers: bool,
}

impl Config {
    /// From a command line `COMMAND` accepted. The one thing left to check is the operand
    /// count: fewer than two is a usage error.
    pub fn from_parsed(parsed: Parsed) -> Result<Config, String> {
        let mut operands = parsed.operands;
        if operands.len() < 2 {
            return Err("a source and a target are required".into());
        }
        let target = operands.pop().expect("two operands");
        let tty = std::io::stdout().is_terminal();
        let mut c = Config {
            sources: operands,
            target,
            recursive: false,
            follow: Follow::Never,
            overwrite: Overwrite::Replace,
            preserve: false,
            verbose: false,
            output: None,
            dry_run: false,
            headers: tty,
        };
        for g in parsed.given {
            match (g.key(), g.value) {
                ("recursive", _) => c.recursive = true,
                ("H", _) => c.follow = Follow::CommandLine,
                ("L", _) => c.follow = Follow::Always,
                ("P", _) => c.follow = Follow::Never,
                ("archive", _) => {
                    c.recursive = true;
                    c.preserve = true;
                    c.follow = Follow::Never;
                }
                ("force", _) => c.overwrite = Overwrite::Force,
                ("interactive", _) => c.overwrite = Overwrite::Ask,
                ("preserve", _) => c.preserve = true,
                ("verbose", _) => c.verbose = true,
                ("output", Typed::Format(o)) => c.output = Some(o),
                ("dry-run", _) => c.dry_run = true,
                ("no-headers", _) => c.headers = false,
                _ => {}
            }
        }
        // Without -R every link is followed, whatever -H, -L or -P said (POSIX).
        if !c.recursive {
            c.follow = Follow::Always;
        }
        Ok(c)
    }

    /// Whether a symbolic link found as an operand is followed.
    pub fn follow_operand(&self) -> bool {
        self.follow != Follow::Never
    }

    /// Whether a symbolic link found below an operand is followed.
    pub fn follow_below(&self) -> bool {
        self.follow == Follow::Always
    }

    /// The `pledge(2)` promises this configuration needs, derived from what it will do:
    /// `dpath` only to recreate FIFOs and device nodes under `-R`, `chown` only to give a
    /// copy its owner under `-p`.
    pub fn promises(&self) -> String {
        let mut p = String::from("stdio rpath wpath cpath fattr");
        if self.recursive {
            p.push_str(" dpath");
        }
        if self.preserve {
            p.push_str(" chown");
        }
        p
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
        .expect("two operands")
    }

    #[test]
    fn operands_split_into_sources_and_target() {
        let c = cfg("a b c");
        assert_eq!(c.sources, ["a", "b"]);
        assert_eq!(c.target, "c");
        assert!(Config::from_parsed(COMMAND.parse(["a".to_string()]).unwrap()).is_err());
    }

    #[test]
    fn the_last_of_a_group_wins_and_follow_means_nothing_without_r() {
        assert_eq!(cfg("-fi a b").overwrite, Overwrite::Ask);
        assert_eq!(cfg("-if a b").overwrite, Overwrite::Force);
        assert_eq!(cfg("-R -H -L a b").follow, Follow::Always);
        assert_eq!(cfg("-RLP a b").follow, Follow::Never);
        assert_eq!(cfg("-RH a b").follow, Follow::CommandLine);
        assert_eq!(
            cfg("-P a b").follow,
            Follow::Always,
            "no -R: every link is followed"
        );
        assert_eq!(cfg("-R a b").follow, Follow::Never);
        let a = cfg("-a a b");
        assert!(a.recursive && a.preserve && a.follow == Follow::Never);
    }

    #[test]
    fn promises_follow_the_configuration() {
        assert_eq!(cfg("a b").promises(), "stdio rpath wpath cpath fattr");
        assert_eq!(
            cfg("-R a b").promises(),
            "stdio rpath wpath cpath fattr dpath"
        );
        assert_eq!(
            cfg("-a a b").promises(),
            "stdio rpath wpath cpath fattr dpath chown"
        );
    }
}
