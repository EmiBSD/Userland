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

//! The record: an ordered, dynamically typed value with JSON and YAML writers of its own,
//! so a program needs no serialisation dependency to speak the common grammar.

use std::cmp::Ordering;
use std::fmt::Write as _;

/// A value of a record. Maps keep their order: it is the order of the schema and of the
/// columns the user sees.
#[derive(Debug, Clone, PartialEq)]
pub enum Value {
    /// Absent or not applicable.
    Null,
    /// A boolean.
    Bool(bool),
    /// A signed integer.
    Int(i64),
    /// An unsigned integer.
    UInt(u64),
    /// Text.
    Str(String),
    /// A sequence.
    List(Vec<Value>),
    /// An ordered mapping.
    Map(Vec<(String, Value)>),
}

impl Value {
    /// The field `path` names, `.a.b` or `a.b`, through nested maps.
    pub fn get(&self, path: &str) -> Option<&Value> {
        let mut cur = self;
        for part in path
            .trim_start_matches('.')
            .split('.')
            .filter(|p| !p.is_empty())
        {
            match cur {
                Value::Map(m) => cur = &m.iter().find(|(k, _)| k == part)?.1,
                _ => return None,
            }
        }
        Some(cur)
    }

    /// Adds or replaces the field `key` of a map.
    pub fn set(&mut self, key: &str, v: Value) {
        if let Value::Map(m) = self {
            if let Some(slot) = m.iter_mut().find(|(k, _)| k == key) {
                slot.1 = v;
            } else {
                m.push((key.to_string(), v));
            }
        }
    }

    /// The value as one table cell: text as is, numbers and booleans spelled out, nothing
    /// for null, a list joined by commas, a map as JSON.
    pub fn to_cell(&self) -> String {
        match self {
            Value::Null => String::new(),
            Value::Bool(b) => b.to_string(),
            Value::Int(i) => i.to_string(),
            Value::UInt(u) => u.to_string(),
            Value::Str(s) => s.clone(),
            Value::List(l) => l.iter().map(Value::to_cell).collect::<Vec<_>>().join(","),
            Value::Map(_) => self.to_json(false),
        }
    }

    /// The order `--sort-by` uses: numbers numerically (signed and unsigned together),
    /// text byte by byte, booleans false first, null last, lists and maps by their JSON.
    pub fn sort_cmp(&self, other: &Value) -> Ordering {
        fn num(v: &Value) -> Option<i128> {
            match v {
                Value::Int(i) => Some(*i as i128),
                Value::UInt(u) => Some(*u as i128),
                _ => None,
            }
        }
        match (self, other) {
            (Value::Null, Value::Null) => Ordering::Equal,
            (Value::Null, _) => Ordering::Greater,
            (_, Value::Null) => Ordering::Less,
            (Value::Bool(a), Value::Bool(b)) => a.cmp(b),
            (Value::Str(a), Value::Str(b)) => a.as_bytes().cmp(b.as_bytes()),
            _ => match (num(self), num(other)) {
                (Some(a), Some(b)) => a.cmp(&b),
                _ => self.to_json(false).cmp(&other.to_json(false)),
            },
        }
    }

    /// JSON, compact or indented by two spaces.
    pub fn to_json(&self, pretty: bool) -> String {
        let mut s = String::new();
        write_json(self, pretty, 0, &mut s);
        s
    }

    /// YAML in block style, one document without the `---` marker.
    pub fn to_yaml(&self) -> String {
        let mut s = String::new();
        write_yaml(self, 0, &mut s, false);
        if !s.ends_with('\n') {
            s.push('\n');
        }
        s
    }
}

fn json_string(s: &str, out: &mut String) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 || c == '\u{7f}' => {
                let _ = write!(out, "\\u{:04x}", c as u32);
            }
            c => out.push(c),
        }
    }
    out.push('"');
}

fn write_json(v: &Value, pretty: bool, depth: usize, out: &mut String) {
    let nl = |out: &mut String, d: usize| {
        if pretty {
            out.push('\n');
            for _ in 0..d {
                out.push_str("  ");
            }
        }
    };
    match v {
        Value::Null => out.push_str("null"),
        Value::Bool(b) => out.push_str(if *b { "true" } else { "false" }),
        Value::Int(i) => {
            let _ = write!(out, "{i}");
        }
        Value::UInt(u) => {
            let _ = write!(out, "{u}");
        }
        Value::Str(s) => json_string(s, out),
        Value::List(l) => {
            out.push('[');
            for (i, x) in l.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                nl(out, depth + 1);
                write_json(x, pretty, depth + 1, out);
            }
            if !l.is_empty() {
                nl(out, depth);
            }
            out.push(']');
        }
        Value::Map(m) => {
            out.push('{');
            for (i, (k, x)) in m.iter().enumerate() {
                if i > 0 {
                    out.push(',');
                }
                nl(out, depth + 1);
                json_string(k, out);
                out.push(':');
                if pretty {
                    out.push(' ');
                }
                write_json(x, pretty, depth + 1, out);
            }
            if !m.is_empty() {
                nl(out, depth);
            }
            out.push('}');
        }
    }
}

/// Whether YAML would misread `s` as something other than the plain string it is.
fn yaml_needs_quotes(s: &str) -> bool {
    if s.is_empty() || s != s.trim() {
        return true;
    }
    let lower = s.to_ascii_lowercase();
    if matches!(
        lower.as_str(),
        "true" | "false" | "null" | "~" | "yes" | "no" | "on" | "off"
    ) {
        return true;
    }
    if s.parse::<f64>().is_ok() || s.starts_with("0x") || s.starts_with("0o") {
        return true;
    }
    let first = s.chars().next().unwrap_or(' ');
    if "-?:,[]{}#&*!|>'\"%@`".contains(first) {
        return true;
    }
    s.contains(": ")
        || s.ends_with(':')
        || s.contains(" #")
        || s.chars().any(|c| (c as u32) < 0x20 || c == '\u{7f}')
}

