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

## MPMC Slot State Machine with Per-Slot Handshakes

**Pattern:** Bounded multi-producer multi-consumer ring where index claims use relaxed CAS and per-slot atomic states (`EMPTY → STORING → STORED → LOADING → EMPTY`) hand the payload between exactly one producer and one consumer.

```cpp
// Requires: <atomic>, <cstddef>, <utility>, <emmintrin.h> (x86)

enum class SlotState : unsigned char { EMPTY, STORING, STORED, LOADING };

template<class T, size_t CAPACITY>
class MpmcSlotRing
{
    static_assert((CAPACITY & (CAPACITY - 1)) == 0, "capacity must be a power of two");
    static constexpr size_t MASK = CAPACITY - 1;

    alignas(64) std::atomic<size_t> m_head{0};
    alignas(64) std::atomic<size_t> m_tail{0};
    alignas(64) std::atomic<SlotState> m_states[CAPACITY]{};
    alignas(64) T m_slots[CAPACITY];

public:
    template<class U>
    bool try_push(U&& value) noexcept
    {
        size_t head = m_head.load(std::memory_order_relaxed);
        for (;;)
        {
            if (head - m_tail.load(std::memory_order_relaxed) >= CAPACITY)
                return false;
            if (m_head.compare_exchange_strong(head, head + 1,
                                               std::memory_order_relaxed,
                                               std::memory_order_relaxed))
                break;
        }
        auto& state = m_states[head & MASK];
        SlotState expected = SlotState::EMPTY;
        while (!state.compare_exchange_strong(expected, SlotState::STORING,
                                              std::memory_order_acquire,
                                              std::memory_order_relaxed))
        {
            while (state.load(std::memory_order_relaxed) != SlotState::EMPTY)
                _mm_pause();
            expected = SlotState::EMPTY;
        }
        m_slots[head & MASK] = std::forward<U>(value);
        state.store(SlotState::STORED, std::memory_order_release);
        return true;
    }

    bool try_pop(T& out) noexcept
    {
        size_t tail = m_tail.load(std::memory_order_relaxed);
        for (;;)
        {
            if (m_head.load(std::memory_order_relaxed) - tail <= 0)
                return false;
            if (m_tail.compare_exchange_strong(tail, tail + 1,
                                               std::memory_order_relaxed,
                                               std::memory_order_relaxed))
                break;
        }
        auto& state = m_states[tail & MASK];
        SlotState expected = SlotState::STORED;
        while (!state.compare_exchange_strong(expected, SlotState::LOADING,
                                              std::memory_order_acquire,
                                              std::memory_order_relaxed))
        {
            while (state.load(std::memory_order_relaxed) != SlotState::STORED)
                _mm_pause();
            expected = SlotState::STORED;
        }
        out = std::move(m_slots[tail & MASK]);
        state.store(SlotState::EMPTY, std::memory_order_release);
        return true;
    }
};
```

**Why:** The per-slot state machine is the primitive behind bounded MPMC queues: producers and consumers claim positions with relaxed CAS, and the acquire/release slot transitions publish payload visibility without `seq_cst`. Each slot carries its own atomic state, so a producer and a consumer never touch the same transition.

**Applies to:** Order/message fan-in, shared-memory channels, any bounded concurrent handoff with a hard capacity ceiling.

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

## Graceful Degradation on External Input

**Pattern:** Decode untrusted input with per-field defaults and invalid-value guards — a missing or out-of-range field degrades to a safe sentinel instead of failing the path.

```cpp
// Untrusted input must not fail the path: missing fields degrade to safe
// sentinels, and out-of-range enums snap to Invalid. No exception path.
msg.CancelCount       = j.value( "CancelCount", -1 );
msg.TodayOpenPosition = j.value( "TodayOpenPosition", -1 );
msg.ModifiedRiskControlFlag = static_cast<RiskControlFlagType>(
    j.value( "ModifiedRiskControlFlag", RiskControlFlagType::RCF_Invalid ) );
if( msg.ModifiedRiskControlFlag >= RiskControlFlagType::RCF_MAX ||
    msg.ModifiedRiskControlFlag < RiskControlFlagType::RCF_Invalid )
{
    msg.ModifiedRiskControlFlag = RiskControlFlagType::RCF_Invalid;
}
```

