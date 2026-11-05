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
 * compat.h: what the base system's C expects of its libc and the development host's
 * (macOS) lacks, so the host tools the build needs (make first) compile from their inherited
 * src/ unchanged. Forced into every host compile with -include; never part of what EmiBSD
 * ships, and never a substitute for a patch: a difference that is a bug goes in patches/.
 */
#ifndef EMIBSD_HOST_COMPAT_H
#define EMIBSD_HOST_COMPAT_H

#include <sys/types.h>
#include <sys/stat.h>
#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <time.h>

/*
 * The host's <signal.h> declares an XSI function named sigset(), a name the base system's
 * code uses for variables: declare the host's under another name, once, before anyone else
 * includes the header.
 */
#define sigset emibsd_host_sigset_function
#include <signal.h>
#undef sigset

/*
 * The base system's <sys/cdefs.h> spells structure attributes with these; without them a
 * trailing `__packed` declares a variable and the structure keeps its padding, which
 * changes an on-disk layout (makefs's disklabel and file system).
 */
#ifndef __packed
#define __packed __attribute__((__packed__))
#endif
#ifndef __aligned
#define __aligned(x) __attribute__((__aligned__(x)))
#endif
/* Its visibility markers, which mean nothing to a host tool. */
#ifndef __BEGIN_HIDDEN_DECLS
#define __BEGIN_HIDDEN_DECLS
#define __END_HIDDEN_DECLS
#endif
#ifndef __dso_hidden
#define __dso_hidden __attribute__((__visibility__("hidden")))
#endif

#ifndef _NSIG
#define _NSIG NSIG
#endif

/* The host names a file's times st_*timespec. */
#define st_atim st_atimespec
#define st_mtim st_mtimespec
#define st_ctim st_ctimespec

#ifndef timespeccmp
#define timespeccmp(a, b, op) \
	(((a)->tv_sec == (b)->tv_sec) ? \
	    ((a)->tv_nsec op (b)->tv_nsec) : ((a)->tv_sec op (b)->tv_sec))
#endif

/* realloc of n elements of size bytes, refusing the product that overflows. */
static inline void *
emibsd_host_reallocarray(void *p, size_t n, size_t size)
{
	if (size != 0 && n > SIZE_MAX / size) {
		errno = ENOMEM;
		return NULL;
	}
	return realloc(p, n * size);
}
#define reallocarray emibsd_host_reallocarray

/* recallocarray(3), libc's own, compiled for the host into libbasehost.a (world.py). */
void *recallocarray(void *, size_t, size_t, size_t);

/* A host tool runs unconfined: the host has no pledge(2). */
static inline int
emibsd_host_pledge(const char *promises, const char *execpromises)
{
	(void)promises;
	(void)execpromises;
	return 0;
}
#define pledge emibsd_host_pledge

/* Nor unveil(2); and a seeded random(3) is deterministic on the host already. */
static inline int
emibsd_host_unveil(const char *path, const char *permissions)
{
	(void)path;
	(void)permissions;
	return 0;
}
#define unveil emibsd_host_unveil
#define srandom_deterministic(seed) srandom(seed)

/* libc's own sources compiled for the host (its hash functions): no symbol aliasing there. */
#define DEF_WEAK(x)
#define DEF_STRONG(x)
#define PROTO_NORMAL(x)
/* A second name for a function (SHA224Update for SHA256Update): an assembler alias, the
 * host's object format having no alias attribute. */
#define MAKE_CLONE(dst, src) __asm__(".globl _" #dst "\n_" #dst " = _" #src)

/* explicit_bzero(3), over the host's memset_s, which the compiler may not remove either. */
#define __STDC_WANT_LIB_EXT1__ 1
#include <string.h>
static inline void
emibsd_host_explicit_bzero(void *p, size_t n)
{
	(void)memset_s(p, n, 0, n);
}
#define explicit_bzero emibsd_host_explicit_bzero

/*
 * pathconfat(2), which the host lacks, nor has it a timestamp resolution to ask for: the
 * answer is "unknown" (pax's -u then compares the times as they are).
 */
#ifndef _PC_TIMESTAMP_RESOLUTION
#define _PC_TIMESTAMP_RESOLUTION (-1)
#endif
static inline long
emibsd_host_pathconfat(int fd, const char *path, int name, int flag)
{
	(void)fd;
	(void)path;
	(void)name;
	(void)flag;
	errno = EINVAL;
	return -1;
}
#define pathconfat emibsd_host_pathconfat

/*
 * strnvis(3) takes its size after the source in the base system, after the destination on
 * the host (mtree): the base system's order, over the host's function.
 */
#include <vis.h>
static inline int
emibsd_host_strnvis(char *dst, const char *src, size_t dstsize, int flag)
{
	return strnvis(dst, dstsize, src, flag);
}
#define strnvis(dst, src, dstsize, flag) emibsd_host_strnvis(dst, src, dstsize, flag)

/* strtofflags(3) stores 32-bit flags in the base system, longs on the host (mtree). */
#include <unistd.h>
static inline int
emibsd_host_strtofflags(char **s, u_int32_t *set, u_int32_t *clear)
{
	unsigned long s1 = 0, c1 = 0;
	int r = strtofflags(s, set ? &s1 : NULL, clear ? &c1 : NULL);

	if (set)
		*set = (u_int32_t)s1;
	if (clear)
		*clear = (u_int32_t)c1;
	return r;
}
#define strtofflags(s, set, clear) emibsd_host_strtofflags(s, set, clear)

/*
 * The base system's login name length, which the host's <limits.h> lacks: a host helper
 * that writes the target's structures (phantasia's setup) must size them as the target does.
 */
#include <limits.h>
#ifndef LOGIN_NAME_MAX
#define LOGIN_NAME_MAX 32
#endif
/* And its host name length, which sizes buffers only. */
#ifndef HOST_NAME_MAX
#define HOST_NAME_MAX 255
#endif

/*
 * The base system's seeding of random(3) for a sequence that must repeat: the host's
 * srandom always is (phantasia's setup, under SOURCE_DATE_EPOCH).
 */
#include <stdlib.h>
#define srandom_deterministic(seed) srandom(seed)

#endif /* EMIBSD_HOST_COMPAT_H */
