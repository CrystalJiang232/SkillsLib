---
name: pc-pybug
description: Python bug detection and pitfall scanning skill. Focuses on catching subtle but potentially lethal bugs in Python code — control flow errors, type safety violations, string handling mistakes, and semantic anti-patterns. Use when analyzing Python code for correctness, reviewing code for subtle bugs, conducting pre-commit safety checks, or working on ultra high reliability systems (HFT, financial infra, safety-critical). Triggers on any Python code review, bug hunting, or reliability audit task. NOT for general code style/linting (use ruff/flake8), obvious syntax errors (compiler catches these), or non-Python languages.
---

# 白虹彤霞 / PyCrimson — Python Bug Hunter

A pitfall-focused bug detection skill for Python. Catches bugs at their spark before they ignite — from trivial pattern mismatches to deep semantic traps that static analyzers miss.

## When to Use

- Analyzing Python code for subtle correctness bugs
- Pre-commit safety scanning on critical code paths
- Reviewing code in HFT, financial, or safety-critical contexts
- Investigating suspicious behavior or elusive bugs
- Complementing static analysis tools (catches what they miss)

## When NOT to Use

- General style/linting enforcement (use `ruff`, `flake8`, `pylint`)
- Obvious syntax errors (Python interpreter catches these)
- Non-Python languages
- High-level architecture review (this skill targets code-level pitfalls)

## Analysis Modes

### Mode A: Pattern-Fast Scanning (Default)

Trigger: Normal invocation of this skill. No special trigger required.

Uses lightweight pattern matching against known bug signatures in the `fast/` directory. One file per bug category. Optimized for speed — scans large codebases quickly.

**Rule**: Always start with pattern-fast. Only escalate to deep semantic when explicitly requested or when pattern-fast findings suggest deeper issues.

### Mode B: Deep Semantic Analysis (Manual Trigger)

Trigger: User explicitly requests deep analysis OR analysis keyword detected in query (e.g., "deep scan", "semantic audit", "thorough analysis").

Uses control-flow and data-flow reasoning to detect bugs requiring semantic understanding — unreachable code, contradiction conditions, state-machine violations, reference lifetime issues.

**Rule**: When triggered, load reference files from `cdecl/` directory. These contain detailed analysis patterns and reasoning instructions comparable to `rt-cppeng`'s `references/patterns.md`.

**Current Status**: `cdecl/` directory is **TODO** — empty pending population with deep semantic analysis patterns.

## Subagent Orchestration

**Eligibility Check**: Before spawning, verify the agent has subagent spawning capability and the user has not forbidden it.

**Rule**: If eligible, spawn **one subagent per task**. Never spawn multiple subagents for the same task — serialize analysis through single focused workers.

### Available Hunter Types

Spawn exactly one hunter based on the primary concern of the code under review:

| Hunter | Domain | Triggers | Fast Reference |
|--------|--------|----------|----------------|
| **Control Flow Hunter** | Branching, loops, exceptions, state machines | `switch`-like patterns (`if/elif/else`), missing `break` equivalents, fallthrough bugs, unreachable `if` conditions, infinite loops, exception swallowing | `fast/control-flow.md` |
| **Type Safety Hunter** | Type mismatches, `None` handling, implicit conversions | Return type mismatches (especially implicit `None`), missing `return` in some branches, mutable default arguments, `is` vs `==`, truthiness traps, type annotation violations | `fast/type-safety.md` |
| **String Hunter** | String formatting, encoding, path handling, interpolation | f-string expression evaluation, `.format()` injection risks, encoding mismatches, path traversal via string concat, regex edge cases, string interning surprises | `fast/string.md` |

**Selection Rule**: If code spans multiple domains, pick the hunter matching the most critical-looking code path. User can request a specific hunter by name.

## Workflow (CTAGV Five-Phase)

Follow the Constraints-Task-Acquire-Generate-Verify loop for every analysis session. All five phases must be executed visibly.

### Phase 1: Constraints — Read

Load governing constraints before any analysis:

- Read this SKILL.md's **Constraints** section (severity rules, fix policy, analysis scope)
- Read the **Severity Levels** table to calibrate judgment
- Load the selected hunter's fast reference (`fast/control-flow.md`, `fast/type-safety.md`, or `fast/string.md`)
- If deep semantic mode: read applicable `cdecl/` reference files

### Phase 2: Task — Select

Determine the analysis task parameters:

- **Select Mode**: Pattern-fast (default) or deep semantic (triggered by user keyword or complexity signal)
- **Select Hunter**: One of Control Flow, Type Safety, or String — based on primary concern in target code
- **Identify Targets**: Confirm the code file(s) or functions to analyze
- **Rule**: If subagent-eligible, prepare Handoff Contract with the above selections; spawn one hunter subagent

### Phase 3: Acquire — Gather

Load all necessary context to perform the analysis:

