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

# mknod.sh: mknod(8) for a build run by a user, who cannot make a device node: each node is
# an empty placeholder file, and its kind, numbers and mode go to $WORLD_METALOG ("<path>
# type=char|block|fifo major=<n> minor=<n> mode=<mode>"), from which makefs's host build
# reports it as the device. Takes the base system's form, several nodes per call:
# mknod [-m mode] name [b | c] major minor [...] and mknod [-m mode] name p.
set -eu
mode=
while [ $# -gt 0 ]; do
	case $1 in
	-m) mode=$2; shift 2; continue ;;
	esac
	name=$1 kind=$2
	case $kind in
	b|c) major=$3 minor=$4; shift 4 ;;
	p) major=0 minor=0; shift 2 ;;
	*) echo "mknod: $name: unknown kind $kind" >&2; exit 1 ;;
	esac
	case $kind in b) type=block ;; c) type=char ;; p) type=fifo ;; esac
	rm -f "$name"
	: > "$name"
	[ -n "$mode" ] && chmod "$mode" "$name"
	case $name in /*) p=$name ;; *) p=$PWD/$name ;; esac
	[ -n "${WORLD_METALOG:-}" ] && printf '%s type=%s major=%s minor=%s%s\n' "$p" "$type" "$major" "$minor" "${mode:+ mode=$mode}" >> "$WORLD_METALOG"
	mode=
done
