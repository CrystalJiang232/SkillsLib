# C++ Style Constraints

## Scope

This file governs **all AI-generated output** for the rt-cppeng skill:
- Documentation (pattern descriptions, rationales)
- Code examples (anti-patterns and solutions)
- Refactoring suggestions

---

## Part 1: Code Style Constraints (STRICT)

### 1. BRACKET PLACEMENT
Always new line after opening brace. Exemptions: short initializer lists and one-line functions/lambdas. **All control flow statements (`if`, `for`, `while`, `do`, `switch`) must use braces even for single-statement bodies.**

CORRECT (from server.cpp):
```cpp
int main()
{
    // code
}

if (condition)
{
    single_statement();
}

for (auto val : container)
{
    process(val);
}
```

Real example from Connection::close():
```cpp
void Connection::close(CloseMode mode)
{
    if(this->state.exchange(ConnState::Closing) == ConnState::Closing)
    {
        LOG_DEBUG("Connection already closing, deferring");
        return;
    }

    net::co_spawn(strand,
        [self = shared_from_this(), mode]() -> net::awaitable<void>
        {
            // ...
            co_await self->close_async(mode);
            // ...
        }, net::detached);
}
```

INCORRECT:
```cpp
int main() {
    // code
}

if (condition)
    single_statement();

for (auto val : container)
    process(val);
```

EXEMPTION (CORRECT):
```cpp
auto x = [](auto ch){return static_cast<std::byte>(ch);};
std::vector<int> vc{1,2,3};
```

### 2. NAMING CONVENTIONS
- Classes/structs: PascalCase (Connection, Server, Msg)
- Functions: snake_case for public, camelCase for private (send, read_header)
- Variables: abbreviations preferred (conn not connection, buf not buffer)
- Member variables: no trailing underscore, use distinct names or prefix if needed (`config`, `conf`, `cfg` OK; `config_` disallowed)
- Constants: UPPER_CASE or static constexpr inline

Correct examples (from server.hpp):  
```cpp
class ConnectionsMap
{
public:
    void insert(std::string id, std::shared_ptr<Connection> conn);
    void erase(std::string_view id);
    [[nodiscard]] std::shared_ptr<Connection> find(std::string_view id) const;
    [[nodiscard]] std::vector<std::shared_ptr<Connection>> snapshot() const;
    [[nodiscard]] size_t size() const;

private:
    mutable std::shared_mutex mtx;
    std::unordered_map<std::string, std::shared_ptr<Connection>> conns;
};

class Server
{
public:
    explicit Server(const Config& config);
    ~Server();
    
    Server(const Server&) = delete;
    Server& operator=(const Server&) = delete;
    
    [[nodiscard]] bool start();
    void stop();
    [[nodiscard]] bool is_running() const;
    
    [[nodiscard]] ThreadPool& cpu_pool() { return tp; }
    [[nodiscard]] const ThreadPool& cpu_pool() const { return tp; }
    
    [[nodiscard]] auth::AuthManager& auth() { return *auth_mgr; }
    [[nodiscard]] const auth::AuthManager& auth() const { return *auth_mgr; }
    [[nodiscard]] bool has_auth() const { return auth_mgr.has_value(); }

private:
    const Config& cfg;
    ServerMetrics mts;
    ThreadPool tp;
    std::optional<auth::AuthManager> auth_mgr;
    ConnectionsMap connections;
    std::unique_ptr<iocore::ContextPool> io_pool;
    std::atomic<bool> running{false};
};
```

### 3. COMMENTS
No inline comments between code lines. Use separate explanation blocks before functions if needed.

Exemption: Informative ones for functions, enumeration values or specific data type meaning/bit fields, etc. (ones that help during Intellisense; yet keep briefest, word-like as possible)

If unsure keep the comments there. Remove ones inline first (especially AI-generated).

Good comments examples (from server.hpp):
```cpp
// Graceful for queue-draining, abort for immediate shutdown
enum class CloseMode
{
    Graceful,
    Immediate
};
```

