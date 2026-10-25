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

//! The names of the errno numbers of the BSD lineage, the same on EmiBSD and on its
//! development host for the first eighty-one: what a `Diagnostic` record carries as `code`,
//! so a tool decides by `EACCES` and never by the text of strerror(3).

/// The standard name of errno `n`, or `None` beyond the shared range.
pub fn errno_name(n: i32) -> Option<&'static str> {
    const NAMES: [&str; 81] = [
        "EPERM",
        "ENOENT",
        "ESRCH",
        "EINTR",
        "EIO",
        "ENXIO",
        "E2BIG",
        "ENOEXEC",
        "EBADF",
        "ECHILD",
        "EDEADLK",
        "ENOMEM",
        "EACCES",
        "EFAULT",
        "ENOTBLK",
        "EBUSY",
        "EEXIST",
        "EXDEV",
        "ENODEV",
        "ENOTDIR",
        "EISDIR",
        "EINVAL",
        "ENFILE",
        "EMFILE",
        "ENOTTY",
        "ETXTBSY",
        "EFBIG",
        "ENOSPC",
        "ESPIPE",
        "EROFS",
        "EMLINK",
        "EPIPE",
        "EDOM",
        "ERANGE",
        "EAGAIN",
        "EINPROGRESS",
        "EALREADY",
        "ENOTSOCK",
        "EDESTADDRREQ",
        "EMSGSIZE",
        "EPROTOTYPE",
        "ENOPROTOOPT",
        "EPROTONOSUPPORT",
        "ESOCKTNOSUPPORT",
        "EOPNOTSUPP",
        "EPFNOSUPPORT",
        "EAFNOSUPPORT",
        "EADDRINUSE",
        "EADDRNOTAVAIL",
        "ENETDOWN",
        "ENETUNREACH",
        "ENETRESET",
        "ECONNABORTED",
        "ECONNRESET",
        "ENOBUFS",
        "EISCONN",
        "ENOTCONN",
        "ESHUTDOWN",
        "ETOOMANYREFS",
        "ETIMEDOUT",
        "ECONNREFUSED",
        "ELOOP",
        "ENAMETOOLONG",
        "EHOSTDOWN",
        "EHOSTUNREACH",
        "ENOTEMPTY",
        "EPROCLIM",
        "EUSERS",
        "EDQUOT",
        "ESTALE",
        "EREMOTE",
        "EBADRPC",
        "ERPCMISMATCH",
        "EPROGUNAVAIL",
        "EPROGMISMATCH",
        "EPROCUNAVAIL",
        "ENOLCK",
        "ENOSYS",
        "EFTYPE",
        "EAUTH",
        "ENEEDAUTH",
    ];
    usize::try_from(n)
        .ok()
        .and_then(|i| i.checked_sub(1))
        .and_then(|i| NAMES.get(i))
        .copied()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_shared_range_and_its_edges() {
        assert_eq!(errno_name(1), Some("EPERM"));
        assert_eq!(errno_name(2), Some("ENOENT"));
        assert_eq!(errno_name(13), Some("EACCES"));
        assert_eq!(errno_name(17), Some("EEXIST"));
        assert_eq!(errno_name(81), Some("ENEEDAUTH"));
        assert_eq!(errno_name(0), None);
        assert_eq!(errno_name(-1), None);
        assert_eq!(errno_name(82), None);
        let e = std::io::Error::from_raw_os_error(13);
        assert_eq!(e.kind(), std::io::ErrorKind::PermissionDenied);
    }
}
