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

//! Option parsing with POSIX's rules, plus long options.
//!
//! Short options cluster (`-la`), a short option's value may be attached or the next word
//! (`-ojson`, `-o json`), a long option's value is attached with `=` or the next word
//! (`--sort-by=.size`, `--sort-by .size`), `--` ends the options, and the first word that
//! is not an option ends them too, as `getopt(3)` does on the BSDs: what follows are the
//! operands. Options are returned in the order given, because for many programs the last
//! of a group wins.

use std::fmt;

/// What a program accepts.
#[derive(Debug, Clone, Copy)]
pub struct Spec {
    /// Short options that take no value, e.g. `"1AacdFghiklnpqRrSstuHL"`.
    pub short_flags: &'static str,
    /// Short options that take a value, e.g. `"o"`.
    pub short_with_value: &'static str,
    /// Long options that take no value, without the dashes.
    pub long_flags: &'static [&'static str],
    /// Long options that take a value, without the dashes.
    pub long_with_value: &'static [&'static str],
}

/// One option as given: its name (a single character for a short one) and its value.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Opt {
    /// `"l"` for `-l`, `"sort-by"` for `--sort-by`.
    pub name: String,
    /// The value, for options that take one.
    pub value: Option<String>,
}

/// The options in order, then the operands.
#[derive(Debug, Default, Clone, PartialEq, Eq)]
pub struct Parsed {
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
}

impl fmt::Display for ArgError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ArgError::Unknown(o) => write!(f, "unknown option -- {o}"),
            ArgError::MissingValue(o) => write!(f, "option requires an argument -- {o}"),
            ArgError::UnexpectedValue(o) => write!(f, "option does not take an argument -- {o}"),
        }
    }
}

impl std::error::Error for ArgError {}

impl Spec {
    /// Parses `args` (without the program name) against this spec.
    pub fn parse<I: IntoIterator<Item = String>>(&self, args: I) -> Result<Parsed, ArgError> {
        let mut it = args.into_iter().peekable();
        let mut out = Parsed::default();
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
                if self.long_with_value.contains(&name.as_str()) {
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
                } else if self.long_flags.contains(&name.as_str()) {
                    if attached.is_some() {
                        return Err(ArgError::UnexpectedValue(name));
                    }
                    out.opts.push(Opt { name, value: None });
                } else {
                    return Err(ArgError::Unknown(name));
                }
                continue;
            }
            if word.len() > 1 && word.starts_with('-') {
                let mut chars = word[1..].chars();
                while let Some(c) = chars.next() {
                    if self.short_with_value.contains(c) {
                        let rest: String = chars.collect();
                        let value = if rest.is_empty() {
                            it.next()
                                .ok_or_else(|| ArgError::MissingValue(c.to_string()))?
                        } else {
                            rest
                        };
                        out.opts.push(Opt {
                            name: c.to_string(),
                            value: Some(value),
                        });
                        break;
                    } else if self.short_flags.contains(c) {
                        out.opts.push(Opt {
                            name: c.to_string(),
                            value: None,
                        });
                    } else {
                        return Err(ArgError::Unknown(c.to_string()));
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
}

#[cfg(test)]
mod tests {
    use super::*;

    const LS: Spec = Spec {
        short_flags: "la1",
        short_with_value: "o",
        long_flags: &["no-headers"],
        long_with_value: &["sort-by"],
    };

    fn parse(s: &str) -> Result<Parsed, ArgError> {
        LS.parse(s.split_whitespace().map(String::from))
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
    }

    #[test]
    fn a_lone_dash_is_an_operand() {
        let p = parse("-").unwrap();
        assert_eq!(p.operands, ["-"]);
    }
}