Real example from Connection class showing member documentation pattern:
```cpp
class Connection : public std::enable_shared_from_this<Connection>
{
public:
    struct FailureTracker
    {
        const size_t max_failures = 5;
        std::atomic<size_t> count{0};
        
        explicit FailureTracker(size_t max_fail = 5) : max_failures(max_fail) {}
        
        [[nodiscard("record() returns whether count has exceeded max failure after pre self-increment.")]]
        bool record()
        {
            return count.fetch_add(1, std::memory_order_acq_rel) + 1 >= max_failures;
        }

        void reset() { count.store(0, std::memory_order_release); }
        [[nodiscard]] bool threshold_exceeded() const 
        { 
            return count.load(std::memory_order_acquire) >= max_failures; 
        }
    };
    
    [[nodiscard("Do not discard send_error's value: caller is responsible for co_return \
                 upon this function returning true to prevent connection leakage. \
                 Use std::ignore or void cast for explicit schematics.")]]
    bool send_error(std::string_view err, CloseMode mode = CloseMode::Graceful, 
                    bool force_close = false);
```

Bad comments(DON'T):
```cpp
// INCORRECT: inline comments clutter code flow
int x = 5; // initialize x to 5
if (x > 0) { // check if x is positive
    do_something(); // call the function
}
```

### 4. INDENTATION
4 spaces, no tabs

### 5. MODERN C++
- Use `std::optional`, `std::expected` for error handling, avoid throwing exceptions
- Use `std::span` for non-owning views (for strings, use `std::string_view`), avoid c-refs to contiguous ranges, prefer spans (or constant spans) over refs/c-refs
- Use `std::ranges` for algorithms, along with `std::views` for pipeline operations. For container generation, prefer using `std::ranges::to`.
- Use C++20 `concepts` where applicable
- Use `auto` with structured bindings
- Use `<format>` and `std::print(ln)` for formatted output
- Use type aliases in-class actively

Real example from server.cpp showing std::ranges::to and std::views:
```cpp
std::vector<std::shared_ptr<Connection>> ConnectionsMap::snapshot() const
{
    std::shared_lock lock(mtx);
    return conns | std::views::values | std::ranges::to<std::vector>();
}

void Server::broadcast(const Msg& m, std::string_view exclude_id)
{
    for (auto& conn : connections.snapshot() | std::views::filter([this, exclude_id](auto&& x){
        return x && 
            x->get_id() != exclude_id && 
            x->is_authenticated();
        }))
    {
        conn->send_encrypted(m);
    }
}
```

Real example from connection.cpp showing std::optional for async results:
```cpp
net::awaitable<std::optional<Connection::IoResult>> Connection::read_with_timeout(
    net::mutable_buffer buf,
    std::chrono::seconds timeout)
{
    if(is_closing())
    {
        co_return std::nullopt;
    }
    
    // ...
    
    auto result = co_await (read_op() || timer_op());
    if(result.index() == 0)
    {
        co_return std::get<0>(result);
    }

    co_return std::nullopt;
}
```

### 6. ERROR HANDLING
Early return pattern, validate then proceed

Real example from context_pool.cpp:
```cpp
std::expected<void, ContextPoolError> ContextPool::Impl::start()
{
    if (running.load(std::memory_order_acquire))
    {
        return std::unexpected(ContextPoolError::AlreadyStarted);
    }
    
    auto ep = tcp::endpoint(net::ip::address_v4::any(), port);
    
    for (size_t i = 0; i < n_cores; ++i)
    {
        // ...
        core->acc.bind(ep, ec);
        if (ec)
        {
            return std::unexpected(ContextPoolError::AcceptorBindFailed);
        }
    }
    
    // ...
    return {};
}
```

### 7. ASYNC
Use `net::awaitable<void>` for coroutines, `co_await` for suspension, `co_return` for exit

Real example from connection.cpp showing coroutine patterns:
```cpp
net::awaitable<void> Connection::read_header()
{
    if(is_closing())
    {
        co_return;
    }

    read_buf.resize(4);

    auto result = co_await read_with_timeout(
        net::buffer(read_buf, 4),
        cfg.timeouts().read_timeout);
    
    if (!result)
    {
        error_and_close("Read header timeout");
        co_return;
    }
    
    if (auto e = result->ec)
    {
        // ...
        co_return;
    }
    
    // ...
    co_await read_body(len);
}
```

### 8. MEMORY

- Minimal raw pointer existance; for C-Style APIs, use custom deleter for `std::unique_ptr` to embed RAII semantics(primary option for single resource) or wrapper class(alternative).  
- For contiguous ranges prefer `std::span` over (c-)refs on containers(namely `std::vector`).  

Examples:  

```cpp
// INCORRECT: non-RAII, fragile and not exception-safe
FILE* fp = fopen("a.txt","r");  
fclose(fp);  

// CORRECT: Embed RAII semantics via custom deleter of `std::unique_ptr`
std::unique_ptr<FILE, decltype(&fclose)> fp(fopen("a.txt","r"), fclose);  

// CORRECT: Use wrapper class + proper RAII implementation, particularly for intricate scenarios  
// Optionally integrate both for clarity  

class MyClass
{
private:
    std::unique_ptr<FILE, decltype(&fclose)> fp;

public:
    MyClass(std::string filename, std::string mode): fp(fopen(filename,mode), fclose)
    {
        if(!fp)
        {
            // Error handling
        }
    }

    // No need for explicit cleanup in MyClass::~MyClass()  
    // If managing raw pointer, fclose(fp) is needed
};


void foo1(const std::vector<int>&); // BAD: Fixed to `std::vector<int>`, less agile than span  
void foo2(std::span<const int>); // GOOD  

```

Real example from connection.cpp showing RAII cleanup:
```cpp
Connection::~Connection() noexcept
{
    if (ss_local)
    {
        secure_clear(*ss_local);
    }
    if (ss_remote)
    {
        secure_clear(*ss_remote);
    }
    // ...
    sess.clear();
}
```

### 9. TEMPLATES
Abbreviated function templates with auto parameters where possible. Use `class`, not `typename` for template typename parameter declaration:

```cpp
template<class Ty> // CORRECT
template<typename Ty> // INCORRECT

template<std::unsigned_integral Ty> // CORRECT, PREFERRED IF SCHEMATIC CONSTRAINT NEEDED
template<class ...Tys> // CORRECT, ENCOURAGED FOR FORWARDING FUNCTIONS
```

Real example from threadpool.hpp showing template usage:
```cpp
template<class Fn>
auto submit(Fn&& fn) -> std::expected<std::invoke_result_t<Fn>, std::string>
{
    using Ret = std::invoke_result_t<Fn>;
    
    if (!running.load(std::memory_order_acquire))
    {
        return std::unexpected("ThreadPool stopped");
    }
    
    std::packaged_task<Ret()> task(std::forward<Fn>(fn));
    // ...
    return fut.get();
}
```

### 10. FORMATTING
Compact, dense code. Group related operations. Minimize vertical whitespace within functions.

Real example from server.cpp showing compact formatting:
```cpp
void ConnectionsMap::insert(std::string id, std::shared_ptr<Connection> conn)
{
    std::unique_lock lock(mtx);
    conns.insert_or_assign(std::move(id), std::move(conn));
}

void ConnectionsMap::erase(std::string_view id)
{
    std::unique_lock lock(mtx);
    conns.erase(std::string(id));
}

std::shared_ptr<Connection> ConnectionsMap::find(std::string_view id) const
{
    std::shared_lock lock(mtx);
    auto it = conns.find(std::string(id));
    return (it != conns.end()) ? it->second : nullptr;
}
```

---

## Part 2: Documentation Style Constraints

### Pattern Format Standard

All anti-patterns and solutions must follow this structure:

```markdown
### Pattern Name [Severity]
**Problem:** One-line description
```cpp
// problematic code
```
**Solution:** Directive or brief fix
```cpp
// corrected code (optional)
```

### Severity Markers

| Marker | Meaning | Usage |
|--------|---------|-------|
| `[C]` | Critical | Memory safety, undefined behavior, resource leaks |
| `[R]` | Recommended | Performance, maintainability, clarity improvements |
| `[?]` | Question | Design decision, context-dependent |

### Language Style

**Problem Description:**
- Concise, technical English
- Focus on the *mechanism* of failure
- Explain *why* the pattern is problematic

**Code Examples:**
- Minimal reproduction of the issue
- Include comments explaining the failure point
- Show realistic backend/server contexts where applicable
- **Must conform to Part 1 code style constraints**

**Solution Section:**
- Direct imperative ("Use X", "Replace with Y", "Migrate to Z")
- Provide corrected code when non-obvious
- Include brief rationale if the fix has trade-offs
- **Explicit comparisons preferred** (show "Bad: X / Better: Y")

### Content Boundaries

- Skill reference files: concise technical English; Chinese appears only as decorative entry/index headers
- Optional style sidelane: `interchange/language-style-guide.md` (clang-format complement; not mandatory)
- Never mix persona, blog flavor, or decorative prose into operational reference content

---

## Workflow Requirement

**Before generating any content for this skill:**

1. Read this style guide (`references/cpp.md`)
2. Review existing patterns in `references/patterns.md` for tone/examples
3. Ensure output matches:
   - Code style constraints (Part 1)
   - Documentation format (Part 2)

This applies to all output: pattern documentation, code refinement suggestions, checklist items, flagship examples.
