# Shared recipes for every program and library; each one's justfile imports this file.
# The program's name is its directory's name.

name := file_name(justfile_directory())

# Build the package (once src/Cargo.toml exists).
build:
    cargo build --manifest-path src/Cargo.toml

# Unit and integration tests.
test:
    cargo test --manifest-path src/Cargo.toml

# Format check and clippy with warnings denied.
lint:
    cargo fmt --manifest-path src/Cargo.toml -- --check
    cargo clippy --manifest-path src/Cargo.toml -- -D warnings

# Render the manual to the terminal.
man:
    mandoc -T utf8 man/{{name}}.* | less -R

# This program's STATUS line.
status:
    @printf '%s\t%s\n' "$(cat STATUS)" "{{name}}"
