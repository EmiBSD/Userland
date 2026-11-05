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

#endif /* EMIBSD_HOST_COMPAT_H */