**Why:** Decoding external input must not be able to fail the consuming path. Per-field defaults express "absent is safe", and the explicit range guard catches out-of-range or legacy values before they reach the hot path.

**Applies to:** Wire/JSON/config decoding, telemetry ingestion, admin-plane messages (must-not-fail operations).

---

## SPSC Slot Handshake with Release Publish

**Pattern:** Single-producer single-consumer ring where the producer fills a slot and publishes with a release store, and the consumer acquires before reading; the fast path is loads and stores only — no read-modify-write.

```cpp
// Requires: <atomic>, <cstddef>, <utility>

template<class T, size_t CAPACITY>
class SpscHandshakeRing
{
    static_assert((CAPACITY & (CAPACITY - 1)) == 0, "capacity must be a power of two");
    static constexpr size_t MASK = CAPACITY - 1;

    alignas(64) std::atomic<size_t> m_writeIdx{0};
    alignas(64) std::atomic<size_t> m_readIdx{0};
    alignas(64) T m_slots[CAPACITY];

public:
    template<class U>
    bool try_push(U&& value) noexcept
    {
        size_t const w = m_writeIdx.load(std::memory_order_relaxed);
        if (w - m_readIdx.load(std::memory_order_acquire) >= CAPACITY)
            return false;
        m_slots[w & MASK] = std::forward<U>(value);
        m_writeIdx.store(w + 1, std::memory_order_release);  // publish the fill
        return true;
    }

    bool try_pop(T& out) noexcept
    {
        size_t const r = m_readIdx.load(std::memory_order_relaxed);
        if (m_writeIdx.load(std::memory_order_acquire) - r == 0)
            return false;
        out = std::move(m_slots[r & MASK]);
        m_readIdx.store(r + 1, std::memory_order_release);   // hand the slot back
        return true;
    }
};
```

**Why:** In SPSC, no atomic exchange is needed: the producer's release store after the slot write and the consumer's acquire load before the slot read are the entire handshake. This is the zero-RMW fast path that MPMC generalizes with CAS.

**Applies to:** Market-data fan-out, order IPC rings, any one-writer/one-reader boundary with a capacity bound.

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

## Thread-Per-Role Topology with Pinned Workers

**Pattern:** Replace generic task pools on latency-critical paths with dedicated threads per role, each pinned once at startup, draining a bounded batch queue and sleeping with bounded backoff when idle.

```cpp
// Requires: <atomic>, <functional>, <list>, <mutex>, <thread>

class PinnedRoleWorker
{
public:
    PinnedRoleWorker(int cpu, std::function<void()> on_batch)
        : m_cpu(cpu), m_on_batch(std::move(on_batch)) {}

    void start()
    {
        m_thread = std::jthread([this] { run(); });
    }

    void post(std::function<void()> task)
    {
        std::lock_guard lock(m_mutex);
        if (m_tasks.size() < kMaxBatched)          // bounded, deterministic backlog
            m_tasks.push_back(std::move(task));
    }

private:
    void run()
    {
        pin_current_thread(m_cpu);                 // affinity set once, inside the thread
        for (;;)
        {
            std::list<std::function<void()>> batch;
            {
                std::lock_guard lock(m_mutex);
                batch.swap(m_tasks);               // drain the whole backlog in one batch
            }
            if (batch.empty())
            {
                std::this_thread::sleep_for(kIdleBackoff);   // bounded, not a busy spin
                continue;
            }
            for (auto& task : batch)
                std::invoke(m_on_batch, task);
        }
    }

    static constexpr size_t kMaxBatched = 1024;
    static constexpr auto kIdleBackoff = std::chrono::microseconds(50);

    int m_cpu;
    std::function<void()> m_on_batch;
    std::mutex m_mutex;
    std::list<std::function<void()>> m_tasks;
    std::jthread m_thread;
};
```

**Why:** A generic pool with `packaged_task` and futures pays per-task heap allocation, unbounded queues, and unpredictable scheduling. Role-dedicated pinned threads make the data path deterministic: one role per core, affinity set at thread start, batches amortize queue work, and idle sleep bounds CPU burn.

**Applies to:** Market-data receive, order routing, position reconciliation — any role where determinism matters more than generic load balancing.

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

