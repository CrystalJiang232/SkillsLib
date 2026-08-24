# C++ Patterns: Anti-Patterns and Solutions

Error patterns, analysis, and brief solutions for Modern C++ code review.

---

## Fixed-Size Instrument Codes for Concurrent Hot Paths

### String keys in concurrent hot paths [R]
**Problem:** String keys (`std::string`/`std::string_view`) in shared maps cost allocation, hashing, and lifetime discipline; a `string_view` key dangles if the source mutates, and a stored `std::string` key allocates on the hot path.

**Real-world insight:** Production trading systems pack instrument codes and composite identifiers into fixed-size integers: text is decoded once at startup into a compact ID, and hot-path lookups use the integer by value — no allocation, no lifetime coupling, no per-access hashing of variable-length text.

```cpp
// Decode once at the boundary: "IC2409" -> packed integer id (fixed-size, by value).
constexpr uint32_t pack_instrument_code(std::string_view code) noexcept
{
    uint32_t id = 0;
    for (char c : code)
        id = id * 37 + static_cast<uint32_t>(c); // illustrative fixed-width encoding
    return id;
}

// Composite order id: (orderRef << k) | strategyId — extract with a mask, no division.
inline int64_t pack_order_ref(int32_t ref, int strategy_id) noexcept
{
    return (static_cast<int64_t>(ref) << 8) | strategy_id;
}
inline int get_strategy_id(int64_t ref_with_strategy) noexcept
{
    return static_cast<int>(ref_with_strategy & 0xFF);
}
```

**When to keep `string_view`:**
- Read-only lookups against an immutable, externally owned buffer (e.g., config text parsed once)
- Single-threaded contexts where lifetime is trivially controlled
- I/O boundaries where the text must be parsed anyway

**When to switch to fixed-size IDs:**
- The key crosses thread or process boundaries on a hot path
- The key is looked up repeatedly (per order, per tick) and can be decoded once
- The codebase already has a canonical ID space (instruments, strategies, users)

---

## Buffer Handling

### Length-Prefixed Framing [R]
**Problem:** Raw `(ptr, len)` messages carry no framing metadata: the parser cannot locate the next message, tolerate version drift, or validate bounds before decoding.
```cpp
void process(const std::byte* data, std::size_t len);
```
**Solution:** Prefix every frame with a header carrying type and total length; decode through a bounded, length-checked walk and expose the payload as `std::span`:

```cpp
struct FrameHeader { std::uint32_t type; std::uint32_t length; };

std::optional<std::span<const std::byte>> next_frame(
    std::span<const std::byte> buffer, std::size_t& pos) noexcept
{
    if (buffer.size() - pos < sizeof(FrameHeader))
        return std::nullopt;
    const auto* hdr = reinterpret_cast<const FrameHeader*>(buffer.data() + pos);
    if (hdr->length < sizeof(FrameHeader) || hdr->length > buffer.size() - pos)
        return std::nullopt; // bounded: reject truncated or oversized frames
    std::span<const std::byte> frame(buffer.data() + pos, hdr->length);
    pos += hdr->length;
    return frame;
}
```

Length-checked decoding — copying at most `min(available, expected)` bytes and verifying sizes match — prevents truncated-input overreads and makes framing version-tolerant.

### Container-Specific References [R]
**Problem:** Tied to specific container, cannot accept arrays or strings
```cpp
void parse(const std::vector<std::byte>& data);
```
**Solution:** Use `std::span<const Ty>` for read-only views

### C-style Array References [R]
**Problem:** Fixed size only, awkward syntax
```cpp
void handle(const std::byte (&arr)[256]);
```
**Solution:** Use `std::span<Ty, N>` with const as needed

### Pointer Arithmetic for Element Access [C]
**Problem:** Using `ptr + i` or `ptr[i]` without guaranteed bounds. Undefined behavior on out-of-bounds access; manual index tracking is error-prone.
```cpp
void process(const int* data, size_t n)
{
    for (size_t i = 0; i <= n; ++i)
    {  // Off-by-one: UB when i == n
        sum += data[i];
    }
}
```
**Solution:** Prefer range-based for loops. For index-fetching, use `std::views::enumerate` (C++20). For parallel iteration, use `std::views::zip`.
```cpp
// Good: range-based for (no indices needed)
void process(std::span<const int> data)
{
    for (auto val : data)
    {
        sum += val;
    }
}

// Good: enumerate for index + value (C++20)
void process_with_index(std::span<const int> data)
{
    for (auto [idx, val] : data | std::views::enumerate)
    {
        results[idx] = val * 2;
    }
}

// Good: zip for parallel iteration (C++20)
void merge(std::span<const int> a, std::span<const int> b, std::span<int> out)
{
    for (auto [x, y, z] : std::views::zip(a, b, out))
    {
        z = x + y;
    }
}
```

### Pointer Arithmetic on string_view::data() [C]
**Problem:** `string_view` is non-owning and not guaranteed null-terminated. Pointer arithmetic past `size()` is UB; assuming null-termination causes buffer over-read.
```cpp
void parse(std::string_view sv)
{
    const char* p = sv.data();
    while (*p != '\0')  // Dangerous: may read past sv.size()
    {
        // ...
        ++p;
    }
}
```
**Solution:** Never treat `string_view::data()` as null-terminated. Use iterators, explicit bounds, or range algorithms.
```cpp
// Good: iterate by index with explicit bound
void parse(std::string_view sv)
{
    for (size_t i = 0; i < sv.size(); ++i)
    {
        process(sv[i]);
    }
}

// Good: use iterators (end is authoritative)
void parse(std::string_view sv)
{
    for (auto it = sv.begin(); it != sv.end(); ++it)
    {
        process(*it);
    }
}

// Good: algorithms with explicit range
void parse(std::string_view sv)
{
    auto comma = std::find(sv.begin(), sv.end(), ',');
}
```

### Manual Pointer Loops vs Algorithms [R]
**Problem:** Raw pointer loops obscure intent, prevent optimizations, and invite off-by-one errors.
```cpp
// Verbose, error-prone
for (const int* p = arr; p < arr + n; ++p)
{
    if (*p > 0)
    {
        result.push_back(*p * 2);
    }
}
```
**Solution:** Use `<algorithm>` or ranges. Clearer intent, optimizable, bounds-safe.
```cpp
// Good: C++20 ranges with filter + transform
std::ranges::copy(
    arr | std::views::filter([](int x) { return x > 0; })
        | std::views::transform([](int x) { return x * 2; }),
    std::back_inserter(result));

// Good: if materialization needed, use ranges::to (C++23)
auto result = arr
    | std::views::filter([](int x) { return x > 0; })
    | std::views::transform([](int x) { return x * 2; })
    | std::ranges::to<std::vector>();
```

---

## Move Semantics

### Wrong Semantics in Move Operations [C]
**Problem:** Implements copy semantics in move constructor
```cpp
SomeClass::SomeClass(SomeClass&& l)
{
    this->data = std::copy_n(l.data.data(), l.size);
    this->size = l.size;
}
```
**Solution:** Transfer ownership properly, prefer using `= default` if not directly managing resources(avoid handcrafting)

### Missing `noexcept` on Move Operations [R]
**Problem:** STL containers prefer copy over non-noexcept move (rollback safety requirements)
```cpp
SomeClass::SomeClass(SomeClass&& l);  // NOT noexcept by default
```
**Solution:** Add `noexcept` specifier to move ctor and move assignment

### Default Move for Raw Resource Managers [C]
**Problem:** Default move does not transfer ownership for raw pointers
```cpp
class SomeClass
{
    int* data; // Heap allocated
};
SomeClass::SomeClass(SomeClass&&) = default; // Double-free risk
```
**Solution:** Implement manual resource transfer; reset moved object to default state if possible

### Moving local objects on `return`
**Problem:** Applies `std::move` on `return` local variables, prevents NRVO
```cpp
SomeClass func()
{
    SomeClass sc;
    // ...
    return std::move(sc);
    // `sc` is automatically treated as xvalue on `return`, no need to *std::move* it
    // Even if this function returns `SomeClass&&` it's OK to `return sc` (valid binding)
    // explicitly adding `std::move` prevents compiler NRVO
}
```
**Solution:** Remove `std::move` wrapper on `return` local variables

### Disregards `std::forward` when forwarding arguments
**Problem:** Forgets `std::forward` wrapper for preserving reference type information upon forwarding arguments
```cpp
void f1(int& x); // 1
void f1(int&& x); // 2

void f2(int&& a)
{
    f1(a);  // Calls #1, named rvalue references(*any* named variables) are lvalues
    f1(std::forward<int>(a)); // Calls #2 correctly
}

// METAPROGRAMMING EXAMPLE - MORE REALISTIC(universal reference applied)
template<class ...Tys>
void f3(Tys&&... args)
{
    return std::format("{0} {1} {2}", std::forward<Tys>(args)...);
}
```
**Solution:** Use `std::forward<Ty>(arg)` to forward arguments

---

## Modern Utility Functions/Syntax

### Hardcoded type-specific function calling syntax
**Problem:** Uses calling syntax specific for one particular callable(lambda/mem-func/func-ptr), sacrifies readability and maintainability, not metaprogramming-compactible
```cpp
template<class Fn, class ...Args>
void call(Fn&& func, Args&&... args)
{
    func(std::forward<Args>(args)...);  // Won't compile for member functions or pointer-to-functions(strictly)
}
```
**Solution:** Uses `std::invoke` + Perfect forwarding to adapt to all possible calling syntax

### Hardcoded `operator&` when obtaining variable address
**Problem:** Using `operator&()` for variable's address fetching, disregards cases where `operator&` overloaded by variables; possibly fetching address of *xvalues* ; lacks code clarity and readability
```cpp
int a;
int* x = &std::move(a); // xvalue issue, rare but possible in metaprogramming

struct A{int operator&();} a;
auto y = &a; // Uncommon, yet cannot handle overloaded `operator&` properly

//...
some_apis(&ptr, &xx, var, &addrofvar); // Lacks clarity - '&' mixed into variables
```
**Solution:** Replace all occurances of `operator&()` (for address-fetching) with `std::addressof`

### `void`-casting for ignoring values
**Problem:** Usage of `void`-casting has unclear semantics + readability sacrifies
```cpp
(void)scanf("%*c");  // Why cast it to `void` - only for ignoring it?
```
**Solution:** Use `std::ignore` and assignment for expressing *ignore* semantic

---

## New era's I/O: `std::print[ln]`
### `<ostream>`/`<cstdio>`-based output
**Problem**: `<cstdio>` based output functions(`printf`, `putc`, etc.) has no type safety and is not compactible with modern C++. `<ostream>` are less efficient and lacks readability when comes to compound/format controlling.
```cpp
SomeClass c;

c.print(); print_someclass(c); // Incomplete customization: relies heavily on helper functions

double d = some_computation();
std::cout << "Value: (" << std::setw(10) << std::setprecision(5) << c << ")" << std::endl; // Hard-to-read: what is the ultimate output?
```

**Solution**:
- For format control output of trivial types, or concerning output with context messages, migrate to `std::print[ln]`
- For custom types that requires formatting, provide specialization of `std::formatter`
- Other custom types that calls for uniformed output, defer specializing `std::formatter`, but use `std::print[ln]` in output wrappers

