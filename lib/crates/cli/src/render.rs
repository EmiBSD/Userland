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

//! The renderers `-o` selects, and the two layouts a terminal needs: a table and a grid.

use std::io::{self, Write};

use crate::text::display_width;
use crate::value::Value;

/// What `-o` chose.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Output {
    /// One identifier per line, or in columns on a terminal.
    Name,
    /// The program's classic columns.
    Table,
    /// Every field of the record as a table.
    Wide,
    /// The records as JSON.
    Json,
    /// The records as YAML.
    Yaml,
    /// The fields asked for: `(header, path)` pairs.
    Custom(Vec<(String, String)>),
}

impl Output {
    /// Parses the value of `-o`: `name`, `table`, `wide`, `json`, `yaml`, or
    /// `custom-columns=NAME:.path,SIZE:.size`.
    pub fn parse(s: &str) -> Result<Output, String> {
        match s {
            "name" => Ok(Output::Name),
            "table" => Ok(Output::Table),
            "wide" => Ok(Output::Wide),
            "json" => Ok(Output::Json),
            "yaml" => Ok(Output::Yaml),
            _ => {
                if let Some(spec) = s.strip_prefix("custom-columns=") {
                    let mut cols = Vec::new();
                    for part in spec.split(',').filter(|p| !p.is_empty()) {
                        let (h, p) = part.split_once(':').ok_or_else(|| {
                            format!("custom-columns: `{part}` is not HEADER:.path")
                        })?;
                        cols.push((h.to_string(), p.to_string()));
                    }
                    if cols.is_empty() {
                        return Err("custom-columns: no columns".into());
                    }
                    Ok(Output::Custom(cols))
                } else {
                    Err(format!(
                        "`{s}` is not one of name, table, wide, json, yaml, custom-columns=NAME:.path,..."
                    ))
                }
            }
        }
    }
}

/// How a column lines up.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Align {
    /// Text.
    Left,
    /// Numbers.
    Right,
}

/// A column of a [`Table`].
#[derive(Debug, Clone)]
pub struct Column {
    /// The header, upper case by convention.
    pub header: String,
    /// Its alignment.
    pub align: Align,
}

impl Column {
    /// A left-aligned column.
    pub fn left(h: &str) -> Column {
        Column {
            header: h.to_string(),
            align: Align::Left,
        }
    }
    /// A right-aligned column.
    pub fn right(h: &str) -> Column {
        Column {
            header: h.to_string(),
            align: Align::Right,
        }
    }
}

/// Rows of cells under columns, rendered with two spaces between columns and no padding
/// after the last one, so a line never carries trailing blanks.
#[derive(Debug, Clone, Default)]
pub struct Table {
    /// The columns.
    pub columns: Vec<Column>,
    /// The rows; a short row is padded with empty cells.
    pub rows: Vec<Vec<String>>,
}

impl Table {
    /// A table over `columns`.
    pub fn new(columns: Vec<Column>) -> Table {
        Table {
            columns,
            rows: Vec::new(),
        }
    }

    /// Writes the table, with the header line when `headers`.
    pub fn render(&self, headers: bool, out: &mut dyn Write) -> io::Result<()> {
        let n = self.columns.len();
        let mut widths: Vec<usize> = if headers {
            self.columns
                .iter()
                .map(|c| display_width(&c.header))
                .collect()
        } else {
            vec![0; n]
        };
        for row in &self.rows {
            for (i, cell) in row.iter().enumerate().take(n) {
                widths[i] = widths[i].max(display_width(cell));
            }
        }
        if headers {
            let cells: Vec<&str> = self.columns.iter().map(|c| c.header.as_str()).collect();
            emit_row(&self.columns, &widths, &cells, out)?;
        }
        for row in &self.rows {
            let cells: Vec<&str> = (0..n)
                .map(|i| row.get(i).map(String::as_str).unwrap_or(""))
                .collect();
            emit_row(&self.columns, &widths, &cells, out)?;
        }
        Ok(())
    }
}

fn emit_row(
    columns: &[Column],
    widths: &[usize],
    cells: &[&str],
    out: &mut dyn Write,
) -> io::Result<()> {
    let n = columns.len();
    let mut line = String::new();
    for (i, cell) in cells.iter().enumerate().take(n) {
        let last = i + 1 == n;
        let pad = widths[i].saturating_sub(display_width(cell));
        match columns[i].align {
            Align::Right => {
                line.extend(std::iter::repeat_n(' ', pad));
                line.push_str(cell);
            }
            Align::Left => {
                line.push_str(cell);
                if !last {
                    line.extend(std::iter::repeat_n(' ', pad));
                }
            }
        }
        if !last {
            line.push_str("  ");
        }
    }
    writeln!(out, "{}", line.trim_end())
}

