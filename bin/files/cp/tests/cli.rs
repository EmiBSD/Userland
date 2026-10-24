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

//! Integration tests: the binary on a small tree, output to a pipe. The differential tests
//! against OpenBSD's cp (tests/golden) run on EmiBSD, not here.

use std::fs::{self, File, FileTimes};
use std::io::Write;
use std::os::unix::fs::{MetadataExt, PermissionsExt, symlink};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{Duration, UNIX_EPOCH};

struct Tree(PathBuf);

impl Tree {
    fn new(tag: &str) -> Tree {
        let dir = std::env::temp_dir().join(format!("emibsd-cp-test-{}-{tag}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(dir.join("src/sub/deeper")).unwrap();
        fs::write(dir.join("a.txt"), b"hello").unwrap();
        fs::write(dir.join("b.txt"), b"hi").unwrap();
        fs::write(dir.join("src/one"), b"one").unwrap();
        fs::write(dir.join("src/sub/two"), b"two two").unwrap();
        fs::write(dir.join("src/sub/deeper/three"), b"").unwrap();
        symlink("one", dir.join("src/link")).unwrap();
        symlink("nowhere", dir.join("src/broken")).unwrap();
        fs::create_dir_all(dir.join("dest")).unwrap();
        Tree(dir)
    }

    fn path(&self, p: &str) -> PathBuf {
        self.0.join(p)
    }

    fn read(&self, p: &str) -> String {
        fs::read_to_string(self.path(p)).unwrap_or_else(|e| panic!("{p}: {e}"))
    }
}

impl Drop for Tree {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

fn run(dir: &Path, args: &[&str], stdin: Option<&str>) -> (i32, String, String) {
    let mut cmd = Command::new(env!("CARGO_BIN_EXE_cp"));
    cmd.args(args)
        .current_dir(dir)
        .env("TZ", "UTC")
        .stdin(if stdin.is_some() {
            Stdio::piped()
        } else {
            Stdio::null()
        })
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    let mut child = cmd.spawn().expect("runs cp");
    if let Some(s) = stdin {
        child.stdin.take().unwrap().write_all(s.as_bytes()).unwrap();
    }
    let out = child.wait_with_output().unwrap();
    (
        out.status.code().unwrap_or(-1),
        String::from_utf8_lossy(&out.stdout).into_owned(),
        String::from_utf8_lossy(&out.stderr).into_owned(),
    )
}

fn cp(dir: &Path, args: &[&str]) -> (i32, String, String) {
    run(dir, args, None)
}

fn mode(p: &Path) -> u32 {
    fs::symlink_metadata(p).unwrap().mode() & 0o7777
}

#[test]
fn a_file_to_a_new_name_and_files_into_a_directory() {
    let t = Tree::new("basic");
    let (rc, out, err) = cp(&t.0, &["a.txt", "copy.txt"]);
    assert_eq!((rc, out.as_str(), err.as_str()), (0, "", ""));
    assert_eq!(t.read("copy.txt"), "hello");
    fs::set_permissions(t.path("a.txt"), fs::Permissions::from_mode(0o640)).unwrap();
    let (rc, _, _) = cp(&t.0, &["a.txt", "b.txt", "dest"]);
    assert_eq!(rc, 0);
    assert_eq!(t.read("dest/a.txt"), "hello");
    assert_eq!(t.read("dest/b.txt"), "hi");
    // a new file takes the source's mode, shaped by the umask (022 at most here)
    assert_eq!(mode(&t.path("dest/a.txt")) | 0o022, 0o640 | 0o022);
}

#[test]
fn an_existing_target_keeps_its_mode_unless_forced() {
    let t = Tree::new("exists");
    fs::write(t.path("old"), b"old contents").unwrap();
    fs::set_permissions(t.path("old"), fs::Permissions::from_mode(0o600)).unwrap();
    let (rc, _, _) = cp(&t.0, &["a.txt", "old"]);
    assert_eq!(rc, 0);
    assert_eq!(t.read("old"), "hello");
    assert_eq!(mode(&t.path("old")), 0o600, "written over, mode kept");
    // read-only: writing over fails, -f removes it first
    fs::write(t.path("ro"), b"x").unwrap();
    fs::set_permissions(t.path("ro"), fs::Permissions::from_mode(0o444)).unwrap();
    if sys_is_not_root() {
        let (rc, _, err) = cp(&t.0, &["a.txt", "ro"]);
        assert_eq!(rc, 1, "{err}");
        assert!(err.starts_with("cp: ro: Permission denied"), "{err}");
        assert_eq!(t.read("ro"), "x");
    }
    let (rc, _, err) = cp(&t.0, &["-f", "a.txt", "ro"]);
    assert_eq!(rc, 0, "{err}");
    assert_eq!(t.read("ro"), "hello");
}

fn sys_is_not_root() -> bool {
    fs::metadata("/").map(|m| m.uid()).unwrap_or(0) != 0
        || std::env::var("USER").map(|u| u != "root").unwrap_or(true)
}

#[test]
fn interactive_asks_and_a_no_skips_without_error() {
    let t = Tree::new("ask");
    fs::write(t.path("keep"), b"keep me").unwrap();
    let (rc, out, err) = run(&t.0, &["-i", "a.txt", "keep"], Some("n\n"));
    assert_eq!(rc, 0);
    assert_eq!(out, "");
    assert_eq!(err, "overwrite keep? ");
    assert_eq!(t.read("keep"), "keep me");
    let (rc, _, _) = run(&t.0, &["-i", "-o", "json", "a.txt", "keep"], Some("yes\n"));
    assert_eq!(rc, 0);
    assert_eq!(t.read("keep"), "hello");
    // -i then -f: the last wins, no question asked
    let (rc, _, err) = cp(&t.0, &["-if", "b.txt", "keep"]);
    assert_eq!((rc, err.as_str()), (0, ""));
    assert_eq!(t.read("keep"), "hi");
}

#[test]
fn refusals_are_reported_and_the_rest_is_copied() {
    let t = Tree::new("refuse");
    let (rc, out, err) = cp(&t.0, &["a.txt", "a.txt"]);
    assert_eq!((rc, out.as_str()), (1, ""));
    assert_eq!(err, "cp: a.txt and a.txt are identical (not copied).\n");
    let (rc, _, err) = cp(&t.0, &["src", "nope", "a.txt", "dest"]);
    assert_eq!(rc, 1);
    assert_eq!(
        err,
        "cp: src is a directory (not copied).\ncp: nope: No such file or directory\n"
    );
    assert_eq!(t.read("dest/a.txt"), "hello");
    let (rc, _, err) = cp(&t.0, &["a.txt", "src"]);
    assert_eq!(
        rc, 0,
        "a file into an existing directory goes under its name: {err}"
    );
    assert_eq!(t.read("src/a.txt"), "hello");
    let (rc, _, err) = cp(&t.0, &["-R", "src", "a.txt"]);
    assert_eq!(rc, 1);
    assert_eq!(err, "cp: a.txt: Not a directory\n");
}

#[test]
fn recursion_keeps_links_by_default_and_follows_with_l() {
    let t = Tree::new("tree");
    let (rc, out, err) = cp(&t.0, &["-R", "src", "copy"]);
    assert_eq!((rc, out.as_str(), err.as_str()), (0, "", ""));
    assert_eq!(t.read("copy/one"), "one");
    assert_eq!(t.read("copy/sub/two"), "two two");
    assert_eq!(t.read("copy/sub/deeper/three"), "");
    let link = fs::symlink_metadata(t.path("copy/link")).unwrap();
    assert!(link.file_type().is_symlink());
    assert_eq!(
        fs::read_link(t.path("copy/link")).unwrap(),
        Path::new("one")
    );
    assert!(
        fs::symlink_metadata(t.path("copy/broken"))
            .unwrap()
            .file_type()
            .is_symlink()
    );
    // -L: the link's target is copied; the broken one stays a link
    let (rc, _, err) = cp(&t.0, &["-RL", "src", "copyl"]);
    assert_eq!(rc, 0, "{err}");
    assert!(
        fs::symlink_metadata(t.path("copyl/link"))
            .unwrap()
            .file_type()
            .is_file()
    );
    assert_eq!(t.read("copyl/link"), "one");
    assert!(
        fs::symlink_metadata(t.path("copyl/broken"))
            .unwrap()
            .file_type()
            .is_symlink()
    );
    // into an existing directory: under its own name; `src/.` means its contents
    let (rc, _, _) = cp(&t.0, &["-R", "src", "dest"]);
    assert_eq!(rc, 0);
    assert_eq!(t.read("dest/src/sub/two"), "two two");
    fs::create_dir(t.path("contents")).unwrap();
    let (rc, _, err) = cp(&t.0, &["-R", "src/.", "contents"]);
    assert_eq!(rc, 0, "{err}");
    assert_eq!(t.read("contents/one"), "one");
    assert!(!t.path("contents/src").exists());
    // -H: an operand that is a link is followed, links below are not
    symlink("src", t.path("srclink")).unwrap();
    let (rc, _, err) = cp(&t.0, &["-RH", "srclink", "copyh"]);
    assert_eq!(rc, 0, "{err}");
    assert!(
        t.path("copyh").is_dir()
            && !fs::symlink_metadata(t.path("copyh"))
                .unwrap()
                .file_type()
                .is_symlink()
    );
    assert!(
        fs::symlink_metadata(t.path("copyh/link"))
            .unwrap()
            .file_type()
            .is_symlink()
    );
    // -P (the default): the link operand itself is copied
    let (rc, _, _) = cp(&t.0, &["-R", "srclink", "copyp"]);
    assert_eq!(rc, 0);
    assert!(
        fs::symlink_metadata(t.path("copyp"))
            .unwrap()
            .file_type()
            .is_symlink()
    );
}

#[test]
fn a_cycle_under_l_is_refused_once() {
    let t = Tree::new("cycle");
    symlink("..", t.path("src/sub/up")).unwrap();
    let (rc, _, err) = cp(&t.0, &["-RL", "src", "copy"]);
    assert_eq!(rc, 1);
    assert_eq!(err, "cp: src/sub/up: directory causes a cycle\n");
    assert_eq!(t.read("copy/sub/two"), "two two");
}

#[test]
fn preserve_keeps_times_and_mode() {
    let t = Tree::new("preserve");
    let f = File::options().write(true).open(t.path("a.txt")).unwrap();
    let when = UNIX_EPOCH + Duration::new(1_000_000_000, 123_000_000);
    f.set_times(FileTimes::new().set_accessed(when).set_modified(when))
        .unwrap();
    fs::set_permissions(t.path("a.txt"), fs::Permissions::from_mode(0o640)).unwrap();
    fs::set_permissions(t.path("src/sub"), fs::Permissions::from_mode(0o750)).unwrap();
    let (rc, _, err) = cp(&t.0, &["-p", "a.txt", "p.txt"]);
    assert_eq!(rc, 0, "{err}");
    let m = fs::metadata(t.path("p.txt")).unwrap();
    assert_eq!(m.mtime(), 1_000_000_000);
    assert_eq!(m.mode() & 0o7777, 0o640);
    let (rc, _, err) = cp(&t.0, &["-a", "src", "arch"]);
    assert_eq!(rc, 0, "{err}");
    assert_eq!(mode(&t.path("arch/sub")), 0o750);
    assert!(
        fs::symlink_metadata(t.path("arch/link"))
            .unwrap()
            .file_type()
            .is_symlink()
    );
    // without -p a created directory still gets the source's mode, unshaped by the umask
    fs::set_permissions(t.path("src/sub"), fs::Permissions::from_mode(0o777)).unwrap();
    let (rc, _, _) = cp(&t.0, &["-R", "src", "plain"]);
    assert_eq!(rc, 0);
    assert_eq!(mode(&t.path("plain/sub")), 0o777);
}

#[test]
fn zero_blocks_are_skipped_and_the_copy_is_whole() {
    // The hole path runs (every 64 KB block of zeros is seeked over, the length fixed at the
    // end); whether the file system makes a hole of it is its own business: the APFS volume
    // of the development host does not (dd with seek= allocates too), so blocks are only
    // checked not to grow. The real measure is cp(1)'s bench on EmiBSD.
    let t = Tree::new("sparse");
    let mut zeros = vec![0u8; 4 * 1024 * 1024];
    zeros[100] = 1;
    fs::write(t.path("big"), &zeros).unwrap();
    let (rc, _, err) = cp(&t.0, &["big", "big2"]);
    assert_eq!(rc, 0, "{err}");
    assert_eq!(fs::read(t.path("big2")).unwrap(), zeros);
    let src = fs::metadata(t.path("big")).unwrap();
    let dst = fs::metadata(t.path("big2")).unwrap();
    assert_eq!(dst.len(), src.len());
    assert!(
        dst.blocks() <= src.blocks(),
        "{} vs {} blocks",
        dst.blocks(),
        src.blocks()
    );
}

#[test]
fn a_fifo_is_recreated_under_r() {
    let t = Tree::new("fifo");
    sys::mkfifo(&t.path("src/pipe"), 0o600).unwrap();
    let (rc, _, err) = cp(&t.0, &["-R", "src", "copy"]);
    assert_eq!(rc, 0, "{err}");
    use std::os::unix::fs::FileTypeExt;
    assert!(
        fs::symlink_metadata(t.path("copy/pipe"))
            .unwrap()
            .file_type()
            .is_fifo()
    );
}

#[test]
fn verbose_dry_run_and_the_records() {
    let t = Tree::new("records");
    let (rc, out, err) = cp(&t.0, &["-v", "a.txt", "v.txt"]);
    assert_eq!((rc, err.as_str()), (0, ""));
    assert_eq!(out, "a.txt -> v.txt\n");
    let (rc, out, _) = cp(&t.0, &["-Rv", "--dry-run", "src", "planned"]);
    assert_eq!(rc, 0);
    assert!(
        out.starts_with("src -> planned\nsrc/broken -> planned/broken\n"),
        "{out}"
    );
    assert!(!t.path("planned").exists(), "dry run wrote nothing");
    let (rc, out, _) = cp(&t.0, &["-R", "--dry-run", "-o", "json", "src", "planned"]);
    assert_eq!(rc, 0);
    assert!(
        out.starts_with("{\n  \"apiVersion\": \"emibsd.org/v1\",\n  \"kind\": \"CopyList\","),
        "{out}"
    );
    assert!(out.contains("\"action\": \"planned\""), "{out}");
    assert!(out.contains("\"type\": \"symlink\""), "{out}");
    assert!(!out.contains("\"action\": \"created\""), "{out}");
    let (rc, out, _) = cp(&t.0, &["-o", "json", "a.txt", "j.txt"]);
    assert_eq!(rc, 0);
    for field in [
        "\"source\": \"a.txt\"",
        "\"target\": \"j.txt\"",
        "\"type\": \"file\"",
        "\"action\": \"created\"",
        "\"size\": 5",
    ] {
        assert!(out.contains(field), "missing {field} in {out}");
    }
    let (_, out, _) = cp(&t.0, &["-o", "json", "a.txt", "j.txt"]);
    assert!(out.contains("\"action\": \"replaced\""), "{out}");
    let (_, out, _) = cp(&t.0, &["-o", "name", "a.txt", "b.txt", "dest"]);
    assert_eq!(out, "dest/a.txt\ndest/b.txt\n");
    let (_, out, _) = cp(&t.0, &["-o", "table", "a.txt", "t.txt"]);
    assert_eq!(out, "a.txt  t.txt  file  5  created\n");
    let (_, out, _) = cp(
        &t.0,
        &["-o", "custom-columns=T:.target,A:.action", "a.txt", "c.txt"],
    );
    assert_eq!(out, "c.txt  created\n");
    let (rc, out, err) = cp(&t.0, &["-o", "yaml", "a.txt", "src/sub"]);
    assert_eq!(rc, 0, "{err}");
    assert!(out.starts_with("apiVersion: emibsd.org/v1\nkind: CopyList\nitems:\n  - source: a.txt\n    target: src/sub/a.txt\n"), "{out}");
    // a failure is a record too, and goes to stderr
    let (rc, out, err) = cp(&t.0, &["-o", "json", "nope", "x"]);
    assert_eq!(rc, 1);
    assert_eq!(err, "cp: nope: No such file or directory\n");
    assert!(
        out.contains("\"action\": \"failed\"")
            && out.contains("\"error\": \"nope: No such file or directory\""),
        "{out}"
    );
}

#[test]
fn a_failed_standard_output_is_a_failure() {
    // Only a device that refuses writes shows it: std's stdout swallows EBADF (a closed or
    // read-only descriptor is written to "successfully"), and a closed pipe is a quiet exit
    // by design. /dev/full exists on Linux and NetBSD, not on macOS or OpenBSD; without it
    // the test checks only that the copy itself is made.
    let t = Tree::new("stdout");
    let Ok(full) = File::options().write(true).open("/dev/full") else {
        let (rc, _, _) = cp(&t.0, &["-v", "a.txt", "w.txt"]);
        assert_eq!(rc, 0);
        assert_eq!(t.read("w.txt"), "hello");
        return;
    };
    let out = Command::new(env!("CARGO_BIN_EXE_cp"))
        .args(["-v", "a.txt", "w.txt"])
        .current_dir(&t.0)
        .stdin(Stdio::null())
        .stdout(full)
        .stderr(Stdio::piped())
        .output()
        .unwrap();
    assert_eq!(out.status.code(), Some(1));
    assert!(
        String::from_utf8_lossy(&out.stderr).starts_with("cp: stdout: "),
        "{:?}",
        out.stderr
    );
    assert_eq!(t.read("w.txt"), "hello", "the copy itself was made");
}

#[test]
fn usage_errors_exit_2_and_help_is_a_record() {
    let t = Tree::new("usage");
    let (rc, out, err) = cp(&t.0, &["a.txt"]);
    assert_eq!((rc, out.as_str()), (2, ""));
    assert!(
        err.starts_with(
            "cp: a source and a target are required\nusage: cp [-afipv] [-R [-H | -L | -P]]"
        ),
        "{err}"
    );
    assert!(err.contains("\n       cp [-afipv]"), "{err}");
    let (rc, _, err) = cp(&t.0, &["a.txt", "b.txt", "c.txt"]);
    assert_eq!(rc, 2);
    assert!(
        err.starts_with("cp: c.txt: No such file or directory\nusage: cp"),
        "{err}"
    );
    let (rc, _, err) = cp(&t.0, &["a.txt", "b.txt", "src/one"]);
    assert_eq!(rc, 2);
    assert!(err.starts_with("cp: src/one: not a directory\n"), "{err}");
    let (rc, _, err) = cp(&t.0, &["-Z", "a", "b"]);
    assert_eq!(rc, 2);
    assert!(
        err.starts_with("cp: unknown option -- Z\nusage: cp"),
        "{err}"
    );
    let (rc, out, _) = cp(&t.0, &["--help", "-o", "json"]);
    assert_eq!(rc, 0);
    assert!(
        out.contains("\"kind\": \"CommandHelp\"") && out.contains("\"long\": \"--dry-run\""),
        "{out}"
    );
}
