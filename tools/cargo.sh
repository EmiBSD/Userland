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

# cargo.sh: cargo for the written programs, with DevTools' toolchains and nothing else (the
# user's rule of 2026-11-11). Every recipe that runs cargo runs it through this file.
#
# cargo, rustc, rustfmt and clippy are the Rust release's (EMIBSD_RUST_BIN), run straight
# from the toolchains directory: never rustup's, not even as a launcher, so PATH is rebuilt
# without the caller's. The linker is the LLVM release's (EMIBSD_LLVM_BIN): left alone, rustc
# links a host binary with the host's `cc`. Of the host, only its SDK is used (a host
# program links its libc). A toolchain that is not there is an error, never a fallback.
#
# The two pins are the tags DevTools released; moving one is the user's decision.

set -eu
toolchains=$HOME/devel/emibsd/toolchains
rust=${EMIBSD_RUST_BIN:-$toolchains/rust-1.99.1+emibsd.6-aarch64-apple-darwin-arm64/bin}
llvm=${EMIBSD_LLVM_BIN:-$toolchains/llvm-23.1.4+emibsd.7-aarch64-apple-darwin-arm64/bin}

[ -x "$rust/cargo" ] || { echo "cargo.sh: no cargo in $rust (set EMIBSD_RUST_BIN)" >&2; exit 1; }
[ -x "$llvm/clang" ] || { echo "cargo.sh: no clang in $llvm (set EMIBSD_LLVM_BIN)" >&2; exit 1; }
case "$("$rust/rustc" -vV)" in
*"(EmiBSD DevTools"*) ;;	# the stamp carries the release since +emibsd.5
*) echo "cargo.sh: $rust/rustc is not DevTools' rustc" >&2; exit 1 ;;
esac

# The host's link: DevTools' clang aimed at the host, with its lld.
case "$(uname -s)-$(uname -m)" in
Darwin-arm64)
	sdk=$(/usr/bin/xcrun --show-sdk-path)
	export CARGO_TARGET_AARCH64_APPLE_DARWIN_LINKER="$llvm/clang"
	export CARGO_TARGET_AARCH64_APPLE_DARWIN_RUSTFLAGS="-C link-arg=--target=arm64-apple-macos -C link-arg=-isysroot -C link-arg=$sdk -C link-arg=-fuse-ld=lld"
	;;
*) echo "cargo.sh: no host profile for $(uname -s)-$(uname -m)" >&2; exit 1 ;;
esac

export PATH="$rust:$llvm:/usr/bin:/bin"
export RUSTC="$rust/rustc" RUSTDOC="$rust/rustdoc"
exec "$rust/cargo" "$@"
