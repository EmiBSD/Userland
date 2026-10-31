# compiler

Moved to [DevTools](https://github.com/EmiBSD/DevTools) on 2026-10-31: the toolchains are built
there, from the forks alone, upstream LLVM and rust-lang/rust, one LLVM for the C and for rustc,
nothing from OpenBSD's tree. The pins under `llvm/` and `rust/` here are the superseded first
draft and are removed with the next restart of `main`; nothing reads them.
