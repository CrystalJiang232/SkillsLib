# Python Bug Catalog

Canonical quasi-trivial Python bug patterns for fast, high-confidence review. Impact levels are contextual defaults, not substitutes for assessing the affected code path.

## Control Flow

### CF001: Constant Operand in Boolean Branch

**Default impact**: HIGH (contextual) - a truthy constant can make the branch unconditional.
**Confidence**: High when a non-boolean constant is a direct `and` or `or` operand.
**Signature**: `condition or <truthy constant>` or `condition and <falsy constant>` where the constant is not an intentional result value.
**Minimal example**:
```python
if state == "ready" or "queued":
    dispatch()
```
**Confirmation**: Evaluate each Boolean operand independently and confirm the branch was meant to compare the same value more than once.
**False-positive guard**: Exclude value-selection idioms such as `name = supplied or "default"` and deliberate constant feature gates.
**Fix**: Repeat the comparison, for example `state == "ready" or state == "queued"`, or use membership.
**Source**: Curated common-pattern proposal, 2026-08-06

### CF002: Mutually Exclusive Equality Conjunction

**Default impact**: HIGH (contextual) - the guarded suite is unreachable for ordinary scalar values.
**Confidence**: High when one expression is compared by equality with distinct immutable literals under `and`.
**Signature**: `value == A and value == B` where `A != B` and no overloaded comparison semantics can satisfy both.
**Minimal example**:
```python
if status == "open" and status == "closed":
    reconcile()
```
**Confirmation**: Confirm both comparisons apply to the same value and the literals are distinct.
**False-positive guard**: Exclude overloaded equality, state-changing property access, and comparisons intended for different variables.
**Fix**: Use `or` or membership for alternatives, or correct the variable used by one comparison.
**Source**: Curated common-pattern proposal, 2026-08-06

### CF003: Always-True Inequality Disjunction

**Default impact**: HIGH (contextual) - the branch always runs for ordinary scalar values.
**Confidence**: High when one expression is compared with distinct immutable literals under `or`.
**Signature**: `value != A or value != B` where `A != B` and ordinary equality semantics apply.
**Minimal example**:
```python
if mode != "read" or mode != "write":
    reject()
```
**Confirmation**: Confirm the intended rule was to reject values outside both allowed alternatives.
**False-positive guard**: Exclude overloaded inequality and expressions whose repeated evaluation can change state.
**Fix**: Use `and`, or write `mode not in ("read", "write")`.
**Source**: Curated common-pattern proposal, 2026-08-06

### CF004: Repeated Pure Elif Condition

**Default impact**: HIGH (contextual) - the later branch can never be selected.
**Confidence**: High when an `elif` exactly repeats an earlier side-effect-free condition in the same chain.
**Signature**: Duplicate pure conditions in one `if`/`elif` chain with no intervening mutation relevant to evaluation.
**Minimal example**:
```python
if code == 1:
    start()
elif code == 1:
    stop()
```
**Confirmation**: Normalize trivial syntax differences and confirm both conditions have the same meaning.
**False-positive guard**: Exclude calls, descriptors, or other expressions whose repeated evaluation may intentionally produce different results.
**Fix**: Correct the repeated condition or merge the branch bodies when they share the same case.
**Source**: Curated common-pattern proposal, 2026-08-06

### CF005: Code After Suite Terminator

**Default impact**: MEDIUM (contextual; HIGH when required work is skipped) - statements cannot execute.
**Confidence**: High for statements after an unconditional `return`, `raise`, `break`, or `continue` in the same suite.
**Signature**: A suite terminator followed by another statement without an intervening branch boundary.
**Minimal example**:
```python
def load():
    return cached
    refresh_cache()
```
**Confirmation**: Confirm the terminator is unconditional on every path reaching the following statement.
**False-positive guard**: Exclude code in a nested function, handler, `finally` suite, or a different conditional branch.
**Fix**: Remove dead code or move required work before the terminator or onto a reachable path.
**Source**: Curated common-pattern proposal, 2026-08-06

### CF006: Boolean Expression in Except Type

