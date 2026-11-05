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
 * owners.c: the functions owners.h puts in the place of the host's, for the host builds
 * of the base system's tools that read or set the owners of the tree being built.
 *
 * $WORLD_METALOG holds one record per line, "<path> [uname=<name>] [gname=<name>]
 * [mode=<octal>]", a later field for the same path winning. $WORLD_DESTDIR is the tree;
 * only a path under it is corrected. $WORLD_PASSWD and $WORLD_GROUP are the tree's
 * master.passwd(5) and group(5), which turn the recorded names into ids. Compiled without
 * owners.h, so the host's functions are the ones called here.
 */
#include <sys/types.h>
#include <sys/stat.h>

#include <err.h>
#include <errno.h>
#include <fcntl.h>
#include <fts.h>
#include <grp.h>
#include <limits.h>
#include <pwd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define NAME_LEN 64

struct record {
	char	*path;
	size_t	 order;			/* its first line, for a stable merge */
	char	 uname[NAME_LEN];
	char	 gname[NAME_LEN];
	mode_t	 mode;
	int	 has_mode;
};

struct id {
	char	 name[NAME_LEN];
	unsigned int number;
};

static struct record	*records;
static size_t		 nrecords;
static struct id	*users, *groups;
static size_t		 nusers, ngroups;
static char		 destdir[PATH_MAX];
static size_t		 destdirlen;
static int		 loaded;

/* The open trees and the directory each was opened from, which their paths are relative to. */
#define MAX_TREES 16
static struct {
	FTS	*fts;
	char	 cwd[PATH_MAX];
} trees[MAX_TREES];

/*
 * `path` made absolute and its directory resolved, its last component kept as it is (a
 * symbolic link is the link, as chown -h and lstat see it). Returns buf, or NULL when the
 * result does not fit.
 */
static char *
normal(const char *path, const char *cwd, char *buf, size_t len)
{
	char full[PATH_MAX], dir[PATH_MAX], *slash;
	const char *base;

	if (path[0] == '/')
		strlcpy(full, path, sizeof(full));
	else if (snprintf(full, sizeof(full), "%s/%s", cwd, path) >= (int)sizeof(full))
		return NULL;
	/* No trailing slashes, and "x/." is x. */
	for (size_t n = strlen(full); n > 1 && full[n - 1] == '/'; n--)
		full[n - 1] = '\0';
	for (size_t n = strlen(full); n > 2 && strcmp(full + n - 2, "/.") == 0; n = strlen(full))
		full[n - 2] = '\0';
	slash = strrchr(full, '/');
	base = slash + 1;
	if (slash == full)
		strlcpy(dir, "/", sizeof(dir));
	else {
		*slash = '\0';
		if (realpath(full, dir) == NULL)
			strlcpy(dir, full, sizeof(dir));
	}
	if (strcmp(base, "..") == 0 || strcmp(base, ".") == 0 || base[0] == '\0') {
		if (snprintf(full, sizeof(full), "%s/%s", dir, base) >= (int)sizeof(full) ||
		    realpath(full, buf) == NULL)
			return NULL;
		return buf;
	}
	if (snprintf(buf, len, "%s%s%s", dir, strcmp(dir, "/") == 0 ? "" : "/", base) >= (int)len)
		return NULL;
	return buf;
}

static int
byname(const void *a, const void *b)
{
	const struct record *x = a, *y = b;
	int c = strcmp(x->path, y->path);

	if (c != 0)
		return c;
	return x->order < y->order ? -1 : x->order > y->order;
}

/* A field-per-line file of names and numbers: master.passwd(5) and group(5) alike. */
static void
load_ids(const char *file, struct id **ids, size_t *n)
{
	char *line = NULL, *name, *number, *p;
	size_t size = 0, cap = 0;
	FILE *fp;

	if (file == NULL || (fp = fopen(file, "r")) == NULL)
		return;
	while (getline(&line, &size, fp) != -1) {
		p = line;
		if ((name = strsep(&p, ":")) == NULL || strsep(&p, ":") == NULL ||
		    (number = strsep(&p, ":\n")) == NULL || *name == '#' || *name == '\0')
			continue;
		if (*n == cap) {
			cap = cap ? cap * 2 : 64;
			if ((*ids = reallocarray(*ids, cap, sizeof(**ids))) == NULL)
				err(1, NULL);
		}
		strlcpy((*ids)[*n].name, name, NAME_LEN);
		(*ids)[*n].number = (unsigned int)strtoul(number, NULL, 10);
		(*n)++;
	}
	free(line);
	fclose(fp);
}

