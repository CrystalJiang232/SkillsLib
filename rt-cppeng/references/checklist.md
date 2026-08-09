# C++ Code Review Checklist

Quick-scan checklist organized by C++ version progression.

---

## C++98/03 (Legacy Baseline)

### Buffer Handling
- [ ] No raw `new`/`delete` for ownership [C]
- [ ] No raw pointer + size pairs [R]
- [ ] No container-specific const-refs when generic views suffice [R]

---

## C++11

### Ownership (Smart Pointers)
- [ ] `unique_ptr` for exclusive ownership [C] — See patterns: "Raw new/delete for memory management"
- [ ] `shared_ptr` only when ownership sharing required [R] — See patterns: "Cyclic references with shared_ptr"
- [ ] `weak_ptr` to break cycles / cache observers [R] — See patterns: "Cyclic references with shared_ptr [C]"
- [ ] `make_shared` over raw `new` [R] — See patterns: "Multiple explicit resource allocations in one expression [C]"
- [ ] No `shared_ptr` aliasing without understanding semantics [?] — See patterns: "shared_ptr aliasing constructor misuse [R]"
- [ ] Custom deleters for non-default cleanup (C APIs) [R] — See patterns: "Manual resource acquire/release without RAII [C]"
- [ ] `unique_ptr<T[]>` for array ownership [C] — See patterns: "Raw new/delete for memory management [C]" (array vs non-array mismatch)
- [ ] `enable_shared_from_this` for async callbacks [C] — See patterns: "shared_ptr without enable_shared_from_this in async callbacks [C]"
- [ ] Use `shared_from_this()`, never `shared_ptr<T>(this)` [C] — See patterns: "shared_ptr without enable_shared_from_this in async callbacks [C]"
- [ ] `get()` for non-owning observation only [C] — See patterns: "Misuse of smart pointer's get() and release() method"
- [ ] Avoid `release()`; prefer move semantics for ownership transfer [R] — See patterns: "Misuse of smart pointer's get() and release() method"

### RAII and Resource Management
- [ ] Encapsulate resources in RAII classes [C] — See patterns: "Manual resource acquire/release without RAII [C]"
- [ ] Destructor releases all acquired resources [C] — See patterns: "Missing destructor for resource-owning class [C]"
- [ ] Follow Rule of Three/Five/Zero [C] — See patterns: "Missing destructor for resource-owning class [C]"
- [ ] No `malloc`/`free` in C++ code [C] — See patterns: "malloc/free mixed with C++ allocation [C]"

### Move Operations
- [ ] Proper move ctor/`operator=` semantics (not copy) [C]
- [ ] `noexcept` on user-defined move operations [R]
- [ ] Manual implementation for raw resource managers [C]
- [ ] Use `= default` **when and only when** not **directly** managing raw resources [C]
- [ ] Use `std::forward` only on forwarding references (template parameters deduced as rvalue references); do not apply it to ordinary parameters [?]

### Utility Functions
- [ ] Prefer `std::invoke` in template/metaprogramming contexts (generic or type-erased callables); not a general rule for direct calls [?]
- [ ] Prefer `std::addressof` over `operator&()` for getting address

### Concurrency (Memory Order)
- [ ] Default `seq_cst` ordering deserves manual consideration on hot paths; prefer weaker orders only where semantics are proven [?] — See patterns: "Atomic default seq_cst memory order [R]"
- [ ] Establish proper happens-before with `acquire`/`release` pairs [C] — See patterns: "Broken happens-before with atomic memory orders [C]"
- [ ] Use `relaxed` only when cross-thread visibility is not required [?]
- [ ] Correct memory order for operation type: `acquire` for read, `release` for write [C] — See patterns: "Broken happens-before with atomic memory orders [C]"
- [ ] Minimize thread-local data; prefer explicit context passing [R] — See patterns: "Thread-local storage abuse [?]"

### Mutex and Locking
- [ ] Use `lock_guard` for single mutex RAII [C] — See patterns: "Mutex without RAII lock guards [C]"
- [ ] Never lock multiple mutexes in different orders [C] — See patterns: "Not using scoped_lock for multiple mutexes [R]"
- [ ] `condition_variable` with predicate (spurious wakeup protection) [C] — See patterns: "Condition variable without predicate [C]"
- [ ] `atomic` for simple counters/flags [R] — See patterns: "Data race on shared mutable data [C]"
- [ ] `volatile` is NOT for synchronization [C] — See patterns: "volatile for synchronization [C]"

