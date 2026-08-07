# Deep Semantic Review Guide

Load this guide only when the user explicitly requests a deep semantic
correctness review. Do not infer that intent from a keyword such as `thorough`,
a complexity signal, or a fast-scan finding. A fast scan may recommend deep
review, but it must not activate this guide.

## Scope

Limit review to the selected function, class, or code region and its directly
relevant local helpers. Do not expand into an architecture review, style
review, speculative whole-program audit, or whole-program proof.

## Method

1. State the expected invariant or outcome.
2. Trace only values and state that can affect that invariant.
3. Enumerate feasible normal, exceptional, and early-exit paths.
4. Check whether aliases, closures, mutation, or delayed execution change a
   value or object's lifetime before use.
5. Report a finding only when a feasible path violates the invariant.

## Reasoning Lenses

### Path Feasibility

Check whether branch conditions overlap, contradict each other, make a path
unreachable, or leave an expected result unset. Include exception and
early-return paths.

### Value Provenance

Trace where a relevant value originates, how it changes, and whether every
feasible producer satisfies the consumer's assumptions.

### State Transitions

List the allowed states and transitions visible in scope. Flag operations that
can occur before initialization, after finalization, or in an invalid order.

### Alias And Lifetime

Check whether mutation through another reference, closure capture, deferred
callbacks, or object replacement invalidates an assumption before use.

## Evidence Gate

Report a finding only when it identifies:

- the violated invariant;
- a concrete feasible path;
- the relevant value or state transition; and
- the observable incorrect outcome.

Mark a finding `[?]` when external behavior or omitted context determines
feasibility. Do not infer undocumented contracts or report theoretical paths
that the available code excludes.

## Stop Rule

Stop after examining the selected region and its directly relevant local
helpers. If a claim requires broader system context, state what is missing and
ask whether the user wants to expand the scope.