## Edge-Triggered Threshold Alerting

**Pattern:** Fire an alert on the rising edge of a threshold crossing, latch until the condition recovers, and never re-fire while the condition persists.

```cpp
// Requires: <cstdint>

class EdgeTriggeredAlert
{
public:
    explicit EdgeTriggeredAlert(double limit) : m_limit(limit) {}

    // Returns true only on the transition into the alert state.
    bool update(double value) noexcept
    {
        bool const triggered = value >= m_limit;
        bool const fire = triggered && !m_latched;
        m_latched = triggered;
        return fire;
    }

    void reset() noexcept { m_latched = false; }

private:
    double m_limit;
    bool   m_latched = false;
};
```

**Why:** A level-triggered check (`if (value >= limit) alert();`) fires on every poll while the condition holds, flooding the risk or operations path. Edge triggering reports each crossing exactly once and latches until recovery, which suits per-duration rate limits, cancel-ratio limits, and circuit breakers.

**Applies to:** Risk limits, rate/cancel-ratio thresholds, stop-loss monitoring, alert deduplication.

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

## `std::optional` for Absent Configuration Values

**Pattern:** Model absent or malformed external values with `std::optional`; strict parsers return `std::nullopt`, and setters keep the previous field value on failure.

```cpp
// Absent or malformed values are std::nullopt; setters keep the previous
// field value when parsing fails (graceful defaulting, no exceptions).
std::optional<std::string> findValue( const ConfigValues&                values,
                                      std::initializer_list<const char*> aliases )
{
    for( const char* alias : aliases )
    {
        const auto iter = values.find( alias );
        if( iter != values.end() )
        {
            return iter->second;
        }
    }

    return std::nullopt;
}

template<typename ValueT>
std::optional<ValueT> parseInteger( const std::string& value )
{
    int64_t parsed = 0;
    if( !parseInt64( value, parsed ) ||
        parsed < std::numeric_limits<ValueT>::min() ||
        parsed > std::numeric_limits<ValueT>::max() )
    {
        return std::nullopt;
    }

    return static_cast<ValueT>( parsed );
}

void setInteger( const ConfigValues&                values,
                 std::initializer_list<const char*> aliases,
                 int&                               field )
{
    if( const auto value = findValue( values, aliases ) )
    {
        if( const auto parsed = parseInteger<int>( *value ) )
        {
            field = *parsed;
        }
    }
}
```

**Why:**
- Absence and malformed input are first-class: `std::nullopt` means "no usable value" — never a sentinel and never a thrown exception.
- Strict range validation happens at the boundary; a failed parse leaves the previous field value intact instead of corrupting state.
- No null pointers or magic defaults scattered through callers.

**Applies to:** Configuration parsing, API option lookup, any boundary where a value may be absent or invalid.

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

**Pattern:** Own OS resources with a class whose constructor acquires and whose destructor releases through a member owner — use sites never call free/unmap manually. `unique_ptr` with a custom deleter remains the right tool for C API init/free pairs; class-based RAII fits resources with richer state.

```cpp
class SharedMemBuffer
{
    struct Header
    {
        std::atomic<size_t> writePos{ 0 };
        size_t              size;
    };

public:
    explicit SharedMemBuffer( const std::string& name,
                              size_t             size,
                              bool               writer,
                              bool               create )
        : m_mmap( name,
                  roundToPow2( size ) + sizeof( Header ) + kSafeRemain,
                  writer,
                  create,
                  /*wait=*/true )
        , m_header( reinterpret_cast<Header*>( m_mmap.addr() ) )
    {
    }

    // The destructor releases the kernel resource through the m_mmap member;
    // use sites never call free/unmap manually.

    void* getWriteBuffer() noexcept
    {
        return bytes() + m_header->writePos.load( std::memory_order_relaxed );
    }

    size_t updateWritePos( size_t len ) noexcept
    {
        const size_t pos = m_header->writePos.load( std::memory_order_relaxed );
        if( pos >= m_bufferSize )
        {
            return 0; // explicit bounds clamp instead of a silent wrap
        }
        m_header->writePos.store( pos + len, std::memory_order_release ); // publish
        return len;
    }

private:
    MmapResource m_mmap;      // RAII owner of the kernel resource
    Header*      m_header;
    size_t       m_bufferSize;
};
```