### Macro Migration
- [ ] Replace `NULL` with `nullptr` for pointers [R]
- [ ] Migrate macro constants to `constexpr` [R] — See patterns: "Macro constant/function when constexpr would suffice [R]"
- [ ] Migrate macro functions to `constexpr` functions or modern alternatives [R] — See patterns: "Macro constant/function when constexpr would suffice [R]"

### Resource Management
- [ ] Use `unique_ptr` / `shared_ptr` to express ownership [C]
- [ ] Prefer `unique_ptr` over `shared_ptr` unless sharing is needed [R]
- [ ] Avoid explicit `new` / `delete` calls [C]

---

## C++14

### Lambda Capture
- [ ] Move capture with init-capture for heavy objects [R]

### Exception Specifiers
- [ ] No `throw(xxx)` exception specifiers (removed in C++17) [C] — See patterns: "throw exception specifier"
- [ ] Replace `throw()` with `noexcept` [R] — See patterns: "throw exception specifier"

### Smart Pointer Factory
- [ ] `make_unique` over raw `new` [R] — See patterns: "Multiple explicit resource allocations in one expression [C]"

---

## C++17

### Return Values
- [ ] No `std::move` on return values (prevents NRVO) [R] — See patterns: "Moving local objects on return"

### Error Handling
- [ ] Catch exceptions by const-reference: `catch(const Ex& e)` [R] — See patterns: "Catch and re-throw with unnecessary copy/move"
- [ ] Re-throw with bare `throw;`, no `std::move` or wrapping [R] — See patterns: "Catch and re-throw with unnecessary copy/move"
- [ ] `std::optional<T>` for "may not return value" [R] — See patterns: "std::optional unchecked dereference [C]"
- [ ] Check `has_value()` before `optional` dereference [C] — See patterns: "std::optional unchecked dereference [C]"
- [ ] Use `value_or()` for defaults with `optional` [R] — See patterns: "std::optional unchecked dereference [C]"
- [ ] `[[nodiscard]]` on error-returning functions [R] — See patterns: "Not using [[nodiscard]] on error-returning functions [R]"
- [ ] Pick one error-handling mechanism per component (exceptions, error codes, or tagged union types); never mix them silently [C] — See patterns: "Unnecessary exception workflow overhead"
- [ ] Confirm semantics before marking functions `noexcept` with expected/optional error handling; a function is `noexcept` only if it cannot throw. Prefer one error path (exceptions OR expected/optional) for unified semantics — avoid mixing both paths [?] — See patterns: "Unnecessary exception workflow overhead"

### Interface Design
- [ ] Pass small/cheap types by value; pass large types by const reference (and by value + move for sink parameters) [R]
- [ ] Use non-const reference for in-out parameters [R]
- [ ] Prefer simple and conventional parameter passing patterns [R]

### Strings
- [ ] `std::string_view` for read-only string parameters [R] — See patterns: "string_view lifetime dependency [C]"
- [ ] Never store `string_view` as class member [C] — See patterns: "string_view lifetime dependency [C]"
- [ ] Check `string_view::data()` null-termination before C API [C] — See patterns: "string_view treated as null-terminated [C]"
- [ ] Pass `string_view` by value (cheap: two pointers) [R] — See patterns: "string_view lifetime dependency [C]"
- [ ] `std::string` for owned mutable strings [C] — See patterns: "string_view lifetime dependency [C]"
- [ ] `std::string` by value for map insert keys in concurrent contexts [?] — See patterns: "string_view for map keys in multi-threaded code [?]"

### Concurrency
- [ ] `std::scoped_lock` for multiple mutexes (deadlock-free) [C] — See patterns: "Not using scoped_lock for multiple mutexes [R]"

### Templates
- [ ] `if constexpr` over tag dispatch [R] — See patterns: "if constexpr not used for compile-time branching [?]"

---

## C++20 (Concepts & Ranges)

