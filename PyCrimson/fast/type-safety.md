# Type Safety Fast Scan

Use these cards only for localized, quasi-trivial correctness checks. Report a
match only when the card's confirmation is available from the current function
or a nearby declaration. Do not infer custom API contracts from method names,
perform deep data-flow analysis, or report typing-style preferences.

## TS001: Literal Value Compared by Identity

**Signature:** `is` or `is not` compares a value with a string, bytes, numeric,
or container literal.
**Confirm:** The code needs value equality and both operands are local or
otherwise obvious.
**Guard:** Allow `None`, `True`, `False`, `Ellipsis`, sentinels, enum members,
classes, and deliberate identity checks.
**Fix:** Replace `is` / `is not` with `==` / `!=`.
**Catalog:** [TS001](../references/python-bug-catalog.md#ts001-literal-value-compared-by-identity)

## TS002: Mutable Default Argument

**Signature:** A parameter defaults to a mutable literal or a locally proven
mutable constructor result.
**Confirm:** The function mutates the parameter or lets it escape where later
mutation can expose state shared across calls.
**Guard:** Skip immutable factory results and explicitly documented persistent
state or memoization.
**Fix:** Default to `None` and create a fresh value inside the function.
**Catalog:** [TS002](../references/python-bug-catalog.md#ts002-mutable-default-argument)

## TS003: In-Place Mutator Result Used as Value

**Signature:** The result of a built-in container mutator such as `append`,
`extend`, `sort`, `update`, or `add` is assigned, returned, chained, or used in
an expression.
**Confirm:** A nearby literal, annotation, or initialization proves the receiver
is the relevant built-in container.
**Guard:** Skip custom objects whose same-named method has a proven return value.
**Fix:** Mutate in a standalone statement and then use the container; use
`sorted()` when a new sorted list is required.
**Catalog:** [TS003](../references/python-bug-catalog.md#ts003-in-place-mutator-result-used-as-value)

## TS004: Non-Optional Return Can Fall Through

**Signature:** A function with a non-optional return annotation has a shallow,
reachable path to its end or a bare `return`.
**Confirm:** Inspect all local branches and account for unconditional raises and
non-returning loops before concluding that the path returns `None`.
**Guard:** Skip generators, abstract or protocol stubs, overload declarations,
and annotations that permit `None`.
**Fix:** Return the intended value, raise explicitly, or correct the contract to
permit `None`.
**Catalog:** [TS004](../references/python-bug-catalog.md#ts004-non-optional-return-can-fall-through)

## TS005: List Passed as isinstance Class Info

**Signature:** The second argument to `isinstance()` or `issubclass()` is a list
literal.
**Confirm:** The call resolves locally to the Python built-in and the list is the
class-info argument.
**Guard:** Skip shadowed or custom functions and list arguments in other
positions.
**Fix:** Replace the list with a tuple of types.
**Catalog:** [TS005](../references/python-bug-catalog.md#ts005-list-passed-as-isinstance-class-info)

## TS006: Repeated Mutable Element Aliases

**Signature:** List multiplication repeats a nested mutable value, such as
`[[]] * count` or `[[0] * width] * height`.
**Confirm:** A local mutation or use proves that the repeated elements are
expected to be independent.
**Guard:** Skip immutable elements and explicitly intentional shared-reference
tables.
**Fix:** Build independent elements with a comprehension.
**Catalog:** [TS006](../references/python-bug-catalog.md#ts006-repeated-mutable-element-aliases)

## TS007: dict.fromkeys Shares Mutable Value

**Signature:** `dict.fromkeys()` receives a mutable value as its second argument.
**Confirm:** The receiver is the built-in `dict`, there can be multiple keys, and
a local mutation proves that per-key values should be independent.
**Guard:** Skip immutable values and explicitly intentional shared state.
**Fix:** Use a dictionary comprehension that creates a fresh value per key.
**Catalog:** [TS007](../references/python-bug-catalog.md#ts007-dictfromkeys-shares-mutable-value)

## TS008: Obvious Literal Return-Type Mismatch

**Signature:** A return statement uses a literal or container shape plainly
incompatible with a simple built-in return annotation.
**Confirm:** The annotation and return expression are locally explicit, with no
alias, coercion, union, protocol, or generic interpretation required.
**Guard:** Skip `Any`, compatible unions, overload implementations, protocols,
and subclass-compatible values.
**Fix:** Return the declared type or correct the function's documented contract.
**Catalog:** [TS008](../references/python-bug-catalog.md#ts008-obvious-literal-return-type-mismatch)

## TS009: Dictionary View Indexed as Sequence

**Signature:** A result of `.keys()`, `.values()`, or `.items()` is directly
subscripted.
**Confirm:** A nearby literal, annotation, or initialization proves the receiver
is a built-in mapping and the runtime is Python 3.
**Guard:** Skip custom mapping-like APIs that return a proven subscriptable
object.
**Fix:** Use `next(iter(view))` for first-only access or materialize `list(view)`
when indexing is genuinely required.
**Catalog:** [TS009](../references/python-bug-catalog.md#ts009-dictionary-view-indexed-as-sequence)

## TS010: Dictionary View Method Not Called

**Signature:** Bare `.items`, `.keys`, or `.values` is consumed as an iterable
without calling the method.
**Confirm:** A nearby literal, annotation, or initialization proves the receiver
is a built-in mapping and the attribute is in an iteration or membership
position.
**Guard:** Skip custom properties and deliberate use of a bound method as a
callback or stored value.
**Fix:** Add `()` to obtain the dictionary view.
**Catalog:** [TS010](../references/python-bug-catalog.md#ts010-dictionary-view-method-not-called)

## TS011: Statically Absent Attribute on Known Instance

**Signature:** Code reads an attribute absent from a locally known concrete
class and its locally inspectable bases while a nearby established attribute is
the evident contract.
**Confirm:** Resolve the receiver to that concrete class, inspect its class body,
constructor, and available bases, and confirm the intended attribute from local
initialization or consistent nearby use.
**Guard:** Skip unresolved receiver types, `__getattr__` or `__getattribute__`,
dynamic descriptors, framework injection, and documented monkey-patching.
**Fix:** Use the established attribute when the read is a typo, or explicitly
declare and initialize the missing attribute when it is part of the contract.
**Catalog:** [TS011](../references/python-bug-catalog.md#ts011-statically-absent-attribute-on-known-instance)