**Why:**
- The resource is acquired in the constructor and released by the member's destructor — cleanup happens even on early returns and exceptions.
- Cursors shared across processes are `std::atomic` with a release-store publish, and bounds are checked explicitly rather than clamped silently.
- The owning member keeps the acquire/release pairing in one place instead of at every use site.

**Applies to:** Shared-memory regions, file mappings, descriptors, any OS resource with acquire/release semantics.

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

**Pattern:** Validate constraints at the boundary and return `std::nullopt` on pass or a structured one-string report on violation.

```cpp
// Pass = std::nullopt; violation = structured one-string report with the
// instrument, current value, and threshold.
std::optional<std::string> checkSelfTrade( const Trade*      trade,
                                           const Instrument* inst )
{
    if( !trade || !inst )
    {
        return std::nullopt;
    }

    const std::string hint = instrumentHint( inst );
    if( hint.empty() )
    {
        return std::nullopt;
    }

    // ... per-instrument risk state accumulates here ...
    if( selfTradeVolume >= maxSelfTrade )
    {
        return std::format(
            "=== self-trade ===\n"
            "[InstrumentID: {}]\n"
            "[Current SelfTrade Volume: {}]\n"
            "[Max: {}]",
            inst->id,
            selfTradeVolume,
            maxSelfTrade );
    }

    return std::nullopt;
}
```

**Why:**
- `std::optional<std::string>` encodes both outcomes in the type: no value means pass, an engaged string is the full violation report.
- The report carries the entity, current value, and threshold, so callers can act on the reason without re-deriving state.
- The pass path stays allocation-light; report building happens only on violation.

**Applies to:** Risk gates, rate/ratio limits, config and input validation where the caller needs the reason, not just a boolean.

---

## Case-Insensitive String Comparison with Whitelist Lookup

**Pattern:** Normalize the input once with `toupper`/`tolower`, then compare or look it up in a set.

```cpp
// Whitelist lookup: normalize once, then O(1) set lookup.
std::string upperMac( mac );
for( auto& ch : upperMac )
{
    ch = static_cast<char>( std::toupper( static_cast<unsigned char>( ch ) ) );
}
const bool allowed = config.getMacList().count( upperMac ) > 0;
```

**Why:**
- One normalization pass turns a case-insensitive comparison into a single set lookup instead of repeated string compares.
- The `unsigned char` cast keeps `toupper` well-defined for all byte values.
- Ranges pipelines remain the declarative choice where the codebase already uses them; the loop form is the same one-allocation cost without the pipeline machinery.

**Applies to:** Whitelists (MAC/IP/user lists), login checks, case-insensitive lookups on non-hot paths.

---

## Summary Table

| Pattern | C++ Standard | Primary Benefit |
|---------|--------------|-----------------|
| `shared_from_this` capture | C++11 | Lifetime safety |
| Awaitable races | C++20 | Clean async composition |
| MPMC slot state machine | C++11 | Bounded lock-free handoff |
| Secure memory clearing | C++11 | Security hardening |
| Pimpl + `unique_ptr` | C++11 | Encapsulation |
| `std::expected` | C++23 | Explicit error handling |
| Strand dispatch | C++20 | Ordered async execution |
| Ranges pipeline | C++23 | Composable transformations |
| Defaulted decode | C++17 | Resilience |
| SPSC slot handshake | C++11 | Zero-RMW producer/consumer publish |
| `std::expected` factory | C++23 | Fallible construction |
| Thread-per-role topology | C++20 | Deterministic pinned workers |
| Weak pointer registry | C++11 | Non-owning observation |
| Edge-triggered alerting | C++11 | Alert deduplication |
| `std::formatter` spec | C++23 | Type-safe formatting |
| `optional` absent values | C++17 | Defensive parsing |
| Enum class state machine | C++11 | Type-safe states |
| RAII resource wrapper | C++11 | Resource safety |
| Secret combination | C++20 | Key derivation |
| Constraint validation | C++17 | Structured reporting |
| Case-insensitive compare | C++11 | Whitelist lookup |

---

*Production-derived; patterns generalized from high-frequency trading infrastructure.*
