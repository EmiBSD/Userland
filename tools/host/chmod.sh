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


# chmod.sh: chmod(1) for a build run by a user, not by root. The mode is applied, the user
# keeping read and write on what it owns (install.sh's rule, so the sets and the image can
# be made from it), and recorded in $WORLD_METALOG ("<path> mode=<octal>"), which the image
# and the sets are made with. A symbolic mode is recorded as the octal mode it leaves.
set -eu
flags=
while getopts hRHLP opt; do flags="$flags -$opt"; done
shift $((OPTIND - 1))
mode=$1; shift
for f in "$@"; do
	case $f in /*) p=$f ;; *) p=$PWD/$f ;; esac
	/bin/chmod $flags "$mode" "$f"
	case $mode in
	*[!0-7]*) octal=$(/usr/bin/stat -f %Lp "$f") ;;
	*) octal=$mode ;;
	esac
	[ -L "$f" ] || /bin/chmod u+rw "$f"
	[ -n "${WORLD_METALOG:-}" ] && printf '%s mode=%s\n' "$p" "$octal" >> "$WORLD_METALOG"
done
exit 0
