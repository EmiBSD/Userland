#!/bin/sh
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

# sort.sh: sort(1) for the build, its -R random order drawn from $WORLD_RANDOM, a seed that
# world.py derives from the commit. The base system links each shared library, ld.so and
# a re-link kit's program with its objects in a random order (bsd.lib.mk, ld.so's
# Makefile): with the seed fixed, two builds of one commit choose the same order and a new
# commit another one; /etc/rc's reorder_libs still draws a new order on every boot.
if [ -n "${WORLD_RANDOM:-}" ]; then
	exec /usr/bin/sort --random-source="$WORLD_RANDOM" "$@"
fi
exec /usr/bin/sort "$@"
