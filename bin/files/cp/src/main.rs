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

//! `cp`: copy files and directories (DEFINITION.md, DESIGN.md beside this file).
//!
//! An action whose every step is a record: the sources are walked into operations, each
//! operation is performed and becomes a [`copy::Record`] with the schema of
//! `schemas/copy.v1.json`, and the records are shown as `-v` or `-o` asks. OpenBSD's `cp(1)`
//! is the reference for what the POSIX flags mean; nothing of its code is here.

#![forbid(unsafe_code)]

mod copy;
mod options;
mod report;
mod walk;

use std::io::{self, BufWriter, Write};
use std::process::ExitCode;

use cli::exit;

use crate::options::COMMAND;

fn main() -> ExitCode {
    // `--help` and a wrong command line are handled by `cli`, alike for every program.
    let parsed = match COMMAND.from_env() {
        Ok(p) => p,
        Err(code) => return code,
    };
    let cfg = match options::Config::from_parsed(parsed) {
        Ok(c) => c,
        Err(msg) => {
            COMMAND.warn(msg);
            eprintln!("{}", COMMAND.usage());
            return ExitCode::from(exit::USAGE);
        }
    };
    // Before touching anything: only what this configuration will do.
    if let Err(e) = sys::pledge(&cfg.promises()) {
        COMMAND.report("pledge", e);
        return ExitCode::from(exit::FAILURE);
    }
    let shape = match walk::shape(&cfg) {
        Ok(s) => s,
        Err(walk::ShapeError::Usage(msg)) => {
            COMMAND.warn(msg);
            eprintln!("{}", COMMAND.usage());
            return ExitCode::from(exit::USAGE);
        }
        Err(walk::ShapeError::Io(msg)) => {
            COMMAND.warn(msg);
            return ExitCode::from(exit::FAILURE);
        }
    };
    let stdout = io::stdout();
    let mut out = BufWriter::new(stdout.lock());
    let mut reporter = report::Reporter::new(&cfg, &mut out);
    let mut copier = copy::Copier::new(&cfg);
    let mut output_failed = false;
    walk::walk(&cfg, shape, &mut |op| {
        let (record, descend) = copier.perform(op);
        if let Some(r) = record
            && let Err(e) = reporter.record(r)
        {
            if e.kind() != io::ErrorKind::BrokenPipe {
                COMMAND.report("stdout", e);
            }
            output_failed = true;
        }
        descend
    });
    if let Err(e) = reporter.finish()
        && e.kind() != io::ErrorKind::BrokenPipe
    {
        COMMAND.report("stdout", e);
        output_failed = true;
    }
    let mut failed = reporter.failed || output_failed;
    // The buffer holds the -v lines and a small document until here: a failure to write
    // them is a failure of the program, not a quiet exit.
    if let Err(e) = out.flush()
        && e.kind() != io::ErrorKind::BrokenPipe
    {
        COMMAND.report("stdout", e);
        failed = true;
    }
    if failed {
        ExitCode::from(exit::FAILURE)
    } else {
        ExitCode::from(exit::OK)
    }
}
