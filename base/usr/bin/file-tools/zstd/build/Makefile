# Copyright (c) 2026 Emilio Navarrete Lineros <enavarre@outlook.com>
#
# Permission to use, copy, modify, and distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

# The build of zstd(1) in the base system, by the base system's make, from the pinned source
# that world.py puts beside this file (lib/, programs/). The command line program as
# upstream's programs/Makefile builds it by default, with its library compiled in: threads,
# dictionaries and the benchmark; no legacy formats, no gzip, xz or lz4 support (those
# would link libraries the base system does not have); the generic C decoder, not the
# x86-64 assembly one. unzstd and zstdcat are links to it, as upstream installs them.

PROG=	zstd
LINKS=	${BINDIR}/zstd ${BINDIR}/unzstd ${BINDIR}/zstd ${BINDIR}/zstdcat
MAN=	zstd.1
MLINKS=	zstd.1 unzstd.1 zstd.1 zstdcat.1

.PATH:	${.CURDIR}/programs ${.CURDIR}/lib/common ${.CURDIR}/lib/compress \
	${.CURDIR}/lib/decompress ${.CURDIR}/lib/dictBuilder

SRCS=	zstdcli.c zstdcli_trace.c fileio.c fileio_asyncio.c benchfn.c benchzstd.c \
	datagen.c dibio.c lorem.c timefn.c util.c
# lib/common
SRCS+=	debug.c entropy_common.c error_private.c fse_decompress.c pool.c threading.c \
	xxhash.c zstd_common.c
# lib/compress
SRCS+=	fse_compress.c hist.c huf_compress.c zstd_compress.c zstd_compress_literals.c \
	zstd_compress_sequences.c zstd_compress_superblock.c zstd_double_fast.c \
	zstd_fast.c zstd_lazy.c zstd_ldm.c zstd_opt.c zstd_preSplit.c zstdmt_compress.c
# lib/decompress
SRCS+=	huf_decompress.c zstd_ddict.c zstd_decompress.c zstd_decompress_block.c
# lib/dictBuilder
SRCS+=	cover.c divsufsort.c fastcover.c zdict.c

CPPFLAGS+=	-I${.CURDIR}/lib -I${.CURDIR}/lib/common -I${.CURDIR}/programs \
		-DXXH_NAMESPACE=ZSTD_ -DZSTD_LEGACY_SUPPORT=0 -DZSTD_DISABLE_ASM \
		-DZSTD_MULTITHREAD -DBACKTRACE_ENABLE=0
LDADD+=	-lpthread
DPADD+=	${LIBPTHREAD}

.include <bsd.prog.mk>
