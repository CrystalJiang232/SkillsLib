# C++ Flagship Code Reference

Production-ready code demonstrations for Modern C++ idioms.

---

## Coroutine Safety with `enable_shared_from_this`

**Pattern:** Capture `shared_from_this()` in coroutine lambdas to ensure lifetime safety across suspension points.

```cpp
class Connection : public std::enable_shared_from_this<Connection>
{
public:
    void start()
    {
        net::co_spawn(strand,
            [self = shared_from_this()]() -> net::awaitable<void>
            {
                co_await self->read_header();
            },
            net::detached);
    }
};
```

**Why:** The coroutine may outlive the calling scope. Raw `this` would dangle if the object is destroyed while the coroutine is suspended.

**Applies to:** Any async operation that suspends and resumes on a different execution context.

---

## Awaitable Race Composition

**Pattern:** Use `operator||` to race two awaitables — first to complete wins.

```cpp
using net::experimental::awaitable_operators::operator||;

net::awaitable<std::optional<IoResult>> read_with_timeout(
    net::mutable_buffer buf,
    std::chrono::seconds timeout)
{
    net::steady_timer timer(strand);
    timer.expires_after(timeout);
    
    auto read_op = [&]() -> net::awaitable<IoResult>
    {
        auto [ec, n] = co_await net::async_read(socket, buf, 
            net::as_tuple(net::use_awaitable));
        timer.cancel();
        co_return IoResult{ec, n};
    };
    
    auto timer_op = [&]() -> net::awaitable<void>
    {
        std::ignore = co_await timer.async_wait(
            net::as_tuple(net::use_awaitable));
        co_return;
    };
    
    auto result = co_await (read_op() || timer_op());
    if (result.index() == 0)
        co_return std::get<0>(result);
    co_return std::nullopt;
}
```

**Why:** Declarative timeout handling without callback hell. The result is a `std::variant`-like discriminated union.

**Applies to:** I/O timeouts, connection attempts, cancellation scenarios.

---

## Atomic State Machine with Memory Ordering

**Pattern:** Explicit `acquire`/`release` pairs for thread-safe state transitions.

```cpp
enum class ConnState : uint8_t { Connected, Handshaking, Established, Closing };

class Connection
{
    std::atomic<ConnState> state;
    
public:
    ConnState get_state() const 
    { 
        return state.load(std::memory_order_acquire); 
    }
    
    void set_state(ConnState new_state) 
    { 
        state.store(new_state, std::memory_order_release); 
    }
    
    bool transition_to_closing()
    {
        // Atomic test-and-set
        return state.exchange(ConnState::Closing, std::memory_order_acq_rel) 
            != ConnState::Closing;
    }
};
```

**Why:** `acquire`/`release` establish happens-before relationships without the cost of `seq_cst`. `exchange` enables lock-free state transitions.

**Applies to:** Connection lifecycles, protocol state machines, thread coordination.

---

## Secure Memory Clearing

**Pattern:** Explicitly overwrite cryptographic secrets before deallocation.

```cpp
Connection::~Connection() noexcept
{
    if (ss_local)  secure_clear(*ss_local);
    if (ss_remote) secure_clear(*ss_remote);
    if (kp)        secure_clear(kp->secret_key);
    
    sess.clear();
}
```

**Why:** Standard `free`/`delete` does not zero memory. Secrets remain in RAM until overwritten, vulnerable to memory inspection attacks.

**Applies to:** Cryptographic keys, authentication tokens, sensitive session data.

---

## Pimpl with `unique_ptr`

**Pattern:** Hide implementation details while maintaining move semantics.

```cpp
// header.hpp
class ContextPool
{
public:
    ContextPool(size_t n_cores, uint16_t port, ConnectionFactory factory);
    ~ContextPool();
    
    ContextPool(const ContextPool&) = delete;
    ContextPool& operator=(const ContextPool&) = delete;
    
    ContextPool(ContextPool&&) noexcept = default;
    ContextPool& operator=(ContextPool&&) noexcept = default;
    
private:
    class Impl;
    std::unique_ptr<Impl> impl;
};

// implementation.cpp
class ContextPool::Impl { /* ... */ };

ContextPool::ContextPool(size_t n, uint16_t port, ConnectionFactory f)
    : impl(std::make_unique<Impl>(n, port, std::move(f))) {}

ContextPool::~ContextPool() = default;
```