## Deducing `this`
### Redundant overloads for *cvref*-differentiated member functions
**Problem:**
```cpp
class A
{
private:
    int* ptr;
    //...

public:
    // Only two overloads here with simple returning, yet logic duplicates
    // Inflates rapidly as ref-qualifier and function logic joins
    int* data() { return ptr; }
    const int* data() const { return ptr; }
};
```
**Solution:** For such redundant overload member function, reduce to `template` + explicit `this` + perfect forwarding combination

## Macros
### `NULL` macro
**Problem:** `NULL` acts as C Legacy; defined as `(void*)0`, it guarantees no type safety and creates ambiguity in overload resolution, confusion in debugging, etc.
```cpp

```
**Solution:** Eliminate `NULL` usages. Replace pointer occurances with `nullptr`, literal `0` otherwise.
### Hardcoded constants
**Problem:** Macro-defined constants have behavior that are *not* intuitively observable, thus they are subject to errors and difficult to debug. Also their computation are done runtime and perform inferior to `constexpr` counterparts.
```cpp
#define SZ sizeof(int)
// What is the type of `SZ`? Not clear when mixed up
// SZ might got undefined/redefined in other headers
// Also `SZ` won't appear in program/debug workflow(it's not a variable), difficult to track

// Modern syntax
constexpr size_t SZ = sizeof(int);

```
**Solution:** Migrate to `constexpr` constants, which do computation compile-time, eliminate UBs(`constexpr` UB are compile errors) and boost performance & readability.

### Macro-defined functions
**Problem:** Functions defined by macros are notoriously fragile. They require near-infinite brackets in order to, just 'function', sacrificing readability, maintainability and are extremely difficult debugging. 'Inline' nature also results in code inflation and degraded performance.
```cpp
#define ADD(x,x) x+x  // Classic example of 'counter-intuitive'
#define ADD2(x,x) (x+x) // Still buggy: What if x contains ops whose precedence are inferior, i.e. `a << 1`?
#define ADD3(x,x) ((x) + (x)) // Grudgingly work, disregarding type safety issues, etc. But why not the one as follows?

// Make it a template to be generic
template<class Ty>
constexpr Ty add(Ty x, Ty y)
{
    return x + y;
}
```

**Solution:** Migrate to `constexpr` functions if possible(constraints reliving as C++ standards update). Consider implementation alternatives for readability otherwise(i.e. lambdas/CPOs, coroutines). Integrate with `if constexpr`, `consteval` and `if consteval` for compile-time instructions.

## Unions and sum-types

