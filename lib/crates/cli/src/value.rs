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

//! The record: an ordered, dynamically typed value with JSON and YAML writers of its own and
//! a JSON reader (RFC 8259), so a program needs no serialisation dependency to speak the
//! common grammar.

use std::cmp::Ordering;
use std::fmt::{self, Write as _};

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
    /// A number with a fraction or an exponent, or an integer beyond 64 bits. Finite when
    /// read from JSON; written as `null` otherwise, since JSON has no infinity.
    Float(f64),
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
            Value::Float(f) => float_text(*f),
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
        fn float(v: &Value) -> Option<f64> {
            match v {
                Value::Int(i) => Some(*i as f64),
                Value::UInt(u) => Some(*u as f64),
                Value::Float(f) => Some(*f),
                _ => None,
            }
        }
        match (self, other) {
            (Value::Null, Value::Null) => Ordering::Equal,
            (Value::Null, _) => Ordering::Greater,
            (_, Value::Null) => Ordering::Less,
            (Value::Bool(a), Value::Bool(b)) => a.cmp(b),
            (Value::Str(a), Value::Str(b)) => a.as_bytes().cmp(b.as_bytes()),
            _ => match (num(self), num(other), float(self), float(other)) {
                (Some(a), Some(b), _, _) => a.cmp(&b),
                (_, _, Some(a), Some(b)) => a.total_cmp(&b),
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

/// The shortest spelling that reads back as the same number, always with a fraction or an
/// exponent, so a float stays a float through JSON.
fn float_text(f: f64) -> String {
    format!("{f:?}")
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
        Value::Float(f) if f.is_finite() => out.push_str(&float_text(*f)),
        Value::Float(_) => out.push_str("null"),
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
        Value::Float(f) => {
            let t = match *f {
                f if f.is_nan() => ".nan".to_string(),
                f if f == f64::INFINITY => ".inf".to_string(),
                f if f == f64::NEG_INFINITY => "-.inf".to_string(),
                f => float_text(f),
            };
            out.push_str(&t);
            out.push('\n');
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

/// Why a text is not JSON: where, the line and the column counted from 1 (the column in
/// characters), and what was found there.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct JsonError {
    /// The line, from 1.
    pub line: usize,
    /// The column, from 1, in characters.
    pub column: usize,
    /// What is wrong there, a sentence fragment.
    pub message: String,
}

impl fmt::Display for JsonError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "line {}, column {}: {}",
            self.line, self.column, self.message
        )
    }
}

impl std::error::Error for JsonError {}

/// Deeper than this, a document is refused rather than allowed to exhaust the stack.
const MAX_DEPTH: usize = 512;

impl Value {
    /// Reads one JSON text (RFC 8259) whole: objects, arrays, strings with every escape
    /// (surrogate pairs joined, a lone surrogate refused), numbers, `true`, `false`, `null`,
    /// and the four whitespace characters; a leading byte order mark is skipped. An integer
    /// reads as `Int` within 64 signed bits, as `UInt` beyond them within 64 unsigned, as
    /// `Float` beyond that; a fraction or an exponent reads as `Float`. Objects keep their
    /// order and repeated names. Nesting is bounded at 512 levels.
    pub fn from_json(text: &str) -> Result<Value, JsonError> {
        let mut r = Reader {
            text,
            s: text.as_bytes(),
            pos: 0,
        };
        if text.starts_with('\u{feff}') {
            r.pos = '\u{feff}'.len_utf8();
        }
        r.ws();
        let v = r.value(0)?;
        r.ws();
        if r.pos < r.s.len() {
            return Err(r.error(r.pos, "content after the value"));
        }
        Ok(v)
    }
}

struct Reader<'a> {
    text: &'a str,
    s: &'a [u8],
    pos: usize,
}