**Why:** Compile-time firewall — changes to `Impl` don't recompile translation units including the header. `unique_ptr` provides automatic cleanup.

**Applies to:** Large classes, platform-specific implementations, API stability boundaries.

---

## `std::expected` for Explicit Errors

**Pattern:** Return errors as values, not exceptions.

```cpp
enum class ContextPoolError
{
    Ok = 0,
    AlreadyStarted,
    AcceptorBindFailed,
    ThreadCreateFailed
};

class ContextPool
{
public:
    [[nodiscard]] std::expected<void, ContextPoolError> start();
};

// Usage
if (auto result = pool.start(); !result)
{
    switch (result.error())
    {
        case ContextPoolError::AcceptorBindFailed:
            LOG_ERROR("Port already in use");
            break;
        // ...
    }
}
```

**Why:** Errors are part of the type system — callers cannot ignore them. No exception overhead for expected failure paths.

**Applies to:** Resource initialization, I/O operations, validation routines.

---

## Strand-Synchronized Dispatch

**Pattern:** Serialize operations on an executor without holding locks across suspension points.

```cpp
void Connection::send(const Msg& msg)
{
    net::dispatch(strand, [this, self = shared_from_this(), msg]()
    {
        bool should_spawn = false;
        {
            std::lock_guard lock(write_mtx);
            bool was_empty = write_queue.empty();
            write_queue.push_back(msg);
            
            if (!write_in_progress.load(std::memory_order_acquire) && was_empty)
            {
                write_in_progress.store(true, std::memory_order_release);
                should_spawn = true;
            }
        }
        
        if (should_spawn)
        {
            net::co_spawn(strand, [this, self]() -> net::awaitable<void>
            {
                co_await write();
            }, net::detached);
        }
    });
}
```

**Why:** Strand guarantees serialization — no two handlers on the same strand execute concurrently. Lock is held only for the critical section (queue manipulation), not across I/O.

**Applies to:** Multi-threaded I/O, producer-consumer queues, ordered message processing.

---

## Ranges Pipeline for Data Transformation

**Pattern:** Composable, lazy data transformation chains.

```cpp
auto plaintext = json::serialize(response) 
    | std::views::transform([](char c) { return static_cast<uint8_t>(c); })
    | std::ranges::to<std::vector<uint8_t>>();

auto payload = *encrypted 
    | std::views::transform(int2byte) 
    | std::ranges::to<Msg::payload_t>();
```

**Why:** Self-documenting data flow. Lazy evaluation until `ranges::to` materializes. No intermediate allocations.

**Applies to:** Protocol serialization, encoding/decoding, data normalization.

---

## Graceful Degradation with `value_or`

**Pattern:** Pre-computed fallback for failure cases.

```cpp
static const Msg decay_msg = *msg::make(
    bytes::to_bytes("Unknown error"), 
    plaintext_error
);

auto err_msg = msg::make(bytes::to_bytes(err), plaintext_error)
    .value_or(decay_msg);

send(err_msg);  // Always succeeds, even if make() failed
```

**Why:** Network servers must be resilient. Even error-message construction can fail — have a fallback ready.

**Applies to:** Error handling, logging, telemetry (must-not-fail operations).

---

## Atomic Exchange for Lock-Free State Transitions

**Pattern:** Test-and-set with a single atomic operation.

```cpp
void Connection::close(CloseMode mode)
{
    // Only the first caller succeeds
    if (state.exchange(ConnState::Closing, std::memory_order_acq_rel) 
        == ConnState::Closing)
    {
        LOG_DEBUG("Connection already closing, deferring");
        return;
    }
    
    net::co_spawn(strand,
        [self = shared_from_this(), mode]() -> net::awaitable<void>
        {
            co_await self->close_async(mode);
        }, net::detached);
}
```

**Why:** `exchange` atomically reads and writes. No race between test and set. Idempotent operation — safe to call multiple times.

**Applies to:** Connection teardown, resource cleanup, one-shot initialization.