**Default impact**: HIGH (contextual) - one or more intended exception types are not caught.
**Confidence**: High for `except A or B` and `except A and B` with exception classes.
**Signature**: A Boolean operation is used as the exception type expression instead of a tuple.
**Minimal example**:
```python
try:
    parse(data)
except ValueError or TypeError:
    recover()
```
**Confirmation**: Evaluate the exception expression and verify that it resolves to only one operand.
**False-positive guard**: Exclude a named tuple of exception classes and deliberate dynamically computed exception-type expressions.
**Fix**: Catch a tuple: `except (ValueError, TypeError):`.
**Source**: Curated common-pattern proposal, 2026-08-06

### CF007: Broad Handler Before Narrow Handler

**Default impact**: HIGH (contextual) - specialized recovery is unreachable.
**Confidence**: High when an earlier handler catches a superclass of a later handler's exception.
**Signature**: `except BaseType` precedes `except SubType` in the same `try` statement.
**Minimal example**:
```python
try:
    convert(value)
except Exception:
    fallback()
except ValueError:
    report_bad_value()
```
**Confirmation**: Verify the later exception is a subclass of the earlier caught type.
**False-positive guard**: Account for tuples and project-defined exception inheritance before classifying handler reachability.
**Fix**: Order handlers from narrowest to broadest.
**Source**: Curated common-pattern proposal, 2026-08-06

### CF008: Bare Except Catches Process Signals

**Default impact**: MEDIUM (contextual; HIGH in long-running services) - shutdown and interruption signals can be swallowed.
**Confidence**: High that bare `except:` catches `BaseException` subclasses beyond ordinary application errors.
**Signature**: A bare `except:` handler, especially one that continues, retries, or returns normally.
**Minimal example**:
```python
try:
    poll()
except:
    retry()
```
**Confirmation**: Determine which operational exceptions are actually expected at this boundary.
**False-positive guard**: Exclude top-level cleanup that immediately re-raises and intentionally documented process-boundary handling.
**Fix**: Catch the narrow expected exception tuple; re-raise process-control exceptions when a broad boundary is unavoidable.
**Source**: Curated common-pattern proposal, 2026-08-06

### CF009: Silent Exception Suppression

**Default impact**: MEDIUM (contextual; HIGH when failure changes correctness) - execution proceeds without evidence of failure.
**Confidence**: High for handlers whose body is only `pass`, an ellipsis, or an unobserved no-op.
**Signature**: An exception handler suppresses a caught error without logging, state repair, fallback, or re-raise.
**Minimal example**:
```python
try:
    persist(record)
except OSError:
    pass
```
**Confirmation**: Verify that ignoring this exact failure is not part of the documented contract.
**False-positive guard**: Exclude narrow best-effort cleanup and absence checks where suppression is deliberate and harmless.
**Fix**: Handle, report, translate, or re-raise the exception; document a truly intentional suppression.
**Source**: Curated common-pattern proposal, 2026-08-06

### CF010: Control Transfer in Finally

**Default impact**: HIGH (contextual) - a pending exception or earlier return can be silently replaced.
**Confidence**: High for `return`, `break`, or `continue` executed by a `finally` suite.
**Signature**: A control-transfer statement occurs in `finally`, directly or on a statically selected path.
**Minimal example**:
```python
def run():
    try:
        raise RuntimeError("failed")
    finally:
        return None
```
**Confirmation**: Trace pending exceptions and return values into the `finally` suite.
**False-positive guard**: Exclude transfers inside a nested function and distinguish cleanup calls from control transfer.
**Fix**: Remove the transfer from `finally`; perform cleanup there and return or branch afterward.
**Source**: Curated common-pattern proposal, 2026-08-06

## Type Safety

### TS001: Literal Value Compared by Identity

**Default impact**: HIGH (contextual) - equal values may compare unequal depending on object identity.
**Confidence**: High for `is` or `is not` against string, numeric, bytes, or container literals.
**Signature**: Value identity comparison with a literal other than the singleton sentinels `None`, `True`, `False`, or `Ellipsis`.
**Minimal example**:
```python
if command is "stop":
    shutdown()
```
**Confirmation**: Confirm value equality, rather than singleton identity, expresses the intended contract.
**False-positive guard**: Preserve identity checks for `None`, explicit sentinels, and objects whose identity is the contract.
**Fix**: Use `==` or `!=` for value comparison.
**Source**: Curated common-pattern proposal, 2026-08-06