fn yaml_scalar(s: &str, out: &mut String) {
    if yaml_needs_quotes(s) {
        json_string(s, out); // a JSON string is a valid double-quoted YAML scalar
    } else {
        out.push_str(s);
    }
}

fn indent(out: &mut String, depth: usize) {
    for _ in 0..depth {
        out.push_str("  ");
    }
}

/// `inline_first`: the first line continues a `- ` or `key:` already written.
fn write_yaml(v: &Value, depth: usize, out: &mut String, inline_first: bool) {
    match v {
        Value::Null => out.push_str("null\n"),
        Value::Bool(b) => {
            out.push_str(if *b { "true" } else { "false" });
            out.push('\n');
        }
        Value::Int(i) => {
            let _ = writeln!(out, "{i}");
        }
        Value::UInt(u) => {
            let _ = writeln!(out, "{u}");
        }
        Value::Str(s) => {
            yaml_scalar(s, out);
            out.push('\n');
        }
        Value::List(l) if l.is_empty() => out.push_str("[]\n"),
        Value::Map(m) if m.is_empty() => out.push_str("{}\n"),
        Value::List(l) => {
            if inline_first {
                out.push('\n');
            }
            for x in l {
                indent(out, depth);
                out.push_str("- ");
                match x {
                    Value::Map(_) | Value::List(_) => write_yaml_nested_item(x, depth + 1, out),
                    _ => write_yaml(x, depth + 1, out, true),
                }
            }
        }
        Value::Map(m) => {
            if inline_first {
                out.push('\n');
            }
            for (k, x) in m {
                indent(out, depth);
                yaml_scalar(k, out);
                out.push(':');
                match x {
                    Value::Map(mm) if !mm.is_empty() => write_yaml(x, depth + 1, out, true),
                    Value::List(ll) if !ll.is_empty() => write_yaml(x, depth + 1, out, true),
                    _ => {
                        out.push(' ');
                        write_yaml(x, depth + 1, out, true);
                    }
                }
            }
        }
    }
}

/// A map or list as a list item: its first key shares the `- ` line.
fn write_yaml_nested_item(v: &Value, depth: usize, out: &mut String) {
    match v {
        Value::Map(m) if !m.is_empty() => {
            for (i, (k, x)) in m.iter().enumerate() {
                if i > 0 {
                    indent(out, depth);
                }
                yaml_scalar(k, out);
                out.push(':');
                match x {
                    Value::Map(mm) if !mm.is_empty() => write_yaml(x, depth + 1, out, true),
                    Value::List(ll) if !ll.is_empty() => write_yaml(x, depth + 1, out, true),
                    _ => {
                        out.push(' ');
                        write_yaml(x, depth + 1, out, true);
                    }
                }
            }
        }
        _ => write_yaml(v, depth, out, true),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> Value {
        Value::Map(vec![
            ("name".into(), Value::Str("a b".into())),
            ("size".into(), Value::UInt(42)),
            ("ok".into(), Value::Bool(true)),
            (
                "tags".into(),
                Value::List(vec![Value::Str("x".into()), Value::Str("yes".into())]),
            ),
            ("none".into(), Value::Null),
            (
                "inner".into(),
                Value::Map(vec![("k".into(), Value::Int(-1))]),
            ),
        ])
    }

    #[test]
    fn json_compact_and_pretty() {
        let v = sample();
        assert_eq!(
            v.to_json(false),
            r#"{"name":"a b","size":42,"ok":true,"tags":["x","yes"],"none":null,"inner":{"k":-1}}"#
        );
        let p = v.to_json(true);
        assert!(p.starts_with("{\n  \"name\": \"a b\","));
        assert!(p.ends_with("\n}"));
    }

    #[test]
    fn json_escapes_controls_and_quotes() {
        let v = Value::Str("q\"\\\n\u{1}".into());
        assert_eq!(v.to_json(false), r#""q\"\\\n\u0001""#);
    }

    #[test]
    fn yaml_block_style() {
        let y = sample().to_yaml();
        assert_eq!(
            y,
            "name: a b\nsize: 42\nok: true\ntags:\n  - x\n  - \"yes\"\nnone: null\ninner:\n  k: -1\n"
        );
    }

    #[test]
    fn yaml_list_of_maps() {
        let v = Value::List(vec![
            sample(),
            Value::Map(vec![("name".into(), Value::Str("1.5".into()))]),
        ]);
        let y = v.to_yaml();
        assert!(y.starts_with("- name: a b\n  size: 42\n"), "{y}");
        assert!(y.contains("- name: \"1.5\"\n"), "{y}");
    }

    #[test]
    fn paths() {
        let v = sample();
        assert_eq!(v.get(".inner.k"), Some(&Value::Int(-1)));
        assert_eq!(v.get("inner.k"), Some(&Value::Int(-1)));
        assert_eq!(v.get(".nope"), None);
        assert_eq!(v.get(".name.x"), None);
    }

    #[test]
    fn cells_and_order() {
        assert_eq!(
            Value::List(vec![Value::UInt(1), Value::Str("b".into())]).to_cell(),
            "1,b"
        );
        assert_eq!(Value::Int(-5).sort_cmp(&Value::UInt(3)), Ordering::Less);
        assert_eq!(Value::Null.sort_cmp(&Value::UInt(3)), Ordering::Greater);
        assert_eq!(
            Value::Str("B".into()).sort_cmp(&Value::Str("a".into())),
            Ordering::Less
        );
    }
}