---

## `std::expected` Factory Pattern

**Pattern:** Static factory method returning `std::expected` for fallible construction with complex initialization logic.

```cpp
class AuthManager
{
public:
    [[nodiscard]] static std::expected<AuthManager, std::string> create(
        std::string_view db_path, ThreadPool& tp);

private:
    AuthManager(UserDB db, ThreadPool& tp);  // Private ctor
};

// Implementation
std::expected<AuthManager, std::string> AuthManager::create(
    std::string_view db_path, ThreadPool& tp)
{
    auto db_result = UserDB::open(db_path);
    if (!db_result)
        return std::unexpected(db_result.error());
    
    if (!db_result->init_schema())
        return std::unexpected("Failed to initialize database schema");
    
    return AuthManager(std::move(*db_result), tp);
}
```

**Why:** 
- Constructor cannot return errors (exceptions aside). Factory with `std::expected` makes failure explicit and type-safe.
- Private constructor enforces factory usage — callers cannot construct directly and bypass validation.
- Error messages are rich strings, not just error codes.

**Applies to:** Database connections, resource initialization, any complex setup that can fail.

---

## Thread Pool with `packaged_task` Submission

**Pattern:** Submit work to a thread pool and receive results via `std::expected` + `std::packaged_task`.

```cpp
class ThreadPool
{
public:
    template<class Fn>
    auto submit(Fn&& fn) -> std::expected<std::invoke_result_t<Fn>, std::string>
    {
        using Ret = std::invoke_result_t<Fn>;
        
        if (!running.load(std::memory_order_acquire))
            return std::unexpected("ThreadPool stopped");
        
        std::packaged_task<Ret()> task(std::forward<Fn>(fn));
        auto fut = task.get_future();
        
        net::post(pool_exec, 
            [t = std::make_shared<std::packaged_task<Ret()>>(std::move(task))] { 
                std::invoke(*t); 
            });
        
        return fut.get();
    }

private:
    net::io_context pool_ctx;
    net::executor_work_guard<net::io_context::executor_type> work_guard;
    std::vector<std::jthread> workers;
};
```

**Why:**
- `packaged_task` bridges functors and futures — enables any callable to return a value asynchronously.
- `shared_ptr` capture ensures the task outlives the lambda until execution.
- `std::expected` wrapper handles both executor errors (pool stopped) and task exceptions.

**Applies to:** CPU-bound work offloading, parallel algorithms, async task systems.

---

## Weak Pointer Registry for Non-Owning Observation

**Pattern:** Store `weak_ptr` in a registry to track objects without preventing their destruction.

```cpp
class CoreConnectionMap
{
public:
    void insert(size_t core_id, std::shared_ptr<CoreConnection> conn);
    std::shared_ptr<CoreConnection> find(std::string_view conn_id) const;
    
    std::vector<std::shared_ptr<CoreConnection>> snapshot() const
    {
        std::shared_lock lock(mtx);
        std::vector<std::shared_ptr<CoreConnection>> result;
        result.reserve(conns.size());
        
        for (const auto& [id, weak] : conns)
        {
            if (auto sp = weak.lock())
                result.push_back(sp);  // Only alive connections
        }
        return result;
    }

private:
    mutable std::shared_mutex mtx;
    std::unordered_map<std::string, std::weak_ptr<CoreConnection>> conns;
};
```

**Why:**
- Registry doesn't extend object lifetime — connections can die naturally when last owner releases them.
- `snapshot()` filters expired weak_ptrs implicitly — callers only get valid pointers.
- Prevents circular ownership between registry and connections.

**Applies to:** Connection pools, session managers, any observer registry where owners control lifetime.

---

## Atomic Failure Tracker with Threshold

**Pattern:** Self-contained atomic counter with configurable threshold for failure-based circuit breaking.

```cpp
struct FailureTracker
{
    const size_t max_failures = 5;
    std::atomic<size_t> count{0};
    
    explicit FailureTracker(size_t max_fail = 5) : max_failures(max_fail) {}
    
    [[nodiscard("Returns whether threshold exceeded after increment")]]
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
```

