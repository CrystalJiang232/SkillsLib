# Control Flow Fast Scan

Use these cards for localized, quasi-trivial control-flow checks. Treat the catalog as canonical. Report a finding only when its signature matches and its guard does not apply. Where confirmation is context-required, mark the finding `[?]` and ask the confirmation question before asserting a fix.

For overlapping exception cards, report the most specific root pattern once and include secondary consequences in its rationale. Prefer predicate and ordering defects before catch breadth, then catch breadth before silent handling.

## Constant Operand in Boolean Branch

**Signature**: A boolean `or` or `and` mixes a comparison with a bare constant that appears to be an omitted comparison operand.
**Confirm**: Verify that the constant is intended as another value for the same compared expression.
**Guard**: Skip deliberate truth constants, named flags, and operands whose own truthiness is intentionally tested.
**Fix**: Repeat the comparison explicitly or use a membership test.
**Catalog**: [CF001](../references/python-bug-catalog.md#cf001-constant-operand-in-boolean-branch)

## Mutually Exclusive Equality Conjunction

**Signature**: An `and` joins equality comparisons of the same pure expression against distinct immutable literals.
**Confirm**: Verify that the expression is stable and the values cannot be equal under the relevant semantics.
**Guard**: Skip overloaded equality, side-effectful expressions, aliases, and nonliteral comparison values.
**Fix**: Use `or` or membership when either value is accepted; otherwise correct the intended predicate.
**Catalog**: [CF002](../references/python-bug-catalog.md#cf002-mutually-exclusive-equality-conjunction)

## Always-True Inequality Disjunction

**Signature**: An `or` joins inequality comparisons of the same pure expression against distinct immutable literals.
**Confirm**: Verify that the intended condition is that the expression matches neither value.
**Guard**: Skip overloaded comparison behavior, side-effectful expressions, aliases, and nonliteral comparison values.
**Fix**: Use `and` between the inequalities or a `not in` membership test.
**Catalog**: [CF003](../references/python-bug-catalog.md#cf003-always-true-inequality-disjunction)

## Repeated Pure Elif Condition

**Signature**: A later `elif` repeats an earlier structurally identical, side-effect-free condition in the same chain.
**Confirm**: Verify that no evaluation side effect or state change can make the repeated test differ.
**Guard**: Skip calls, assignment expressions, iterator advancement, descriptors, and other stateful evaluations.
**Fix**: Correct the later condition or merge the duplicate branch bodies.
**Catalog**: [CF004](../references/python-bug-catalog.md#cf004-repeated-pure-elif-condition)

## Code After Suite Terminator

**Signature**: A statement follows an unconditional `return`, `raise`, `break`, or `continue` in the same statement suite.
**Confirm**: Verify that the terminator is unconditional at that exact nesting level.
**Guard**: Do not flatten nested branches or treat statements in a different suite as unreachable.
**Fix**: Remove or relocate the unreachable code, or correct the premature terminator.
**Catalog**: [CF005](../references/python-bug-catalog.md#cf005-code-after-suite-terminator)

## Boolean Expression in Except Type

**Signature**: An exception handler type is a boolean expression such as `A or B` instead of a tuple of exception classes.
**Confirm**: Resolve the operands and verify that each is intended to be caught.
**Guard**: Skip only when a computed exception-class expression is demonstrably intentional; otherwise keep the finding context-required.
**Fix**: Replace the boolean expression with an exception tuple such as `(A, B)`.
**Catalog**: [CF006](../references/python-bug-catalog.md#cf006-boolean-expression-in-except-type)

## Broad Handler Before Narrow Handler

**Signature**: An earlier exception handler resolves to a superclass of an exception caught by a later handler in the same `try` statement.
**Confirm**: Resolve both exception classes and verify their inheritance relationship.
**Guard**: Skip unresolved, dynamically rebound, or conditionally defined exception classes.
**Fix**: Put the narrower handler first or remove the unreachable handler.
**Catalog**: [CF007](../references/python-bug-catalog.md#cf007-broad-handler-before-narrow-handler)

## Bare Except Catches Process Signals

**Signature**: An exception handler omits its type and therefore catches `BaseException` descendants as well as ordinary exceptions.
**Confirm**: Context required: determine which failures are expected and whether process-control exceptions must propagate.
**Guard**: Skip handlers that immediately re-raise, or perform cleanup and then re-raise; treat an explicitly documented process boundary as context-required.
**Fix**: Catch the narrow expected exception set; using `Exception` is only an interim boundary when narrower types are not yet known.
**Catalog**: [CF008](../references/python-bug-catalog.md#cf008-bare-except-catches-process-signals)

## Silent Exception Suppression

**Signature**: An exception handler discards a caught exception with only `pass`, ellipsis, or an unobserved sentinel return.
**Confirm**: Context required: determine whether the operation is an intentional best-effort probe and how failure is meant to be observed.
**Guard**: Skip documented optional probes and handlers that provide meaningful fallback state, telemetry, or an immediate re-raise.
**Fix**: Handle, record, or re-raise the failure, and narrow the caught exception type where possible.
**Catalog**: [CF009](../references/python-bug-catalog.md#cf009-silent-exception-suppression)

## Control Transfer in Finally

**Signature**: A `finally` suite contains `return`, `break`, or `continue`, excluding transfers inside a nested function or class.
**Confirm**: Context required: verify whether overriding a pending return or suppressing an active exception is explicitly intended.
**Guard**: Skip transfers belonging to nested definitions; do not assert a fix when intentional suppression is documented.
**Fix**: Keep `finally` focused on cleanup and move the control transfer after the `try` statement.
**Catalog**: [CF010](../references/python-bug-catalog.md#cf010-control-transfer-in-finally)
