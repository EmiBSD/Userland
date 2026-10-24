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

//! The lexical half of option parsing, with POSIX's rules plus long options.
//!
//! Short options cluster (`-la`), a short option's value may be attached or the next word
//! (`-ojson`, `-o json`), a long option's value is attached with `=` or the next word
//! (`--sort-by=.size`, `--sort-by .size`), `--` ends the options, and the first word that
//! is not an option ends them too, as `getopt(3)` does on the BSDs: what follows are the
//! operands. Options come back in the order given, because for many programs the last of a
//! group wins. What each option is, and what its value means, is [`crate::Command`]'s
//! business: this module only asks it whether a name is a flag, takes a value, or is unknown.

use std::fmt;

/// One option as given: its name (a single character for a short one) and its raw value.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Opt {
    /// `"l"` for `-l`, `"sort-by"` for `--sort-by`.
    pub name: String,
    /// The value, for options that take one.
    pub value: Option<String>,
}

/// The options in order, then the operands, before any value is typed.
#[derive(Debug, Default, Clone, PartialEq, Eq)]
pub struct Raw {
    /// The options, in the order given.
    pub opts: Vec<Opt>,
    /// Everything after the options.
    pub operands: Vec<String>,
}

/// Why a command line was refused.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ArgError {
    /// An option the program does not have.
    Unknown(String),
    /// An option that takes a value, given last with none.
    MissingValue(String),
    /// A long option given a value it does not take.
    UnexpectedValue(String),
    /// A value that is not of the option's type: `option` as the user wrote it (`-o`,
    /// `--max-depth`), `message` what was expected.
    Invalid {
        /// The option, with its dashes.
        option: String,
        /// What is wrong with the value, a complete sentence fragment.
        message: String,
    },
}

impl fmt::Display for ArgError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ArgError::Unknown(o) => write!(f, "unknown option -- {o}"),
            ArgError::MissingValue(o) => write!(f, "option requires an argument -- {o}"),
            ArgError::UnexpectedValue(o) => write!(f, "option does not take an argument -- {o}"),
            ArgError::Invalid { option, message } => write!(f, "{option}: {message}"),
        }
    }
}

impl std::error::Error for ArgError {}

