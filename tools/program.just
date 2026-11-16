# Shared recipes for every program and library; each one's justfile imports this file.
# The program's name is its directory's name; the class is the first word of STATUS.

name := file_name(justfile_directory())
root := `git rev-parse --show-toplevel`

# Build: a written program through cargo (tools/cargo.sh: DevTools' toolchains only); an imported one through build/ after fetch; an
# inherited one through the build driver, which is not here yet (README, Open).
build:
    #!/bin/sh
    set -e
    case "$(cat STATUS)" in
      imported*) python3 -I "{{root}}/tools/upstream.py" check . && sh build/build.sh ;;
      inherited*) echo "{{name}}: inherited; the build driver is not in this repository yet (README, Open)"; exit 1 ;;
      *) sh "{{root}}/tools/cargo.sh" build --manifest-path src/Cargo.toml ;;
    esac

# Fetch and verify the upstream source (imported programs).
fetch:
    python3 -I "{{root}}/tools/upstream.py" fetch .

# Unit and integration tests (tests/, with stress/, cve/ and golden/ inside).
test:
    sh "{{root}}/tools/cargo.sh" test --manifest-path src/Cargo.toml

# The stress tests alone, on four CPUs.
stress:
    EMIBSD_NCPU=4 sh "{{root}}/tools/cargo.sh" test --manifest-path src/Cargo.toml --test 'stress*'

# Host benchmarks against a reference system's program on the same input.
bench:
    sh "{{root}}/tools/cargo.sh" bench --manifest-path src/Cargo.toml

# Format check and clippy with warnings denied.
lint:
    sh "{{root}}/tools/cargo.sh" fmt --manifest-path src/Cargo.toml -- --check
    sh "{{root}}/tools/cargo.sh" clippy --manifest-path src/Cargo.toml -- -D warnings

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
