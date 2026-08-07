# String Handling Bug Patterns

> Fast signatures extracted from `references/python-bug-catalog.md`.
> The catalog is authoritative; these cards are compact scan instructions.

## Scan Contract

- Report only when the signature and guard both pass.
- Use only local, statically provable evidence for literal formatting checks.
- Mark confirmation-required cards as uncertain until their stated intent is confirmed.
- Escalate regex, security, path, locale, and encoding-architecture analysis out of the fast scan.

## Empty split Separator

**Signature**: A built-in `str.split`, `str.rsplit`, `bytes.split`, or `bytes.rsplit` call receives a literal empty separator.
**Confirm**: Verify the first positional argument is statically `""` or `b""`; the call will raise `ValueError`.
**Guard**: Do not report a dynamic separator unless local constant propagation proves it is empty.
**Fix**: Use the intended non-empty separator, or use `list(value)` when individual characters are required.
**Catalog**: [ST001](../references/python-bug-catalog.md#st001-empty-split-separator)

## List Passed to startswith or endswith

**Signature**: A proven built-in `str` or `bytes` receiver calls `startswith` or `endswith` with a list as its first argument.
**Confirm**: Verify the argument is a list literal or a locally proven list; the built-ins require one prefix or suffix, or a tuple of them.
**Guard**: Do not report methods on custom or unknown receiver types that may accept lists.
**Fix**: Replace the list with a tuple containing the same prefixes or suffixes.
**Catalog**: [ST002](../references/python-bug-catalog.md#st002-list-passed-to-startswith-or-endswith)

## Static str.format Placeholder Mismatch

**Signature**: A literal format string calls `format` with statically inspectable arguments, and its parsed positional or named fields cannot be satisfied.
**Confirm**: Parse the literal fields and prove a missing position, missing name, or invalid automatic/manual numbering combination without relying on runtime values.
**Guard**: Respect escaped braces and nested format specifications; skip dynamic templates, `*args`, `**kwargs`, and any case whose mismatch is not statically certain.
**Fix**: Add, remove, or rename the decisive field or argument so the literal fields and supplied arguments agree.
**Catalog**: [ST003](../references/python-bug-catalog.md#st003-static-strformat-placeholder-mismatch)

## Static Percent-Formatting Mismatch

**Signature**: A literal percent-format string and a statically inspectable scalar, tuple, or mapping operand have a provable arity, key, or operand-shape mismatch.
**Confirm**: Parse the supported conversion fields and prove the mismatch from the literal format and literal or locally constant operand.
**Guard**: Skip dynamic formats, starred data, dynamic mappings, and width or precision cases the detector cannot parse completely.
**Fix**: Supply the required tuple or mapping entries, remove the unmatched field, or replace the local expression with an equivalent f-string.
**Catalog**: [ST004](../references/python-bug-catalog.md#st004-static-percent-formatting-mismatch)

## find Result Used as Boolean

**Signature**: A built-in `str.find`, `str.rfind`, `bytes.find`, or `bytes.rfind` result is used directly as a condition or directly under `not`.
**Confirm**: Verify the condition is testing substring presence; index `0` is false while not-found index `-1` is true.
**Guard**: Do not report explicit numeric comparisons or logic that intentionally branches on the returned index.
**Fix**: Use `needle in value` or `needle not in value`; use an explicit comparison with `-1` only when the index API must remain.
**Catalog**: [ST005](../references/python-bug-catalog.md#st005-find-result-used-as-boolean)

## Discarded Immutable String Transform

**Signature**: A proven built-in `str` or `bytes` transformation call is a standalone expression whose returned value is discarded.
**Confirm**: Restrict matching to side-effect-free methods such as `strip`, `replace`, `lower`, `upper`, and their direct variants, and verify no enclosing expression consumes the result.
**Guard**: Do not report custom receivers, unknown method dispatch, or calls whose result is returned, assigned, passed, compared, or otherwise consumed.
**Fix**: Assign the returned value or use it directly at the consuming expression.
**Catalog**: [ST006](../references/python-bug-catalog.md#st006-discarded-immutable-string-transform)

## str(bytes) Used as Decoding

**Confirmation required**

**Signature**: `str(value)` receives a value locally proven to be `bytes`, without an explicit encoding argument.
**Confirm**: Verify the caller needs decoded text rather than the printable `b'...'` representation produced by `str(bytes_value)`.
**Guard**: Do not report logging, debugging, representation output, or arguments whose `bytes` type is not locally proven.
**Fix**: Decode once at the local text boundary with `value.decode(expected_encoding)` after confirming the expected encoding.
**Catalog**: [ST007](../references/python-bug-catalog.md#st007-strbytes-used-as-decoding)

## Static bytes and str Comparison

**Signature**: An equality or inequality comparison has one operand proven to be built-in `bytes` and the other proven to be built-in `str`.
**Confirm**: Verify both operand types from literals, annotations, or direct local construction; equal-looking content across these types does not compare equal.
**Guard**: Skip unknown or custom operand types, overloaded comparison behavior, and explicit type-discrimination logic.
**Fix**: Normalize both operands to the locally intended text or byte domain before comparing.
**Catalog**: [ST008](../references/python-bug-catalog.md#st008-static-bytes-and-str-comparison)

## Interpolation Placeholder Without f Prefix

**Confirmation required**

**Signature**: A plain string literal contains simple interpolation-like fields such as `{name}`, is not formatted later, and matching names are locally in scope.
**Confirm**: Verify the string is emitted, returned, or stored as final text and interpolation was intended.
**Guard**: Skip templates, escaped braces, documentation, fixtures, logging templates, and values later passed to `format` or `format_map`.
**Fix**: Add the `f` prefix when immediate interpolation is intended, or retain the template and apply its intended explicit formatter.
**Catalog**: [ST009](../references/python-bug-catalog.md#st009-interpolation-placeholder-without-f-prefix)

## Accidental Adjacent String Literal Concatenation

**Confirmation required**

**Signature**: Token or concrete-syntax inspection finds adjacent string literals inside a collection or call argument region where a comma may be missing.
**Confirm**: Verify the literals were intended as separate elements or arguments; the AST alone cannot recover the source boundary after implicit concatenation.
**Guard**: Skip deliberate multiline message construction, intentionally split long literals, and explicitly concatenated expressions.
**Fix**: Insert the missing comma between the literals.
**Catalog**: [ST010](../references/python-bug-catalog.md#st010-accidental-adjacent-string-literal-concatenation)

## strip Argument Mistaken for Exact Affix

**Confirmation required**

**Signature**: `strip`, `lstrip`, or `rstrip` receives a multi-character literal that resembles an exact prefix, suffix, or extension.
**Confirm**: Verify the intent is to remove one exact affix rather than any run of characters from the supplied character set.
**Guard**: Skip deliberate character-set trimming, locally proven payload grammars disjoint from every strip character, and environments where the selected exact-affix API is unavailable without a compatible replacement.
**Fix**: Use `removeprefix` or `removesuffix`, or a guarded compatibility slice when required by the target Python version.
**Catalog**: [ST011](../references/python-bug-catalog.md#st011-strip-argument-mistaken-for-exact-affix)

## String Literal Identity Cross-Reference

**Signature**: `is` or `is not` compares a value with a string literal.
**Confirm**: Verify the code intends string value equality; interning does not make identity a valid value comparison.
**Guard**: Restrict this card to literal strings; do not report identity checks against object sentinels.
**Fix**: Replace `is` with `==`, or `is not` with `!=`.
**Catalog**: [TS001](../references/python-bug-catalog.md#ts001-literal-value-compared-by-identity)