impl Reader<'_> {
    /// `pos` is always on a character boundary: errors are reported at ASCII bytes, at the
    /// first byte of a character, or at the end.
    fn error(&self, pos: usize, message: impl Into<String>) -> JsonError {
        let before = &self.text[..pos];
        JsonError {
            line: before.matches('\n').count() + 1,
            column: before.rsplit('\n').next().unwrap_or("").chars().count() + 1,
            message: message.into(),
        }
    }

    fn peek(&self) -> Option<u8> {
        self.s.get(self.pos).copied()
    }

    fn unexpected(&self) -> JsonError {
        match self.text[self.pos..].chars().next() {
            Some(c) => self.error(self.pos, format!("unexpected `{c}`")),
            None => self.error(self.pos, "unexpected end of input"),
        }
    }

    fn ws(&mut self) {
        while let Some(b' ' | b'\t' | b'\n' | b'\r') = self.peek() {
            self.pos += 1;
        }
    }

    fn value(&mut self, depth: usize) -> Result<Value, JsonError> {
        match self.peek() {
            Some(b'{') => self.object(depth + 1),
            Some(b'[') => self.array(depth + 1),
            Some(b'"') => Ok(Value::Str(self.string()?)),
            Some(b't') => self.literal("true", Value::Bool(true)),
            Some(b'f') => self.literal("false", Value::Bool(false)),
            Some(b'n') => self.literal("null", Value::Null),
            Some(b'-' | b'0'..=b'9') => self.number(),
            _ => Err(self.unexpected()),
        }
    }

    fn literal(&mut self, word: &str, v: Value) -> Result<Value, JsonError> {
        if self.s[self.pos..].starts_with(word.as_bytes()) {
            self.pos += word.len();
            Ok(v)
        } else {
            Err(self.error(self.pos, format!("expected `{word}`")))
        }
    }

    fn nest(&self, depth: usize) -> Result<(), JsonError> {
        if depth > MAX_DEPTH {
            return Err(self.error(self.pos, format!("nested deeper than {MAX_DEPTH} levels")));
        }
        Ok(())
    }

    fn array(&mut self, depth: usize) -> Result<Value, JsonError> {
        self.nest(depth)?;
        self.pos += 1;
        let mut items = Vec::new();
        self.ws();
        if self.peek() == Some(b']') {
            self.pos += 1;
            return Ok(Value::List(items));
        }
        loop {
            self.ws();
            if !items.is_empty() && self.peek() == Some(b']') {
                return Err(self.error(self.pos, "a trailing comma"));
            }
            items.push(self.value(depth)?);
            self.ws();
            match self.peek() {
                Some(b',') => self.pos += 1,
                Some(b']') => {
                    self.pos += 1;
                    return Ok(Value::List(items));
                }
                None => return Err(self.unexpected()),
                Some(_) => return Err(self.error(self.pos, "expected `,` or `]`")),
            }
        }
    }

    fn object(&mut self, depth: usize) -> Result<Value, JsonError> {
        self.nest(depth)?;
        self.pos += 1;
        let mut members = Vec::new();
        self.ws();
        if self.peek() == Some(b'}') {
            self.pos += 1;
            return Ok(Value::Map(members));
        }
        loop {
            self.ws();
            match self.peek() {
                Some(b'"') => {}
                Some(b'}') if !members.is_empty() => {
                    return Err(self.error(self.pos, "a trailing comma"));
                }
                None => return Err(self.unexpected()),
                Some(_) => return Err(self.error(self.pos, "expected a name in double quotes")),
            }
            let name = self.string()?;
            self.ws();
            match self.peek() {
                Some(b':') => self.pos += 1,
                None => return Err(self.unexpected()),
                Some(_) => return Err(self.error(self.pos, "expected `:`")),
            }
            self.ws();
            let v = self.value(depth)?;
            members.push((name, v));
            self.ws();
            match self.peek() {
                Some(b',') => self.pos += 1,
                Some(b'}') => {
                    self.pos += 1;
                    return Ok(Value::Map(members));
                }
                None => return Err(self.unexpected()),
                Some(_) => return Err(self.error(self.pos, "expected `,` or `}`")),
            }
        }
    }

    fn hex4(&self, at: usize) -> Option<u32> {
        let digits = self.s.get(at..at + 4)?;
        let mut n = 0u32;
        for d in digits {
            n = n * 16 + (*d as char).to_digit(16)?;
        }
        Some(n)
    }

    fn string(&mut self) -> Result<String, JsonError> {
        let start = self.pos;
        self.pos += 1;
        let mut out = String::new();
        loop {
            let run = self.pos;
            while let Some(b) = self.peek() {
                if b == b'"' || b == b'\\' || b < 0x20 {
                    break;
                }
                self.pos += 1;
            }
            out.push_str(&self.text[run..self.pos]);
            match self.peek() {
                None => return Err(self.error(start, "an unterminated string")),
                Some(b'"') => {
                    self.pos += 1;
                    return Ok(out);
                }
                Some(b'\\') => self.escape(&mut out, start)?,
                Some(_) => {
                    return Err(self.error(self.pos, "a control character not escaped in a string"));
                }
            }
        }
    }

    fn escape(&mut self, out: &mut String, start: usize) -> Result<(), JsonError> {
        let at = self.pos;
        self.pos += 1;
        let c = match self.peek() {
            None => return Err(self.error(start, "an unterminated string")),
            Some(b'"') => '"',
            Some(b'\\') => '\\',
            Some(b'/') => '/',
            Some(b'b') => '\u{8}',
            Some(b'f') => '\u{c}',
            Some(b'n') => '\n',
            Some(b'r') => '\r',
            Some(b't') => '\t',
            Some(b'u') => return self.unicode(out, at),
            Some(_) => {
                let c = self.text[self.pos..].chars().next().unwrap_or('?');
                return Err(self.error(at, format!("an invalid escape `\\{c}`")));
            }
        };
        self.pos += 1;
        out.push(c);
        Ok(())
    }

    /// `\uXXXX` at `at`, joined with the low half that must follow a high surrogate.
    fn unicode(&mut self, out: &mut String, at: usize) -> Result<(), JsonError> {
        let Some(hi) = self.hex4(at + 2) else {
            return Err(self.error(at, "`\\u` needs four hexadecimal digits"));
        };
        self.pos = at + 6;
        let lone = |r: &Self| {
            let digits = &r.text[at + 2..at + 6];
            r.error(at, format!("a lone surrogate `\\u{digits}`"))
        };
        let code = match hi {
            0xD800..=0xDBFF => {
                let next = self.s.get(self.pos..self.pos + 2);
                let lo = match (next, self.hex4(self.pos + 2)) {
                    (Some(b"\\u"), Some(lo @ 0xDC00..=0xDFFF)) => lo,
                    _ => return Err(lone(self)),
                };
                self.pos += 6;
                0x10000 + ((hi - 0xD800) << 10) + (lo - 0xDC00)
            }
            0xDC00..=0xDFFF => return Err(lone(self)),
            c => c,
        };
        out.push(char::from_u32(code).ok_or_else(|| lone(self))?);
        Ok(())
    }

    fn digits(&mut self) -> usize {
        let from = self.pos;
        while let Some(b'0'..=b'9') = self.peek() {
            self.pos += 1;
        }
        self.pos - from
    }

    fn number(&mut self) -> Result<Value, JsonError> {
        let start = self.pos;
        if self.peek() == Some(b'-') {
            self.pos += 1;
        }
        let int = self.pos;
        match self.digits() {
            0 => return Err(self.error(self.pos, "a number needs a digit here")),
            n if n > 1 && self.s[int] == b'0' => {
                return Err(self.error(int, "a number with a leading zero"));
            }
            _ => {}
        }
        let mut float = false;
        if self.peek() == Some(b'.') {
            self.pos += 1;
            if self.digits() == 0 {
                return Err(self.error(self.pos, "a fraction needs a digit here"));
            }
            float = true;
        }
        if let Some(b'e' | b'E') = self.peek() {
            self.pos += 1;
            if let Some(b'+' | b'-') = self.peek() {
                self.pos += 1;
            }
            if self.digits() == 0 {
                return Err(self.error(self.pos, "an exponent needs a digit here"));
            }
            float = true;
        }
        let t = &self.text[start..self.pos];
        if !float {
            if let Ok(i) = t.parse::<i64>() {
                return Ok(Value::Int(i));
            }
            if let Ok(u) = t.parse::<u64>() {
                return Ok(Value::UInt(u));
            }
        }
        match t.parse::<f64>() {
            Ok(f) if f.is_finite() => Ok(Value::Float(f)),
            _ => Err(self.error(start, format!("`{t}` is out of range"))),
        }
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

    fn read(s: &str) -> Value {
        Value::from_json(s).unwrap_or_else(|e| panic!("{s:?}: {e}"))
    }

    fn refused(s: &str) -> String {
        match Value::from_json(s) {
            Ok(v) => panic!("{s:?} read as {v:?}"),
            Err(e) => e.to_string(),
        }
    }

    #[test]
    fn reads_every_kind_of_value() {
        assert_eq!(read("null"), Value::Null);
        assert_eq!(read("true"), Value::Bool(true));
        assert_eq!(read("false"), Value::Bool(false));
        assert_eq!(read("0"), Value::Int(0));
        assert_eq!(read("-0"), Value::Int(0));
        assert_eq!(read("-12"), Value::Int(-12));
        assert_eq!(read("9223372036854775807"), Value::Int(i64::MAX));
        assert_eq!(read("-9223372036854775808"), Value::Int(i64::MIN));
        assert_eq!(read("9223372036854775808"), Value::UInt(1 << 63));
        assert_eq!(read("18446744073709551615"), Value::UInt(u64::MAX));
        assert_eq!(
            read("18446744073709551616"),
            Value::Float(18446744073709551616.0)
        );
        assert_eq!(read("1.5"), Value::Float(1.5));
        assert_eq!(read("-0.25e2"), Value::Float(-25.0));
        assert_eq!(read("1E3"), Value::Float(1000.0));
        assert_eq!(read("2e-1"), Value::Float(0.2));
        assert_eq!(read("3.0"), Value::Float(3.0));
        assert_eq!(read("\"\""), Value::Str(String::new()));
        assert_eq!(read("\"añ €\""), Value::Str("añ €".into()));
        assert_eq!(read("[]"), Value::List(vec![]));
        assert_eq!(read("{}"), Value::Map(vec![]));
        assert_eq!(
            read(" \t\r\n[1, \"a\", [true], {\"k\": null}] \n"),
            Value::List(vec![
                Value::Int(1),
                Value::Str("a".into()),
                Value::List(vec![Value::Bool(true)]),
                Value::Map(vec![("k".into(), Value::Null)]),
            ])
        );
        assert_eq!(
            read("{\"b\": 1, \"a\": 2, \"b\": 3}"),
            Value::Map(vec![
                ("b".into(), Value::Int(1)),
                ("a".into(), Value::Int(2)),
                ("b".into(), Value::Int(3)),
            ]),
            "order and repeated names kept"
        );
        assert_eq!(read("\u{feff}[1]"), Value::List(vec![Value::Int(1)]));
    }

    #[test]
    fn reads_every_escape() {
        assert_eq!(
            read(r#""\" \\ \/ \b \f \n \r \t""#),
            Value::Str("\" \\ / \u{8} \u{c} \n \r \t".into())
        );
        assert_eq!(read(r#""Aé€""#), Value::Str("Aé€".into()));
        assert_eq!(read(r#""\u0000""#), Value::Str("\0".into()));
        assert_eq!(read(r#""😀""#), Value::Str("\u{1f600}".into()));
        assert_eq!(read(r#""𝄞""#), Value::Str("\u{1d11e}".into()));
        assert_eq!(read(r#""abc""#), Value::Str("abc".into()));
    }

    #[test]
    fn refuses_what_is_not_json_and_says_where() {
        assert_eq!(refused(""), "line 1, column 1: unexpected end of input");
        assert_eq!(refused("   "), "line 1, column 4: unexpected end of input");
        assert_eq!(refused("[1,]"), "line 1, column 4: a trailing comma");
        assert_eq!(refused("{\"a\": 1,}"), "line 1, column 9: a trailing comma");
        assert_eq!(refused("[1 2]"), "line 1, column 4: expected `,` or `]`");
        assert_eq!(refused("{\"a\" 1}"), "line 1, column 6: expected `:`");
        assert_eq!(
            refused("{\"a\": 1 \"b\"}"),
            "line 1, column 9: expected `,` or `}`"
        );
        assert_eq!(
            refused("{a: 1}"),
            "line 1, column 2: expected a name in double quotes"
        );
        assert_eq!(refused("{\"a\":}"), "line 1, column 6: unexpected `}`");
        assert_eq!(refused("[1"), "line 1, column 3: unexpected end of input");
        assert_eq!(
            refused("{\"a\": 1"),
            "line 1, column 8: unexpected end of input"
        );
        assert_eq!(refused("\"abc"), "line 1, column 1: an unterminated string");
        assert_eq!(
            refused("\"abc\\"),
            "line 1, column 1: an unterminated string"
        );
        assert_eq!(
            refused("\"a\tb\""),
            "line 1, column 3: a control character not escaped in a string"
        );
        assert_eq!(
            refused(r#""\x""#),
            "line 1, column 2: an invalid escape `\\x`"
        );
        assert_eq!(
            refused(r#""\é""#),
            "line 1, column 2: an invalid escape `\\é`"
        );
        assert_eq!(
            refused(r#""\u12""#),
            "line 1, column 2: `\\u` needs four hexadecimal digits"
        );
        assert_eq!(
            refused(r#""\u12G4""#),
            "line 1, column 2: `\\u` needs four hexadecimal digits"
        );
        assert_eq!(
            refused(r#""\ud800""#),
            "line 1, column 2: a lone surrogate `\\ud800`"
        );
        assert_eq!(
            refused(r#""\uD800A""#),
            "line 1, column 2: a lone surrogate `\\uD800`"
        );
        assert_eq!(
            refused(r#""\udc00""#),
            "line 1, column 2: a lone surrogate `\\udc00`"
        );
        assert_eq!(
            refused("01"),
            "line 1, column 1: a number with a leading zero"
        );
        assert_eq!(
            refused("-01"),
            "line 1, column 2: a number with a leading zero"
        );
        assert_eq!(
            refused("-"),
            "line 1, column 2: a number needs a digit here"
        );
        assert_eq!(
            refused("-a"),
            "line 1, column 2: a number needs a digit here"
        );
        assert_eq!(
            refused("1."),
            "line 1, column 3: a fraction needs a digit here"
        );
        assert_eq!(
            refused("1.e5"),
            "line 1, column 3: a fraction needs a digit here"
        );
        assert_eq!(
            refused("1e"),
            "line 1, column 3: an exponent needs a digit here"
        );
        assert_eq!(
            refused("1e+"),
            "line 1, column 4: an exponent needs a digit here"
        );
        assert_eq!(refused("+1"), "line 1, column 1: unexpected `+`");
        assert_eq!(refused(".5"), "line 1, column 1: unexpected `.`");
        assert_eq!(
            refused("1e400"),
            "line 1, column 1: `1e400` is out of range"
        );
        assert_eq!(refused("tru"), "line 1, column 1: expected `true`");
        assert_eq!(refused("nul"), "line 1, column 1: expected `null`");
        assert_eq!(refused("True"), "line 1, column 1: unexpected `T`");
        assert_eq!(refused("NaN"), "line 1, column 1: unexpected `N`");
        assert_eq!(
            refused("[1] [2]"),
            "line 1, column 5: content after the value"
        );
        assert_eq!(
            refused("1 // no"),
            "line 1, column 3: content after the value"
        );
        assert_eq!(refused("'a'"), "line 1, column 1: unexpected `'`");
        assert_eq!(refused("\u{a0}1"), "line 1, column 1: unexpected `\u{a0}`");
        assert_eq!(
            refused("{\n  \"a\": [\n    1,\n    é\n  ]\n}"),
            "line 4, column 5: unexpected `é`"
        );
        assert_eq!(refused("[\"é\", x]"), "line 1, column 7: unexpected `x`");
    }

    #[test]
    fn nesting_is_bounded() {
        let ok = "[".repeat(512) + &"]".repeat(512);
        assert!(Value::from_json(&ok).is_ok());
        let deep = "[".repeat(513) + &"]".repeat(513);
        assert_eq!(
            Value::from_json(&deep).unwrap_err().to_string(),
            "line 1, column 513: nested deeper than 512 levels"
        );
        let objects = "{\"a\":".repeat(600) + "1" + &"}".repeat(600);
        assert!(Value::from_json(&objects).is_err());
    }

    #[test]
    fn what_to_json_writes_from_json_reads_back_equal() {
        let v = Value::Map(vec![
            (
                "name".into(),
                Value::Str("a \"b\"\\\n\t\u{1}\u{7f}é\u{1f600}".into()),
            ),
            ("int".into(), Value::Int(-7)),
            ("min".into(), Value::Int(i64::MIN)),
            ("big".into(), Value::UInt(u64::MAX)),
            ("pi".into(), Value::Float(3.25)),
            ("tiny".into(), Value::Float(1e-300)),
            ("huge".into(), Value::Float(1e300)),
            ("whole".into(), Value::Float(2.0)),
            ("yes".into(), Value::Bool(true)),
            ("no".into(), Value::Bool(false)),
            ("none".into(), Value::Null),
            ("empty".into(), Value::List(vec![])),
            ("nothing".into(), Value::Map(vec![])),
            (
                "nested".into(),
                Value::List(vec![
                    Value::Map(vec![("size".into(), Value::Int(42))]),
                    Value::List(vec![Value::Int(1)]),
                ]),
            ),
            ("".into(), Value::Str(String::new())),
        ]);
        for pretty in [false, true] {
            assert_eq!(read(&v.to_json(pretty)), v, "pretty {pretty}");
        }
        assert_eq!(
            read(&sample().to_json(true)).to_json(false),
            sample().to_json(false)
        );
    }

    #[test]
    fn floats_are_written_as_json_and_yaml_can_read() {
        assert_eq!(Value::Float(1.5).to_json(false), "1.5");
        assert_eq!(Value::Float(2.0).to_json(false), "2.0");
        assert_eq!(Value::Float(f64::NAN).to_json(false), "null");
        assert_eq!(Value::Float(f64::INFINITY).to_json(false), "null");
        assert_eq!(Value::Float(f64::NEG_INFINITY).to_yaml(), "-.inf\n");
        assert_eq!(Value::Float(0.5).to_yaml(), "0.5\n");
        assert_eq!(Value::Float(0.5).to_cell(), "0.5");
        assert_eq!(Value::Float(0.5).sort_cmp(&Value::Int(1)), Ordering::Less);
        assert_eq!(
            Value::UInt(2).sort_cmp(&Value::Float(1.5)),
            Ordering::Greater
        );
    }
}
