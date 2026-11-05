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
 * mklocale.h: forced in after compat.h for the host build of the base system's
 * mklocale(1). The host's <ctype.h> brings its own rune tables, under the names the base
 * system's lib/libc/locale/runetype.h uses for different structures: the host's are
 * declared first, then the base system's are renamed, so mklocale writes the tables in
 * the base system's layout.
 */
#ifndef EMIBSD_HOST_MKLOCALE_H
#define EMIBSD_HOST_MKLOCALE_H

#include <ctype.h>
#include <runetype.h>

#define rune_t		emibsd_rune_t
#define _RuneType	emibsd_RuneType
#define _RuneEntry	emibsd_RuneEntry
#define _RuneRange	emibsd_RuneRange
#define _RuneLocale	emibsd_RuneLocale

#endif /* EMIBSD_HOST_MKLOCALE_H */