- Read the target Python code file(s)
- Search `references/python-bug-catalog.md` for matching bug patterns (grep-search code anchors)
- Load any additional references indicated by the selected hunter or deep semantic mode
- Review calibration examples in SKILL.md to align output style

### Phase 4: Generate — Analyze

Execute the hunt. For each potential bug found:

- **Bug Category**: Control flow? Type safety? String handling?
- **Risk Assessment**: What happens if this bug fires in production?
- **Confidence**: Certain, or context-dependent [?]?
- **Proposed Fix**: Definitive fix (LETHAL/HIGH) or tentative fix + verification question (MEDIUM/LOW [?])
- **Output**: Structured finding in the format defined in **Output Format**

Prefer file output (`analysis/<filename>-<timestamp>.md`) over session window.

### Phase 5: Verify — Check

Before returning, validate all findings:

- [ ] Severity matches actual risk (not over/under-rated)
- [ ] Every finding has: specific location (file:line), bug type, and proposed fix
- [ ] Uncertain findings marked with [?] — no definitive fix asserted without confirmation
- [ ] No duplicate findings across categories
- [ ] If novel bug discovered: cataloged in `references/python-bug-catalog.md` per **Self-Learning & Growth Mechanism**

## Output Format

```markdown
## File: `path/to/file.py`

### Line 42 — LETHAL
**Bug Type**: Control Flow — Missing break equivalent (fallthrough)
**Current:**
```python
def handle_state(state):
    if state == STATE_ERROR:
        log_error()
        # Missing return — falls through to STATE_OK logic
    if state == STATE_OK:
        process_normal()
```

**Rationale**:
Missing `return` after `STATE_ERROR` handling causes error state to fall through to `STATE_OK` processing. In HFT contexts, this could trigger trades on invalid data.

**Proposed Fix**:
```python
def handle_state(state):
    if state == STATE_ERROR:
        log_error()
        return  # or raise
    if state == STATE_OK:
        process_normal()
```

---

### Line 67 — HIGH
**Bug Type**: Type Safety — Implicit None return
**Current:**
```python
def get_price(symbol: str) -> float:
    if symbol in cache:
        return cache[symbol]
    # Missing return: implicitly returns None, violating -> float
```

**Rationale**:
Function declares `-> float` but returns `None` when `symbol` not in cache. Type checker may not catch this if cache lookup is dynamic. Calling code doing arithmetic on the result will crash with `TypeError`.

**Proposed Fix**:
```python
def get_price(symbol: str) -> float:
    if symbol in cache:
        return cache[symbol]
    return 0.0  # Or: raise KeyError(f"No price for {symbol}")
```
```

## Severity Levels

| Level | Priority | Criteria | Example |
|-------|----------|----------|---------|
| **LETHAL** | P0 | Silent data corruption, wrong-branch execution, production crash | Missing `return` causing fallthrough, mutable default dict accumulating state |
| **HIGH** | P1 | Will crash or produce wrong results under specific conditions | Implicit `None` return violating type hint, `is` used instead of `==` for value comparison |
| **MEDIUM** | P2 | Bug-risk pattern that may be intentional but needs verification | `except:` bare clause swallowing `KeyboardInterrupt`, f-string with unsanitized user input |
| **LOW** | P3 | Defensive coding recommendation, edge case | Missing `final` equivalent on constants, redundant condition |

**Constraint Validation**: For each finding, mentally verify severity against this table before outputting.

## Self-Learning & Growth Mechanism

This skill grows through real-world bug discovery. Every agent using this skill contributes to its catalog.

### How Growth Works

When you (the agent) discover a bug pattern not documented in the references:

1. **Spot it** — Find a novel bug during code analysis
2. **Characterize it** — Write a concise description + minimal code example
3. **Append it** — Add to `references/python-bug-catalog.md` following the existing format
4. **Flag it** — Note in your output: `[NEW PATTERN] Cataloged in references/python-bug-catalog.md`

### Catalog Entry Format

Each entry in `references/python-bug-catalog.md`:

```markdown
### <Bug Short Name>
**Category**: Control Flow | Type Safety | String
**Severity**: LETHAL | HIGH | MEDIUM | LOW
**Description**: One-line description of the bug.
**Trigger**: What code pattern triggers this bug.
**Looks Like**:
```python
# Minimal code example showing the buggy pattern
# Keep under 10 lines. This is the grep-search anchor.
```
**Fix Pattern**: Brief description of the fix approach.
**Discovered**: YYYY-MM-DD context (optional)
```

### Growth Rules

- **Never duplicate**: Before adding, search the catalog for existing similar entries
- **Minimal examples**: Code blocks must be under 10 lines — this is the grep-search anchor
- **One bug per entry**: Don't combine multiple related bugs into one entry
- **Mark date**: Include discovery date and context for traceability
- **Categories only**: Control Flow, Type Safety, String — don't invent new categories

### Fast File Growth

When a bug category accumulates 5+ entries in the catalog, consider extracting to a dedicated `fast/<category>.md` file for faster lookup. The catalog always remains the master index.

## Reference Files

