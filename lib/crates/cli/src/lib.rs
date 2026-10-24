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

//! `cli`: the common grammar of the written programs (docs/PROGRAM.md, "The common grammar").
//!
//! A program is a query over records. This crate gives it the pieces every program shares:
//! option parsing with POSIX's rules ([`args`]), a [`Value`] that is the record, the
//! renderers `-o` selects ([`Output`], [`render`]), sorting by a field path ([`sort_by`]),
//! and the text helpers a terminal needs ([`text`]).

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod args;
pub mod help;
pub mod render;
pub mod text;
pub mod value;

pub use args::{ArgError, Opt, Parsed, Spec};
pub use help::{Help, OptDoc};
pub use render::{Align, Column, Output, Table};
pub use value::Value;

/// Sorts records by the field `path` names, stable, numbers numerically and strings byte by
/// byte; records without the field go last. `reverse` flips the whole order.
pub fn sort_by(records: &mut [Value], path: &str, reverse: bool) {
    records.sort_by(|a, b| {
        let o = match (a.get(path), b.get(path)) {
            (Some(x), Some(y)) => x.sort_cmp(y),
            (Some(_), None) => std::cmp::Ordering::Less,
            (None, Some(_)) => std::cmp::Ordering::Greater,
            (None, None) => std::cmp::Ordering::Equal,
        };
        if reverse { o.reverse() } else { o }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rec(name: &str, size: u64) -> Value {
        Value::Map(vec![
            ("name".into(), Value::Str(name.into())),
            ("size".into(), Value::UInt(size)),
        ])
    }

    #[test]
    fn sorts_by_a_numeric_field_and_reverses() {
        let mut v = vec![rec("b", 20), rec("a", 5), rec("c", 300)];
        sort_by(&mut v, ".size", false);
        let names: Vec<_> = v
            .iter()
            .map(|r| r.get(".name").unwrap().to_cell())
            .collect();
        assert_eq!(names, ["a", "b", "c"]);
        sort_by(&mut v, "size", true);
        let names: Vec<_> = v
            .iter()
            .map(|r| r.get(".name").unwrap().to_cell())
            .collect();
        assert_eq!(names, ["c", "b", "a"]);
    }

    #[test]
    fn a_missing_field_sorts_last() {
        let mut v = vec![
            Value::Map(vec![("name".into(), Value::Str("x".into()))]),
            rec("a", 1),
        ];
        sort_by(&mut v, ".size", false);
        assert_eq!(v[0].get("name").unwrap().to_cell(), "a");
    }
}
