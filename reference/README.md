# reference/

Specifications the written programs are surveyed and defined against, kept locally so the
`surveyor` and the `designer` read them with `sed -n` and `grep` instead of the web. Each one
sits in its own directory, **read-only** and gitignored (the directories, not this file, `SHA256`
or `ECMA-404-GRAMMAR.md`); `SHA256` records the hash of every downloaded file, so a copy on
another machine can be checked against it. Nothing is downloaded here without the user's OK; each
entry says when it was asked for. The reference is read to write a program's DEFINITION, never
copied into the repository: a quoted sentence with its section is the most that enters a
document.

The POSIX text (IEEE Std 1003.1-2024, Issue 8) is not here but in
`../Kernel/reference/posix-2024/`, with the other pinned trees (see that README).

## rfc9535/ (the user's request of 2026-10-24, for `jpath`)

RFC 9535, "JSONPath: Query Expressions for JSON", February 2024, Standards Track.  `rfc9535.txt`
is the canonical plain text from the RFC Editor (https://www.rfc-editor.org/rfc/rfc9535.txt);
`rfc9535.html` is the datatracker rendering (https://datatracker.ietf.org/doc/html/rfc9535).
Terms: the IETF Trust Legal Provisions (BCP 78 and TLP, in the RFC's own front matter) permit
reproduction of the RFC without change; the ABNF and the examples may be used under the Revised
BSD License, as the RFC states. What it defines: the query syntax (root `$`, child and descendant
segments, name, wildcard, index, slice and filter selectors), its semantics as a nodelist, the
five standard functions (`length`, `count`, `match`, `search`, `value`), the function-extension
type system, Normalized Paths (Section 2.7), the collected ABNF (Appendix A) and the IANA
registry of functions. Its JSON is RFC 8259's.

## ecma-404/ (the same request)

ECMA-404, 2nd edition, December 2017, "The JSON Data Interchange Syntax"
(https://ecma-international.org/wp-content/uploads/ECMA-404_2nd_edition_december_2017.pdf).
`ECMA-404.txt` is `pdftotext -layout` of the PDF: all the prose, but not the five railroad
diagrams; `ECMA-404-GRAMMAR.md`, beside this README and tracked, transcribes those five figures
into a text grammar, with the prose's restrictions beside each. Terms (page v of the PDF): the
document may be copied and distributed; derivative works are limited to commentary and
explanation, feature incorporation, translation into other languages and formats, and
implementation; the text itself may not be modified. The grammar is intended to be identical to
RFC 8259's.

## json.org/ (the same request)

`json-en.html`, the page https://www.json.org/json-en.html, the informal presentation of the same
grammar with the diagrams as text, including the `whitespace` nodes the Ecma figures leave to the
prose. No licence is stated on the page: a personal reading copy, nothing more.

## nota/ (the same request, added later on 2026-10-24)

`nota.html`, Douglas Crockford's technical note "Nota Message Format" (2023-10-24,
https://www.crockford.com/nota.html), a binary JSON-like format for Misty's Procession
Protocol: Kim continuation bytes (one continue bit, seven data bits) for every count and
character, a preamble byte whose three high bits give the type (blob, text, array, record,
floating point with positive or negative exponent, integer, symbol), counts instead of
brackets, decimal floating point as coefficient times a power of ten, blobs, and the symbols
null, false, true, private and system. `nota.txt` is the page rendered to text: each of its
bit-layout figures is an HTML table (a titled row of eight one-bit cells with a legend under
it, then worked examples in hex), kept here as a row of cells per figure, so nothing is lost.
That presentation, one titled row of bit boxes with the legend beneath and the bytes of an
example in hex, is the model the user pointed at for documenting a binary layout. No licence
is stated on the page: a personal reading copy.

## Reading cheaply

`grep -n '^[0-9]' rfc9535/rfc9535.txt` lists the sections; `sed -n 'a,bp'` reads a range.  The
HTML files are for a browser. Nobody `cd`s into these directories, nothing is written here after
the download, and a refreshed download replaces the file and the `SHA256` line together.
