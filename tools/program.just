# Shared recipes for every program and library; each one's justfile imports this file.
# The program's name is its directory's name; the class is the first word of STATUS.

name := file_name(justfile_directory())
root := justfile_directory() / "../../.."

# Build: a written program through cargo; an imported one through build/ after fetch.
build:
    #!/bin/sh
    set -e
    case "$(cat STATUS)" in
      imported*) python3 -I "{{root}}/tools/upstream.py" check . && sh build/build.sh ;;
      *) cargo build --manifest-path src/Cargo.toml ;;
    esac

# Fetch and verify the upstream source (imported programs).
fetch:
    python3 -I "{{root}}/tools/upstream.py" fetch .

# Unit and integration tests (tests/, with stress/, cve/ and golden/ inside).
test:
    cargo test --manifest-path src/Cargo.toml

# The stress tests alone, on four CPUs.
stress:
    EMIBSD_NCPU=4 cargo test --manifest-path src/Cargo.toml --test 'stress*'

# Host benchmarks against a reference system's program on the same input.
bench:
    cargo bench --manifest-path src/Cargo.toml

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

# CHANGELOG.md from this program's commits' Change: trailers.
changelog:
    python3 -I "{{root}}/tools/version.py" changelog .

# This program's CVE history from NVD (network), as rows for DEFINITION.md.
cve:
    python3 -I "{{root}}/tools/cve.py" .
