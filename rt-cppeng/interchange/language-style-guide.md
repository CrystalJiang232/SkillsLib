# 语言风格旁路 / Language Style Sidelane — clang-format Complement

> Secondary-level style reference for C++ output: the conventions that clang-format cannot enforce. Feature-driven only; mechanical formatting (brackets, indentation, whitespace) belongs to clang-format and `references/cpp.md` Part 1.

## Scope

- Covers naming conventions, comment semantics, language preferences, and documentation structure for AI-generated C++ content.
- Complements clang-format; does not restate its rules.
- Optional sidelane: load when styling code output; not part of the mandatory skill load path.

## Naming Conventions

- Classes/structs: PascalCase (`Connection`, `Server`, `Msg`)
- Functions: snake_case public, camelCase private (`send`, `read_header`)
- Variables: abbreviations preferred (`conn` not `connection`, `buf` not `buffer`)
- Member variables: no trailing underscore; use distinct names or a prefix when needed (`config`, `conf`, `cfg` OK; `config_` disallowed)
- Constants: `UPPER_CASE` or `static constexpr` inline

## Comment Conventions

- No inline comments between code lines; use separate explanation blocks before functions when needed.
- Exemption: brief, informative comments for functions, enumeration values, bit fields, or type meaning (helpful for tooling); keep them as short as possible.
- Remove inline comments first when unsure (especially AI-generated ones).

```cpp
// Graceful for queue-draining, abort for immediate shutdown
enum class CloseMode
{
    Graceful,
    Immediate
};
```

```cpp
// INCORRECT: inline comments clutter code flow
int x = 5; // initialize x to 5
if (x > 0) { // check if x is positive
    do_something(); // call the function
}
```

## Language Preferences (C++11→23)

- Error handling: `std::optional` / `std::expected` over throwing exceptions; early-return "validate then proceed".
- Non-owning views: `std::span` for contiguous ranges, `std::string_view` for strings; prefer spans over container const-refs.
- Algorithms: `std::ranges` + `std::views` pipelines; `std::ranges::to` for container generation.
- Concepts: use C++20 `concepts` where applicable; abbreviated function templates with `auto` parameters where possible.
- Template parameters: `class`, not `typename`; prefer constrained abbreviations (`std::unsigned_integral`) and forwarding packs (`class ...Tys`).
- Bindings: `auto` with structured bindings.
- Formatting output: `<format>` and `std::print(ln)`.
- Type aliases: used actively in-class.
- Async: `net::awaitable<void>` coroutines with `co_await` suspension and `co_return` exit.
- Memory: minimal raw pointers; C-style APIs wrapped via `std::unique_ptr` custom deleter or a wrapper class for RAII.

## Documentation Structure

- Pattern entries follow `### Pattern Name [Severity]` with `**Problem:**` / `**Solution:**` sections (see `references/cpp.md` Part 2).
- Problem descriptions: concise, technical English focused on the failure mechanism.
- Solutions: direct imperative ("Use X", "Replace with Y"); include corrected code when non-obvious.
- Prefer explicit comparisons ("Bad: X / Better: Y").

## Consistency Checklist

- [ ] Naming follows the conventions above (clang-format cannot check this)
- [ ] No inline comments between code lines
- [ ] Modern C++ preferences applied (spans, ranges, expected/optional, print)
- [ ] Pattern format matches `references/cpp.md` Part 2
- [ ] Language is concise technical English; no persona or decorative prose in operational content

*Sidelane status: kept in place for now; integration into the skill flow is pending the learning-from-codebase overhaul.*