### `union`
**Problem:** `union` is not type-safe(doesn't carry type information nor does any type checks, just a convenient 'reinterpret-caster') and disregards Modern C++ class alignment/construction/destruction requirements.
```cpp

```
**Solution:** Migrate to `std::variant`. Type-safe(`.index()` type info + boundary check when obtaining values) while maintaining spatial efficiency.

### `void*` for sum-types
**Problem:** `void*` is not type-safe, erases type information when receiving parameter, no checks for correct interpretation(relies on fragile `reinterpret_cast`).
```cpp

```
**Solution:** Replace all `void*` occurances with `std::variant`(preferred for deterministic, finite types) or `std::any`(identical semantics with what one would expect `void` to have)

## Variadic

### Variadic function
**Problem:** Variadic functions using `...` is still a C-Style legacy that can't relay C++ types reliably(classes, references, etc.). Also with the absence of boundary check it can't be easier to trigger some out-of-bound error.
```

```
**Solution:** Eliminate variadic function parameter list by:
- Prioritize using argument type `initializer_list` or `vector` of some sum-types, or apply function overloads for distinguish
- Migrate to Modern variadic functions(`template<class ...Tys> void func(Tys&&... args)`)

## Error handling

### `throw` exception specifier
**Problem:** `throw` as a exception specifier(except for `throw()`) has been deprecated(since C++11)/removed(since C++17); latter `throw()` only serves as compactability layer(behaves equivalent to `noexcept(true)`)
```cpp
void foo() throw(int) {} // Deprecated since C++11, Removed since C++17
void fun() throw() {} // Not encouraged
void fun2() noexcept {} //Modern syntax
```
**Solution:**
- Remove all occurances of `throw(xxx)`(doesn't compile since C++17)
- Replace all `throw()` specifier with `noexcept`(or `noexcept(true)`)

### Catch and re-throw with unnecessary copy/move
**Problem:** Incorrect type declaration in `catch` statement resulting in redundant copy/move operation of exception object
```cpp
try
{
    foo(); // Say that `foo()` throws an `std::exception e0`
}
// catch(std::exception e) // BAD: Redundant copy initialization from `e0`
catch(const std::exception& e) // GOOD: No redundant copy occur
{
    throw e; // Correct: Re-throw directly without any wrappers(DO NOT add `std::move` or anything that prevents NRVO)
}
```
**Solution:** For catch statements, ensure using c-refs of exception type; re-throw without any wrappers

### Unnecessary exception workflow overhead
**Problem:**
```cpp
// Conventional C++
// Reasonable pattern, but is such small error worthy of exception flow overhead?
int foo(std::string_view sv)
{
    int x = 0;
    if(auto [ec, ptr] = std::from_chars(sv.data(), sv.data() + sv.size(), x); ec != std::errc{})
    {
        throw std::exception("Invalid numeric string!");
    }
    return x;
}

// Modern patterns, much more efficient
// noexcept -> compiler optimizes further
// optional -> cannot 'disregard' absence-of-values, checkable, etc.
std::optional<int> foo(std::string_view sv)
{
    int x = 0;
    if(auto [ec, ptr] = std::from_chars(sv.data(), sv.data() + sv.size(), x); ec != std::errc{})
    {
        return std::nullopt;
    }
    return x;
}

// If requiring error message passing(better pattern, C++23):
std::expected<int, std::string> foo(std::string_view sv)
{
    int x = 0;
    if(auto [ec, ptr] = std::from_chars(sv.data(), sv.data() + sv.size(), x); ec != std::errc{})
    {
        return std::format("foo() parse string error: invalid character at position {}",ptr - sv.data());
    }
    return x;
}
```


**Solution:**
- Recommend that, for simple value-or-error workflow, replace exceptions with `std::optional` or `std::expected`(if exception string varies and matters) as return value; if pursuing for efficiency/C-compactability only, use comments and attributes like `[[nodiscard("reason")]]` properly. Ultimate goal is to make functions `noexcept` as possible(no exceptions escape, enabling compiler optimization)

### Not using `[[nodiscard]]` on error-returning functions [R]
**Problem:** Functions returning error codes or `std::optional`/`std::expected` can have their return values silently ignored, leading to unhandled errors and difficult-to-debug failures.
```cpp
// Bad: error return ignored
std::optional<int> parse_int(std::string_view sv);

void process()
{
    parse_int("abc");  // Silent ignore: error not handled
    // ... continues with undefined behavior
}

// Bad: error code ignored
ErrorCode open_file(const char* path);

void process()
{
    open_file("/tmp/data.txt");  // Silent ignore
    // ... assumes file opened successfully
}
```
**Solution:** Mark functions with `[[nodiscard]]` or `[[nodiscard("reason")]]` to enforce handling of return values.
```cpp
// Good: forces caller to handle error
[[nodiscard("Error return value must be checked")]]
std::optional<int> parse_int(std::string_view sv);

void process()
{
    if (auto val = parse_int("abc"); val.has_value())
    {
        // ... use val
    }
    else
    {
        // handle error
    }
}

// Good: C++23 attributes with message
[[nodiscard("File handle must be verified before use")]]
std::expected<FileHandle, Error> open_file(const char* path);
```

### `std::optional` unchecked dereference [C]
**Problem:** Dereferencing `std::optional` with `operator*()` or `value()` without checking if value exists. `operator*()` skips validity check (UB if empty); `value()` throws if empty (exception overhead, may not be caught).
```cpp
std::optional<int> maybe_value = compute();

// Bad: unchecked dereference
int x = *maybe_value;           // UB if maybe_value is empty
int y = maybe_value.value();    // Throws std::bad_optional_access if empty

// Bad: assuming value after function call
auto result = fetch_data();
process(*result);               // UB if fetch_data() returns nullopt
```
**Solution:** Always check `has_value()` before dereferencing, or use `value_or()` with default, or `if` with initializer.
```cpp
std::optional<int> maybe_value = compute();

// Good: explicit check
if (maybe_value.has_value())
{
    int x = *maybe_value;       // Safe: checked first
}

// Good: if with initializer (C++17)
if (auto val = compute(); val.has_value())
{
    process(*val);              // Safe within scope
}

// Good: default value
int x = maybe_value.value_or(0);  // Safe: uses 0 if empty

// Good: early return pattern
auto result = fetch_data();
if (!result.has_value())
{
    return Error::NoData;
}
process(*result);               // Safe: checked above
```

### Not using `std::expected` monadic operations (C++23) [?]
**Problem:** Manual error checking and propagation with `std::expected` instead of using monadic operations `and_then`, `or_else`, `transform`. Verbose code obscures the success-path logic.
```cpp
std::expected<int, Error> parse_and_compute(std::string_view sv);

// Bad: manual error propagation
std::expected<int, Error> process(std::string_view sv)
{
    auto result = parse_and_compute(sv);
    if (!result.has_value())
    {
        return std::unexpected(result.error());  // Manual propagation
    }
    
    auto val = *result;
    if (val < 0)
    {
        return std::unexpected(Error::Negative);
    }
    
    return val * 2;
}
```
**Solution:** Use C++23 monadic operations to chain operations and separate error handling from success logic.
```cpp
// Good: monadic chaining (C++23)
std::expected<int, Error> process(std::string_view sv)
{
    return parse_and_compute(sv)
        .and_then([](int val) -> std::expected<int, Error>
        {
            if (val < 0)
            {
                return std::unexpected(Error::Negative);
            }
            return val;
        })
        .transform([](int val) { return val * 2; });
}

// Good: or_else for error transformation
std::expected<Data, Error> fetch_and_validate(int id)
{
    return fetch_data(id)
        .or_else([](Error e) -> std::expected<Data, Error>
        {
            log_error(e);
            return std::unexpected(e);
        })
        .and_then(validate_data);
}
```
**Benefits:** Clear separation of success/error paths, composable operations, no manual error propagation boilerplate.

---

## Smart Pointers and Ownership

### Misuse of smart pointer's `get()` and `release()` method

**Problem:** `get()` and `release()` method of smart pointers are often misused. `get()` does not releases ownership while `release()` does, implying rejecting/explicit transfering ownership of pointer(and its underlyinig source).
```cpp

void c_api_use(int* ptr)
{
    int x = *ptr;
    // ...
}

void c_api_free(int* ptr)
{
    // ...
    delete ptr;
}

std::unique_ptr<int> p(5);

c_api_use(p.release()); // Error: memory leak occur(`c_api_use` does not release the resource)
c_api_free(p.get()); // Error: `c_api_free` frees the memory; upon invocation of `p`'s dtor, double-free
```
**Solution:**
- Ensure that `get()` is only used for C-compact API compactability, with **no ownership transfer**; *always* double-verify the semantics of the API invoked(non-owning, non-releasing, precarious writing)
- Discourage the use of `release()`. Use whenever *absolutely necessary* for ownership transfer. Ensure that the receiptant deals with the pointer properly(i.e. another RAII-designed class that manages it, or a C-compact API releasing the resource dereferenced by the pointer)
- For ownership transfer, recommend using move semantics instead("less raw pointers as possible" paradigm)

### Cyclic references with `shared_ptr` [C]

**Problem:** Two objects holding `shared_ptr` to each other. Reference count never reaches zero. Memory leak as a consequence of circular ownership.
```cpp
struct Node
{
    std::shared_ptr<Node> next;
    // ...
};

auto a = std::make_shared<Node>();
auto b = std::make_shared<Node>();
a->next = b;
b->next = a; // Cycle created. Leak on scope exit.
// Both ref counts = 2, then 1. Never 0. Never destroyed.
```
**Solution:** Break cycles with `std::weak_ptr`. Non-owning observer. Check `expired()` or `lock()` before use.
```cpp
struct Node
{
    std::weak_ptr<Node> next; // Breaks the cycle
    // ...
};

auto a = std::make_shared<Node>();
auto b = std::make_shared<Node>();
a->next = b;
b->next = a; // Safe: weak_ptr doesn't increment use count
// On scope exit: both ref counts reach 0. Proper destruction.
```

### `shared_ptr` without `enable_shared_from_this` in async callbacks [C]

**Problem:** Returning `shared_ptr` to `this` from within a member function. Dangerous. No guarantee the object is owned by a `shared_ptr`. Stack allocated objects cause undefined behavior. Double-free or use-after-free.
```cpp
struct Worker
{
    void start()
    {
        // Dangerous: what guarantees `this` is managed by shared_ptr?
        std::async([this] { do_work(); });
    }

    void do_work() { /* ... */ }
};

Worker w; // Stack allocated
w.start(); // Async task holds raw this. w destroyed? Use-after-free.
```
**Solution:** Inherit from `std::enable_shared_from_this`. Use `shared_from_this()` to obtain a `shared_ptr` sharing ownership with existing `shared_ptr`s managing the object.
```cpp
struct Worker : std::enable_shared_from_this<Worker>
{
    void start()
    {
        // Safe: shared_from_this() increments ref count
        std::async([self = shared_from_this()] { self->do_work(); });
    }

    void do_work() { /* ... */ }
};

// Must be heap allocated and owned by shared_ptr
auto w = std::make_shared<Worker>();
w->start(); // Async task holds shared_ptr. Ref count = 2. Safe even if w goes out of scope.
```
**Note:** `shared_from_this()` throws `std::bad_weak_ptr` if called on an object not owned by any `shared_ptr`. Ensure proper construction via `make_shared`.

### `shared_ptr` aliasing constructor misuse [R]

**Problem:** Using `shared_ptr<T>` to point to a member of an object managed by `shared_ptr<U>`. Separate control blocks. Risk of double delete. Member may outlive its parent. Undefined behavior when parent destroyed.
```cpp
struct Buffer
{
    std::vector<std::byte> data;
    std::byte* raw_ptr; // Points into data
};

auto buf = std::make_shared<Buffer>();
// Dangerous: separate allocation for control block
std::shared_ptr<std::byte> alias(buf->raw_ptr); // Wrong. Custom deleter needed?
// buf destroyed? alias still holds dangling pointer.
```
**Solution:** Use aliasing constructor. Shares ownership with original `shared_ptr`. Same control block. Member lifetime tied to parent.
```cpp
auto buf = std::make_shared<Buffer>();
// Aliasing constructor: shares buf's control block, points to member
std::shared_ptr<std::byte> alias(buf, buf->data.data());
// Ref count shared with buf. buf kept alive as long as alias exists.
```

---

## RAII and Resource Management

### Manual resource acquire/release without RAII [C]

**Problem:** Explicit resource acquisition and release without encapsulation. Easy to forget release on early return, exception, or error path. Complexity increases with each exit point.
```cpp
void send(X* x, string_view destination)
{
    auto port = open_port(destination);     // acquire
    my_mutex.lock();                         // acquire
    // ... code that might throw ...
    send(port, x);
    // ... more code ...
    my_mutex.unlock();                       // release - might be skipped
    close_port(port);                        // release - might be skipped
    delete x;                                // release - might be skipped
}
// If exception thrown: mutex remains locked, port remains open, x leaked
```
**Solution:** Encapsulate resource in RAII class. Constructor acquires, destructor releases. Exception-safe by default, automatic cleanup on all paths.
```cpp
class Port
{
    PortHandle port;
public:
    Port(string_view destination) : port{open_port(destination)} {}
    ~Port() { close_port(port); }
    operator PortHandle() { return port; }
    Port(const Port&) = delete;
    Port& operator=(const Port&) = delete;
};

void send(unique_ptr<X> x, string_view destination)
{
    Port port{destination};                  // RAII: acquires
    lock_guard<mutex> guard{my_mutex};       // RAII: acquires
    // ... code that might throw ...
    send(port, x);
    // ... more code ...
} // All resources released automatically, even if exception thrown
```
**Reference:** C++ Core Guidelines R.1 - "Manage resources automatically using resource handles and RAII".

### Raw `new`/`delete` for memory management [C]

**Problem:** Raw `new`/`delete` is non-RAII. Risk of memory leak on exception or early return, double-free, semantics mismatch (array vs non-array), and implicit/ambiguous ownership.
```cpp
int* p1 = new int(3);
int* p2 = new int[3];
// How to distinguish p1 from p2? Requires delete vs delete[]

foo(); // If foo() throws, stack rewinding -> heap memory never released
if (!good)
{
    return; // Early return, heap memory never released
}

bar(p1); // Does bar own p1? What if bar frees it?

delete p1;
delete p2; // Wrong delete - memory space occupied by p2[1:] never released
```
**Solution:** Eliminate raw `new`/`delete` in production code. For heap memory, use `std::unique_ptr`/`std::shared_ptr` for management, `std::weak_ptr` as observer. Use STL containers whenever possible.
```cpp
// Bad: raw pointer with unclear ownership
void process(int* ptr);

// Better: smart pointers express ownership explicitly
void take_ownership(std::unique_ptr<int> p);  // Takes ownership
void observe(const std::unique_ptr<int>& p);  // Observes only
void share(std::shared_ptr<int> p);           // Shares ownership

// Good: use make functions for exception safety
auto p1 = std::make_unique<int>(3);
auto p2 = std::make_shared<std::vector<int>>(3);
```
**Reference:** C++ Core Guidelines R.11 - "Avoid calling `new` and `delete` explicitly".

### Multiple explicit resource allocations in one expression [C]

**Problem:** Two or more explicit resource allocations in a single statement. Evaluation order is unspecified; if one allocation succeeds and another throws, the first resource leaks.
```cpp
// Bad: potential leak if second new throws before first shared_ptr constructed
fun(shared_ptr<Widget>(new Widget(a, b)), shared_ptr<Widget>(new Widget(c, d)));
// Compiler may interleave: allocate both, then construct both
// If second constructor throws, first Widget's memory never released
```
**Solution:** Use `make_shared`/`make_unique` (single allocation) or separate statements.
```cpp
// Good: make_shared does single allocation, exception-safe
fun(make_shared<Widget>(a, b), make_shared<Widget>(c, d));

// Also good: separate statements ensure immediate ownership
auto sp1 = make_shared<Widget>(a, b);
auto sp2 = make_shared<Widget>(c, d);
fun(sp1, sp2);
```
**Reference:** C++ Core Guidelines R.13 - "Perform at most one explicit resource allocation in a single expression statement".

### Missing destructor for resource-owning class [C]

**Problem:** Class acquires resources (files, sockets, memory, locks) but lacks destructor to release them. Resource leaks on destruction, especially in error cases.
```cpp
// Bad: acquires resource but no destructor
class FileWrapper
{
    FILE* f;  // Resource acquired in constructor
public:
    FileWrapper(const char* name) : f{fopen(name, "r")} {}
    // No destructor! fclose never called
};

void use()
{
    FileWrapper fw{"data.txt"};  // File opened
    // ... might throw ...
} // File never closed, resource leaked
```
**Solution:** Define destructor to release all acquired resources. Follow Rule of Three/Five/Zero - if you need custom destructor, you probably need custom copy/move operations too.
```cpp
// Good: RAII with proper destructor
class FileWrapper
{
    FILE* f;
public:
    FileWrapper(const char* name) : f{fopen(name, "r")} {}
    ~FileWrapper() { if (f) fclose(f); }  // Release in destructor

    // Disable copying (or implement properly)
    FileWrapper(const FileWrapper&) = delete;
    FileWrapper& operator=(const FileWrapper&) = delete;

    // Enable moving
    FileWrapper(FileWrapper&& other) noexcept : f{other.f} { other.f = nullptr; }
    FileWrapper& operator=(FileWrapper&& other) noexcept;
};
```
**Reference:** C++ Core Guidelines C.30 - "Define a destructor if a class needs an explicit resource" and C.31 - "All resources acquired by a class must be released by the class's destructor".

### `goto exit` cleanup pattern [R]

**Problem:** Using `goto` to centralize cleanup code. Fragile, error-prone, obscures control flow. Easy to forget cleanup on new exit paths.
```cpp
// Bad: ad-hoc cleanup with goto
ErrorCode process()
{
    FILE* f = fopen("file", "r");
    if (!f) return Error::OpenFailed;

    Buffer* buf = allocate_buffer();
    if (!buf) goto cleanup_file;

    if (!parse(f, buf)) goto cleanup_buf;

    // ... more processing ...

cleanup_buf:
    free_buffer(buf);
cleanup_file:
    fclose(f);
    return error;
}
```
**Solution:** Use RAII for automatic cleanup. If ad-hoc cleanup is truly needed, use C++23 `std::scope_exit` (or GSL `finally` as interim solution).
```cpp
// Good: RAII handles cleanup automatically
ErrorCode process()
{
    ifstream f{"file"};  // RAII
    if (!f) return Error::OpenFailed;

    vector<char> buf;    // RAII
    // ...
    return Error::None;
} // All cleanup automatic

// Alternative: std::scope_exit for ad-hoc cleanup (C++23)
void legacy_api()
{
    FILE* f = fopen("file", "r");
    if (!f) return;

    std::scope_exit close_file([&] { fclose(f); });
    // ... use f ...
} // fclose called automatically
```
**Reference:** C++ Core Guidelines R.1 - RAII preferred over ad-hoc cleanup; C++23 `std::scope_exit` for cases where RAII wrapper is impractical.

### `malloc`/`free` mixed with C++ allocation [C]

**Problem:** `malloc`/`free` do not support construction/destruction, do not mix with `new`/`delete`. Type-unsafe, no initialization guarantees.
```cpp
class Record
{
    int id;
    string name;
    // ...
};

void use()
{
    // Bad: malloc returns uninitialized memory
    Record* p1 = static_cast<Record*>(malloc(sizeof(Record)));
    // *p1 is a bag of bits, string destructor never called

    Record* p2 = new Record;  // Properly constructed

    delete p1;    // Error: cannot delete malloc'd memory
    free(p2);     // Error: cannot free new'd memory
}
```
**Solution:** Use C++ memory management exclusively. Prefer `std::make_unique`/`std::make_shared` or containers.
```cpp
// Good: C++ allocation with proper construction
auto p1 = std::make_unique<Record>();
auto p2 = std::make_shared<Record>();
vector<Record> records;  // Batch allocation with proper construction
```
**Reference:** C++ Core Guidelines R.10 - "Avoid `malloc()` and `free()`".

---

## String Handling

### `string_view` lifetime dependency [C]
**Problem:** `std::string_view` is a non-owning reference to a character sequence. It does not manage the lifetime of the underlying data. Using a `string_view` after the source string has been destroyed results in undefined behavior.
```cpp
std::string_view get_view()
{
    std::string s = "temporary";
    return s;  // Returns view to destroyed stack memory
}

void use()
{
    std::string_view sv = get_view();
    // sv now refers to deallocated memory
    std::cout << sv;  // Undefined behavior
}
```
**Solution:** Ensure the underlying character sequence outlives the `string_view`. Use `std::string` for ownership when lifetime extension is required. Pass `string_view` by value (it is cheap to copy) and avoid storing it as a class member unless the lifetime relationship is explicitly guaranteed.
```cpp
// Bad: Unnecessary const reference to lightweight view type
void process(const std::string_view& sv);

// Better: Pass lightweight view-types by value
void process(std::string_view sv);

// Good: Ownership when needed
std::string store = get_string();  // Owns the data
std::string_view view = store;     // Safe: store outlives view
```

### `string_view` treated as null-terminated [C]

**Problem:** `std::string_view` stores `{pointer, length}` - no null terminator guaranteed. Passing `data()` to C APIs expecting null-terminated strings causes undefined behavior. The pointer may reference a substring or a buffer without sentinel value.
```cpp
void c_api(const char* str); // Expects null-terminated

std::string s = "hello world";
std::string_view sv{s.data(), 5}; // Points to "hello", no '\0' at position 5

c_api(sv.data()); // Dangerous: reading past view bounds into unknown memory
```
**Solution:** Explicit conversion to null-terminated representation. Use `std::string` for temporary null-terminated copy, or migrate APIs to `std::string_view` with explicit length parameters.
```cpp
// Bad: assumes null termination
void process(std::string_view sv);
void caller() { c_api(sv.data()); } // Silent hazard

// Better: explicit conversion
void caller_safe(std::string_view sv)
{
    std::string tmp{sv}; // Guarantees null termination
    c_api(tmp.c_str());
}

// Best: migrate API to accept string_view with length
void modern_api(std::string_view sv); // Uses sv.size(), not strlen
```
**Reference:** C++ Core Guidelines SL.str.2 - `string_view` is read-only and non-owning; F.25 - "If you don't need null termination, use `string_view`."

### `char*` ambiguity between single character and C-string [R]

**Problem:** `char*` has multiple meanings in legacy code: pointer to single character, pointer to array of characters, or pointer to null-terminated C-string. This variety is a major source of errors. No compile-time distinction between `char arr[] = {'a', 'b', 'c'}` (not null-terminated) and valid C-strings.
```cpp
void print(const char* p)
{
    // Is p a single char or a string? Null check needed?
    std::cout << p << '\n'; // If not null-terminated: run-time error
}

void use()
{
    char arr[] = {'a', 'b', 'c'}; // No null terminator
    print(arr); // Potentially very bad: reads past array bounds
}
```
**Solution:** Use GSL type aliases for explicit intent. `zstring`/`czstring` designate C-style null-terminated sequences; `char*` reserved for single character references.
```cpp
// Bad: ambiguous contract
void process(char* p);

// Better: explicit semantics from GSL
void process_char(char* p);           // Single character
void process_string(zstring p);       // C-string, may be null
void process_string_nn(not_null<zstring> p); // C-string, never null

// Modern: prefer string_view when null termination not required
void modern_process(std::string_view sv); // Length + pointer, no ambiguity
```
**Reference:** C++ Core Guidelines SL.str.3 - "Use `zstring` or `czstring` to refer to a C-style, zero-terminated, sequence of characters"; SL.str.4 - "Use `char*` to refer to a single character"; F.25 - distinguishes `zstring` from pointer to single object.

### Repeated string concatenation in loops [R]
**Problem:** Repeated `+=` on `std::string` causes multiple reallocations and copies. Quadratic complexity for large numbers of concatenations.
```cpp
// Bad: repeated reallocation
std::string build;
for (auto part : parts)
{
    build += part;  // May reallocate each iteration
}
```
**Solution:** Pre-reserve capacity if total size knowable, or use `std::ostringstream` / `std::format` for complex construction.
```cpp
// Good: pre-reserve when size is knowable
std::string build;
build.reserve(total_size);
for (auto part : parts)
{
    build += part;  // No reallocation until reserve exceeded
}

// Good: ostringstream for complex building
std::ostringstream oss;
for (auto part : parts)
{
    oss << part;
}
auto build = oss.str();
```
**Reference:** C++ Core Guidelines SL.str.4 - "Avoid unnecessary string allocations".

### `substr` returning temporary copies [R]
**Problem:** `string::substr` returns a new `std::string`, copying data. Unnecessary overhead when only observation needed.
```cpp
// Suboptimal: copies substring
void process(std::string s);
process(full_str.substr(0, 10));  // Allocates + copies
```
**Solution:** Use `std::string_view` for non-owning observation of substrings. Zero-copy, lightweight.
```cpp
// Good: string_view for observation
void process(std::string_view sv);
process(std::string_view{full_str}.substr(0, 10));  // No copy
```
**Reference:** C++ Core Guidelines SL.str.5 - "Use `std::string_view` to avoid copying string data".

### Not using `std::format` over `<iostream>` [R]
**Problem:** `<iostream>` formatting has virtual dispatch overhead, locale machinery, and synchronization costs. `std::stringstream` is verbose for simple formatting.
```cpp
// Bad: verbose stream formatting
std::ostringstream oss;
oss << "Value: (" << std::setw(10) << std::setprecision(5) << val << ")" << std::endl;
auto s = oss.str();
```
**Solution:** Use `std::format` (C++20) for type-safe, efficient formatting. No virtual dispatch, direct buffer write, clearer syntax.
```cpp
// Good: format is concise and efficient
auto s = std::format("Value: ({:>10.5f})", val);

// Good: format_to avoids intermediate string
std::string buf;
buf.reserve(64);
std::format_to(std::back_inserter(buf), "{}:{}", key, val);
```
**Reference:** C++ Core Guidelines SL.io.3 - "Prefer `std::format` over stream formatting"; `std::format` avoids virtual dispatch and stream state machinery, offering better performance than `<iostream>`.

### `find` loops instead of `contains`/`starts_with` [?]
**Problem:** Manual `find` comparisons obscure intent and are less readable than purpose-built predicates.
```cpp
// Verbose: intent not immediately clear
if (s.find(prefix) == 0) { /* starts with */ }
if (s.find(substr) != std::string::npos) { /* contains */ }
if (s.rfind(suffix) == s.size() - suffix.size()) { /* ends with */ }
```
**Solution:** Use `starts_with`, `ends_with`, `contains` (C++20/23). Clear intent, self-documenting.
```cpp
// Good: clear intent
if (s.starts_with(prefix)) { }
if (s.contains(substr)) { }
if (s.ends_with(suffix)) { }
```

### Raw `char*` manipulation [C]
**Problem:** `strcpy`, `strcat`, `sprintf` have no bounds checking. Buffer overflows, security vulnerabilities.
```cpp
// Dangerous: buffer overflow possible
char buf[32];
strcpy(buf, input);  // No size check
strcat(buf, suffix); // No size check
```
**Solution:** Use `std::string` for ownership, `std::string_view` for observation, `std::format`/`snprintf` for bounded formatting.
```cpp
// Good: string handles memory automatically
std::string s = input;
s += suffix;  // Safe, automatic reallocation if needed

// Good: bounded formatting
std::string s = std::format("{}{}", input, suffix);
// Or: snprintf with explicit bound
snprintf(buf, sizeof(buf), "%s%s", input, suffix);
```
**Reference:** C++ Core Guidelines SL.str.1 - "Use `std::string` to own character sequences"; SL.str.11 - "Avoid `strcpy()`, `strcat()`, `sprintf()` and similar".

---

## Compile-Time Computation

### Runtime check where `static_assert` suffices [R]

**Problem:** Run-time validation of conditions that are known at compile time. Unnecessary code generation, missed optimization opportunities, and error handling for errors that should never exist in a correct build.
```cpp
// Bad: run-time check for compile-time knowable condition
int check_size()
{
    if (sizeof(int) < 4)
    {
        std::cerr << "Int too small\n";
        return -1;
    }
    // ...
    return 0;
}

// Worse: undefined behavior in attempt to validate
int bits = 0;
for (int i = 1; i; i <<= 1) ++bits; // Overflow: undefined
if (bits < 32) { /* handle error */ }
```
**Solution:** Use `static_assert` for compile-time verification. Fail fast at compilation, zero run-time cost, no error handling needed.
```cpp
// Good: compile-time check
static_assert(sizeof(int) >= 4, "int must be at least 32 bits");

// Better: use type system
using int32 = std::int32_t; // Guaranteed size, no check needed
```
**Reference:** C++ Core Guidelines P.5 - "Prefer compile-time checking to run-time checking"; "Don't postpone to run time what can be done well at compile time."

### Function not marked `constexpr` when compile-time evaluation possible [R]

**Problem:** Functions that could be evaluated at compile time but lack `constexpr` specifier. Missed optimization opportunities, inability to use results in compile-time contexts (array sizes, template arguments, `static_assert`).
```cpp
// Bad: could be constexpr, but isn't
int square(int n) { return n * n; }

int arr[square(5)]; // Error: square not constexpr

// Bad: forces run-time evaluation even with constant arguments
const int x = square(10); // Run-time call (unless inlined and optimized)
```
**Solution:** Declare functions `constexpr` when they might need compile-time evaluation. C++14 relaxed constraints (loops, local variables allowed).
```cpp
// Good: enables compile-time usage
constexpr int square(int n) { return n * n; }

int arr[square(5)];       // OK: compile-time evaluation
const int x = square(10); // Compile-time evaluation

// Note: constexpr does not guarantee compile-time evaluation
// The compiler decides based on context
int y = 20;
int z = square(y); // Run-time evaluation (y not constant)
```
**Reference:** C++ Core Guidelines F.4 - "If a function might have to be evaluated at compile time, declare it `constexpr`".

### Macro constant/function when `constexpr` would suffice [R]

**Problem:** Macros for constants or simple functions. No type safety, no scoping, difficult debugging (no symbol in debugger), fragile syntax requiring excessive parentheses.
```cpp
// Bad: macro constant, type unclear, no scoping
#define BUFFER_SIZE 1024

// Bad: macro function, precedence pitfalls, no type checking
#define SQUARE(x) ((x) * (x)) // Even with parentheses: fragile
#define ADD(x, y) x + y       // Classic error: ADD(1, 2) * 3 == 7

// Worse: multiple evaluation side effects
int i = 5;
int j = SQUARE(i++); // Undefined behavior: i++ evaluated twice
```
**Solution:** Migrate to `constexpr` for constants and functions. Type-safe, scoped, debuggable, no multiple-evaluation hazards.
```cpp
// Good: constexpr constant
constexpr std::size_t BUFFER_SIZE = 1024;

// Good: constexpr function
constexpr int square(int n) { return n * n; }

// C++23: constexpr with more flexibility
constexpr auto calculate()
{
    std::array<int, 4> arr{};
    // ... complex initialization
    return arr;
}
```
**Reference:** C++ Core Guidelines ES.31 enforcement - "Look for macros that could be constexpr."

### `if constexpr` not used for compile-time branching [?]

**Problem:** Template specializations or SFINAE for compile-time code path selection. Verbose, hard to read, increases compilation time.
```cpp
// Bad: full specialization for different types
template<class T>
void process(T val)
{
    // Run-time check even when type is known at compile time
    if (std::is_integral_v<T>)
    {
        // ... integral path (still compiled for non-integral)
    }
}

// Bad: SFINAE for simple branching
template<class T, std::enable_if_t<std::is_integral_v<T>, int> = 0>
void foo(T val) { /* integral */ }

template<class T, std::enable_if_t<!std::is_integral_v<T>, int> = 0>
void foo(T val) { /* non-integral */ }
```
**Solution:** Use `if constexpr` (C++17) for compile-time branching. Cleaner syntax, discarded branches not instantiated, no SFINAE complexity.
```cpp
// Good: compile-time branching with if constexpr
template<class T>
void process(T val)
{
    if constexpr (std::is_integral_v<T>)
    {
        // Only compiled when T is integral
    }
    else
    {
        // Only compiled when T is not integral
    }
}

// Good: simplifying template-heavy code
template<class T>
auto get_value(T t)
{
    if constexpr (std::is_pointer_v<T>)
    {
        return *t;
    }
    else
    {
        return t;
    }
}
```
**Note:** `if constexpr` is especially useful for avoiding unused parameter warnings and simplifying generic code.

### `consteval` not used for forced compile-time evaluation (C++20) [?]

**Problem:** `constexpr` functions that should *always* evaluate at compile time, but can accidentally be called at run time. No compile-time guarantee, potential run-time overhead.
```cpp
// Bad: constexpr allows run-time evaluation
constexpr int must_be_compile_time(int n)
{
    return n * n;
}

int x = 10;
int y = must_be_compile_time(x); // Silent run-time evaluation

// Problem: function intended for compile-time only
// Used in contexts requiring compile-time: OK
// Used with run-time values: silently degrades
```
**Solution:** Use `consteval` (C++20) for functions that *must* evaluate at compile time. Compilation error if run-time evaluation attempted.
```cpp
// Good: forced compile-time evaluation
consteval int must_be_compile_time(int n)
{
    return n * n;
}

constexpr int a = must_be_compile_time(5); // OK
// int b = must_be_compile_time(x);        // Error: x not constant

// Use case: parsing literal strings at compile time
consteval auto parse_version(std::string_view sv)
{
    // Must process string at compile time
    return /* parsed result */;
}
```
**Note:** `consteval` is stricter than `constexpr`. Use when run-time evaluation would indicate a programming error or semantic violation.

### `if constexpr` with `std::is_constant_evaluated()` pitfall (C++23) [C]

**Problem:** Using `if constexpr (std::is_constant_evaluated())` to guard `consteval` function calls. The condition is always true because `if constexpr` itself is evaluated at compile time. Compiler sees potential runtime call to `consteval` function and rejects the code.
```cpp
consteval int compile_time_algo(std::span<const int> sp)
{
    int res = 0;
    for (auto a : sp) { res += a * a; }
    return res;
}

// Bad: attempting to call consteval from constexpr with runtime guard
constexpr int compute(std::span<const int> sp)
{
    if (std::is_constant_evaluated())
    {
        return compile_time_algo(sp); // Error: compiler sees possible runtime call
    }
    else
    {
        __asm__("simd optimized");
    }
}

// Worse: "obviously incorrect" fix - condition always true
constexpr int compute_wrong(std::span<const int> sp)
{
    if constexpr (std::is_constant_evaluated()) // OOPS: always true!
    {
        return compile_time_algo(sp);
    }
    else
    {
        __asm__("simd optimized");
    }
}
```
**Solution:** Use `if consteval` (C++23) to establish a consteval evaluation context. Braces are mandatory.
```cpp
// Good: if consteval creates compile-time-only context
constexpr int compute(std::span<const int> sp)
{
    if consteval // C++23: consteval context established
    {
        return compile_time_algo(sp); // OK: can call consteval
    }
    else
    {
        __asm__("simd optimized");
    }
}

// Also available: negated form
constexpr int compute_neg(std::span<const int> sp)
{
    if !consteval // Runtime path only
    {
        __asm__("simd optimized");
    }
    else
    {
        return compile_time_algo(sp);
    }
}
```
**Reference:** C++23 P1938R3 - `if consteval` as bugfix for `std::is_constant_evaluated()` + `consteval` interaction.

---

## Three-way Comparison

### Manual implementation of six comparison operators [R]
**Problem:** Pre-C++20 code manually implements `<`, `<=`, `>`, `>=`, `==`, `!=` with redundant logic. Violates DRY principle, increases maintenance burden.
```cpp
class Widget
{
    int data;
public:
    bool operator<(const Widget& other) const { return data < other.data; }
    bool operator<=(const Widget& other) const { return data <= other.data; }
    bool operator>(const Widget& other) const { return data > other.data; }
    bool operator>=(const Widget& other) const { return data >= other.data; }
    bool operator==(const Widget& other) const { return data == other.data; }
    bool operator!=(const Widget& other) const { return !(data == other.data); }
};
```
**Solution:** Use C++20 `operator<=>` with `= default`. Compiler generates `<`, `<=`, `>`, `>=` from `<=>` and `!=` from `==`.
```cpp
class Widget
{
    int data;
public:
    auto operator<=>(const Widget&) const = default;
    bool operator==(const Widget&) const = default;
};
```

### Incorrect `<=>` return type [?]
**Problem:** Custom `<=>` returns `int` or `bool` instead of proper comparison category types. Loses semantic information about ordering strength.
```cpp
// Bad: returns int like strcmp
class Record
{
public:
    int operator<=>(const Record& other) const // Wrong: not a comparison category
    {
        return id - other.id;
    }
};
```
**Solution:** Return proper comparison category from `<compare>` header: `std::strong_ordering`, `std::weak_ordering`, or `std::partial_ordering`.
```cpp
class Record
{
    int id;
public:
    std::strong_ordering operator<=>(const Record& other) const
    {
        return id <=> other.id;
    }
};
```

### Missing `operator==` with custom `<=>` [C]
**Problem:** Defining custom `operator<=>` without `operator==`. C++20 only generates relational operators from `<=>`; equality operators require separate definition unless both are defaulted.
```cpp
class Config
{
    std::string name;
    int priority;
public:
    std::strong_ordering operator<=>(const Config& other) const
    {
        if (auto cmp = priority <=> other.priority; cmp != 0)
            return cmp;
        return name <=> other.name;
    }
    // Missing: operator== - undefined behavior for == and != usage
};
```
**Solution:** Explicitly define `operator==` when `<=>` is custom, or default both.
```cpp
class Config
{
    std::string name;
    int priority;
public:
    std::strong_ordering operator<=>(const Config& other) const
    {
        if (auto cmp = priority <=> other.priority; cmp != 0)
            return cmp;
        return name <=> other.name;
    }
    bool operator==(const Config& other) const = default;
};
```

### Manual lexicographical comparison [R]
**Problem:** Manual member-by-member comparison instead of using defaulted `<=>` or `std::tie`. Verbose and error-prone.
```cpp
class Person
{
    std::string last_name;
    std::string first_name;
    int age;
public:
    bool operator<(const Person& other) const
    {
        if (last_name != other.last_name)
            return last_name < other.last_name;
        if (first_name != other.first_name)
            return first_name < other.first_name;
        return age < other.age;
    }
};
```
**Solution:** Use defaulted `<=>` for member-wise lexicographical comparison, or `std::tie` for custom ordering.
```cpp
class Person
{
    std::string last_name;
    std::string first_name;
    int age;
public:
    // Member-wise lexicographical (declaration order)
    auto operator<=>(const Person&) const = default;
};

// Or for custom ordering:
class Employee
{
    int priority;
    std::string name;
public:
    auto operator<=>(const Employee& other) const
    {
        return std::tie(priority, name) <=> std::tie(other.priority, other.name);
    }
};
```

### Incorrect `<=>` result usage [?]
**Problem:** Treating `<=>` result as boolean or comparing to non-zero values. Undefined behavior or incorrect semantics.
```cpp
void check_order(int a, int b)
{
    if (a <=> b) // Wrong: not convertible to bool
        std::cout << "not equal";
    if ((a <=> b) == 1) // Wrong: should compare to literal 0
        std::cout << "greater";
}
```
**Solution:** Compare `<=>` result to literal `0`, or use the generated comparison operators directly.
```cpp
void check_order(int a, int b)
{
    // Compare to literal 0
    if (auto cmp = a <=> b; cmp > 0)
    {
        std::cout << "a > b";
    }
    else if (cmp < 0)
    {
        std::cout << "a < b";
    }
    else
    {
        std::cout << "a == b";
    }
    // Or use generated operators:
    if (a > b)
    {
        std::cout << "a > b";
    }
}
```

---

## Concepts

### Using SFINAE instead of concepts [R]
**Problem:** Using `std::enable_if` and SFINAE for template constraints when concepts are available. SFINAE is verbose, produces poor error messages, requires mutually exclusive constraints for overload resolution, and increases compilation time.
```cpp
// Bad: SFINAE-based constraint
template<class Ty, std::enable_if_t<!std::is_array_v<Ty>, int> = 0>
void process(Ty val);

template<class Ty, std::enable_if_t<!std::is_array_v<Ty> && !std::is_reference_v<Ty>, int> = 0>
void process(Ty val);  // Ambiguous with above when both match
```
**Solution:** Use C++20 concepts with `requires` clauses or concept short syntax. Concepts provide clearer intent, better error messages, and proper subsumption ordering.
```cpp
// Good: concept-based constraint
template<class Ty>
concept not_array = !std::is_array_v<Ty>;

template<class Ty>
concept not_array_nor_ref = not_array<Ty> && !std::is_reference_v<Ty>;

template<not_array Ty>
void process(Ty val);  // #1

template<not_array_nor_ref Ty>
void process(Ty val);  // #2 - more constrained, preferred when both match

// Or inline requires clause:
template<class Ty>
    requires (!std::is_array_v<Ty>)
void process(Ty val);
```

### `requires` expression not convertible to `bool` [C]
**Problem:** Using a `requires` clause with an expression that has `operator bool` but is not implicitly convertible to `bool`. The expression must have type `bool` exactly; no user-defined conversion is performed during constraint checking.
```cpp
template<class Ty>
struct S
{
    constexpr operator bool() const { return sizeof(Ty) <= 4; }
};

template<class Ty>
    requires (S<Ty>{})  // Error: S<Ty>{} does not have type bool
void f(Ty);
```
**Solution:** Explicitly cast to `bool` in the `requires` clause.
```cpp
template<class Ty>
    requires (static_cast<bool>(S<Ty>{}))  // OK: explicit conversion
void f(Ty);

// Or use a constexpr bool variable template:
template<class Ty>
constexpr bool is_small_v = sizeof(Ty) <= 4;

template<class Ty>
    requires is_small_v<Ty>  // OK: bool type
void f(Ty);
```

### Atomic constraint identity causing subsumption failure [C]
**Problem:** Two concepts that are logically equivalent but use different atomic constraints fail subsumption. Concepts are compared by atomic constraint identity, not by semantic equivalence. Even if `concept A = B<T>` always yields the same result as `is_meowable<T>`, they are distinct atomic constraints.
```cpp
template<class T>
constexpr bool is_meowable = true;

template<class T>
constexpr bool is_cat = true;

template<class T>
concept Meowable = is_meowable<T>;

template<class T>
concept BadMeowableCat = is_meowable<T> && is_cat<T>;  // Uses is_meowable directly

template<class T>
concept GoodMeowableCat = Meowable<T> && is_cat<T>;    // Uses Meowable

template<Meowable T>
void f1(T);  // #1

template<BadMeowableCat T>
void f1(T);  // #2 - ambiguous with #1: is_meowable<T> and Meowable<T> are distinct

template<Meowable T>
void f2(T);  // #3

template<GoodMeowableCat T>
void f2(T);  // #4 - OK: subsumes #3 (GoodMeowableCat gets is_meowable from Meowable)
```
**Solution:** Reuse existing concepts in concept definitions to ensure atomic constraint identity is preserved. Forward through concept names rather than duplicating constraint expressions.
```cpp
// Good: reuse Meowable to preserve atomic constraint identity
template<class T>
concept GoodMeowableCat = Meowable<T> && is_cat<T>;
```

### Not using standard library concepts [R]
**Problem:** Defining custom concepts that duplicate standard library concepts. Reinvents `std::integral`, `std::copyable`, `std::ranges::range`, etc., leading to maintenance burden and potential semantic mismatches.
```cpp
// Bad: reinventing standard concepts
template<class Ty>
concept is_integer = std::is_integral_v<Ty>;

template<class Ty>
concept can_copy = std::copy_constructible<Ty> && std::copy_assignable<Ty>;
```
**Solution:** Use concepts from `<concepts>` and `<iterator>`/`<ranges>` headers. Standard concepts are well-tested, documented, and interoperate with standard library facilities.
```cpp
#include <concepts>

// Good: use standard concepts
template<std::integral Ty>
void process_integer(Ty val);

template<std::copyable Ty>
void duplicate(Ty val);

// Compose with standard concepts:
template<class Ty>
concept numeric = std::integral<Ty> || std::floating_point<Ty>;
```

### Over-constraining templates [?]
**Problem:** Constraining templates to implementation details rather than semantic requirements. Over-constrained templates reject valid types that could satisfy the interface, reducing reusability.
```cpp
// Bad: over-constrained to implementation details
template<class Ty>
    requires std::is_default_constructible_v<Ty> &&
             std::is_copy_constructible_v<Ty> &&
             std::is_nothrow_move_assignable_v<Ty>
class Container
{
    // Implementation uses: default construction, copy, move assignment
};

// Problem: A type with move-only semantics could work, but is rejected
// Problem: A type with throwing move assignment works fine, but is rejected
```
**Solution:** Constrain to the minimal requirements of the interface. Use semantic concepts rather than type traits when possible. Document requirements through concept names.
```cpp
// Good: constrain to semantic requirements
template<class Ty>
    requires std::default_initializable<Ty> && std::copyable<Ty>
class Container
{
    // Clear intent: needs default init and copyability
};

// Better: define a concept for your specific interface
template<class Ty>
concept container_element = std::movable<Ty> && requires(Ty t)
{
    { Ty() } -> std::same_as<Ty>;  // Default constructible
};

template<container_element Ty>
class FlexibleContainer;
```
**Guideline:** Distinguish between "requires copyability" (semantic) and "requires `std::is_copy_constructible_v`" (implementation). The former expresses intent; the latter exposes implementation details.

---

## Containers

### Range check not performed [C]
**Problem:** Accessing container elements without bounds checking. Using `operator[]` or `front()`/`back()` on empty containers causes undefined behavior.
```cpp
std::vector<int> vec{1, 2, 3};
int x = vec[5];           // Undefined behavior: out of bounds
int y = vec.front();      // OK here, but dangerous if vec empty

void process(std::vector<int>& v, size_t idx)
{
    int val = v[idx];     // No bounds check, potential UB
    // ...
}
```
**Solution:** Use `at()` for checked access, or verify bounds before indexing. Prefer range-based for loops for iteration.
```cpp
std::vector<int> vec{1, 2, 3};
int x = vec.at(5);        // Throws std::out_of_range

void process(std::vector<int>& v, size_t idx)
{
    if (idx < v.size())
    {   // Explicit bounds check
        int val = v[idx];
        // ...
    }
}

// Or use range-based for:
for (auto& elem : vec)
{
    // ...
}
```
**Reference:** C++ Core Guidelines SL.con.3 - "Avoid bounds errors".

### Using C-style arrays instead of standard containers [R]
**Problem:** Using raw arrays `T[]` or `T[N]` instead of `std::array`, `std::vector`, or `std::span`. Raw arrays decay to pointers, don't know their size, and don't support standard container interfaces.
```cpp
// Bad: C-style array
int arr[10];
void process(int* p, size_t n);  // Size information lost

// Bad: array new
int* dyn = new int[10];          // Requires manual delete[], no size tracking
```
**Solution:** Use `std::array` for fixed-size, `std::vector` for dynamic-size, `std::span` for non-owning views. They preserve size information and provide bounds-safe interfaces.
```cpp
// Good: std::array for fixed size
std::array<int, 10> arr;

// Good: std::vector for dynamic size
std::vector<int> vec(10);

// Good: std::span for non-owning view
void process(std::span<int> sp);  // Size preserved, bounds-safe
```
**Reference:** C++ Core Guidelines SL.con.1 - "Prefer using STL array or vector instead of a C array".

### Assuming vector capacity growth strategy [?]
**Problem:** Code that depends on specific `std::vector` reallocation behavior. Assuming iterators/pointers remain valid after push_back, or assuming specific growth factor.
```cpp
std::vector<int> vec;
vec.push_back(1);
int* p = &vec[0];           // Pointer to first element

vec.push_back(2);           // May reallocate
*p = 3;                     // Undefined behavior if reallocation occurred

// Bad: assuming specific growth
if (vec.capacity() == vec.size())
{
    // Assuming growth factor is 2x (implementation-defined)
}
```
**Solution:** Don't assume reallocation behavior. Use `reserve()` when capacity needs are known, and treat iterators/pointers as invalid after any modifying operation.
```cpp
std::vector<int> vec;
vec.reserve(100);           // Pre-allocate if size known

vec.push_back(1);
int* p = &vec[0];

vec.push_back(2);
p = &vec[0];                // Re-acquire pointer after modification
*p = 3;                     // OK
```
**Reference:** C++ Core Guidelines SL.con.2 - "Avoid dependence on potentially changing container layout".

### Not using `reserve` when size is known [R]
**Problem:** Repeatedly growing a vector without pre-allocating. Causes multiple reallocations and copies, hurting performance. Total cost is implementation-defined but generally amortized linear.
```cpp
std::vector<int> result;
for (int i = 0; i < 100000; ++i)
{
    result.push_back(i);  // Multiple reallocations, implementation-defined cost
}
```
**Solution:** Use `reserve()` when the final size or an upper bound is known. Reduces allocations and improves cache locality.
```cpp
std::vector<int> result;
result.reserve(100000);     // Single allocation
for (int i = 0; i < 100000; ++i)
{
    result.push_back(i);    // No reallocations until 100000 elements
}

// Or construct with size if default-initialization acceptable
std::vector<int> result(100000);
for (int i = 0; i < 100000; ++i)
{
    result[i] = i;
}
```
**Reference:** C++ Core Guidelines SL.con.5 - "Use `reserve()` to avoid invalidating pointers/iterators/references".

### Iterator invalidation ignored [C]
**Problem:** Using iterators, pointers, or references after container modification that invalidates them. Different containers have different invalidation rules; assuming uniform behavior causes bugs.
```cpp
// Vector: all iterators invalidated on reallocation
std::vector<int> vec{1, 2, 3, 4, 5};
auto it = vec.begin() + 2;
vec.push_back(6);           // May invalidate all iterators
*it = 10;                   // Undefined behavior

// Unordered_map: iterators invalidated on rehash
std::unordered_map<int, std::string> map{{1, "a"}, {2, "b"}};
auto it = map.find(1);
map.reserve(1000);          // May trigger rehash
it->second = "c";           // Undefined behavior if rehashed

// Set: iterators not invalidated on insert/erase (except erased element)
std::set<int> st{1, 2, 3};
auto it = st.find(2);
st.insert(4);               // Existing iterators remain valid
*st.begin() = 0;            // Error: set elements are immutable

// Range-based for modifying container
for (auto& elem : vec)
{
    if (elem % 2 == 0)
    {
        vec.push_back(elem * 2);  // Invalidates iterators
    }
}
```
**Solution:** Re-acquire iterators after modifying operations. Know your container's invalidation rules:
- `vector`: All iterators invalidated on reallocation; insert/erase at position invalidates from there to end
- `deque`: All iterators invalidated on insert/erase at ends; middle operations invalidate all
- `list`/`forward_list`: Only iterators to erased elements invalidated; insert doesn't invalidate
- `map`/`set`: Only iterators to erased elements invalidated; insert doesn't invalidate
- `unordered_map`/`unordered_set`: All iterators invalidated on rehash; insert may invalidate
```cpp
// Vector: re-acquire after modification
std::vector<int> vec{1, 2, 3, 4, 5};
vec.push_back(6);
auto it = vec.begin() + 2;  // Re-acquire after modification

// Unordered_map: check before use or re-acquire
std::unordered_map<int, std::string> map{{1, "a"}, {2, "b"}};
map.reserve(1000);          // Rehash before acquiring iterators
auto it = map.find(1);      // Safe after rehash

// Index-based for modification
for (size_t i = 0; i < vec.size(); ++i)
{
    if (vec[i] % 2 == 0)
    {
        vec.push_back(vec[i] * 2);  // OK: index remains valid
    }
}

// Or use remove-erase idiom for filtering
```
**Reference:** C++ Core Guidelines SL.con.4 - "Don't invalidate all pointers/iterators/references to container elements".

### Returning C-style array from function [C]
**Problem:** Returning a pointer to local array or using `T[]` as return type. Local arrays are destroyed when function returns; caller gets dangling pointer.
```cpp
// Bad: returns pointer to local
int* get_array()
{
    int arr[10] = {1, 2, 3};
    return arr;             // arr destroyed, pointer dangling
}

// Bad: array new requires manual delete[]
int* get_dynamic()
{
    return new int[10];     // Caller must delete[], error-prone
}
```
**Solution:** Return standard containers that manage their own memory. Use `std::vector` for dynamic size, `std::array` for fixed size.
```cpp
// Good: returns by value (NRVO/move optimization)
std::vector<int> get_vector()
{
    std::vector<int> vec(10);
    // ... populate ...
    return vec;
}

// Good: fixed size
std::array<int, 10> get_array()
{
    std::array<int, 10> arr{1, 2, 3};
    return arr;
}
```
**Reference:** C++ Core Guidelines SL.con.6 - "Use `std::vector` or `std::array` rather than a C array".

### Improper container selection [?]
**Problem:** Choosing a container without considering usage patterns. Performance characteristics vary significantly between containers; wrong choice leads to suboptimal complexity.
```cpp
// Bad: vector with frequent middle insertion/removal
std::vector<int> vec;
for (int i = 0; i < 10000; ++i)
{
    vec.insert(vec.begin() + vec.size() / 2, i);  // O(n) each
}

// Bad: map when read-mostly with no ordering needs
std::map<std::string, int> lookup;  // O(log n) lookup
// Frequent iteration over all elements, rare inserts

// Bad: set when hash would suffice
std::set<int> unique_items;         // O(log n) insert
// Only need uniqueness, no ordering requirements
```
**Solution:** Select container based on primary operations:
- Frequent random access: `std::vector`
- Frequent insertion/removal at ends: `std::vector` (push_back/pop_back)
- Frequent insertion/removal in middle: `std::list` or `std::deque`
- Frequent lookup with ordering: `std::map`/`std::set`
- Frequent lookup without ordering: `std::unordered_map`/`std::unordered_set`
- Frequent iteration over all elements: contiguous containers (vector, array)
```cpp
// Good: list for frequent middle insertion
std::list<int> lst;
for (int i = 0; i < 10000; ++i)
{
    auto it = lst.begin();
    std::advance(it, lst.size() / 2);
    lst.insert(it, i);      // O(1) insert
}

// Good: unordered_map for hash-based lookup
std::unordered_map<std::string, int> lookup;  // O(1) average lookup

// Good: unordered_set for uniqueness without ordering
std::unordered_set<int> unique_items;         // O(1) average insert
```
**Guideline:** Profile if uncertain, but prefer `std::vector` by default (cache-friendly), then migrate to other containers when usage patterns demand.

---

## Flat Containers (C++23)

### Not considering `flat_map`/`flat_set` as alternatives [?]
**Problem:** Using `std::map`/`std::set` or `std::unordered_map`/`std::unordered_set` without considering `std::flat_map`/`std::flat_set` for lookup-heavy workloads. Missing performance opportunities from cache-friendly contiguous storage.
```cpp
// Suboptimal: map for read-heavy, few modifications
std::map<int, std::string> lookup;
for (int i = 0; i < 1000000; ++i)
{
    auto it = lookup.find(keys[i]);  // O(log n) with high constant, cache misses
}

// Suboptimal: unordered_map when ordered iteration needed occasionally
std::unordered_map<int, std::string> hash_lookup;
// ... many lookups ...
// Need sorted output: must copy and sort
std::vector<std::pair<int, std::string>> sorted(hash_lookup.begin(), hash_lookup.end());
std::sort(sorted.begin(), sorted.end());
```
**Solution:** Consider `std::flat_map`/`std::flat_set` when:
- Lookups dominate insertions/deletions (read-heavy workloads)
- Ordered iteration is occasionally needed
- Memory footprint matters (no node overhead)
- Cache performance is critical (contiguous storage)
```cpp
// Good: flat_map for lookup-heavy with occasional ordered iteration
std::flat_map<int, std::string> lookup;
for (int i = 0; i < 1000000; ++i)
{
    auto it = lookup.find(keys[i]);  // O(log n), lower constant, cache-friendly
}
// Ordered iteration is free (already sorted)
for (const auto& [k, v] : lookup)
{
    // ...
}
```
**Trade-offs:**
- Insert/erase: O(n) vs O(log n) for `map`, O(1) for `unordered_map`
- Iterators invalidated on insert/erase (like `vector`)
- Cannot store non-movable types
- No node extraction API (`extract`/`splice`)

### `flat_map` iterator dereferencing incorrectly [C]
**Problem:** `std::flat_map` uses separate storage for keys and values (`vector<Key>` + `vector<Value>`), requiring a proxy iterator. Dereferencing returns a proxy reference `pair<const Key&, Value&>`, not a real reference. Storing the result of `operator*` fails or produces unexpected behavior.
```cpp
std::flat_map<int, std::string> fm{{1, "a"}, {2, "b"}};
auto it = fm.find(1);

// Bad: storing proxy reference
auto kv = *it;              // kv is a proxy, not pair<int, string&>
kv.second = "c";            // May not modify the map!

// Bad: auto& to proxy
auto& ref = *it;            // ref is proxy reference, not real reference
```
**Solution:** Access key/value directly through iterator, or use structured binding with care. Do not store the result of `operator*`.
```cpp
std::flat_map<int, std::string> fm{{1, "a"}, {2, "b"}};
auto it = fm.find(1);

// Good: access members directly
std::cout << it->first << ": " << it->second << "\n";
it->second = "c";           // OK: modifies the map

// Good: structured binding from iterator (C++23)
auto&& [k, v] = *it;       // OK: forwarding reference handles proxy
v = "d";                    // OK

// Good: copy if needed
int key = it->first;
std::string val = it->second;  // Copy value
```
**Note:** `std::flat_set` does not have this issue - its iterator returns direct `const Key&`.

---

## Ranges (C++20/23)

### Eager materialization of intermediate results [R]
**Problem:** Materializing intermediate containers when views suffice. Unnecessary allocations, cache pollution, impedes fusion optimizations.
```cpp
// Bad: materializes intermediate vector
auto filtered = std::vector<int>{};
std::copy_if(data.begin(), data.end(), std::back_inserter(filtered),
    [](int x) { return x > 0; });
auto doubled = std::vector<int>{};
std::transform(filtered.begin(), filtered.end(), std::back_inserter(doubled),
    [](int x) { return x * 2; });
```
**Solution:** Use lazy views. Composable, fused evaluation, no intermediate allocations.
```cpp
// Good: lazy pipeline, fused evaluation
auto result = data
    | std::views::filter([](int x) { return x > 0; })
    | std::views::transform([](int x) { return x * 2; })
    | std::ranges::to<std::vector>();  // Single materialization at end
```

### Dangling views from temporary containers [C]
**Problem:** Storing views that reference temporary containers. View outlives source -> undefined behavior.
```cpp
// Bad: view references destroyed temporary
auto get_positive()
{
    return fetch_data()  // Returns vector
        | std::views::filter([](int x) { return x > 0; });  // Dangling!
}  // fetch_data() result destroyed, view now dangling

void use()
{
    for (auto x : get_positive())  // UB: accessing destroyed data
    {
        process(x);
    }
}
```
**Solution:** Ensure source container outlives view. Materialize if ownership transfer needed.
```cpp
// Good: materialize when returning from function
auto get_positive()
{
    auto data = fetch_data();
    return data
        | std::views::filter([](int x) { return x > 0; })
        | std::ranges::to<std::vector>();  // Owns the data
}

// Good: accept view parameter, lifetime managed by caller
void process_positive(std::ranges::view auto data)
{
    for (auto x : data | std::views::filter([](int x) { return x > 0; }))
    {
        process(x);
    }
}
```

### Mutating container while raw iterating [C]
**Problem:** Raw loops that modify containers (insert/erase) during iteration. Iterator invalidation, missed elements, UB.
```cpp
// Bad: modifying vector while iterating by index
for (size_t i = 0; i < vec.size(); ++i)
{
    if (vec[i] % 2 == 0)
    {
        vec.push_back(vec[i] * 2);  // May invalidate, skip elements
    }
}

// Bad: erasing while iterating
for (auto it = lst.begin(); it != lst.end(); ++it)
{
    if (*it < 0)
    {
        lst.erase(it);  // Invalidates it, UB on ++it
    }
}
```
**Solution:** Use `std::ranges::copy_if` to new container, or `std::erase_if` for in-place removal.
```cpp
// Good: copy-if to new container
auto result = vec
    | std::views::filter([](int x) { return x % 2 == 0; })
    | std::views::transform([](int x) { return x * 2; })
    | std::ranges::to<std::vector>();

// Good: in-place erase_if (C++20)
std::erase_if(lst, [](int x) { return x < 0; });  // Handles invalidation correctly
```

### Nested loops instead of cartesian_product [R]
**Problem:** Manual nested loops for cross-product iteration. Verbose, harder to optimize, obscures intent.
```cpp
// Verbose nested loops
for (auto x : xs)
{
    for (auto y : ys)
    {
        process(x, y);
    }
}
```
**Solution:** Use `std::views::cartesian_product` (C++23) for clarity and potential optimization.
```cpp
// Good: cartesian_product expresses intent clearly
for (auto [x, y] : std::views::cartesian_product(xs, ys))
{
    process(x, y);
}
```

### Manual flattening instead of join [R]
**Problem:** Nested loops or recursion to flatten nested ranges. Verbose, obscures intent, harder to optimize.
```cpp
// Bad: manual flattening with nested loops
std::vector<std::vector<int>> batches = fetch_batches();
for (const auto& batch : batches)
{
    for (int item : batch)
    {
        process(item);
    }
}
```
**Solution:** Use `std::views::join` (C++20) to flatten nested ranges.
```cpp
// Good: join flattens nested ranges
for (int item : batches | std::views::join)
{
    process(item);
}

// Good: join_with for adding separators (C++23)
for (auto elem : words | std::views::join_with(','))
{
    output(elem);
}
```

### Not using chunk for batching [?]
**Problem:** Manual index arithmetic for fixed-size batching. Error-prone, obscures algorithm.
```cpp
// Manual batching
for (size_t i = 0; i < data.size(); i += batch_size)
{
    auto end = std::min(i + batch_size, data.size());
    process_batch(data.begin() + i, data.begin() + end);
}
```
**Solution:** Use `std::views::chunk` (C++23) for fixed-size batches.
```cpp
// Good: chunk for fixed-size batches
for (auto batch : data | std::views::chunk(100))
{
    process_batch(batch);
}
```

### Traditional `for`-loops for single variable iteration [?]
**Problem:** Conventional `for`-based loops are fragile when expecting for 'definite-range iteration': since they're essentially `while` + initializers with a (hopefully) better readability syntax. Loop-dependent variable can be unexpectedly modified, resulting in a forsaken failing point for mistakes.  
```cpp
for(int i=0; i<10; ++i)
{
    // ...
    i += get_offset(); // Clarity and intuitive for processing, but at what cost?  
    process(i);  

    // Iteration will often go not-as-expected  
}
```
**Solution:** If target *range* is definite, prefer `std::views::iota` over conventional for-loops. They behave more like Python's `range()`, creating an definite iterate sequence that eliminates inadvertent mistakes and allow compiler optimization.  
```cpp
for(int i : std::views::iota(0, 10))
{
    // Tamper with `i` whatever way you want
    i += get_offset();
    process(i);
    i = 0;

    // At next loop `i` will definitely be 1 greater than this loop's initial `i`, no exceptions  
}
```

### Manual push_back loop instead of range construction [R]
**Problem:** Manual iteration to populate containers misses optimization opportunities; container cannot pre-allocate without knowing range size.
```cpp
// Bad: manual insertion loop
std::vector<int> v;
for (auto x : data | std::views::filter(pred))
{
    v.push_back(x);
}

// Bad: copy with back_inserter
std::ranges::copy(filtered_view, std::back_inserter(v));
```
**Solution:** Use `ranges::to` or `from_range` construction. Container can query range size for single allocation.
```cpp
// Good: ranges::to for view materialization
auto v = data | std::views::filter(pred) | std::ranges::to<std::vector>();

// Good: from_range tagged construction
std::vector<int> v{std::from_range, data | std::views::filter(pred)};
```

### Iterator-pair constructor with ranges::begin/end [R]
**Problem:** Iterator-pair constructors predate C++20 ranges; they fail for non-common ranges where iterator and sentinel types differ.
```cpp
// Bad: may fail for non-common ranges
auto res = vec | std::views::filter(pred);
std::vector<int> v(std::ranges::begin(res), std::ranges::end(res));

// Bad: workaround with views::common is verbose and limited
std::vector<int> v(res | std::views::common);
```
**Solution:** Use `ranges::to` which handles all range types including non-common and non-copyable ranges.
```cpp
// Good: ranges::to handles iterator/sentinel mismatch
auto v = res | std::ranges::to<std::vector>();

// Good: works with move-only ranges like std::generator
auto m = fun() | std::ranges::to<std::map>();
```

### Element-wise insertion instead of range batch operations [R]
**Problem:** Looping to insert/append/prepend elements prevents container from optimizing bulk operations (pre-reservation, single allocation).
```cpp
// Bad: loop insertion at end
for (auto x : new_data)
{
    vec.push_back(x);
}

// Bad: loop insertion at position
for (auto x : data)
{
    vec.insert(vec.begin() + pos++, x);
}

// Bad: clear + reinsert for replacement
vec.clear();
for (auto x : new_data)
{
    vec.push_back(x);
}
```
**Solution:** Use C++23 range batch methods. Container can inspect range size for efficient pre-allocation.
```cpp
// Good: append_range for tail insertion
vec.append_range(new_data);

// Good: prepend_range for head insertion (deque, list)
deque.prepend_range(new_data);

// Good: insert_range for middle insertion
vec.insert_range(vec.begin() + pos, data);

// Good: assign_range for replacement (may reuse capacity)
vec.assign_range(new_data);
```

---

## Concurrency

### Atomic default `seq_cst` memory order [R]
**Problem:** `std::memory_order::seq_cst` is the default for atomic operations. It provides the strongest ordering guarantees but minimizes CPU optimization opportunities, often unnecessarily heavy for semantic correctness.
```cpp
std::atomic<int> x;

x++;                    // Defaults to `seq_cst`
x = 3;                  // Defaults to `seq_cst`
int a = x;              // Defaults to `seq_cst`
x.store(some_func());   // Defaults to `seq_cst`
```
**Solution:** Use explicit memory orders. Prefer `acquire`/`release` pairs for producer-consumer patterns, `relaxed` when only atomicity matters without ordering constraints.
```cpp
// Good: explicit acquire/release for synchronization
x.store(1, std::memory_order::release);
if (x.load(std::memory_order::acquire) == 1)
{
    // Happens-after the store
}

// Good: relaxed when only atomicity needed
x.fetch_add(1, std::memory_order::relaxed);
```
**Reference:** C++ Core Guidelines CP.119 - Use `memory_order` correctly.

### Broken `happens-before` with atomic memory orders [C]
**Problem:** Incorrect pairing of memory orders fails to establish `happens-before` relationships. Data races or stale reads result.
```cpp
// Bad: no synchronization established
std::atomic<int> x{0};

void producer()
{
    x.store(1, std::memory_order::relaxed);  // No release
}

void consumer()
{
    if (x.load(std::memory_order::relaxed))  // No acquire
    {
        // No guarantee producer's writes are visible
    }
}
```
**Solution:** Establish proper `happens-before` with `release`-`acquire` pairs. Use `seq_cst` for debugging or multi-variable ordering.
```cpp
// Good: release-acquire pair establishes happens-before
void producer()
{
    prepare_data();
    x.store(1, std::memory_order::release);
}

void consumer()
{
    if (x.load(std::memory_order::acquire) == 1)
    {
        // Guaranteed to see producer's prepare_data effects
        use_data();
    }
}
```
**Reference:** C++ Core Guidelines CP.119 - Use `memory_order` correctly; requires paired `release`/`acquire` for visibility.

### Mutex without RAII lock guards [C]
**Problem:** Manual `lock()`/`unlock()` is exception-unsafe. Early returns or exceptions leave mutex locked, causing deadlock.
```cpp
// Bad: exception-unsafe
void process()
{
    mtx.lock();
    if (error)
    {
        return;  // Deadlock: mutex remains locked
    }
    may_throw();  // Deadlock if throws
    mtx.unlock();
}
```
**Solution:** Use `std::lock_guard` or `std::unique_lock` RAII. Automatic unlock on all exit paths.
```cpp
// Good: RAII ensures unlock
void process()
{
    std::lock_guard<std::mutex> lock{mtx};
    if (error)
    {
        return;  // Safe: lock released
    }
    may_throw();  // Safe: lock released if throws
}
```
**Reference:** C++ Core Guidelines CP.43 - Minimize time spent in a critical section; use RAII for locking.

### Not using `scoped_lock` for multiple mutexes [R]
**Problem:** Locking multiple mutexes manually risks deadlock when order varies across threads.
```cpp
// Bad: potential deadlock if different lock order in different threads
std::lock_guard<std::mutex> lock1{mtx1};
std::lock_guard<std::mutex> lock2{mtx2};  // Deadlock if other thread locks 2 then 1
```
**Solution:** Use `std::scoped_lock` (C++17). Deadlock-free algorithm for multiple locks.
```cpp
// Good: deadlock-free multiple lock
std::scoped_lock lock{mtx1, mtx2};  // Locks in consistent order
```
**Reference:** C++ Core Guidelines CP.21 - Use `std::lock()` or `std::scoped_lock` to acquire multiple mutexes.

### `std::async` without explicit launch policy [?]
**Problem:** Default `std::launch` is implementation-defined. May defer execution unexpectedly, causing latency or blocking.
```cpp
// Bad: policy unclear
auto fut = std::async(some_task);  // May be deferred or async
```
**Solution:** Explicit launch policy. Use `std::launch::async` for true parallelism, `std::launch::deferred` for lazy evaluation.
```cpp
// Good: explicit policy
auto fut = std::async(std::launch::async, some_task);  // Guaranteed new thread
```
**Reference:** C++ Core Guidelines CP.42 - Prefer `std::async` for spawning tasks; be explicit about launch policy.

### Thread join without exception safety [C]
**Problem:** Missing `join()` before thread destruction terminates program. Manual `join()` is fragile on exception paths.
```cpp
// Bad: terminates if exception before join
void process()
{
    std::thread t{worker};
    may_throw();  // Terminates if throws here
    t.join();
}
```
**Solution:** Use RAII wrapper or `std::jthread` (C++20). Automatic join on destruction.
```cpp
// Good: jthread auto-joins
void process()
{
    std::jthread t{worker};  // C++20
    may_throw();  // Safe: t.join() called automatically
}
```
**Reference:** C++ Core Guidelines CP.25 - Prefer `std::jthread` over `std::thread`; ensure `join()` on all paths.

### Data race on shared mutable data [C]
**Problem:** Unsynchronized access to shared mutable data from multiple threads. Undefined behavior, silent corruption.
```cpp
// Bad: data race
int shared = 0;

void worker()
{
    for (int i = 0; i < 1000; ++i)
    {
        ++shared;  // Data race: concurrent read-modify-write
    }
}
```
**Solution:** Synchronize with mutex, use atomics, or eliminate sharing. Prefer immutability or thread-local data.
```cpp
// Good: atomic for simple counters
std::atomic<int> shared{0};

void worker()
{
    for (int i = 0; i < 1000; ++i)
    {
        shared.fetch_add(1, std::memory_order::relaxed);
    }
}

// Good: mutex for complex operations
std::mutex mtx;
int shared = 0;

void worker()
{
    for (int i = 0; i < 1000; ++i)
    {
        std::lock_guard<std::mutex> lock{mtx};
        ++shared;
    }
}
```
**Reference:** C++ Core Guidelines CP.31 - Pass data by value, pointer, or reference; don't share mutable data unsynchronized.

### Condition variable without predicate [C]
**Problem:** Spurious wakeups cause `wait()` to return without notification. Loop without predicate may proceed with invalid state.
```cpp
// Bad: spurious wakeup may proceed with !ready
std::unique_lock<std::mutex> lock{mtx};
cv.wait(lock);  // May wake up spuriously
use_data();     // Undefined if !ready
```
**Solution:** Always use predicate form of `wait()`. Ensures condition is actually satisfied.
```cpp
// Good: predicate ensures condition
std::unique_lock<std::mutex> lock{mtx};
cv.wait(lock, [] { return ready; });  // Re-checks on spurious wakeup
use_data();  // Safe: ready is true
```
**Reference:** C++ Core Guidelines CP.42 - Wait on condition variables using a predicate.

### `volatile` for synchronization [C]
**Problem:** `volatile` prevents compiler optimization but provides no atomicity or memory ordering guarantees. Insufficient for inter-thread communication.
```cpp
// Bad: volatile is not thread-safe
volatile int flag = 0;

void producer()
{
    data = 42;
    flag = 1;  // No happens-before guarantee
}

void consumer()
{
    while (flag == 0) {}  // May never see update
    use(data);  // May see stale data
}
```
**Solution:** Use `std::atomic` with proper memory ordering for synchronization.
```cpp
// Good: atomic with acquire-release
std::atomic<int> flag{0};

void producer()
{
    data = 42;
    flag.store(1, std::memory_order::release);
}

void consumer()
{
    while (flag.load(std::memory_order::acquire) == 0) {}
    use(data);  // Guaranteed to see 42
}
```
**Reference:** C++ Core Guidelines CP.55 - Don't use `volatile` for synchronization.

### Thread-local storage abuse [?]
**Problem:** `thread_local` data is hard to reason about, hides dependencies, complicates testing. Often used when explicit context passing suffices.
```cpp
// Bad: hidden dependency
thread_local int context_id;

void process()
{
    use(context_id);  // Where did this come from?
}
```
**Solution:** Prefer explicit context passing. Clearer dependencies, easier testing, works with coroutines.
```cpp
// Good: explicit context
void process(int context_id)
{
    use(context_id);  // Clear where it came from
}
```
**Reference:** C++ Core Guidelines CP.40 - Minimize thread-local storage; prefer explicit context passing.
