---
name: pc-pybug
description: Review Python code for common, localized, quasi-trivial correctness mistakes in control flow, type and None handling, and strings. Use when the user explicitly requests a quick Python bug scan or common-pitfall check. Do not use for deep semantic or data-flow analysis, architecture, security, performance, syntax, style or linting, or non-Python code.
---

# PyCrimson Python Bug Scan

Use this skill for a bounded, pattern-based correctness scan. Find localized Python
mistakes that have a direct confirmation test and a practical fix.

## Scope

- Review only the Python files, functions, or snippets in the user's stated target.
- Focus on common control-flow, type-safety, `None`, and string-handling mistakes.
- Report correctness risks, not good practices or general code quality observations.
- Exclude syntax, style, architecture, security, performance, concurrency, and
  whole-program semantic analysis.
- Do not claim that a local pattern proves behavior outside the available context.
- Keep the scan read-only unless the user separately requests implementation.

If the request is broad or the target is missing, ask for a bounded Python target.
Do not activate this skill merely because Python code is present in a general review.

## Reference Routing

Classify the target before loading references:

- Branches, loops, exceptions, cleanup, and reachability: read
  `fast/control-flow.md`.
- Return values, `None`, defaults, equality, and type assumptions: read
  `fast/type-safety.md`.
- Formatting, interpolation, encoding, splitting, and text boundaries: read
  `fast/string.md`.

Load every relevant fast file when the target crosses categories. Do not load an
unrelated category merely to broaden the scan.

Consult `references/python-bug-catalog.md` only when a fast card points to its
canonical entry, a match is ambiguous, canonical detail is needed, or the user has
explicitly requested catalog maintenance. The fast files are the first review path.

## Workflow

1. Confirm that the request is an explicit quick scan of a bounded Python target.
2. Read the target and enough surrounding code to understand the local behavior.
3. Select and read the relevant fast category files.
4. Compare candidate code with each card's signature and confirmation conditions.
5. Apply the card's false-positive guard before reporting a match.
6. Trace the shortest concrete failure path supported by the available context.
7. Merge duplicate symptoms that arise from the same root cause.
8. Return findings in the session, ordered by contextual impact.

Do not report a signature-only match. If confirmation depends on unavailable caller,
configuration, runtime, or library behavior, mark the finding uncertain with `[?]`
and state the exact fact that must be verified.

## Finding Format

Use this compact structure for each finding:

```markdown
### HIGH|MEDIUM|LOW[?] - Short finding title
`path/to/file.py:line`

Cause: The specific local behavior that creates the risk.
Impact: The failure supported by the reviewed context.
Fix: The smallest direct correction, or a tentative correction for `[?]` findings.
Verify: The missing fact or focused check required for `[?]` findings.
```

Assign severity from demonstrated contextual impact, not from the pattern name:

- `HIGH`: likely crash, incorrect result, or corrupt state on a reachable path.
- `MEDIUM`: conditional correctness failure with plausible inputs or state.
- `LOW`: narrow edge-case failure with limited impact.

Use `[?]` whenever intent or reachability is unresolved. Do not present an uncertain
fix as definitive. If no supported findings remain after false-positive checks, say
so and identify any material context that was unavailable.

## Deep-Review Boundary

A fast finding may recommend a separate deep review, but it must not activate one.
Do not load `cdecl/` unless the user explicitly asks to use the PyCrimson deep-review
guidance after being told that it expands beyond this skill's quasi-trivial scope.
Words such as "thorough" or "careful" alone are insufficient opt-in. On explicit
opt-in, read `cdecl/README.md` and follow its evidence gate and stop rule as a
separate workflow.

## Write Boundary

Do not create report files or modify the catalog, fast cards, guidance, source code,
or any other file during a scan. Suggestions and newly observed candidates stay in
the session.

Treat catalog, fast-card, or guidance edits as a separate maintenance task requiring
an explicit user request. Before any such write, re-read the target reference,
confirm the candidate is not a duplicate, preserve canonical IDs and anchors, and
validate cross-references after the change.
