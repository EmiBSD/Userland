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
 * makefs-host.c: the lstat(2) and cgetent(3) that makefs(8) of the base system is built
 * with on the development host (makefs.h).
 *
 * lstat: a user cannot give the staging tree the owners, the modes or the device nodes
 * the image must have, so the build writes them to a table, $WORLD_ATTRS, one entry per
 * line, "<mode> <uid> <gid> <kind> <major> <minor> <path>": mode in octal, kind f, d, l, c
 * or b, path relative to $WORLD_STAGING. For a path under the staging tree the real
 * lstat's answer is corrected from the table: owner, group, permission bits, and for c and
 * b the file type and st_rdev in the base system's makedev() encoding. A path the table
 * does not name is root's and wheel's, with the permissions it has.
 *
 * cgetent: getdiskbyname(3) reads /etc/disktab; $WORLD_DISKTAB, when set, is read instead.
 */
#include <sys/types.h>
#include <sys/stat.h>

#include <err.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

struct attr {
	char		*path;
	mode_t		 mode;
	uid_t		 uid;
	gid_t		 gid;
	char		 kind;
	unsigned int	 major;
	unsigned int	 minor;
};

static struct attr	*attrs;
static size_t		 nattrs;
static int		 loaded;
static char		 staging[PATH_MAX];
static size_t		 staginglen;

static int
bypath(const void *a, const void *b)
{
	return strcmp(((const struct attr *)a)->path, ((const struct attr *)b)->path);
}

static void
load(void)
{
	const char *table, *root;
	char *line = NULL, path[PATH_MAX];
	size_t size = 0, cap = 0;
	unsigned int mode, uid, gid, major, minor;
	char kind;
	FILE *fp;

	if (loaded)
		return;
	loaded = 1;
	if ((root = getenv("WORLD_STAGING")) == NULL ||
	    (table = getenv("WORLD_ATTRS")) == NULL)
		return;
	if (realpath(root, staging) == NULL)
		err(1, "WORLD_STAGING %s", root);
	staginglen = strlen(staging);
	if ((fp = fopen(table, "r")) == NULL)
		err(1, "WORLD_ATTRS %s", table);
	while (getline(&line, &size, fp) != -1) {
		if (sscanf(line, "%o %u %u %c %u %u %[^\n]", &mode, &uid, &gid,
		    &kind, &major, &minor, path) != 7)
			errx(1, "%s: malformed line: %s", table, line);
		if (nattrs == cap) {
			cap = cap ? cap * 2 : 1024;
			if ((attrs = reallocarray(attrs, cap, sizeof(*attrs))) == NULL)
				err(1, NULL);
		}
		attrs[nattrs].path = strdup(path);
		attrs[nattrs].mode = mode;
		attrs[nattrs].uid = uid;
		attrs[nattrs].gid = gid;
		attrs[nattrs].kind = kind;
		attrs[nattrs].major = major;
		attrs[nattrs].minor = minor;
		if (attrs[nattrs].path == NULL)
			err(1, NULL);
		nattrs++;
	}
	free(line);
	fclose(fp);
	qsort(attrs, nattrs, sizeof(*attrs), bypath);
}

/* The path relative to the staging tree, "." for its root; NULL when outside it. */
static const char *
relative(const char *path, char *buf, size_t len)
{
	char full[PATH_MAX];
	const char *p;

	if (path[0] == '/')
		strlcpy(full, path, sizeof(full));
	else if (getcwd(full, sizeof(full)) == NULL ||
	    strlcat(full, "/", sizeof(full)) >= sizeof(full) ||
	    strlcat(full, path, sizeof(full)) >= sizeof(full))
		return NULL;
	if (strncmp(full, staging, staginglen) != 0 ||
	    (full[staginglen] != '/' && full[staginglen] != '\0'))
		return NULL;
	p = full + staginglen;
	buf[0] = '\0';
	/* Drop the empty and "." components makefs's walk leaves in its paths. */
	while (*p != '\0') {
		const char *q;
		size_t n;

		while (*p == '/')
			p++;
		q = strchr(p, '/');
		n = q ? (size_t)(q - p) : strlen(p);
		if (n != 0 && !(n == 1 && p[0] == '.')) {
			if (buf[0] != '\0' && strlcat(buf, "/", len) >= len)
				return NULL;
			if (strlen(buf) + n >= len)
				return NULL;
			strncat(buf, p, n);
		}
		p += n;
	}
	if (buf[0] == '\0')
		strlcpy(buf, ".", len);
	return buf;
}

int
emibsd_host_lstat(const char *path, struct stat *sb)
{
	char rel[PATH_MAX];
	struct attr key, *a;

	if (lstat(path, sb) == -1)
		return -1;
	load();
	if (staginglen == 0 || relative(path, rel, sizeof(rel)) == NULL)
		return 0;
	key.path = rel;
	a = bsearch(&key, attrs, nattrs, sizeof(*attrs), bypath);
	if (a == NULL) {
		sb->st_uid = 0;
		sb->st_gid = 0;
		return 0;
	}
	sb->st_uid = a->uid;
	sb->st_gid = a->gid;
	sb->st_mode = (sb->st_mode & S_IFMT) | (a->mode & 07777);
	if (a->kind == 'c' || a->kind == 'b') {
		sb->st_mode = (a->kind == 'c' ? S_IFCHR : S_IFBLK) | (a->mode & 07777);
		/* The base system's makedev(): minor's low byte, major, minor's upper bits. */
		sb->st_rdev = ((a->major & 0xff) << 8) | (a->minor & 0xff) |
		    ((a->minor & 0xffff00) << 8);
		sb->st_size = 0;
	}
	return 0;
}

int
emibsd_host_cgetent(char **buf, char **db, const char *name)
{
	char *disktab[2];

	if ((disktab[0] = getenv("WORLD_DISKTAB")) != NULL) {
		disktab[1] = NULL;
		return cgetent(buf, disktab, name);
	}
	return cgetent(buf, db, name);
}
