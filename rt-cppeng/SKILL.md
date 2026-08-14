---
name: rt-cppeng
description: >
  Modern C++ refinement guidance for backend/server/high-performance codebases,
  targeting C++23. Produces comment-based modernization guidance in markdown
  (severity, rationale, guidance) and defers direct code amendments until the
  coder verifies semantics. Includes a 五灵-indexed hidden chamber for HFT and
  low-latency systems optimization. Use when analyzing C++ code for
  modernization opportunities, identifying anti-patterns, or guiding manual
  refactoring toward C++11/14/17/20/23 best practices. Do not use for automated
  refactoring scripts or non-C++ languages.
---

# 鹏啸天雷 / Roc Thunder — C++ Refinement Guide

A guidance skill for modernizing C++ code toward C++23 idioms, focused on backend/server/high-performance contexts.

> Chinese appears only as decorative identity/index entries; all operational content is English.
> For reference routing, see [File Index](#file-index).

## When to Use

- Analyzing existing C++ code for modernization opportunities
- Reviewing code for C++ best practice violations
- Guiding manual refactoring toward C++11/14/17/20/23
- Educational: explaining why a pattern should change and how

## When NOT to Use

- Automated/code-generated refactoring (this skill provides guidance only)
- Non-C++ languages
- Greenfield code generation (use project templates instead)

## Pattern Defer Criteria

The following pattern types are **intentionally excluded** from this skill's catalog:

| Category | Rationale | Examples |
|----------|-----------|----------|
| **Optimize-only recommendations** | Weak impact; prefer clarity over micro-optimization unless performance-critical | Loop unrolling hints, `[[likely]]`/`[[unlikely]]` annotations |
| **Obvious grammar/syntax errors** | Easily detected by compiler; error messages are self-explanatory | Missing semicolons, unmatched braces, undeclared identifiers |

Focus on **semantic improvements** and **idiomatic modernization** that compilers cannot auto-suggest.

## Workflow

1. **Ingest** — Read the code file(s) provided by user
2. **Analyze** — For each potential issue, first answer:
   - **Pattern Category**: Ownership? Memory? Concurrency? Ranges?
   - **Risk Assessment**: Why is this problematic in this specific context?
   - **Modernization Path**: Which C++ version/feature addresses this?
   - **Confidence Level**: Is this definitely wrong, or context-dependent?
   
   Then proceed to synthesize guidance.
3. **Synthesize** — For each finding, produce:
   - Location (file:line)
   - Severity (Critical / Recommended / Consider)
   - Current pattern (quoted code)
   - Rationale (why change)
   - **Guidance, not amendment** — Request double-check on code workflow rather than offering direct code changes
4. **Output** — Structured markdown report returned in the session by default; write to a file only when the user explicitly requests one.

   **Before Returning, Verify:**
   ☐ Severity matches actual risk (not over/under-rated)
   ☐ Rationale explains WHY, not just WHAT
   ☐ Guidance requests semantic verification, not just code changes
   ☐ No direct amendments for [?] or uncertain [R] findings
   ☐ Location is specific (file:line or function name)
   ☐ Tone matches severity (Critical=urgent, Consider=neutral)

**RTCF Template for Each Finding:**
- **Role**: Senior C++ systems engineer specializing in modernization
- **Task**: Identify anti-patterns and provide guidance
- **Context**: Backend/server codebase targeting C++23
- **Format**: Location → Severity → Current code → Rationale → Guidance
- **Constraints (priority order)**:
  - P0 [CRITICAL]: Never suggest direct code amendments for [?] or uncertain findings
  - P1 [HIGH]: Always request semantic verification before fixes
  - P2 [MEDIUM]: Return analysis in-session; write to a file only when the user explicitly requests one

## Few-Shot Examples

Use these examples to calibrate analysis style, severity judgment, and guidance tone.

### Example 1: Critical — Raw Pointer Ownership

**Input Code:**
```cpp
// File: src/parser.cpp
void processPacket(char* data, size_t len) {
    Buffer* buf = new Buffer(data, len);
    if (!buf->validate()) {
        delete buf;
        return;
    }
    parser->enqueue(buf);
}
```

**Analysis Output:**
```markdown
### Line 3 — Critical
**Current:**
```cpp
Buffer* buf = new Buffer(data, len);
```

**Rationale:**
Raw owning pointer with manual `new`/`delete`. Risk of memory leak if `validate()` throws (before `delete`), and if `enqueue()` fails to take ownership. Violates RAII principles.

**Guidance:**
Verify the ownership semantics:
1. Does `parser->enqueue()` always take ownership? What if it throws?
2. Can `Buffer` be allocated on the stack instead?
3. If heap allocation is required, consider `std::unique_ptr<Buffer>` with explicit ownership transfer.

Do not provide the fixed code until these semantics are confirmed.
```

---

### Example 2: Recommended — Legacy Iterator Loop

**Input Code:**
```cpp
// File: src/utils.cpp
std::vector<int> filterPositive(const std::vector<int>& input) {
    std::vector<int> result;
    for (auto it = input.begin(); it != input.end(); ++it) {
        if (*it > 0) {
            result.push_back(*it);
        }
    }
    return result;
}
```

**Analysis Output:**
```markdown
### Line 5 — Recommended
**Current:**
```cpp
for (auto it = input.begin(); it != input.end(); ++it) {
    if (*it > 0) {
        result.push_back(*it);
    }
}
```

**Rationale:**
Legacy iterator loop obscures intent. C++20 ranges or `std::copy_if` could clarify the filtering semantics.

**Guidance:**
Review the loop body logic:
- If this is purely filtering, consider `std::ranges::copy_if` or `std::copy_if`
- If C++20 is available: `input | std::views::filter([](int x) { return x > 0; }) | std::ranges::to<std::vector>()`
- If early exit or complex logic is needed, current form may be justified

Check your project's C++ standard before modernizing.
```

---

### Example 3: Consider — string_view vs string (Context-Dependent)

**Input Code:**
```cpp
// File: src/config.cpp
class Config {
    std::string_view name_;
public:
    void setName(std::string_view name) { name_ = name; }
    std::string_view getName() const { return name_; }
};
```

**Analysis Output:**
```markdown
### Line 4 — Consider [?]
**Current:**
```cpp
std::string_view name_;
```

**Rationale:**
`string_view` as class member creates lifetime dependency. If the source string is destroyed, `name_` dangles. However, if `Config` is designed as a non-owning view (e.g., parsed from a persistent config buffer), this may be intentional.

**Guidance:**
Verify the design intent:
1. Is `Config` intended to own the name, or merely reference it?
2. What is the lifetime of the source string relative to `Config`?
3. If ownership is needed, change to `std::string`; if non-owning view is intentional, document this precondition clearly.

This is a design decision — the pattern itself is not wrong, but the intent must be explicit.
```

---

## Key Calibration Points from Examples

| Aspect | Example 1 (Critical) | Example 2 (Recommended) | Example 3 (Consider) |
|--------|---------------------|------------------------|----------------------|
| **Severity** | [C] Bug risk, unsafe | [R] Clarity improvement | [?] Context-dependent |
| **Tone** | Urgent, safety-focused | Suggestive, improvement-oriented | Neutral, exploratory |
| **Guidance Depth** | Specific questions about ownership flow | Alternative approaches with conditions | Design intent verification |
| **Code Amendment** | None — only questions | None — alternatives suggested | None — decision deferred to user |
| **Assumption Level** | No assumptions — verify everything | Assume loop intent, verify applicability | Acknowledge pattern validity |

## Constraints

### Analysis Scope
- **Skip "good points" analysis** unless user explicitly requests: "Analyze the good part of this code"
- Focus on issues, risks, and improvement opportunities only

### Recommendation Policy
- For **Recommended** severity or any uncertain findings: **defer offering actual code amendments**
- Instead, describe the concern and ask the coder to verify semantics
- Example: "This pattern may have lifetime issues if X happens — please verify the ownership flow"

### Guidance Style
- **Prioritize "request double-check on code workflow"** over direct code fixes
- Guide the coder to examine actual semantics, invariants, and edge cases
- Offer code amendments only when the issue is clear-cut and the fix is unambiguous

### Output Preference
- **Return analysis in the session by default**; do not create report files unless the user explicitly requests one
- If a report file is requested, use the user-specified path; never write to an implicit default location

## Continuous Improvement

When users provide insights about code in response to your analysis, treat it as a skill enhancement opportunity:
- Document the insight in `references/patterns.md` if it reveals a new anti-pattern or edge case
- Update `references/checklist.md` if the insight suggests a new verification item
- Capture the context — real-world codebases often reveal patterns that synthetic examples miss
- Note the resolution — did the guidance lead to a design change, or was the original code justified?

This feedback loop improves the skill's accuracy and relevance for future analyses.

The `references/wuling/` chamber and the reference files are the designated growth area for the learning-from-codebase pass: new real-world patterns, checklist items, and flagship examples belong there.

## Validation Tools Reference

When appropriate, suggest the user verify findings with:

| Tool | Check | Command Example |
|------|-------|-----------------|
| `clang-tidy` | Static analysis | `clang-tidy -checks='cppcoreguidelines-*,modernize-*' file.cpp` |
| `clang-format` | Style consistency | `clang-format -i file.cpp` |
| Compiler warnings | Basic issues | `-Wall -Wextra -Werror -std=c++20` |

Note: This skill does not invoke tools directly — recommend them in guidance when relevant.

## Output Format

```markdown
## File: `src/connection.cpp`

### Line 42 — Critical
**Current:**
```cpp
std::shared_ptr<Buffer> buf = std::make_shared<Buffer>(size);
```

**Rationale:** 
`shared_ptr` for unique ownership. Risk of unnecessary ref-count overhead and unclear ownership semantics.

**Guidance:**
Verify whether this buffer is truly shared across multiple owners or if `unique_ptr` (or stack allocation) would suffice. Check all call sites to confirm ownership requirements.

---

### Line 87 — Recommended
**Current:**
```cpp
for (auto it = vec.begin(); it != vec.end(); ++it) {
```

**Rationale:**
Legacy iterator loop — consider if range-based for or algorithms could clarify intent.

**Guidance:**
Review what operations are performed in the loop body. If simple element-wise processing, range-for may be clearer. If complex logic with early exit, current form may be justified.

```

## File Index

| File | Purpose | Load condition | Status |
|------|---------|----------------|--------|
| `references/cpp.md` | Code + documentation style contract (mandatory) | Read first before generating any output | Complete |
| `references/patterns.md` | Modern C++ anti-pattern catalog (C++11→23) | Per finding category | Complete |
| `references/checklist.md` | Review checklist by C++ version | Review passes | Complete |
| `references/flagship.md` | Production-ready example code | Calibration / examples | Partial |
| `references/checklist-hft.md` | 五灵 HFT checklist | HFT chamber active | Partial |
| `references/wuling/` | 五灵 hidden chamber (index, patterns, checklist, flagship) | Trigger: `五灵应象决` or HFT context | Pass 2 complete (patterns + checklist); flagship pending |
| `interchange/language-style-guide.md` | Optional style sidelane (clang-format complement) | Optional | Sanitized; integration pending |

## Severity Levels (with Priority Annotations)

| Level | Priority | Criteria | Example |
|-------|----------|----------|---------|
| **Critical** | P0 [CRITICAL] | Bug risk, UB, exception-unsafe — never ignore | Raw owning pointers, `new`/`delete` |
| **Recommended** | P1 [HIGH] | Significant clarity/performance gain — should follow | `auto`, range-for, structured bindings |
| **Consider** | P2 [MEDIUM] | Style/consistency, minor modernization — context-dependent | `std::format` vs `printf`, `[[nodiscard]]` |

**Constraint Validation**: For each finding, mentally verify it against the priority level before outputting.

## C++23 Priority Features (Backend/Server)

1. **Modules** (`import` vs `#include`) — compile times
2. **`std::expected`** — error handling without exceptions
3. **`std::print`/`std::format`** — type-safe formatting
4. **`std::ranges` views** — lazy evaluation pipelines
5. **`constexpr` expansion** — compile-time computation
6. **`std::move_only_function`** — type-erased move-only callables
7. **Deducing `this`** — unified member function syntax

Read reference files as needed during analysis.

---

## 五灵应象决密室 / Five Spirits Archive
**Trigger Phrase:** `五灵应象决`

HFT (High-Frequency Trading) and systems optimization archive — a hidden chamber within rt-cppeng skill.

**Design Principles:**
- **Complementary, not replacement**: Does not override general `patterns.md` — works alongside it
- **Context shift**: When triggered, focuses on latency-critical systems (HFT, low-latency infra)
- **Scope**: C++ + Linux kernel + hardware affinity (not limited to C++ language)

**Five Spirits Framework:**
| Spirit | Element | Optimization Domain | Core Techniques |
|:---|:---|:---|:---|
| **木灵·青龙** | 生发 | Memory & Cache | NUMA affinity, memory pools, cache optimization, prefetching, hugepages |
| **火灵·朱雀** | 炎上 | Lock-free & Concurrency | Lock-free programming, Disruptor pattern, atomic operations, SPSC/MPSC queues |
| **土灵·麒麟** | 承载 | Scheduling & Isolation | CPU isolation (isolcpus), real-time scheduling, thread affinity, IRQ affinity |
| **金灵·白虎** | 肃杀 | Kernel & Bypass | PREEMPT_RT, DPDK, RDMA/RoCE, eBPF/XDP, kernel bypass |
| **水灵·玄武** | 润下 | Observability & Profiling | perf, eBPF tracing, flame graphs, RDTSC timing, low-overhead probes |

**Status**: Framework fixed; index in place; pass 1 + pass 2 (atomic_queue/CpuPinning + core/msg_parser) folded into `references/wuling/patterns.md` + `checklist.md`.
- **Quick checklist** → `references/checklist-hft.md` (isolation, lock-free, latency, kernel dimensions)
- **Pending**: flagship examples (`references/wuling/flagship.md`) and kernel-bypass/network-tuning details — designated growth area for the learning-from-codebase pass

---

**Future Evolution — Skill Separation Roadmap**

> The Five Spirits archive is currently hosted inside Roc Thunder. When per-spirit patterns and flagship examples mature, it may become a standalone skill.

**Separation Criteria:**
| Milestone | Description |
|-----------|-------------|
| Mature patterns | Each spirit has a complete patterns.md + flagship.md |
| Broadened scope | Beyond HFT: game engines, telecom core networks, high-frequency data collection |
| Independent trigger | Users can invoke 五灵应象决 directly without going through rt-cppeng |
| Final naming | Standalone name to be decided (`five-spirits` / `wuling` / Chinese name) |

**Current Stance**: Stays inside rt-cppeng; reviewed by maintainers when the criteria are met.