/// Lays `items` out in columns down the page, as `ls -C` does: as many columns as fit in
/// `width`, every column as wide as the widest item plus two blanks, a single column when
/// not even two fit. Returns the lines.
pub fn grid(items: &[String], width: usize) -> Vec<String> {
    if items.is_empty() {
        return Vec::new();
    }
    let maxlen = items.iter().map(|s| display_width(s)).max().unwrap_or(0);
    let colwidth = maxlen + 2;
    let ncols = if width + 2 < 2 * colwidth {
        1
    } else {
        ((width + 2) / colwidth).max(1)
    };
    let nrows = items.len().div_ceil(ncols);
    let mut lines = Vec::with_capacity(nrows);
    for row in 0..nrows {
        let mut line = String::new();
        let mut col = 0;
        let mut idx = row;
        while idx < items.len() {
            let item = &items[idx];
            line.push_str(item);
            idx += nrows;
            col += 1;
            if idx >= items.len() || col == ncols {
                break;
            }
            line.extend(std::iter::repeat_n(' ', colwidth - display_width(item)));
        }
        lines.push(line);
    }
    lines
}

/// Renders `records` as `-o` asked, for the machine formats and the generic tables; a
/// program renders `Table` and `Name` itself, since those are its own columns.
pub fn render_records(
    output: &Output,
    records: &[Value],
    headers: bool,
    out: &mut dyn Write,
) -> io::Result<()> {
    match output {
        Output::Json => {
            let v = Value::List(records.to_vec());
            writeln!(out, "{}", v.to_json(true))
        }
        Output::Yaml => {
            let v = Value::List(records.to_vec());
            write!(out, "{}", v.to_yaml())
        }
        Output::Wide => {
            let keys: Vec<String> = match records.first() {
                Some(Value::Map(m)) => m.iter().map(|(k, _)| k.clone()).collect(),
                _ => Vec::new(),
            };
            let mut t = Table::new(
                keys.iter()
                    .map(|k| Column::left(&k.to_ascii_uppercase()))
                    .collect(),
            );
            for r in records {
                t.rows.push(
                    keys.iter()
                        .map(|k| r.get(k).map(Value::to_cell).unwrap_or_default())
                        .collect(),
                );
            }
            t.render(headers, out)
        }
        Output::Custom(cols) => {
            let mut t = Table::new(cols.iter().map(|(h, _)| Column::left(h)).collect());
            for r in records {
                t.rows.push(
                    cols.iter()
                        .map(|(_, p)| r.get(p).map(Value::to_cell).unwrap_or_default())
                        .collect(),
                );
            }
            t.render(headers, out)
        }
        Output::Name | Output::Table => Err(io::Error::other(
            "render_records: Name and Table are the program's own",
        )),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn output_parsing() {
        assert_eq!(Output::parse("json"), Ok(Output::Json));
        assert_eq!(
            Output::parse("custom-columns=NAME:.name,SIZE:.size"),
            Ok(Output::Custom(vec![
                ("NAME".into(), ".name".into()),
                ("SIZE".into(), ".size".into())
            ]))
        );
        assert!(Output::parse("xml").is_err());
        assert!(Output::parse("custom-columns=NAME").is_err());
    }

    #[test]
    fn table_alignment_and_no_trailing_blanks() {
        let mut t = Table::new(vec![Column::right("SIZE"), Column::left("NAME")]);
        t.rows.push(vec!["5".into(), "a".into()]);
        t.rows.push(vec!["12345".into(), "bb".into()]);
        let mut out = Vec::new();
        t.render(true, &mut out).unwrap();
        assert_eq!(
            String::from_utf8(out).unwrap(),
            " SIZE  NAME\n    5  a\n12345  bb\n"
        );
        let mut out = Vec::new();
        t.render(false, &mut out).unwrap();
        assert_eq!(String::from_utf8(out).unwrap(), "    5  a\n12345  bb\n");
    }

    #[test]
    fn grid_down_the_page() {
        let items: Vec<String> = ["a", "bb", "ccc", "d", "e"]
            .iter()
            .map(|s| s.to_string())
            .collect();
        // width 12: colwidth 5, (12+2)/5 = 2 columns, 3 rows
        assert_eq!(grid(&items, 12), ["a    d", "bb   e", "ccc"]);
        // too narrow for two columns
        assert_eq!(grid(&items, 6), ["a", "bb", "ccc", "d", "e"]);
        // wide: one row
        assert_eq!(grid(&items, 80), ["a    bb   ccc  d    e"]);
    }
}