/// Splits `args` (without the program name) into options and operands. `classify(name)`
/// answers for the long name or the one-character short name: `Some(true)` for an option
/// that takes a value, `Some(false)` for a flag, `None` for an option the program lacks.
pub fn lex<I, F>(args: I, classify: F) -> Result<Raw, ArgError>
where
    I: IntoIterator<Item = String>,
    F: Fn(&str) -> Option<bool>,
{
    let mut it = args.into_iter();
    let mut out = Raw::default();
    while let Some(word) = it.next() {
        if word == "--" {
            out.operands.extend(it);
            break;
        }
        if let Some(long) = word.strip_prefix("--") {
            let (name, attached) = match long.split_once('=') {
                Some((n, v)) => (n.to_string(), Some(v.to_string())),
                None => (long.to_string(), None),
            };
            match classify(&name) {
                Some(true) => {
                    let value = match attached {
                        Some(v) => v,
                        None => it
                            .next()
                            .ok_or_else(|| ArgError::MissingValue(name.clone()))?,
                    };
                    out.opts.push(Opt {
                        name,
                        value: Some(value),
                    });
                }
                Some(false) => {
                    if attached.is_some() {
                        return Err(ArgError::UnexpectedValue(name));
                    }
                    out.opts.push(Opt { name, value: None });
                }
                None => return Err(ArgError::Unknown(name)),
            }
            continue;
        }
        if word.len() > 1 && word.starts_with('-') {
            let mut chars = word[1..].chars();
            while let Some(c) = chars.next() {
                let name = c.to_string();
                match classify(&name) {
                    Some(true) => {
                        let rest: String = chars.collect();
                        let value = if rest.is_empty() {
                            it.next()
                                .ok_or_else(|| ArgError::MissingValue(name.clone()))?
                        } else {
                            rest
                        };
                        out.opts.push(Opt {
                            name,
                            value: Some(value),
                        });
                        break;
                    }
                    Some(false) => out.opts.push(Opt { name, value: None }),
                    None => return Err(ArgError::Unknown(name)),
                }
            }
            continue;
        }
        out.operands.push(word);
        out.operands.extend(it);
        break;
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn classify(name: &str) -> Option<bool> {
        match name {
            "l" | "a" | "1" | "no-headers" => Some(false),
            "o" | "sort-by" => Some(true),
            _ => None,
        }
    }

    fn parse(s: &str) -> Result<Raw, ArgError> {
        lex(s.split_whitespace().map(String::from), classify)
    }

    #[test]
    fn clusters_and_values() {
        let p =
            parse("-la -ojson -o yaml --sort-by=.size --sort-by .name --no-headers a b").unwrap();
        let names: Vec<_> = p
            .opts
            .iter()
            .map(|o| (o.name.as_str(), o.value.as_deref()))
            .collect();
        assert_eq!(
            names,
            [
                ("l", None),
                ("a", None),
                ("o", Some("json")),
                ("o", Some("yaml")),
                ("sort-by", Some(".size")),
                ("sort-by", Some(".name")),
                ("no-headers", None)
            ]
        );
        assert_eq!(p.operands, ["a", "b"]);
    }

    #[test]
    fn the_first_operand_ends_the_options_and_so_does_a_double_dash() {
        let p = parse("-l dir -a").unwrap();
        assert_eq!(p.opts.len(), 1);
        assert_eq!(p.operands, ["dir", "-a"]);
        let p = parse("-- -l").unwrap();
        assert!(p.opts.is_empty());
        assert_eq!(p.operands, ["-l"]);
    }

    #[test]
    fn errors() {
        assert_eq!(parse("-z"), Err(ArgError::Unknown("z".into())));
        assert_eq!(parse("-o"), Err(ArgError::MissingValue("o".into())));
        assert_eq!(
            parse("--no-headers=1"),
            Err(ArgError::UnexpectedValue("no-headers".into()))
        );
        assert_eq!(parse("--bogus"), Err(ArgError::Unknown("bogus".into())));
        assert_eq!(
            ArgError::Invalid {
                option: "--max-depth".into(),
                message: "`x` is not a whole number".into()
            }
            .to_string(),
            "--max-depth: `x` is not a whole number"
        );
    }

    /// A property, with a generator of our own (no dependency): any sequence of known
    /// flags, valued options and operands, spelled in any of the accepted ways (clustered,
    /// attached or separate values, `=` or a word for long ones), lexes back to the same
    /// sequence, with the operands intact after the first one.
    #[test]
    fn every_spelling_of_a_command_line_lexes_back_to_the_same_sequence() {
        let mut seed: u64 = 0x9e37_79b9_7f4a_7c15;
        let mut next = || {
            seed = seed
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            (seed >> 33) as usize
        };
        for _ in 0..500 {
            let n = next() % 6;
            let mut want: Vec<(&str, Option<&str>)> = Vec::new();
            let mut words: Vec<String> = Vec::new();
            let mut cluster = String::new();
            for _ in 0..n {
                match next() % 5 {
                    0 => {
                        want.push(("l", None));
                        cluster.push('l');
                    }
                    1 => {
                        want.push(("a", None));
                        cluster.push('a');
                    }
                    2 => {
                        let v = ["json", "yaml", "name"][next() % 3];
                        want.push(("o", Some(v)));
                        if next() % 2 == 0 {
                            words.push(format!("-{cluster}o{v}"));
                        } else {
                            words.push(format!("-{cluster}o"));
                            words.push(v.to_string());
                        }
                        cluster.clear();
                    }
                    3 => {
                        if !cluster.is_empty() {
                            words.push(format!("-{cluster}"));
                            cluster.clear();
                        }
                        want.push(("no-headers", None));
                        words.push("--no-headers".to_string());
                    }
                    _ => {
                        if !cluster.is_empty() {
                            words.push(format!("-{cluster}"));
                            cluster.clear();
                        }
                        let v = [".size", ".name"][next() % 2];
                        want.push(("sort-by", Some(v)));
                        if next() % 2 == 0 {
                            words.push(format!("--sort-by={v}"));
                        } else {
                            words.push("--sort-by".to_string());
                            words.push(v.to_string());
                        }
                    }
                }
            }
            if !cluster.is_empty() {
                words.push(format!("-{cluster}"));
            }
            // The first operand is a plain word (an option there would be parsed as one);
            // after it anything goes, including what looks like an option.
            let operands: Vec<String> = (0..next() % 3)
                .map(|i| {
                    if i == 0 {
                        ["file", "dir/"][next() % 2].to_string()
                    } else {
                        ["file", "-x", "--", "dir/"][next() % 4].to_string()
                    }
                })
                .collect();
            words.extend(operands.iter().cloned());
            let got = lex(words.clone(), classify).unwrap_or_else(|e| panic!("{words:?}: {e}"));
            let got_opts: Vec<(&str, Option<&str>)> = got
                .opts
                .iter()
                .map(|o| (o.name.as_str(), o.value.as_deref()))
                .collect();
            assert_eq!(got_opts, want, "{words:?}");
            assert_eq!(got.operands, operands, "{words:?}");
        }
    }

    #[test]
    fn a_lone_dash_is_an_operand() {
        let p = parse("-").unwrap();
        assert_eq!(p.operands, ["-"]);
    }
}