### TS002: Mutable Default Argument

**Default impact**: HIGH (contextual) - state leaks across calls that omit the argument.
**Confidence**: High when a function default creates a mutable list, dict, set, or mutable instance.
**Signature**: A mutable object is evaluated in a parameter default at function definition time.
**Minimal example**:
```python
def collect(item, items=[]):
    items.append(item)
    return items
```
**Confirmation**: Confirm calls are expected to receive independent containers when the argument is omitted.
**False-positive guard**: Exclude intentional caches or shared accumulators whose lifetime is explicit and tested.
**Fix**: Default to `None` or a sentinel and allocate inside the function.
**Source**: Curated common-pattern proposal, 2026-08-06

### TS003: In-Place Mutator Result Used as Value

**Default impact**: HIGH (contextual) - the assigned or returned value is usually `None`.
**Confidence**: High for known in-place methods such as `list.sort`, `list.append`, `dict.update`, and `set.add`.
**Signature**: The result of a mutator that returns `None` is assigned, returned, compared, or passed onward.
**Minimal example**:
```python
ordered = values.sort()
consume(ordered)
```
**Confirmation**: Resolve the receiver type and verify the selected method's return contract.
**False-positive guard**: Do not generalize by method name when a project-defined method returns a useful value.
**Fix**: Mutate in a separate statement, then use the object, or choose a value-returning alternative such as `sorted`.
**Source**: Curated common-pattern proposal, 2026-08-06

### TS004: Non-Optional Return Can Fall Through

**Default impact**: HIGH (contextual) - callers unexpectedly receive `None`.
**Confidence**: High when a function annotated with a non-optional return type has a reachable fallthrough path.
**Signature**: Not every reachable path returns or raises in a function whose declared result excludes `None`.
**Minimal example**:
```python
def price(found: bool) -> float:
    if found:
        return 1.0
```
**Confirmation**: Trace all branches and confirm the annotation represents the intended runtime contract.
**False-positive guard**: Exclude abstract stubs, overload declarations, generator functions, and paths terminated by a known no-return call.
**Fix**: Return a valid value, raise, or make `None` explicit in both the implementation and type contract.
**Source**: Curated common-pattern proposal, 2026-08-06

### TS005: List Passed as isinstance Class Info

**Default impact**: HIGH (contextual) - `isinstance` raises `TypeError` when the check executes.
**Confidence**: High when the second argument is syntactically a list.
**Signature**: `isinstance(value, [TypeA, TypeB])` or an equivalent list-valued class-info argument.
**Minimal example**:
```python
if isinstance(value, [int, float]):
    normalize(value)
```
**Confirmation**: Confirm the second argument evaluates to a list rather than a valid type, tuple, or supported union type.
**False-positive guard**: Do not flag tuple class info or runtime-supported union-type class info.
**Fix**: Pass a tuple: `isinstance(value, (int, float))`.
**Source**: Curated common-pattern proposal, 2026-08-06

### TS006: Repeated Mutable Element Aliases

**Default impact**: HIGH (contextual) - mutating one apparent element changes every aliased element.
**Confidence**: High when sequence repetition duplicates one mutable object reference.
**Signature**: `[mutable_value] * count`, or equivalent sequence repetition, followed by independent-element use.
**Minimal example**:
```python
rows = [[]] * 3
rows[0].append("x")
```
**Confirmation**: Verify independent inner objects are required and the repeated value is mutable.
**False-positive guard**: Exclude immutable repeated values and deliberate shared-reference tables.
**Fix**: Construct each element independently, for example `[[] for _ in range(3)]`.
**Source**: Curated common-pattern proposal, 2026-08-06

### TS007: dict.fromkeys Shares Mutable Value

