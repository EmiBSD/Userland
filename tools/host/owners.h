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
 * owners.h: forced into the host builds of the base system's tools that read or set the
 * owners of the tree being built (pax, mtree, pwd_mkdb), after compat.h. A build run by a
 * user cannot give DESTDIR's files their owners; the install, chown, chgrp and chmod
 * stand-ins record them in $WORLD_METALOG instead (tools/host/*.sh). With this header a
 * tool sees the tree as the target will have it (owners.c):
 *
 * - stat, lstat, fstat and the entries fts(3) returns carry, for a path under $WORLD_DESTDIR,
 *   the owner, group and permission bits the metalog last recorded for it (root and
 *   wheel for a path it never named);
 * - a user or group name is the tree's, from $WORLD_PASSWD and $WORLD_GROUP (its
 *   master.passwd and group), never the host's;
 * - chown and its relatives change nothing and record the owner in the metalog; chmod
 *   records the mode and applies it with the user keeping read and write, as the
 *   stand-ins do;
 * - a path under $WORLD_OBJDIR (the build's objects, which a re-link kit archives) is
 *   root's and wheel's, as a build run by root makes them;
 * - with $SOURCE_DATE_EPOCH set, no time of those paths is later than it, and the process
 *   id that names pax's extended headers is 0, so an archive is the same in every build.
 */
#ifndef EMIBSD_HOST_OWNERS_H
#define EMIBSD_HOST_OWNERS_H

#include <sys/types.h>
#include <sys/stat.h>
#include <fts.h>
#include <grp.h>
#include <pwd.h>
#include <unistd.h>

int emibsd_host_stat(const char *, struct stat *);
int emibsd_host_lstat(const char *, struct stat *);
int emibsd_host_fstat(int, struct stat *);
FTS *emibsd_host_fts_open(char * const *, int, int (*)(const FTSENT **, const FTSENT **));
int emibsd_host_fts_close(FTS *);
FTSENT *emibsd_host_fts_read(FTS *);
FTSENT *emibsd_host_fts_children(FTS *, int);
const char *emibsd_host_user_from_uid(uid_t, int);
const char *emibsd_host_group_from_gid(gid_t, int);
int emibsd_host_uid_from_user(const char *, uid_t *);
int emibsd_host_gid_from_group(const char *, gid_t *);
struct group *emibsd_host_getgrnam(const char *);
struct passwd *emibsd_host_getpwnam(const char *);
int emibsd_host_chown(const char *, uid_t, gid_t);
int emibsd_host_fchown(int, uid_t, gid_t);
int emibsd_host_fchownat(int, const char *, uid_t, gid_t, int);
int emibsd_host_chmod(const char *, mode_t);
pid_t emibsd_host_getpid(void);

#define stat(path, sb) emibsd_host_stat(path, sb)
#define lstat(path, sb) emibsd_host_lstat(path, sb)
#define fstat(fd, sb) emibsd_host_fstat(fd, sb)
#define fts_open emibsd_host_fts_open
#define fts_close emibsd_host_fts_close
#define fts_read(ftsp) emibsd_host_fts_read(ftsp)
#define fts_children(ftsp, options) emibsd_host_fts_children(ftsp, options)
#define user_from_uid emibsd_host_user_from_uid
#define group_from_gid emibsd_host_group_from_gid
#define uid_from_user emibsd_host_uid_from_user
#define gid_from_group emibsd_host_gid_from_group
#define getgrnam emibsd_host_getgrnam
#define getpwnam emibsd_host_getpwnam
#define chown emibsd_host_chown
#define lchown emibsd_host_chown
#define fchown emibsd_host_fchown
#define fchownat emibsd_host_fchownat
#define chmod emibsd_host_chmod
#define getpid emibsd_host_getpid

#endif /* EMIBSD_HOST_OWNERS_H */
