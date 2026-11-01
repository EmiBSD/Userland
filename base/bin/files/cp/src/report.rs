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

//! What the user sees of the records: nothing by default, `source -> target` with `-v`, the
//! targets with `-o name`, a table or the machine formats otherwise. Failures always go to
//! standard error as `cp: <what>: <why>`.

use std::io::{self, Write};

use cli::render::render_records;
use cli::{Column, Output, Table, Value};

use crate::copy::{Action, Record};
use crate::options::{COMMAND, Config};

pub struct Reporter<'a> {
    cfg: &'a Config,
    out: &'a mut dyn Write,
    records: Vec<Record>,
    /// Some record failed: the exit status says so.
    pub failed: bool,
}

impl<'a> Reporter<'a> {
    pub fn new(cfg: &'a Config, out: &'a mut dyn Write) -> Reporter<'a> {
        Reporter {
            cfg,
            out,
            records: Vec::new(),
            failed: false,
        }
    }

    pub fn record(&mut self, r: Record) -> io::Result<()> {
        if r.action == Action::Failed {
            self.failed = true;
            COMMAND.warn(r.error.as_deref().unwrap_or("failed"));
        }
        match &self.cfg.output {
            None => {
                if self.cfg.verbose
                    && matches!(
                        r.action,
                        Action::Created | Action::Replaced | Action::Planned
                    )
                {
                    writeln!(self.out, "{} -> {}", r.source.display(), r.target.display())?;
                }
            }
            Some(Output::Name) => {
                if r.action != Action::Failed && r.action != Action::Skipped {
                    writeln!(self.out, "{}", r.target.display())?;
                }
            }
            Some(_) => self.records.push(r),
        }
        Ok(())
    }

    pub fn finish(&mut self) -> io::Result<()> {
        let records = std::mem::take(&mut self.records);
        let Some(output) = &self.cfg.output else {
            return Ok(());
        };
        let headers = self.cfg.headers;
        match output {
            Output::Table => {
                let mut t = Table::new(vec![
                    Column::left("SOURCE"),
                    Column::left("TARGET"),
                    Column::left("TYPE"),
                    Column::right("SIZE"),
                    Column::left("ACTION"),
                ]);
                for r in &records {
                    t.rows.push(vec![
                        r.source.display().to_string(),
                        r.target.display().to_string(),
                        r.kind.to_string(),
                        r.size.map(|n| n.to_string()).unwrap_or_default(),
                        r.action.name().to_string(),
                    ]);
                }
                t.render(headers, self.out)
            }
            Output::Json | Output::Yaml => {
                let doc = Value::Map(vec![
                    ("apiVersion".into(), Value::Str("emibsd.org/v1".into())),
                    ("kind".into(), Value::Str("CopyList".into())),
                    (
                        "items".into(),
                        Value::List(records.iter().map(Record::to_value).collect()),
                    ),
                ]);
                if *output == Output::Json {
                    writeln!(self.out, "{}", doc.to_json(true))
                } else {
                    write!(self.out, "{}", doc.to_yaml())
                }
            }
            other => {
                let values: Vec<Value> = records.iter().map(Record::to_value).collect();
                render_records(other, &values, headers, self.out)
            }
        }
    }
}
