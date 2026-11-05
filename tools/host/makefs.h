/*
 * Copyright (c) 2026 Emilio Navarrete Lineros <enavarre@outlook.com>
 *
 * Permission to use, copy, modify, and distribute this software for any
 * purpose with or without fee is hereby granted, provided that the above
 * copyright notice and this permission notice appear in all copies.
 *
 * THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
 * WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
 * MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
 * ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
 * WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
 * ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
 * OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
 */

/*
 * makefs.h: what makefs(8) of the base system needs on the development host beyond
 * compat.h. Forced in after it. The image makefs writes is EmiBSD's, so its types are
 * EmiBSD's: a 64-bit daddr_t and a 64 KiB MAXBSIZE (the host's are 32 bits and 1 MiB).
 * lstat(2) and cgetent(3) are wrapped (makefs-host.c): makefs takes every file's owner,
 * mode and kind from lstat of the staging tree, which a user cannot set (devices, root's
 * files), so the wrapper reports them from the table the build wrote; and the disktab it
 * reads is the one the build names, not the host's /etc/disktab.
 */
#ifndef EMIBSD_HOST_MAKEFS_H
#define EMIBSD_HOST_MAKEFS_H

#include <sys/param.h>
#include <sys/stat.h>

#define daddr_t int64_t
#undef MAXBSIZE
#define MAXBSIZE (64 * 1024)

int emibsd_host_lstat(const char *, struct stat *);
#define lstat(path, sb) emibsd_host_lstat(path, sb)
int emibsd_host_cgetent(char **, char **, const char *);
#define cgetent(buf, db, name) emibsd_host_cgetent(buf, db, name)
int scan_scaled(char *, long long *);

#endif /* EMIBSD_HOST_MAKEFS_H */
