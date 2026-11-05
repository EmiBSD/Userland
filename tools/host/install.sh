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

# install.sh: install(1) for a build run by a user, not by root. Every file and directory
# is installed as the user; the owner, group and mode the Makefile asked for go to the
# manifest $WORLD_METALOG instead ("<path> <owner> <group> <mode>"), which sets them in the
# image. -s strips with $STRIP (an ELF strip), never the host's. Takes the options of the
# base system's install(1).

set -eu
owner=root group=wheel mode= strip= dir= flags=
while getopts B:bCcDdFf:g:m:o:pSs opt; do
	case $opt in
	o) owner=$OPTARG ;;
	g) group=$OPTARG ;;
	m) mode=$OPTARG; flags="$flags -m $OPTARG" ;;
	s) strip=1 ;;
	d) dir=1; flags="$flags -d" ;;
	c|C|p|S|b) flags="$flags -$opt" ;;
	B|D|F|f) ;;
	*) exit 64 ;;
	esac
done
shift $((OPTIND - 1))
[ $# -gt 0 ] || { echo "install: nothing to install" >&2; exit 64; }

record() {
	[ -n "${WORLD_METALOG:-}" ] && printf '%s %s %s %s\n' "$1" "$owner" "$group" "${mode:--}" >> "$WORLD_METALOG"
	return 0
}

if [ -n "$dir" ]; then
	/usr/bin/install $flags "$@"
	for d in "$@"; do record "$d"; done
	exit 0
fi

eval "dest=\${$#}"
/usr/bin/install $flags "$@"
n=$#
for f in "$@"; do
	n=$((n - 1))
	[ $n -ge 0 ] || break
	[ $n -eq 0 ] && [ "$f" = "$dest" ] && break
	if [ -d "$dest" ]; then t=$dest/${f##*/}; else t=$dest; fi
	if [ -n "$strip" ]; then chmod u+w "$t"; "${STRIP:?install: -s needs STRIP}" "$t"; [ -n "$mode" ] && chmod "$mode" "$t"; fi
	record "$t"
done