**ALWAYS READ FIRST** (when in pattern-fast mode):
- **Python Bug Catalog** → `references/python-bug-catalog.md`
  - Master index of all known bug patterns
  - Grep-searchable code anchors for rapid pattern matching
  - This file grows with every new bug discovery

**FAST PATTERNS** (one file per category):
- `fast/control-flow.md` — Control flow bug signatures
- `fast/type-safety.md` — Type safety bug signatures
- `fast/string.md` — String handling bug signatures

**DEEP SEMANTIC** (manual trigger only):
- `cdecl/` — **TODO: EMPTY DIRECTORY**
  - Will contain detailed semantic analysis patterns, data-flow reasoning guides, and complex bug detection logic
  - Comparable depth to `rt-cppeng`'s `references/patterns.md`
  - Population deferred — requires extensive pattern curation

## Calibration Examples

### Example 1: LETHAL — Mutable Default Argument

**Input Code:**
```python
def process_trades(symbols, results=[]):
    for sym in symbols:
        results.append(fetch(sym))
    return results
```

**Analysis Output:**
```markdown
### Line 1 — LETHAL
**Bug Type**: Type Safety — Mutable default argument
**Current:**
```python
def process_trades(symbols, results=[]):
```

**Rationale**:
Default argument `results=[]` is evaluated once at function definition time. Subsequent calls without the `results` parameter will accumulate into the same list. In HFT systems, this causes cross-request data contamination — trade results from one session leak into the next.

**Proposed Fix**:
```python
def process_trades(symbols, results=None):
    if results is None:
        results = []
    for sym in symbols:
        results.append(fetch(sym))
    return results
```
```

---

### Example 2: HIGH — `is` vs `==` for Value Comparison

**Input Code:**
```python
if user_input is "EXIT":
    shutdown()
```

**Analysis Output:**
```markdown
### Line 1 — HIGH
**Bug Type**: Type Safety — `is` used for value comparison
**Current:**
```python
if user_input is "EXIT":
```

**Rationale**:
`is` checks identity (memory address), not equality. String interning makes this sometimes work for short strings, but it's not guaranteed. `user_input` read from a file or network will never match `"EXIT"` by identity. This is a flaky bug — works in tests, fails in production.

**Proposed Fix**:
```python
if user_input == "EXIT":
    shutdown()
```
```

---

### Example 3: MEDIUM — Exception Swallowing

**Input Code:**
```python
def connect():
    try:
        sock = socket.create_connection((host, port))
        return sock
    except:
        return None
```

**Analysis Output:**
```markdown
### Line 4 — MEDIUM [?]
**Bug Type**: Control Flow — Bare `except:` swallowing all exceptions
**Current:**
```python
    except:
        return None
```

**Rationale**:
Bare `except:` catches `KeyboardInterrupt`, `SystemExit`, and `MemoryError` alongside expected connection errors. In HFT systems, this can mask critical shutdown signals or resource exhaustion, causing the process to appear healthy while being unable to trade.

**Proposed Fix**:
```python
    except OSError:
        return None
```

Verify: Is `socket.timeout` also expected? Consider `except (OSError, socket.timeout):` if so.
```

## Key Calibration Points from Examples

| Aspect | Example 1 (LETHAL) | Example 2 (HIGH) | Example 3 (MEDIUM) |
|--------|---------------------|------------------|--------------------|
| **Severity** | Data corruption risk | Production flakiness | Signal masking |
| **Tone** | Urgent, unambiguous | Firm, explains flakiness | Cautious, requests verification |
| **Fix Style** | Definitive fix provided | Definitive fix provided | Fix + verification question |
| **Confidence** | Certain | Certain | Context-dependent [?] |

## Constraints

### Analysis Scope
- Skip "good points" analysis unless user explicitly requests it
- Focus exclusively on bugs, risks, and correctness violations
- Do not report style issues covered by linters (line length, import sorting)

### Fix Policy
- **LETHAL / HIGH**: Provide definitive proposed fix. These are unambiguous bugs.
- **MEDIUM / LOW [?]**: Provide tentative fix + verification question. May be intentional.
- Never assert a fix for findings marked [?] without user confirmation.

### Output Preference
- Prefer file output over session window
- Save reports to `analysis/<filename>-<timestamp>.md`

## Continuous Improvement

When users provide feedback on findings, treat it as a catalog growth opportunity:
- Document novel patterns in `references/python-bug-catalog.md`
- Extract mature categories to dedicated `fast/<category>.md` files
- Note the resolution — was the bug confirmed, or was the pattern intentional?

## Validation Tools Reference

When appropriate, suggest the user verify findings with:

| Tool | Check | Command Example |
|------|-------|-----------------|
| `mypy` | Static type checking | `mypy --strict file.py` |
| `ruff` | Fast linting | `ruff check --select E,W,F,B file.py` |
| `bandit` | Security bugs | `bandit -r file.py` |

This skill does not invoke tools directly — recommend them in guidance when relevant.