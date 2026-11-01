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

//! Integration tests: the binary on a small tree, output to a pipe (so the POSIX shapes).
//! The differential tests against a reference system's ls (tests/golden) run on EmiBSD, not here.

use std::fs;
use std::os::unix::fs::{PermissionsExt, symlink};
use std::path::{Path, PathBuf};
use std::process::Command;

struct Tree(PathBuf);

impl Tree {
    fn new(tag: &str) -> Tree {
        let dir = std::env::temp_dir().join(format!("emibsd-ls-test-{}-{tag}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(dir.join("sub/deeper")).unwrap();
        fs::write(dir.join("b.txt"), b"hello").unwrap();
        fs::write(dir.join("a.txt"), b"hi").unwrap();
        fs::write(dir.join(".hidden"), b"").unwrap();
        fs::write(dir.join("sub/c.txt"), vec![0u8; 3000]).unwrap();
        fs::write(dir.join("sub/deeper/d.txt"), b"").unwrap();
        symlink("a.txt", dir.join("link")).unwrap();
        symlink("nowhere", dir.join("broken")).unwrap();
        let exe = dir.join("run.sh");
        fs::write(&exe, b"#!/bin/sh\n").unwrap();
        fs::set_permissions(&exe, fs::Permissions::from_mode(0o755)).unwrap();
        Tree(dir)
    }
}

impl Drop for Tree {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

fn ls(dir: &Path, args: &[&str]) -> (i32, String, String) {
    let out = Command::new(env!("CARGO_BIN_EXE_ls"))
        .args(args)
        .current_dir(dir)
        .env("TZ", "UTC")
        .env_remove("BLOCKSIZE")
        .env_remove("COLUMNS")
        .output()
        .expect("runs ls");
    (
        out.status.code().unwrap_or(-1),
        String::from_utf8_lossy(&out.stdout).into_owned(),
        String::from_utf8_lossy(&out.stderr).into_owned(),
    )
}

#[test]
fn names_one_per_line_to_a_pipe_sorted_without_hidden() {
    let t = Tree::new("names");
    let (rc, out, err) = ls(&t.0, &[]);
    assert_eq!(rc, 0, "{err}");
    assert_eq!(out, "a.txt\nb.txt\nbroken\nlink\nrun.sh\nsub\n");
    let (_, out, _) = ls(&t.0, &["-a"]);
    assert!(out.starts_with(".\n..\n.hidden\n"), "{out}");
    let (_, out, _) = ls(&t.0, &["-A"]);
    assert!(out.starts_with(".hidden\na.txt\n"), "{out}");
}

#[test]
fn indicators_and_reverse_and_size_sort() {
    let t = Tree::new("ind");
    let (_, out, _) = ls(&t.0, &["-F"]);
    assert_eq!(out, "a.txt\nb.txt\nbroken@\nlink@\nrun.sh*\nsub/\n");
    let (_, out, _) = ls(&t.0, &["-r"]);
    assert_eq!(out, "sub\nrun.sh\nlink\nbroken\nb.txt\na.txt\n");
    let (_, out, _) = ls(&t.0, &["-S", "sub"]);
    assert_eq!(out, "c.txt\ndeeper\n");
}

#[test]
fn the_long_format_to_a_pipe_is_posix() {
    let t = Tree::new("long");
    let (rc, out, err) = ls(&t.0, &["-l"]);
    assert_eq!(rc, 0, "{err}");
    let mut lines = out.lines();
    assert!(lines.next().unwrap().starts_with("total "), "{out}");
    let a = lines.next().unwrap();
    assert!(a.starts_with("-rw-r--r--"), "{a}");
    assert!(a.ends_with(" a.txt"), "{a}");
    // mode, links, owner, group, size, three date words, name: nine fields
    assert_eq!(a.split_whitespace().count(), 9, "{a}");
    assert!(a.split_whitespace().nth(4) == Some("2"), "{a}");
    let link = out
        .lines()
        .find(|l| l.contains(" link -> "))
        .expect("the symlink line");
    assert!(
        link.starts_with('l') && link.ends_with("link -> a.txt"),
        "{link}"
    );
    let (_, out_n, _) = ls(&t.0, &["-ln"]);
    assert!(
        out_n
            .lines()
            .nth(1)
            .unwrap()
            .split_whitespace()
            .nth(2)
            .unwrap()
            .chars()
            .all(|c| c.is_ascii_digit())
    );
}

#[test]
fn json_is_a_versioned_document_with_the_schema_fields() {
    let t = Tree::new("json");
    let (rc, out, err) = ls(&t.0, &["-o", "json"]);
    assert_eq!(rc, 0, "{err}");
    assert!(
        out.starts_with("{\n  \"apiVersion\": \"emibsd.org/v1\",\n  \"kind\": \"FileList\","),
        "{out}"
    );
    for field in [
        "\"name\": \"a.txt\"",
        "\"type\": \"file\"",
        "\"size\": 2",
        "\"mode\": \"-rw-r--r--\"",
        "\"perm\": \"0644\"",
        "\"mtime\": \"",
        "\"target\": \"a.txt\"",
        "\"type\": \"symlink\"",
    ] {
        assert!(out.contains(field), "missing {field} in {out}");
    }
    let (_, yaml, _) = ls(&t.0, &["-o", "yaml"]);
    assert!(
        yaml.starts_with("apiVersion: emibsd.org/v1\nkind: FileList\nitems:\n  - name: a.txt\n"),
        "{yaml}"
    );
}

#[test]
fn custom_columns_sort_by_and_filters() {
    let t = Tree::new("custom");
    // run.sh is "#!/bin/sh\n", 10 bytes; largest first under -r
    let (_, out, _) = ls(
        &t.0,
        &[
            "-o",
            "custom-columns=N:.name,S:.size",
            "--sort-by=.size",
            "-r",
            "--type=file",
        ],
    );
    assert_eq!(out, "run.sh  10\nb.txt   5\na.txt   2\n", "{out}");
    let (_, out, _) = ls(&t.0, &["--type=dir"]);
    assert_eq!(out, "sub\n");
    let (_, out, _) = ls(&t.0, &["--since=1h", "--type=file"]);
    assert_eq!(out, "a.txt\nb.txt\nrun.sh\n");
}

#[test]
fn recursion_depth_and_directory_headers() {
    let t = Tree::new("rec");
    let (_, out, _) = ls(&t.0, &["-R", "sub"]);
    assert_eq!(out, "sub:\nc.txt\ndeeper\n\nsub/deeper:\nd.txt\n");
    let (_, out, _) = ls(&t.0, &["-R", "--max-depth=0", "sub"]);
    assert_eq!(out, "sub:\nc.txt\ndeeper\n");
    let (_, out, _) = ls(&t.0, &["a.txt", "sub"]);
    assert_eq!(out, "a.txt\n\nsub:\nc.txt\ndeeper\n");
    let (_, out, _) = ls(&t.0, &["-d", "sub"]);
    assert_eq!(out, "sub\n");
}

#[test]
fn errors_are_reported_and_the_rest_is_listed() {
    let t = Tree::new("err");
    let (rc, out, err) = ls(&t.0, &["nope", "a.txt"]);
    assert_eq!(rc, 1);
    assert_eq!(out, "a.txt\n");
    assert_eq!(err, "ls: nope: No such file or directory\n");
    // A wrong command line is exit 2, nothing listed; wrong values name the option.
    let (rc, out, err) = ls(&t.0, &["-Z"]);
    assert_eq!(rc, 2);
    assert_eq!(out, "");
    assert!(
        err.starts_with("ls: unknown option -- Z\nusage: ls"),
        "{err}"
    );
    let (rc, _, err) = ls(&t.0, &["--max-depth=deep"]);
    assert_eq!(rc, 2);
    assert!(
        err.starts_with("ls: --max-depth: `deep` is not a whole number\n"),
        "{err}"
    );
}

#[test]
fn help_is_text_or_a_record() {
    let t = Tree::new("help");
    let (rc, out, _) = ls(&t.0, &["--help"]);
    assert_eq!(rc, 0);
    assert!(
        out.starts_with("ls: list directory contents\n\nusage: ls "),
        "{out}"
    );
    assert!(out.contains("\n  --help "), "{out}");
    let (rc, out, _) = ls(&t.0, &["-o", "json", "--help"]);
    assert_eq!(rc, 0);
    assert!(out.contains("\"kind\": \"CommandHelp\""), "{out}");
    assert!(out.contains("\"type\": \"duration\""), "{out}");
}
