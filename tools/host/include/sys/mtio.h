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
 * sys/mtio.h: the magnetic tape interface pax(1) compiles against, which the host lacks.
 * A host tool never drives a tape: these only let it compile, and the ioctls fail on
 * anything it opens.
 */
#ifndef EMIBSD_HOST_SYS_MTIO_H
#define EMIBSD_HOST_SYS_MTIO_H

#include <sys/ioccom.h>

struct mtop {
	short	mt_op;		/* the operation */
	int	mt_count;	/* how many times */
};

struct mtget {
	short	mt_type;	/* the drive's type */
	short	mt_dsreg;	/* its status register */
	short	mt_erreg;	/* its error register */
	int	mt_resid;	/* residual count */
	int	mt_fileno;	/* the current file */
	int	mt_blkno;	/* the current block */
};

#define MTWEOF	0	/* write an end-of-file record */
#define MTFSF	1	/* forward space a file */
#define MTBSF	2	/* backward space a file */
#define MTFSR	3	/* forward space a record */
#define MTBSR	4	/* backward space a record */
#define MTREW	5	/* rewind */
#define MTOFFL	6	/* rewind and take offline */

#define MTIOCTOP	_IOW('m', 1, struct mtop)
#define MTIOCGET	_IOR('m', 2, struct mtget)

#endif /* EMIBSD_HOST_SYS_MTIO_H */