**Default impact**: HIGH (contextual) - updates through one key appear under every key.
**Confidence**: High when `dict.fromkeys` receives an explicit mutable value.
**Signature**: `dict.fromkeys(keys, mutable_value)` where each key is expected to own separate state.
**Minimal example**:
```python
buckets = dict.fromkeys(names, [])
buckets["a"].append(1)
```
**Confirmation**: Confirm per-key values should be independent and the supplied value is mutable.
**False-positive guard**: Exclude omitted values, immutable shared values, and intentional shared-state mappings.
**Fix**: Use a comprehension such as `{name: [] for name in names}`.
**Source**: Curated common-pattern proposal, 2026-08-06

### TS008: Obvious Literal Return-Type Mismatch

**Default impact**: HIGH (contextual) - callers receive a value that contradicts the declared API.
**Confidence**: High when a literal return is plainly incompatible with a concrete annotation.
**Signature**: A return statement yields a literal of a different built-in type from the declared non-union result.
**Minimal example**:
```python
def count() -> int:
    return "3"
```
**Confirmation**: Resolve aliases and unions, then verify the annotation is current and enforced by callers.
**False-positive guard**: Exclude `Any`, compatible protocols, coercing wrappers, broad unions, and intentionally stale annotations pending clarification.
**Fix**: Return the declared type or correct the annotation and dependent contract.
**Source**: Curated common-pattern proposal, 2026-08-06

### TS009: Dictionary View Indexed as Sequence

**Default impact**: HIGH (contextual) - indexing a dictionary view raises `TypeError`.
**Confidence**: High for subscripting the direct result of `keys()`, `values()`, or `items()`.
**Signature**: `mapping.keys()[index]`, `mapping.values()[index]`, or `mapping.items()[index]`.
**Minimal example**:
```python
first_key = settings.keys()[0]
```
**Confirmation**: Resolve the receiver as a standard mapping view and confirm positional access is intended.
**False-positive guard**: Exclude custom mapping methods that explicitly return an indexable sequence.
**Fix**: Use iteration for the first item or explicitly materialize a list when positional access is justified.
**Source**: Curated common-pattern proposal, 2026-08-06

### TS010: Dictionary View Method Not Called

**Default impact**: HIGH (contextual) - code uses a bound method instead of the intended view and commonly raises `TypeError`.
**Confidence**: High when `.keys`, `.values`, or `.items` is consumed as an iterable without a call.
**Signature**: A standard dictionary view method attribute is iterated, unpacked, or tested for membership without `()`.
**Minimal example**:
```python
for key in settings.keys:
    validate(key)
```
**Confirmation**: Resolve the receiver as a standard mapping and verify the method object is not intentionally passed as a callback.
**False-positive guard**: Exclude callback registration, deferred invocation, and custom attributes that are properties rather than methods.
**Fix**: Call the method, for example `settings.keys()`, or iterate the mapping directly for keys.
**Source**: Curated common-pattern proposal, 2026-08-06

### TS011: Statically Absent Attribute on Known Instance

**Default impact**: HIGH (contextual) - the access raises `AttributeError`, potentially masking the error path that attempted to report the original failure.
**Confidence**: High when local proof resolves the receiver to a concrete class and the attribute is absent from that class and its bases.
**Signature**: An attribute read targets a locally known concrete instance, neither the class nor its bases declare the attribute, and a nearby established attribute is the evident contract.
**Minimal example**:
```python
class Record:
    def __init__(self, cwd: str):
        self.cwd = cwd

record = Record("/logs")
alert(record.record_dir)  # Before: absent
alert(record.cwd)         # After: declared
```
**Confirmation**: Resolve the receiver type, inspect its constructor, class body, bases, and assignments, then confirm the established attribute expresses the intended value.
**False-positive guard**: Exclude `__getattr__`, dynamic descriptors, framework injection, monkey-patching, and unresolved receiver types.
**Fix**: Read the declared intended attribute, or declare and populate the missing attribute consistently when it represents a distinct contract.
**Source**: Historical repair, d3dd198867dd169293c58202a9bc261d779626c7 -> a0394e8be356a5ab3fc20d0d2e302419042ef2ff, x2monitor/x2collect/check_process.py, hunk -444,+469

## String

### ST001: Empty split Separator