### Buffer Views
- [ ] `std::span` for non-owning contiguous ranges [R]

### Sum Types
- [ ] Replace `union` with `std::variant` for type-safe sum types [R] — See patterns: "union"
- [ ] Eliminate `void*` sum-type patterns [R] — See patterns: "void* for sum-types"

### Variadic Modernization
- [ ] Replace C-style variadic functions (`...`) with variadic templates or `initializer_list` [R] — See patterns: "Variadic function"

### Type Safety
- [ ] Avoid lossy (narrowing) arithmetic conversions [C]
- [ ] Use named casts (`static_cast`, etc.) if casting is necessary [R]

### Strings
- [ ] `contains()` / `starts_with()` / `ends_with()` [R] — See patterns: "find loops instead of contains/starts_with [?]"
- [ ] `std::format` over `sprintf` / `<iostream>` [R] — See patterns: "Not using std::format over <iostream> [R]"

### Concurrency
- [ ] `std::jthread` over `std::thread` (auto-join, stop_token) [R] — See patterns: "Thread join without exception safety [C]"
- [ ] `std::async` with explicit launch policy [?] — See patterns: "std::async without explicit launch policy [?]"

### Templates
- [ ] `concept` constraints over `enable_if` / SFINAE [R] — See patterns: "Using SFINAE instead of concepts [R]"
- [ ] `requires` clauses for complex constraints [R] — See patterns: "Using SFINAE instead of concepts [R]"
- [ ] Use standard library concepts (`std::integral`, `std::copyable`, etc.) [R] — See patterns: "Not using standard library concepts [R]"
- [ ] Constrain to semantic requirements, not implementation details [?] — See patterns: "Over-constraining templates [?]"
- [ ] Use `typename`/`template` disambiguators only where the target C++ version requires them; requirements vary by standard (C++20 relaxed several `typename` positions) — verify per version [?] — See patterns: "Using SFINAE instead of concepts [R]"

---

## C++23

### I/O Modernization
- [ ] Replace `cout` or `printf`-based output with `std::print[ln]` [R] — See patterns: "New era's I/O: std::print[ln]"
- [ ] Provide `std::formatter` specializations for custom types [R] — See patterns: "New era's I/O: std::print[ln]"

### Deducing This
- [ ] Consider deducing-this templates when cvref overloads duplicate logic (lambdas, CRTP, recursive calls); not a blanket replacement [R] — See patterns: "Deducing this"
- [ ] Apply perfect forwarding within deducing-this methods [R] — See patterns: "Deducing this"

### Error Handling (Expected)
- [ ] Use `std::expected` for error-code-with-message scenarios [R] — See patterns: "Not using std::expected monadic operations (C++23) [?]"
- [ ] Confirm semantics before marking functions `noexcept` with expected/optional error handling; a function is `noexcept` only if it cannot throw. Prefer one error path (exceptions OR expected/optional) for unified semantics — avoid mixing both paths [?] — See patterns: "Unnecessary exception workflow overhead"
- [ ] Use `expected` monadic ops (`and_then`, `transform`, `or_else`) [?] — See patterns: "Not using std::expected monadic operations (C++23) [?]"

### RAII
- [ ] Use `std::scope_exit` for ad-hoc cleanup (instead of goto-exit pattern); it is an **experimental** facility living in `std::experimental` (`<experimental/scope>`), not in namespace `std` — verify availability for your toolchain [R] — See patterns: "goto exit cleanup pattern [R]"

### Strings
- [ ] Reserve capacity when size known [R] — See patterns: "Repeated string concatenation in loops [R]"
- [ ] `substr` via `string_view` for zero-copy observation [R] — See patterns: "substr returning temporary copies [R]"
- [ ] Avoid `char*` ambiguity (use `zstring`/`string_view`) [R] — See patterns: "char* ambiguity between single character and C-string [R]"



---

## Severity Markers

| Marker | Meaning | Example |
|--------|---------|---------|
| [C] | Critical | Memory safety, undefined behavior |
| [R] | Recommended | Performance, maintainability |
| [?] | Question | Design decision, context-dependent |

---

*Checklist complete — covers C++98/03 through C++23 with severity-marked items [C]/[R]/[?].*