**Why:**
- Thread-safe failure counting without external synchronization.
- `fetch_add` returns previous value — atomic read-modify-write in one operation.
- `[[nodiscard]]` on `record()` forces callers to handle threshold result.

**Applies to:** Rate limiting, circuit breakers, retry logic, authentication lockouts.

---

## `std::formatter` Specialization for Custom Types

**Pattern:** Specialize `std::formatter` for third-party types (e.g., Boost.Asio sockets) to enable `std::format`.

```cpp
template<>
struct std::formatter<tcp::socket>
{
    constexpr auto parse(std::format_parse_context& fpc)
    {
        return fpc.begin();  // No format specifiers supported
    }

    auto format(const tcp::socket& socket, std::format_context& fc) const
    {
        return std::format_to(fc.out(), "{}:{}",
            socket.remote_endpoint().address().to_string(),
            socket.remote_endpoint().port());
    }
};

// Usage
std::string id = std::format("{}", sock);  // "192.168.1.1:54321"
```

**Why:**
- Enables type-safe formatting for types you don't own (third-party library types).
- Integrates with `std::print`, `std::format`, logging frameworks.
- Cleaner than ad-hoc `to_string()` functions scattered through codebase.

**Applies to:** Wrapping third-party types, domain-specific value types, complex identifiers.

---

## `std::optional` for Lazy Member Initialization

**Pattern:** Use `std::optional` for members that are not valid at construction but become valid later.

```cpp
class Connection
{
    std::optional<crypto::Kyber768::keypair_t> kp;
    std::optional<crypto::Kyber768::shared_secret_t> ss_local;
    std::optional<crypto::Kyber768::shared_secret_t> ss_remote;
    std::optional<net::signal_set> signals;
    std::optional<auth::AuthManager> auth_mgr;
    
public:
    void complete_handshake()
    {
        auto kp_result = kem.generate_keypair();
        if (kp_result)
            kp = std::move(*kp_result);  // Now valid
    }
    
    bool has_session_key() const { return sess.is_established(); }
};
```

**Why:**
- Expresses "may not exist yet" in the type system — no null pointers or sentinel values.
- Destructor automatically handles cleanup when `optional` is reset or destroyed.
- Clearer than raw pointers with manual lifetime management.

**Applies to:** Handshake state, deferred initialization, protocol state machines.

---

## Connection State Machine with Enum Class

**Pattern:** Strongly-typed enum for connection lifecycle states with atomic transitions.

```cpp
enum class ConnState : uint8_t
{
    Connected,
    Handshaking,
    Established,
    Authenticated,
    Closing,
    Rekeying,
};

class Connection
{
    std::atomic<ConnState> state;
    
public:
    [[nodiscard]] ConnState getstate() const 
    { 
        return state.load(std::memory_order_acquire); 
    }
    
    void setstate(ConnState newstate) 
    { 
        state.store(newstate, std::memory_order_release); 
    }
    
    [[nodiscard]] bool is_authenticated() const 
    { 
        return state.load(std::memory_order_acquire) == ConnState::Authenticated; 
    }
};
```

**Why:**
- `enum class` prevents implicit conversions — state comparisons are type-safe.
- `uint8_t` underlying type minimizes memory for many connections.
- Atomic with explicit memory order enables lock-free state checks.

**Applies to:** Protocol state machines, connection lifecycles, async workflows.

---

## RAII Wrapper for C Library Handles

**Pattern:** Use `std::unique_ptr` with custom deleter to manage C library resources (OpenSSL, liboqs, libsodium).

```cpp
class Kyber768
{
    std::unique_ptr<OQS_KEM, decltype(&OQS_KEM_free)> kem;

public:
    Kyber768()
        : kem(OQS_KEM_new("Kyber768"), OQS_KEM_free)
    {
        if (!kem)
            throw std::runtime_error("Kyber768 not available");
    }
};
```

**Why:**
- C libraries require explicit cleanup. `unique_ptr` with custom deleter ensures cleanup even on early returns/exceptions.
- Prevents resource leaks in error-heavy code.
- `decltype(&deleter_func)` captures the function pointer type automatically.

**Applies to:** OpenSSL contexts, database handles, file descriptors, any C API with init/free pairs.

---