**Default impact**: HIGH (contextual) - `str.split` raises `ValueError` immediately.
**Confidence**: High when the explicit separator is the empty string.
**Signature**: `text.split("")` or `text.rsplit("")`.
**Minimal example**:
```python
characters = text.split("")
```
**Confirmation**: Confirm character iteration, whitespace splitting, or another delimiter was intended.
**False-positive guard**: Distinguish `split()` with no argument, which is valid, from an explicit empty separator.
**Fix**: Iterate the string, use `list(text)`, omit the separator for whitespace, or supply a non-empty delimiter.
**Source**: Curated common-pattern proposal, 2026-08-06

### ST002: List Passed to startswith or endswith

**Default impact**: HIGH (contextual) - the call raises `TypeError`.
**Confidence**: High when a literal list is supplied as the prefix or suffix argument.
**Signature**: `text.startswith([..])` or `text.endswith([..])` instead of the supported string or tuple.
**Minimal example**:
```python
if filename.endswith([".py", ".pyi"]):
    inspect(filename)
```
**Confirmation**: Confirm multiple alternatives are intended and the receiver is a standard string or bytes object.
**False-positive guard**: Exclude tuples and custom objects with different method contracts.
**Fix**: Pass a tuple, for example `filename.endswith((".py", ".pyi"))`.
**Source**: Curated common-pattern proposal, 2026-08-06

### ST003: Static str.format Placeholder Mismatch

**Default impact**: HIGH (contextual) - formatting raises or silently ignores unintended extra arguments.
**Confidence**: High when a literal format string and arguments prove a missing positional or named field.
**Signature**: Static `{}` fields reference unavailable positional indexes or keyword names.
**Minimal example**:
```python
message = "{}: {detail}".format("error")
```
**Confirmation**: Parse the format string and account for automatic numbering, explicit indexes, named fields, and escaped braces.
**False-positive guard**: Do not infer a mismatch when the template or argument mapping is dynamic or a custom formatter supplies fields.
**Fix**: Supply the missing argument or correct/remove the placeholder.
**Source**: Curated common-pattern proposal, 2026-08-06

### ST004: Static Percent-Formatting Mismatch

**Default impact**: HIGH (contextual) - formatting raises `TypeError`, `ValueError`, or `KeyError`.
**Confidence**: High when a literal percent-format string and static operand have incompatible arity or mapping shape.
**Signature**: Conversion specifiers do not match a tuple's item count, a mapping's keys, or the operand form.
**Minimal example**:
```python
message = "%s: %s" % ("error",)
```
**Confirmation**: Parse conversions while excluding escaped `%%` and verify the operand's static shape.
**False-positive guard**: Defer when either the format string or operand shape is dynamic.
**Fix**: Align conversion fields and operands, or use a correctly formed f-string or `str.format` call.
**Source**: Curated common-pattern proposal, 2026-08-06

### ST005: find Result Used as Boolean

**Default impact**: HIGH (contextual) - index `0` is false while not-found `-1` is true, reversing common intent.
**Confidence**: High when a `find` or `rfind` result directly controls a condition.
**Signature**: `if text.find(needle):` or Boolean composition of the raw integer result.
**Minimal example**:
```python
if text.find("ERROR"):
    alert()
```
**Confirmation**: Determine whether the code needs containment or a specific index comparison.
**False-positive guard**: Exclude explicit comparisons such as `find(...) >= 0` and intentional numeric index truthiness.
**Fix**: Use `needle in text` for containment or compare the result explicitly with `-1`.
**Source**: Curated common-pattern proposal, 2026-08-06

### ST006: Discarded Immutable String Transform

**Default impact**: MEDIUM (contextual; HIGH when normalization is required) - the original string remains unchanged.
**Confidence**: High when a known string-transform result is an unused expression statement.
**Signature**: Calls such as `strip`, `replace`, `lower`, or `upper` are made without assigning, returning, or consuming their result.
**Minimal example**:
```python
name.strip()
store(name)
```
**Confirmation**: Confirm the receiver is a standard immutable string and the transformed value is needed later.
**False-positive guard**: Exclude custom string-like types with side effects and calls used only to validate arguments deliberately.
**Fix**: Assign or directly consume the returned string, for example `name = name.strip()`.
**Source**: Curated common-pattern proposal, 2026-08-06

### ST007: str(bytes) Used as Decoding