static void
load(void)
{
	char *line = NULL, *p, *word, cwd[PATH_MAX], path[PATH_MAX];
	const char *root, *metalog;
	size_t size = 0, cap = 0, lines = 0, i, j;
	FILE *fp;

	if (loaded)
		return;
	loaded = 1;
	load_ids(getenv("WORLD_PASSWD"), &users, &nusers);
	load_ids(getenv("WORLD_GROUP"), &groups, &ngroups);
	if ((root = getenv("WORLD_DESTDIR")) == NULL || realpath(root, destdir) == NULL)
		return;
	destdirlen = strlen(destdir);
	if ((metalog = getenv("WORLD_METALOG")) == NULL || (fp = fopen(metalog, "r")) == NULL)
		return;
	if (getcwd(cwd, sizeof(cwd)) == NULL)
		err(1, "getcwd");
	while (getline(&line, &size, fp) != -1) {
		struct record r = { .order = lines++ };

		p = line;
		if ((word = strsep(&p, " \t\n")) == NULL || *word == '\0' ||
		    normal(word, cwd, path, sizeof(path)) == NULL)
			continue;
		while ((word = strsep(&p, " \t\n")) != NULL) {
			if (strncmp(word, "uname=", 6) == 0)
				strlcpy(r.uname, word + 6, sizeof(r.uname));
			else if (strncmp(word, "gname=", 6) == 0)
				strlcpy(r.gname, word + 6, sizeof(r.gname));
			else if (strncmp(word, "mode=", 5) == 0) {
				char *end;
				unsigned long m = strtoul(word + 5, &end, 8);

				/* A symbolic mode the stand-ins could not reduce is not used. */
				if (*end == '\0' && end != word + 5) {
					r.mode = (mode_t)(m & 07777);
					r.has_mode = 1;
				}
			}
		}
		if ((r.path = strdup(path)) == NULL)
			err(1, NULL);
		if (nrecords == cap) {
			cap = cap ? cap * 2 : 4096;
			if ((records = reallocarray(records, cap, sizeof(*records))) == NULL)
				err(1, NULL);
		}
		records[nrecords++] = r;
	}
	free(line);
	fclose(fp);
	/* One record per path, its fields from the last line that gave each. */
	qsort(records, nrecords, sizeof(*records), byname);
	for (i = 0, j = 0; i < nrecords; i++) {
		if (j > 0 && strcmp(records[j - 1].path, records[i].path) == 0) {
			struct record *into = &records[j - 1];

			if (records[i].uname[0] != '\0')
				strlcpy(into->uname, records[i].uname, sizeof(into->uname));
			if (records[i].gname[0] != '\0')
				strlcpy(into->gname, records[i].gname, sizeof(into->gname));
			if (records[i].has_mode) {
				into->mode = records[i].mode;
				into->has_mode = 1;
			}
			free(records[i].path);
		} else
			records[j++] = records[i];
	}
	nrecords = j;
}

static const struct id *
by_name(const struct id *ids, size_t n, const char *name)
{
	for (size_t i = 0; i < n; i++)
		if (strcmp(ids[i].name, name) == 0)
			return &ids[i];
	return NULL;
}

static const struct id *
by_number(const struct id *ids, size_t n, unsigned int number)
{
	for (size_t i = 0; i < n; i++)
		if (ids[i].number == number)
			return &ids[i];
	return NULL;
}

/* A recorded name as a number: the tree's, or the name itself when it is a number. */
static unsigned int
number_of(const struct id *ids, size_t n, const char *name)
{
	const struct id *id = by_name(ids, n, name);
	char *end;
	unsigned long v;

	if (id != NULL)
		return id->number;
	v = strtoul(name, &end, 10);
	return *end == '\0' && end != name ? (unsigned int)v : 0;
}

