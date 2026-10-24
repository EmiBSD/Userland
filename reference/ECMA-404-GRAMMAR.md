# ECMA-404, 2nd edition (December 2017): the five figures as text

A transcription of the railroad diagrams of ECMA-404 (Figures 1 to 5, pages 2 to 5 of the
PDF in `ecma-404/`), written on 2026-10-24 from the figures themselves so the standard can
be read with `grep` and `sed`. The prose of the standard is in `ecma-404/ECMA-404.txt` (pdftotext,
`-layout`); only the figures are lost there. Ecma's copyright notice (page v) permits works
that "incorporate all or portion of this document for the purpose of providing commentary or
explanation" and translations "into different formats"; this file is both. The standard is
meant to define the same language as RFC 8259, whose ABNF (Section 2 to 8 of the RFC) is the
other formalism; the two were checked against each other here and agree.

Notation: `|` alternatives, `( )` grouping, `?` zero or one, `*` zero or more, `+` one or
more, `U+XXXX` a code point, `'x'` a literal. Non-terminals are the names the figures use.

## Tokens (Clause 4)

Six structural tokens: `'['` U+005B, `'{'` U+007B, `']'` U+005D, `'}'` U+007D, `':'` U+003A,
`','` U+002C. Three literal name tokens: `true`, `false`, `null`, in lowercase, these exact
code points. Strings and numbers are the other tokens.

Whitespace (insignificant, allowed before or after any token, never inside one except the
space inside a string):

```
ws     = ( U+0009 | U+000A | U+000D | U+0020 )*
```

A JSON text is one `value` with optional whitespace around it (Clause 4; RFC 8259 says the
same, `JSON-text = ws value ws`).

## Figure 1: value (Clause 5)

```
value  = object | array | number | string | 'true' | 'false' | 'null'
```

## Figure 2: object (Clause 6)

The figure draws `{`, then either straight to `}` or a loop of `string ':' value` separated
by `,`:

```
object = '{' ws ( member ( ws ',' ws member )* )? ws '}'
member = string ws ':' ws value
```

The standard imposes nothing on the name strings: it does not require them to be unique and
gives no meaning to their order (Clause 6). Those are the processor's decisions.

## Figure 3: array (Clause 7)

```
array  = '[' ws ( value ( ws ',' ws value )* )? ws ']'
```

Order is not given a meaning by the syntax (Clause 7).

## Figure 4: number (Clause 8)

The figure reads left to right: an optional `-`; then either a single `0` or a digit 1-9
followed by any digits; then an optional fraction, `.` followed by one or more digits; then
an optional exponent, `e` or `E`, an optional `+` or `-`, one or more digits:

```
number   = '-'? int frac? exp?
int      = '0' | digit1-9 digit*
frac     = '.' digit+
exp      = ( 'e' | 'E' ) ( '+' | '-' )? digit+
digit    = U+0030 .. U+0039
digit1-9 = U+0031 .. U+0039
```

Consequences the figure fixes: no leading zeros (`01` is two tokens, not a number), no `+`
sign in front, no leading or trailing `.` (`.5` and `5.` are not numbers), no hexadecimal, no
`Infinity`, no `NaN` (Clause 8 says so in words). The standard gives no range or precision:
"JSON is agnostic about the semantics of numbers" (Introduction).

## Figure 5: string (Clause 9)

The figure is `"`, a loop over characters, `"`. Each character is either any code point
except `"` (U+0022), `\` (U+005C) and the control characters U+0000 to U+001F, or `\`
followed by one of ten things:

```
string    = '"' char* '"'
char      = unescaped | '\' escape
unescaped = any code point except U+0022, U+005C and U+0000 .. U+001F
escape    = '"'            ; U+0022 quotation mark
          | '\'            ; U+005C reverse solidus
          | '/'            ; U+002F solidus
          | 'b'            ; U+0008 backspace
          | 'f'            ; U+000C form feed
          | 'n'            ; U+000A line feed
          | 'r'            ; U+000D carriage return
          | 't'            ; U+0009 character tabulation
          | 'u' hex hex hex hex
hex       = digit | U+0041 .. U+0046 | U+0061 .. U+0066
```

Points the prose adds (Clause 9): a `\u` escape names a code point of the Basic Multilingual
Plane; a code point outside it may be written as the UTF-16 surrogate pair, twelve
characters (`"𝄞"` for U+1D11E), and whether a processor joins such a pair into
one code point "is a semantic decision that is determined by the specific processor"; the
grammar permits code points Unicode has not assigned; `\/` and `/` are the same string. The
standard says nothing about the encoding of the text (UTF-8 is RFC 8259's requirement,
Section 8.1, for texts exchanged between systems) and nothing about a byte order mark (RFC
8259, Section 8.1: an implementation must not add one and may ignore one).

## What the standard leaves to the processor (Clause 2)

A conforming processor "should not accept any inputs that are not conforming JSON texts" and
"may impose semantic restrictions that limit the set of conforming JSON texts that it will
process": duplicate names, number range and precision, nesting depth, lone surrogates in
`\u` escapes, the top-level value being a scalar. Each of those is a decision for a program's
DEFINITION, with RFC 8259's Section 9 (parsers) and Section 4 (duplicate names) as the usual
reading.
