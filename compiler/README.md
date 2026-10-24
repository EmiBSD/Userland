# compiler

The toolchains, both imported: LLVM as OpenBSD ships it (clang, lld, libc++, compiler-rt; Apache-2.0 with the LLVM exception, nothing GPL) and Rust (rustc, cargo, std; Apache-2.0 and MIT), so the system builds itself, as OpenBSD's comp set does. The user's decisions of 2026-10-23.

| Directory | What |
|---|---|
| `llvm/` | LLVM with OpenBSD's patches and build glue (gnu/llvm, gnu/usr.bin/clang), from the pinned tree. |
| `rust/` | rust-lang/rust at the pinned stable tag, built with x.py against compiler/llvm; its std for the OpenBSD targets is how the tier 3 problem is solved without nightly. |

Each entry is a group; each group's README lists its programs.