**Default impact**: HIGH (contextual) - output includes the bytes representation rather than decoded text.
**Confidence**: High for one-argument `str(bytes_value)` used where decoded content is expected.
**Signature**: `str()` wraps a value statically known to be `bytes` or `bytearray` without an encoding.
**Minimal example**:
```python
payload = b"hello"
text = str(payload)
```
**Confirmation**: Confirm the intent is textual decoding rather than a diagnostic representation.
**False-positive guard**: Exclude deliberate logging/debug representation and valid `str(bytes_value, encoding)` calls.
**Fix**: Use `payload.decode(encoding)` or `str(payload, encoding)` with an explicit error policy where needed.
**Source**: Curated common-pattern proposal, 2026-08-06

### ST008: Static bytes and str Comparison

**Default impact**: HIGH (contextual) - equality is always false and inequality always true for ordinary values.
**Confidence**: High when operand types are statically certain as `bytes` and `str`.
**Signature**: Equality or inequality directly compares text and binary data without conversion.
**Minimal example**:
```python
response = b"OK"
if response == "OK":
    accept()
```
**Confirmation**: Establish both operand types at the comparison point and the intended encoding boundary.
**False-positive guard**: Defer for `Any`, unions, custom equality implementations, or deliberately type-discriminating comparisons.
**Fix**: Decode bytes or encode text once at a clear boundary, then compare like types.
**Source**: Curated common-pattern proposal, 2026-08-06

### ST009: Interpolation Placeholder Without f Prefix

**Default impact**: MEDIUM (contextual; HIGH in commands, paths, or identifiers) - literal braces reach downstream code.
**Confidence**: High when a plain literal contains a simple `{name}` field and the named value is in scope.
**Signature**: A non-f-string literal looks like intended interpolation and is consumed as completed text.
**Minimal example**:
```python
user = "Ada"
message = "Hello, {user}"
```
**Confirmation**: Confirm braces are intended for immediate interpolation rather than later templating or literal output.
**False-positive guard**: Exclude templates passed to formatters, logging frameworks, localization systems, and escaped/literal brace content.
**Fix**: Add the `f` prefix or invoke the intended formatting mechanism explicitly.
**Source**: Curated common-pattern proposal, 2026-08-06

### ST010: Accidental Adjacent String Literal Concatenation

**Default impact**: MEDIUM (contextual) - two intended elements silently become one string.
**Confidence**: High when adjacent literals occur as list, tuple, set, argument, or mapping elements without a separator.
**Signature**: Two string literals are adjacent where surrounding syntax suggests a missing comma.
**Minimal example**:
```python
roles = ["reader" "writer", "admin"]
```
**Confirmation**: Check the intended element or argument count and whether concatenation was deliberate.
**False-positive guard**: Exclude deliberate source-line wrapping and documented compile-time concatenation of one logical string.
**Fix**: Insert the missing comma, or make intentional concatenation structurally clear.
**Source**: Curated common-pattern proposal, 2026-08-06

### ST011: strip Argument Mistaken for Exact Affix

**Default impact**: MEDIUM (contextual; HIGH when identifiers or paths are altered) - extra edge characters can be removed.
**Confidence**: High when a multi-character `strip`, `lstrip`, or `rstrip` argument resembles a prefix or suffix.
**Signature**: `text.strip(chars)` is used as though it removed one exact substring rather than any run of characters in a set.
**Minimal example**:
```python
name = "archive.tar".rstrip(".tar")
```
**Confirmation**: Confirm the intent is to remove one exact affix and test edge strings containing the same characters in other orders.
**False-positive guard**: Exclude genuine character-set trimming such as whitespace or punctuation cleanup. Also exclude cases where the locally proven payload grammar is disjoint from every strip character; the historical case validates this guard rather than establishing a defect (d3dd198867dd169293c58202a9bc261d779626c7 -> a0394e8be356a5ab3fc20d0d2e302419042ef2ff, x2monitor/x2collect/check_process.py, hunk -112,+112).
**Fix**: Use `removeprefix` or `removesuffix`, or an explicit guarded slice on older Python versions.
**Source**: Curated common-pattern proposal, 2026-08-06