/* The tree's view of `path` (relative to `cwd`) written over what the host said in `sb`. */
static void
correct(const char *path, const char *cwd, struct stat *sb)
{
	char full[PATH_MAX], here[PATH_MAX];
	struct record key, *r;

	load();
	if (destdirlen == 0)
		return;
	if (cwd == NULL) {
		if (getcwd(here, sizeof(here)) == NULL)
			return;
		cwd = here;
	}
	if (normal(path, cwd, full, sizeof(full)) == NULL ||
	    strncmp(full, destdir, destdirlen) != 0 ||
	    (full[destdirlen] != '/' && full[destdirlen] != '\0'))
		return;
	key.path = full;
	key.order = 0;
	r = NULL;
	if (nrecords > 0) {
		/* bsearch on the path alone: the records are one per path after the merge. */
		size_t lo = 0, hi = nrecords;

		while (lo < hi) {
			size_t mid = (lo + hi) / 2;
			int c = strcmp(records[mid].path, key.path);

			if (c == 0) {
				r = &records[mid];
				break;
			}
			if (c < 0)
				lo = mid + 1;
			else
				hi = mid;
		}
	}
	sb->st_uid = r != NULL && r->uname[0] != '\0' ? number_of(users, nusers, r->uname) : 0;
	sb->st_gid = r != NULL && r->gname[0] != '\0' ? number_of(groups, ngroups, r->gname) : 0;
	if (r != NULL && r->has_mode)
		sb->st_mode = (sb->st_mode & S_IFMT) | r->mode;
}

int
emibsd_host_stat(const char *path, struct stat *sb)
{
	if (stat(path, sb) == -1)
		return -1;
	correct(path, NULL, sb);
	return 0;
}

int
emibsd_host_lstat(const char *path, struct stat *sb)
{
	if (lstat(path, sb) == -1)
		return -1;
	correct(path, NULL, sb);
	return 0;
}

FTS *
emibsd_host_fts_open(char * const *argv, int options,
    int (*compar)(const FTSENT **, const FTSENT **))
{
	FTS *fts;
	size_t i;

	if ((fts = fts_open(argv, options, compar)) == NULL)
		return NULL;
	for (i = 0; i < MAX_TREES; i++)
		if (trees[i].fts == NULL) {
			trees[i].fts = fts;
			if (getcwd(trees[i].cwd, sizeof(trees[i].cwd)) == NULL)
				trees[i].cwd[0] = '\0';
			break;
		}
	return fts;
}

int
emibsd_host_fts_close(FTS *fts)
{
	for (size_t i = 0; i < MAX_TREES; i++)
		if (trees[i].fts == fts)
			trees[i].fts = NULL;
	return fts_close(fts);
}

static const char *
opened_from(FTS *fts)
{
	for (size_t i = 0; i < MAX_TREES; i++)
		if (trees[i].fts == fts && trees[i].cwd[0] != '\0')
			return trees[i].cwd;
	return NULL;
}

/* fts_path is relative to where the walk began, wherever fts has gone since. */
static void
correct_entry(FTS *fts, FTSENT *e)
{
	const char *cwd = opened_from(fts);

	if (e->fts_statp == NULL || e->fts_info == FTS_NS || e->fts_info == FTS_NSOK ||
	    e->fts_info == FTS_ERR || e->fts_info == FTS_DNR)
		return;
	if (cwd == NULL && e->fts_path[0] != '/')
		return;
	correct(e->fts_path, cwd != NULL ? cwd : "/", e->fts_statp);
}

FTSENT *
emibsd_host_fts_read(FTS *fts)
{
	FTSENT *e = fts_read(fts);

	if (e != NULL)
		correct_entry(fts, e);
	return e;
}

FTSENT *
emibsd_host_fts_children(FTS *fts, int options)
{
	FTSENT *e, *list = fts_children(fts, options);

	for (e = list; e != NULL; e = e->fts_link)
		correct_entry(fts, e);
	return list;
}

const char *
emibsd_host_user_from_uid(uid_t uid, int nouser)
{
	static char number[16];
	const struct id *id;

	load();
	if ((id = by_number(users, nusers, uid)) != NULL)
		return id->name;
	if (nouser)
		return NULL;
	snprintf(number, sizeof(number), "%u", uid);
	return number;
}

const char *
emibsd_host_group_from_gid(gid_t gid, int nogroup)
{
	static char number[16];
	const struct id *id;

	load();
	if ((id = by_number(groups, ngroups, gid)) != NULL)
		return id->name;
	if (nogroup)
		return NULL;
	snprintf(number, sizeof(number), "%u", gid);
	return number;
}

int
emibsd_host_uid_from_user(const char *name, uid_t *uid)
{
	const struct id *id;

	load();
	if ((id = by_name(users, nusers, name)) == NULL)
		return -1;
	*uid = id->number;
	return 0;
}

