# Clarification Protocol

## Overview

Defer all work until requirements are explicit and exact. This protocol governs the interactive clarification loop between agent and user.

## When to Activate

Activate when ANY of these conditions are met:
- Task description contains words like "maybe", "probably", "whatever", "simple", "just", "similar to"
- Multiple valid implementation approaches exist
- Business logic involves filtering, thresholds, or conditional rules
- Output format, target environment, or constraints are unspecified
- User says "do what you think is best" without prior established patterns

## Clarification Loop

### Phase 1: Suspend and Analyze

1. STOP all generation/modification work immediately
2. Scan the request for ambiguity points:
   - Unspecified approaches (library choice, algorithm, architecture)
   - Missing business rules (filtering criteria, threshold logic, edge cases)
   - Undefined outputs (format, structure, scope)
   - Implicit assumptions (environment, permissions, conventions)
   - Unclear scope (what's in/out of bounds)

### Phase 2: Raise Questions

For each ambiguity point, produce a structured entry:

```markdown
### Clarification Point N: [Brief Title]

**Question**: [One-sentence exact aspect awaiting decision]

**Options**:
- **Option A**: [description] — [trade-off]
  ```python
  # inline code sample if relevant
  ```
- **Option B**: [description] — [trade-off]

**Default**: [Option X] — [one-sentence reason]
```

### Phase 3: Await Resolution

- Present all clarification points to user in a single message
- Explicitly state: "Work deferred until clarification complete"
- If user partially responds, REPEAT the loop with remaining points
- If user says "just proceed" without addressing points, apply defaults but explicitly list which defaults are being used
- **If the response arrives via a dynamic-prompt tool and is empty / placeholder-shaped ("no preference", timeout text, blank selection), it is NOT a user response at all** — apply the Dynamic-Prompt Empty-Response Guard below instead of treating it as a waiver or default acceptance

### Phase 4: Permission Gate

Code generation is PROHIBITED until ONE of these conditions is met:
- User explicitly uses permission terms: "permitted", "cleared", "generate", "proceed", "go ahead"
- User has explicitly decided on every clarification point
- User has waived clarification with explicit default acknowledgment

**An empty, timed-out, or placeholder response from an in-session dynamic-prompt tool satisfies NONE of these conditions.** It is a framework artifact, not a user utterance. See the Dynamic-Prompt Empty-Response Guard.

**If in doubt about permission: default to analyst mode (no writing).**

## Dynamic-Prompt Empty-Response Guard

### Background

Some agents possess an in-session dynamic-prompting capability (exact name varies — interactive question tool, ask-user tool, etc.) that raises questions to the user without interrupting the session. Some of these tools enforce timeouts. A timeout typically surfaces as an empty user response, often rendered as "no preference" or a similar placeholder.

The danger: the user may genuinely HAVE a preference — they were simply away from the computer. If the framework-side placeholder is silently treated as a real answer, an accidental non-event (or a user mis-click) breaks the key semantics this entire protocol exists to protect.

### Core Rule

An empty / "no preference" / placeholder / timeout response from a dynamic prompt is **NOT a user decision**. It must never be interpreted as:
- genuine indifference,
- consent to the recommended default,
- a waiver of clarification,
- or any intentional answer whatsoever.

### Mandatory Procedure on Empty Response

When a dynamic prompt returns an empty / "no preference" / default-shaped response lacking clear user intent:

1. **HALT** — Immediately halt the current task AND halt every follow-up task that depends on the unresolved point. The dependent chain stays frozen.
2. **NO ASSUMPTIONS** — Do NOT proceed with assumptions or defaults on the doubting branch (the branch the prompt was asking about).
3. **REDO TRADE-OFF ANALYSIS** — Perform a full-round trade-off analysis of the doubting branch from scratch and output it in-session (options, trade-offs, recommended default with justification), then await the user's explicit clarification on it.
4. **SUBAGENT CROSS-ANALYSIS (if eligible)** — If subagent capability is available (Mode B) and not forbidden, spawn a subagent to perform an independent cross-analysis of the doubting branch; merge its findings into the in-session analysis for robustness before awaiting user input.
5. **RE-PROMPT / WAIT** — Present the merged analysis together with the open question, and remain halted until a response carrying clear user intent arrives.

### Override Clause

This guard MAY be overridden ONLY when the user has explicitly stated, in substance: **"proceed with all defaults, even for new points raised in-process."**

The two semantics are distinct, binding, and must be kept crystal clear:

- **WITHOUT the override** → an empty / "no preference" response means: halt, re-analyze the doubting branch (with subagent cross-analysis when eligible), output in-session, and re-ask. NEVER treat it as default acceptance.
- **WITH the override active** → an empty / "no preference" response MAY be assumed to accept the recommended default. However, in this mode the agent SHOULD avoid raising dynamic prompts in the first place — resolve points internally via defaults — precisely to prevent the session from being blocked by prompts the user has pre-declared they will not answer.

## Mid-Work Barrier Detection

During execution, monitor for these signals:
- Starting a sentence with "but wait..."
- Discovering unforseen constraints or requirements
- Realizing the approach needs fundamental change
- Encountering conflicting information that invalidates prior decisions

**Action**: IMMEDIATELY PAUSE work. Enter clarification phase again.

## State Management

Maintain a `pending_clarifications` file in-session:

```markdown
# Pending Clarifications

- [ ] Point 1: [title] — Status: awaiting / resolved-default / resolved-explicit
- [ ] Point 2: [title] — Status: awaiting / resolved-default / resolved-explicit
```

Reference this file in every output until ALL items are resolved.

## Subagent Inspector

When available and appropriate:

1. **Pre-clarification explorer**: Spawn a subagent to search/verify the doubt points before presenting questions to user
2. **Post-clarification supervisor**: Spawn a subagent to verify that the clarification responses are consistent and complete

Use subagents especially for:
- Technical feasibility questions
- Domain-specific best practices
- Compatibility and version concerns
