#!/bin/sh
#
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
#
# tools/release.sh <tag>: the GitHub release of the install sets, one artifact per
# architecture, from the main session, by the maintainer (it publishes, like a push).
#
# The tag is YEAR.MONTH.N (2026.11.0): HEAD must carry it, and every artifact in dist/ for it
# (userland-<tag>-<arch>.tar.zst, `just dist <arch>`) must match its .sha256 and have been made
# from it (its MANIFEST says so). The first run creates the release with the artifacts there
# are; a later run, for an architecture built since (amd64 once Kernel boots it), uploads the
# artifacts the release lacks, never replacing one, and rewrites the notes with every sum. A
# consumer (OS's MANIFEST.toml) fetches by tag and architecture and checks the sum.
set -eu
cd "$(dirname "$0")/.."
root=$(pwd)
tag=${1:?the release tag, YEAR.MONTH.N}
repo=EmiBSD/Userland
git tag --points-at HEAD | grep -qx "$tag" \
    || { echo "release: HEAD is not tagged $tag (git tag -a $tag -m '...' first; a release is cut from a tagged commit)" >&2; exit 1; }
set -- dist/userland-"$tag"-*.tar.zst
[ -f "$1" ] || { echo "release: no artifact in dist/ for $tag (just dist arm64)" >&2; exit 1; }
for t in "$@"; do
    [ -f "$t.sha256" ] || { echo "release: $t.sha256 missing" >&2; exit 1; }
    (cd dist && shasum -a 256 -c "$(basename "$t").sha256" >/dev/null) || { echo "release: $t does not match its .sha256" >&2; exit 1; }
    zstd -dc "$t" | tar -xOf - "$(basename "$t" .tar.zst)/MANIFEST" | grep -qx "tag: $tag" \
        || { echo "release: $t was not made from $tag (its MANIFEST says otherwise): just dist again" >&2; exit 1; }
    # Each project signs its own releases (2026-11-07): the artifact's SHA256 is signed with
    # EmiBSD's base key (`just sign <arch>`), and the signature must verify with the public key.
    v=$(mktemp -d)
    zstd -dc "$t" | tar -xf - -C "$v"
    (cd "$v/$(basename "$t" .tar.zst)" && [ -f SHA256.sig ] \
        && signify -C -q -p "$root/base/etc/signify/emibsd-80-base.pub" -x SHA256.sig) \
        || { rm -rf "$v"; echo "release: $t has no SHA256.sig that verifies with emibsd-80-base.pub (just sign)" >&2; exit 1; }
    rm -rf "$v"
done
git ls-remote --tags origin "refs/tags/$tag" | grep -q . \
    || { echo "release: $tag is not on origin yet: git push origin main $tag (the maintainer's), then again" >&2; exit 1; }
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
existing=
if gh release view "$tag" --repo "$repo" >/dev/null 2>&1; then
    existing=$(gh release view "$tag" --repo "$repo" --json assets -q '.assets[].name')
    gh release download "$tag" --repo "$repo" --pattern '*.tar.zst.sha256' --dir "$work"
fi
upload=
for t in "$@"; do
    b=$(basename "$t")
    if printf '%s\n' "$existing" | grep -qx "$b"; then
        cmp -s "$t.sha256" "$work/$b.sha256" \
            || { echo "release: $b is on the release with another sum; a released artifact is never replaced" >&2; exit 1; }
        continue
    fi
    cp "$t.sha256" "$work/"
    upload="$upload $t $t.sha256"
done
[ -n "$upload" ] || { echo "release: $tag already has every artifact in dist/"; exit 0; }
notes=$work/notes
{
    echo "The inherited base system of EmiBSD, built for EmiBSD from the tag \`$tag\`."
    echo
    echo "One artifact per architecture; fetch by this tag, check the sum, then unpack:"
    echo
    echo '```'
    cat "$work"/*.tar.zst.sha256
    echo '```'
    echo
    echo "Inside userland-$tag-<arch>/: the install sets base80.tar.zst, comp80, game80 and man80 (zstd),"
    echo "the installer's ramdisk miniroot80.fs (rdsetroot it into the Kernel's bsd.RAMDISK to make bsd.rd),"
    echo "the installation notes INSTALL.<arch> for the medium, their SHA256 and its signature SHA256.sig (emibsd-80-base), and MANIFEST (the commit, the epoch, the base system's pin, the compiler, the sums,"
    echo "what the sets still lack). Reproducible: \`just dist <arch>\` at this tag gives the same SHA256."
    echo
    echo "The base system is OpenBSD's at its pin, changed only by the patches each program's directory"
    echo "carries. Not affiliated with or endorsed by the OpenBSD project."
} > "$notes"
if [ -z "$existing" ]; then
    echo "release: creating $tag on $repo with:$upload"
    # shellcheck disable=SC2086
    gh release create "$tag" $upload --repo "$repo" --title "$tag" --notes-file "$notes" --verify-tag
else
    echo "release: adding to $tag on $repo:$upload"
    # shellcheck disable=SC2086
    gh release upload "$tag" $upload --repo "$repo"
    gh release edit "$tag" --repo "$repo" --notes-file "$notes"
fi
