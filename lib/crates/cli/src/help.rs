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

//! `--help` as data. A program describes itself once, as a [`Help`]; `--help` prints it as
//! text, and `--help -o json` (or `yaml`) prints the same description as a record, so a
//! tool, an agent or an MCP server can read what the program accepts and what it emits
//! without parsing prose (the user's decision of 2026-10-24).

use crate::render::Output;
use crate::value::Value;

/// One option.
#[derive(Debug, Clone, Copy)]
pub struct OptDoc {
    /// The short form, `l` for `-l`.
    pub short: Option<char>,
    /// The long form, `sort-by` for `--sort-by`.
    pub long: Option<&'static str>,
    /// The name of its value, when it takes one: `FORMAT`, `.FIELD`.
    pub value: Option<&'static str>,
    /// What it does, one sentence.
    pub doc: &'static str,
    /// The values it accepts, when they are a fixed set.
    pub choices: &'static [&'static str],
    /// The group of mutually exclusive options it belongs to, if any; the last one wins.
    pub group: Option<&'static str>,
}

/// A program's description.
#[derive(Debug, Clone, Copy)]
pub struct Help {
    /// `ls`.
    pub name: &'static str,
    /// One line.
    pub summary: &'static str,
    /// The synopsis line(s), without the program name.
    pub synopsis: &'static str,
    /// Every option.
    pub options: &'static [OptDoc],
    /// The `-o` formats: `(name, what it prints)`.
    pub outputs: &'static [(&'static str, &'static str)],
    /// The record schema `-o json` follows, as a path in the repository.
    pub schema: Option<&'static str>,
    /// Exit codes and their meaning.
    pub exit_codes: &'static [(i32, &'static str)],
    /// `(command, what it shows)`.
    pub examples: &'static [(&'static str, &'static str)],
    /// Environment variables read: `(name, effect)`.
    pub environment: &'static [(&'static str, &'static str)],
    /// What a human should know besides the options.
    pub notes: &'static str,
}

impl Help {
    /// The text a terminal gets.
    pub fn text(&self) -> String {
        let mut s = format!(
            "{}: {}\n\nusage: {} {}\n\noptions:\n",
            self.name, self.summary, self.name, self.synopsis
        );
        let flag = |o: &OptDoc| {
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
            if let Some(v) = o.value {
                f.push(' ');
                f.push_str(v);
            }
            f
        };
        let width = self
            .options
            .iter()
            .map(|o| flag(o).len())
            .max()
            .unwrap_or(0)
            .min(28);
        for o in self.options {
            let f = flag(o);
            let mut line = format!("  {f:<width$}  {}", o.doc);
            if !o.choices.is_empty() {
                line.push_str(&format!(" [{}]", o.choices.join(" | ")));
            }
            s.push_str(&line);
            s.push('\n');
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
        if !self.exit_codes.is_empty() {
            s.push_str("\nexit status:\n");
            for (c, d) in self.exit_codes {
                s.push_str(&format!("  {c:<3} {d}\n"));
            }
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
            s.push_str(&format!("\nschema of -o json: {schema}\n--help -o json prints this description as a record.\n"));
        }
        s
    }

    /// The description as a record, `kind: CommandHelp`.
    pub fn value(&self) -> Value {
        let s = |x: &str| Value::Str(x.to_string());
        let options = self
            .options
            .iter()
            .map(|o| {
                let mut m = vec![];
                m.push((
                    "short".into(),
                    o.short
                        .map(|c| Value::Str(format!("-{c}")))
                        .unwrap_or(Value::Null),
                ));
                m.push((
                    "long".into(),
                    o.long
                        .map(|l| Value::Str(format!("--{l}")))
                        .unwrap_or(Value::Null),
                ));
                m.push(("takesValue".into(), Value::Bool(o.value.is_some())));
                m.push(("value".into(), o.value.map(&s).unwrap_or(Value::Null)));
                m.push(("description".into(), s(o.doc)));
                if !o.choices.is_empty() {
                    m.push((
                        "choices".into(),
                        Value::List(o.choices.iter().map(|c| s(c)).collect()),
                    ));
                }
                if let Some(g) = o.group {
                    m.push(("exclusiveGroup".into(), s(g)));
                }
                Value::Map(m)
            })
            .collect();
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
                s(&format!("{} {}", self.name, self.synopsis)),
            ),
            ("options".into(), Value::List(options)),
            ("outputs".into(), pairs(self.outputs, "name", "description")),
            ("schema".into(), self.schema.map(&s).unwrap_or(Value::Null)),
            (
                "exitCodes".into(),
                Value::List(
                    self.exit_codes
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
    pub fn render(&self, output: &Output) -> String {
        match output {
            Output::Json => self.value().to_json(true) + "\n",
            Output::Yaml => self.value().to_yaml(),
            _ => self.text(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const H: Help = Help {
        name: "x",
        summary: "does x",
        synopsis: "[-a] [file ...]",
        options: &[
            OptDoc {
                short: Some('a'),
                long: Some("all"),
                value: None,
                doc: "everything",
                choices: &[],
                group: None,
            },
            OptDoc {
                short: Some('o'),
                long: Some("output"),
                value: Some("FORMAT"),
                doc: "the format",
                choices: &["json", "yaml"],
                group: Some("format"),
            },
        ],
        outputs: &[("json", "the record")],
        schema: Some("schemas/x.v1.json"),
        exit_codes: &[(0, "ok"), (1, "an error")],
        examples: &[("x -a", "all of it")],
        environment: &[("TZ", "the zone")],
        notes: "a note",
    };

    #[test]
    fn text_and_record() {
        let t = H.text();
        assert!(
            t.starts_with("x: does x\n\nusage: x [-a] [file ...]\n\noptions:\n  -a, --all"),
            "{t}"
        );
        assert!(
            t.contains("-o, --output FORMAT  the format [json | yaml]"),
            "{t}"
        );
        let v = H.value();
        assert_eq!(v.get(".kind").unwrap().to_cell(), "CommandHelp");
        assert_eq!(
            v.get(".options")
                .map(|o| matches!(o, Value::List(l) if l.len() == 2)),
            Some(true)
        );
        let j = H.render(&Output::Json);
        assert!(j.contains("\"short\": \"-o\""), "{j}");
        assert!(j.contains("\"exclusiveGroup\": \"format\""), "{j}");
        assert!(
            H.render(&Output::Yaml)
                .starts_with("apiVersion: emibsd.org/v1\nkind: CommandHelp\n")
        );
    }
}
