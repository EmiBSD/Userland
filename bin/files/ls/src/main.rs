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

//! `ls`: list directory contents (DEFINITION.md, DESIGN.md beside this file).
//!
//! A query over file records: the operands are walked into [`entry::Entry`] records with the
//! schema of `schemas/entry.v1.json`, filtered, sorted, and handed to the renderer `-o`
//! chose. OpenBSD's `ls(1)` is the reference for what the POSIX flags mean; nothing of its
//! code is here.

#![forbid(unsafe_code)]

mod entry;
mod mode;
mod options;
mod render;
mod time;
mod walk;

use std::io::{self, BufWriter, Write};
use std::process::ExitCode;

use cli::exit;

use crate::options::COMMAND;

fn main() -> ExitCode {
    // Before anything else: standard I/O, reading the file system, the passwd database.
    if let Err(e) = sys::pledge("stdio rpath getpw") {
        COMMAND.report("pledge", e);
        return ExitCode::from(exit::FAILURE);
    }
    // `--help` and a wrong command line are handled by `cli`, alike for every program.
    let parsed = match COMMAND.from_env() {
        Ok(p) => p,
        Err(code) => return code,
    };
    let config = options::Config::from_parsed(parsed);
    let stdout = io::stdout();
    let mut out = BufWriter::new(stdout.lock());
    let mut failed = false;
    let mut renderer = render::Renderer::new(&config, &mut out);
    walk::walk(&config, &mut |listing| {
        if listing.had_errors() {
            failed = true;
        }
        if let Err(e) = renderer.listing(listing) {
            if e.kind() != io::ErrorKind::BrokenPipe {
                COMMAND.report("stdout", e);
            }
            failed = true;
        }
    });
    if let Err(e) = renderer.finish()
        && e.kind() != io::ErrorKind::BrokenPipe
    {
        COMMAND.report("stdout", e);
        failed = true;
    }
    let _ = out.flush();
    if failed {
        ExitCode::from(exit::FAILURE)
    } else {
        ExitCode::from(exit::OK)
    }
}
