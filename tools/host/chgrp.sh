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

# chgrp.sh: chgrp(1) for a build run by a user: changes nothing and records the group asked
# for in $WORLD_METALOG ("<path> gname=<group>").
set -eu
while getopts hHLPRf opt; do :; done
shift $((OPTIND - 1))
group=$1; shift
for f in "$@"; do
	case $f in /*) p=$f ;; *) p=$PWD/$f ;; esac
	[ -n "${WORLD_METALOG:-}" ] && printf '%s gname=%s\n' "$p" "$group" >> "$WORLD_METALOG"
done
exit 0
