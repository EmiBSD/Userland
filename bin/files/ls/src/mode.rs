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

//! The file mode as `ls -l` shows it and as `strmode(3)` defines it: a type letter and
//! three triplets, with `s`, `S`, `t` and `T` for the set-id and sticky bits.

pub const S_IFMT: u32 = 0o170000;
pub const S_IFIFO: u32 = 0o010000;
pub const S_IFCHR: u32 = 0o020000;
pub const S_IFDIR: u32 = 0o040000;
pub const S_IFBLK: u32 = 0o060000;
pub const S_IFREG: u32 = 0o100000;
pub const S_IFLNK: u32 = 0o120000;
pub const S_IFSOCK: u32 = 0o140000;
const S_ISUID: u32 = 0o4000;
const S_ISGID: u32 = 0o2000;
const S_ISVTX: u32 = 0o1000;

/// The type letter: `d`, `-`, `l`, `c`, `b`, `p`, `s`; `?` for a type the kernel invented.
pub fn type_char(mode: u32) -> char {
    match mode & S_IFMT {
        S_IFDIR => 'd',
        S_IFREG => '-',
        S_IFLNK => 'l',
        S_IFCHR => 'c',
        S_IFBLK => 'b',
        S_IFIFO => 'p',
        S_IFSOCK => 's',
        _ => '?',
    }
}

/// The ten characters of `ls -l`'s first column.
pub fn strmode(mode: u32) -> String {
    let mut s = String::with_capacity(10);
    s.push(type_char(mode));
    let triplet = |s: &mut String, r: u32, w: u32, x: u32, special: u32, on: char, off: char| {
        s.push(if mode & r != 0 { 'r' } else { '-' });
        s.push(if mode & w != 0 { 'w' } else { '-' });
        s.push(match (mode & x != 0, mode & special != 0) {
            (true, true) => on,
            (false, true) => off,
            (true, false) => 'x',
            (false, false) => '-',
        });
    };
    triplet(&mut s, 0o400, 0o200, 0o100, S_ISUID, 's', 'S');
    triplet(&mut s, 0o040, 0o020, 0o010, S_ISGID, 's', 'S');
    triplet(&mut s, 0o004, 0o002, 0o001, S_ISVTX, 't', 'T');
    s
}

/// The `-F` indicator: `/` directory, `*` executable, `@` symlink, `=` socket, `|` FIFO.
pub fn indicator(mode: u32) -> Option<char> {
    match mode & S_IFMT {
        S_IFDIR => Some('/'),
        S_IFLNK => Some('@'),
        S_IFSOCK => Some('='),
        S_IFIFO => Some('|'),
        _ if mode & 0o111 != 0 => Some('*'),
        _ => None,
    }
}

/// The kind as the record names it.
pub fn kind_name(mode: u32) -> &'static str {
    match mode & S_IFMT {
        S_IFDIR => "dir",
        S_IFREG => "file",
        S_IFLNK => "symlink",
        S_IFCHR => "char",
        S_IFBLK => "block",
        S_IFIFO => "fifo",
        S_IFSOCK => "socket",
        _ => "unknown",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn modes_as_strmode_prints_them() {
        assert_eq!(strmode(S_IFREG | 0o644), "-rw-r--r--");
        assert_eq!(strmode(S_IFDIR | 0o755), "drwxr-xr-x");
        assert_eq!(strmode(S_IFREG | 0o4755), "-rwsr-xr-x");
        assert_eq!(strmode(S_IFREG | 0o4644), "-rwSr--r--");
        assert_eq!(strmode(S_IFDIR | 0o2775), "drwxrwsr-x");
        assert_eq!(strmode(S_IFDIR | 0o1777), "drwxrwxrwt");
        assert_eq!(strmode(S_IFDIR | 0o1776), "drwxrwxrwT");
        assert_eq!(strmode(S_IFLNK | 0o777), "lrwxrwxrwx");
        assert_eq!(strmode(S_IFCHR | 0o600), "crw-------");
        assert_eq!(strmode(S_IFSOCK), "s---------");
    }

    #[test]
    fn indicators() {
        assert_eq!(indicator(S_IFDIR | 0o755), Some('/'));
        assert_eq!(indicator(S_IFREG | 0o755), Some('*'));
        assert_eq!(indicator(S_IFREG | 0o644), None);
        assert_eq!(indicator(S_IFLNK), Some('@'));
        assert_eq!(indicator(S_IFIFO), Some('|'));
        assert_eq!(indicator(S_IFSOCK), Some('='));
    }
}