int
emibsd_host_gid_from_group(const char *name, gid_t *gid)
{
	const struct id *id;

	load();
	if ((id = by_name(groups, ngroups, name)) == NULL)
		return -1;
	*gid = id->number;
	return 0;
}

struct group *
emibsd_host_getgrnam(const char *name)
{
	static struct group gr;
	static char *members[1];
	static char grname[NAME_LEN], password[] = "*";
	const struct id *id;

	load();
	if ((id = by_name(groups, ngroups, name)) == NULL) {
		errno = 0;
		return NULL;
	}
	strlcpy(grname, id->name, sizeof(grname));
	gr.gr_name = grname;
	gr.gr_passwd = password;
	gr.gr_gid = id->number;
	gr.gr_mem = members;
	return &gr;
}

struct passwd *
emibsd_host_getpwnam(const char *name)
{
	static struct passwd pw;
	static char pwname[NAME_LEN], empty[] = "", password[] = "*";
	const struct id *id;

	load();
	if ((id = by_name(users, nusers, name)) == NULL) {
		errno = 0;
		return NULL;
	}
	strlcpy(pwname, id->name, sizeof(pwname));
	memset(&pw, 0, sizeof(pw));
	pw.pw_name = pwname;
	pw.pw_passwd = password;
	pw.pw_uid = id->number;
	pw.pw_class = pw.pw_gecos = pw.pw_dir = pw.pw_shell = empty;
	return &pw;
}

/* One line for $WORLD_METALOG, as the stand-ins write it: the path made absolute. */
static void
record(const char *path, const char *fields)
{
	char cwd[PATH_MAX], full[PATH_MAX];
	const char *metalog = getenv("WORLD_METALOG");
	FILE *fp;

	if (metalog == NULL || getcwd(cwd, sizeof(cwd)) == NULL ||
	    normal(path, cwd, full, sizeof(full)) == NULL || (fp = fopen(metalog, "a")) == NULL)
		return;
	fprintf(fp, "%s %s\n", full, fields);
	fclose(fp);
	/* Everything read again at the next question: the metalog now says more. */
	for (size_t i = 0; i < nrecords; i++)
		free(records[i].path);
	free(records);
	free(users);
	free(groups);
	records = NULL;
	users = groups = NULL;
	nrecords = nusers = ngroups = 0;
	destdirlen = 0;
	loaded = 0;
}

/* The owner and group asked for, recorded by name; nothing changes on the host. */
static void
record_owner(const char *path, uid_t uid, gid_t gid)
{
	char fields[2 * NAME_LEN + 16] = "";
	const char *name;

	load();
	if (uid != (uid_t)-1 && (name = emibsd_host_user_from_uid(uid, 0)) != NULL) {
		strlcat(fields, "uname=", sizeof(fields));
		strlcat(fields, name, sizeof(fields));
	}
	if (gid != (gid_t)-1 && (name = emibsd_host_group_from_gid(gid, 0)) != NULL) {
		if (fields[0] != '\0')
			strlcat(fields, " ", sizeof(fields));
		strlcat(fields, "gname=", sizeof(fields));
		strlcat(fields, name, sizeof(fields));
	}
	if (fields[0] != '\0')
		record(path, fields);
}

int
emibsd_host_chown(const char *path, uid_t uid, gid_t gid)
{
	record_owner(path, uid, gid);
	return 0;
}

int
emibsd_host_fchown(int fd, uid_t uid, gid_t gid)
{
	/* No path to record it under: the Makefile's own chown of the file does. */
	(void)fd;
	(void)uid;
	(void)gid;
	return 0;
}

int
emibsd_host_fchownat(int fd, const char *path, uid_t uid, gid_t gid, int flag)
{
	(void)flag;
	if (fd == AT_FDCWD || path[0] == '/')
		record_owner(path, uid, gid);
	return 0;
}

/*
 * The mode asked for is recorded and applied with the user keeping read and write (and
 * search on a directory), as install.sh does: the build must still read what it made.
 */
int
emibsd_host_chmod(const char *path, mode_t mode)
{
	struct stat sb;
	char fields[32];

	if (lstat(path, &sb) == -1)
		return -1;
	if (chmod(path, mode | (S_ISDIR(sb.st_mode) ? S_IRWXU : S_IRUSR | S_IWUSR)) == -1)
		return -1;
	snprintf(fields, sizeof(fields), "mode=%o", (unsigned int)(mode & 07777));
	record(path, fields);
	return 0;
}