## Cryptographic Secret Combination with Hashing

**Pattern:** Combine multiple secrets using a cryptographic hash function for key derivation.

```cpp
shared_secret_t combine_secrets(
    std::span<const uint8_t> secret_a,
    std::span<const uint8_t> secret_b)
{
    std::array<uint8_t, 64> combined{};
    std::copy_n(secret_a.begin(), std::min(secret_a.size(), shared_secret_size), combined.begin());
    std::copy_n(secret_b.begin(), std::min(secret_b.size(), shared_secret_size), combined.begin() + shared_secret_size);

    shared_secret_t result{};
    // ... hash combined into result ...
    return result;
}
```

**Why:**
- Combines bidirectional shared secrets into a single session key.
- Uses `std::span` for flexible input, `std::array` for fixed-size intermediate.
- `std::min` prevents buffer overruns when input sizes vary.

**Applies to:** Key derivation, session key establishment, secret sharing protocols.

---

## Constraint Validation with Structured Reporting

**Pattern:** Validate multiple constraints and return detailed failure reports.

```cpp
std::expected<void, std::string> check_password(std::string_view password, std::string_view ref_username)
{
    std::vector<std::pair<std::string, bool>> cons
    {
        {"Minimum length: 8 characters", password.size() >= 8},
        {"At least three character types", count_chart_fn(password) >= 3},
        {"Does not contain username", !password.contains(ref_username)}
    };

    std::string ret;
    bool pass = true;
    for(auto&& [s, b] : cons)
    {
        ret += std::format("[{}] {}\n", b ? "√" : "×", s);
        pass &= b;
    }

    if(!pass)
        return std::unexpected(ret);
    return {};
}
```

**Why:**
- Collects all validation results before failing — users see all issues at once.
- Structured output with checkmarks/crosses improves UX.
- Lambda encapsulates complex validation logic cleanly.

**Applies to:** Form validation, configuration validation, password policies, input sanitization.

---

## Case-Insensitive String Comparison with Ranges

**Pattern:** Transform string to lowercase for case-insensitive comparison.

```cpp
Level parse_level(std::string_view lvl)
{
    std::string lstr = lvl 
        | std::views::transform([](auto c) -> char { return std::tolower(c); }) 
        | std::ranges::to<std::string>();

    if (lstr == "debug") return Level::Debug;
    if (lstr == "warn") return Level::Warn;
    if (lstr == "error") return Level::Error;
    return Level::Info;
}
```

**Why:**
- Ranges pipeline is declarative and composable.
- Explicit `-> char` return type prevents `std::tolower` overload ambiguity.
- Allocates once — acceptable for non-hot paths (configuration parsing).

**Applies to:** Configuration parsing, command-line arguments, case-insensitive lookups.

---

## Summary Table

| Pattern | C++ Standard | Primary Benefit |
|---------|--------------|-----------------|
| `shared_from_this` capture | C++11 | Lifetime safety |
| Awaitable races | C++20 | Clean async composition |
| Atomic state machine | C++11 | Lock-free synchronization |
| Secure memory clearing | C++11 | Security hardening |
| Pimpl + `unique_ptr` | C++11 | Encapsulation |
| `std::expected` | C++23 | Explicit error handling |
| Strand dispatch | C++20 | Ordered async execution |
| Ranges pipeline | C++23 | Composable transformations |
| `value_or` fallback | C++17 | Resilience |
| Atomic exchange | C++11 | Lock-free state transitions |
| `std::expected` factory | C++23 | Fallible construction |
| Thread pool submission | C++20 | Async CPU work |
| Weak pointer registry | C++11 | Non-owning observation |
| Atomic failure tracker | C++11 | Circuit breaking |
| `std::formatter` spec | C++23 | Type-safe formatting |
| `optional` lazy init | C++17 | Deferred construction |
| Enum class state machine | C++11 | Type-safe states |
| RAII C library wrapper | C++11 | Resource safety |
| Secret combination | C++20 | Key derivation |
| Constraint validation | C++23 | Structured reporting |
| Case-insensitive compare | C++20 | Ranges transform |

---

*Source: TiaoMeng codebase — https://github.com/CrystalJiang232/TiaoMeng*
