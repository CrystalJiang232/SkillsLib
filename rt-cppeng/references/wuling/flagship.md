# 五灵应象决 — Flagship Code Examples

> 以五灵之名，应天地之象。此卷为 HFT 与高性能系统之旗舰代码。

---

## 木灵·青龙 — Memory & Cache (生发)

### Cache-Aligned Struct

Hot record layouts ordered by descending field size, and cross-thread control blocks whose mutable indices never share a cache line.

```cpp
// Requires: <atomic>, <cstddef>, <cstdint>

#if defined( __powerpc64__ )
constexpr size_t CACHE_LINE = 128;
#elif defined( __s390x__ )
constexpr size_t CACHE_LINE = 256;
#else
constexpr size_t CACHE_LINE = 64;
#endif

// Hot record: order fields by descending size so natural layout needs no padding.
struct alignas( CACHE_LINE ) MarketTick
{
    int64_t  price;
    int64_t  bidQty;
    int64_t  askQty;
    uint32_t seq;
    uint16_t symbolId;
    uint8_t  side;
};
static_assert( sizeof( MarketTick ) <= 2 * CACHE_LINE );

// Cross-thread mutable state: each index occupies its own cache line.
struct RingControl
{
    alignas( CACHE_LINE ) std::atomic<size_t> m_writeIdx{ 0 };
    alignas( CACHE_LINE ) std::atomic<size_t> m_readIdx{ 0 };
};
static_assert( sizeof( RingControl ) >= 2 * CACHE_LINE );
```

---

## 火灵·朱雀 — Lock-free & Concurrency (炎上)

### SPSC Ring Buffer

Fixed-capacity single-producer single-consumer ring using per-slot sequence numbers; the hot path is atomic loads and stores only, no read-modify-write.

```cpp
// Requires: <atomic>, <cstddef>, <utility>

template<class T, size_t CAPACITY>
class SpscRing
{
    static_assert( ( CAPACITY & ( CAPACITY - 1 ) ) == 0, "capacity must be a power of two" );
    static_assert( CAPACITY > 0 );
    static constexpr size_t MASK = CAPACITY - 1;

    std::atomic<size_t> m_seq[CAPACITY];
    alignas( CACHE_LINE ) std::atomic<size_t> m_writeIdx{ 0 };
    alignas( CACHE_LINE ) std::atomic<size_t> m_readIdx{ 0 };
    alignas( CACHE_LINE ) T m_slots[CAPACITY];

public:
    SpscRing()
    {
        for( size_t i = 0; i < CAPACITY; ++i )
            m_seq[i].store( i, std::memory_order_relaxed );
    }

    template<class U>
    bool try_push( U&& value ) noexcept
    {
        size_t const w = m_writeIdx.load( std::memory_order_relaxed );
        size_t const pos = w & MASK;
        if( m_seq[pos].load( std::memory_order_acquire ) != w )
            return false;
        m_slots[pos] = std::forward<U>( value );
        m_seq[pos].store( w + 1, std::memory_order_release );
        m_writeIdx.store( w + 1, std::memory_order_relaxed );
        return true;
    }

    bool try_pop( T& out ) noexcept
    {
        size_t const r = m_readIdx.load( std::memory_order_relaxed );
        size_t const pos = r & MASK;
        if( m_seq[pos].load( std::memory_order_acquire ) != r + 1 )
            return false;
        out = std::move( m_slots[pos] );
        m_seq[pos].store( r + CAPACITY, std::memory_order_release );
        m_readIdx.store( r + 1, std::memory_order_relaxed );
        return true;
    }
};
```

### Lock-Free MPMC Queue

Bounded multi-producer multi-consumer ring: index claims via relaxed CAS, then per-slot atomic state transitions (EMPTY/STORING/STORED/LOADING) hand the payload between exactly one producer and one consumer.

```cpp
// Requires: <atomic>, <cstddef>, <thread>, <utility>, <emmintrin.h> (x86)

enum class SlotState : unsigned char
{
    EMPTY,
    STORING,
    STORED,
    LOADING
};

inline void spin_loop_pause() noexcept
{
#if defined( __x86_64__ ) || defined( __i386__ )
    _mm_pause();
#else
    std::this_thread::yield();
#endif
}

template<class T, size_t CAPACITY>
class MpmcRing
{
    static_assert( ( CAPACITY & ( CAPACITY - 1 ) ) == 0, "capacity must be a power of two" );
    static_assert( CAPACITY > 0 );
    static constexpr size_t MASK = CAPACITY - 1;

    alignas( CACHE_LINE ) std::atomic<size_t> m_head{ 0 };
    alignas( CACHE_LINE ) std::atomic<size_t> m_tail{ 0 };
    alignas( CACHE_LINE ) std::atomic<SlotState> m_states[CAPACITY]{};
    alignas( CACHE_LINE ) T m_slots[CAPACITY];

public:
    template<class U>
    bool try_push( U&& value ) noexcept
    {
        size_t head = m_head.load( std::memory_order_relaxed );
        for( ;; )
        {
            if( head - m_tail.load( std::memory_order_relaxed ) >= CAPACITY )
                return false;
            if( m_head.compare_exchange_strong( head, head + 1, std::memory_order_relaxed,
                                                std::memory_order_relaxed ) )
                break;
        }
        std::atomic<SlotState>& state = m_states[head & MASK];
        SlotState expected = SlotState::EMPTY;
        while( !state.compare_exchange_strong( expected, SlotState::STORING,
                                               std::memory_order_acquire, std::memory_order_relaxed ) )
        {
            while( state.load( std::memory_order_relaxed ) != SlotState::EMPTY )
                spin_loop_pause();
            expected = SlotState::EMPTY;
        }
        m_slots[head & MASK] = std::forward<U>( value );
        state.store( SlotState::STORED, std::memory_order_release );
        return true;
    }

    bool try_pop( T& out ) noexcept
    {
        size_t tail = m_tail.load( std::memory_order_relaxed );
        for( ;; )
        {
            if( m_head.load( std::memory_order_relaxed ) - tail <= 0 )
                return false;
            if( m_tail.compare_exchange_strong( tail, tail + 1, std::memory_order_relaxed,
                                                std::memory_order_relaxed ) )
                break;
        }
        std::atomic<SlotState>& state = m_states[tail & MASK];
        SlotState expected = SlotState::STORED;
        while( !state.compare_exchange_strong( expected, SlotState::LOADING,
                                               std::memory_order_acquire, std::memory_order_relaxed ) )
        {
            while( state.load( std::memory_order_relaxed ) != SlotState::STORED )
                spin_loop_pause();
            expected = SlotState::STORED;
        }
        out = std::move( m_slots[tail & MASK] );
        state.store( SlotState::EMPTY, std::memory_order_release );
        return true;
    }
};
```

---

## 土灵·麒麟 — Scheduling & Isolation (承载)

### CPU Pinning Wrapper

Linux affinity helper that reads the real isolated-CPU list from sysfs, pins the calling thread, and reports non-isolated targets instead of silently running unpinned.

```cpp
// Requires: <algorithm>, <cstdio>, <fstream>, <sched.h>, <pthread.h>, <string>, <string_view>, <thread>, <vector>

namespace affinity
{

unsigned parse_uint( std::string_view text ) noexcept
{
    unsigned value = 0;
    for( char ch : text )
        value = value * 10 + static_cast<unsigned>( ch - '0' );
    return value;
}

// Parse a sysfs range list such as "0-3,5,7-9" into individual cpu ids.
std::vector<unsigned> parse_cpu_list( std::string_view text )
{
    std::vector<unsigned> cpus;
    size_t pos = 0;
    while( pos < text.size() )
    {
        size_t const comma = text.find( ',', pos );
        std::string_view const token = text.substr( pos, comma - pos );
        size_t const dash = token.find( '-' );
        unsigned const lo = parse_uint( token.substr( 0, dash ) );
        unsigned hi = lo;
        if( dash != std::string_view::npos )
            hi = parse_uint( token.substr( dash + 1 ) );
        for( unsigned cpu = lo; cpu <= hi; ++cpu )
            cpus.push_back( cpu );
        pos = comma == std::string_view::npos ? text.size() : comma + 1;
    }
    return cpus;
}

std::vector<unsigned> isolated_cpus()
{
    std::ifstream in( "/sys/devices/system/cpu/isolated" );
    std::string text;
    if( !std::getline( in, text ) )
        return {};
    return parse_cpu_list( text );
}

// Pin the calling thread to one core; negative values release affinity to all non-isolated cores.
bool pin_current_thread( int core ) noexcept
{
    std::vector<unsigned> const isolated = isolated_cpus();
    cpu_set_t set;
    CPU_ZERO( &set );
    if( core < 0 )
    {
        unsigned const total = std::thread::hardware_concurrency();
        for( unsigned cpu = 0; cpu < total; ++cpu )
            if( std::find( isolated.begin(), isolated.end(), cpu ) == isolated.end() )
                CPU_SET( cpu, &set );
    }
    else
    {
        if( static_cast<unsigned>( core ) >= std::thread::hardware_concurrency() )
            return false;
        if( std::find( isolated.begin(), isolated.end(), static_cast<unsigned>( core ) ) == isolated.end() )
            std::fprintf( stderr, "pin_current_thread: core %d is not isolated\n", core );
        CPU_SET( core, &set );
    }
    return pthread_setaffinity_np( pthread_self(), sizeof( set ), &set ) == 0;
}

} // namespace affinity

class CpuAffinity
{
public:
    explicit CpuAffinity( int core ) : m_ok( affinity::pin_current_thread( core ) ) {}
    explicit operator bool() const noexcept { return m_ok; }
private:
    bool m_ok;
};
```

---

## 金灵·白虎 — Kernel & Bypass (肃杀)

### Kernel Bypass Example (Zero-Copy Shared-Memory Channel)

Same-host zero-copy channel: a power-of-two shared ring with a monotonic byte position; the writer copies in and publishes with release, the reader copies out with acquire — no syscalls on the data path.

```cpp
// Requires: <atomic>, <cstddef>, <cstdint>, <cstring>

#if defined( __powerpc64__ )
constexpr size_t CACHE_LINE = 128;
#elif defined( __s390x__ )
constexpr size_t CACHE_LINE = 256;
#else
constexpr size_t CACHE_LINE = 64;
#endif

// Published write position; the reader keeps its own monotonic position.
struct alignas( CACHE_LINE ) ShmControl
{
    std::atomic<uint64_t> m_writePos{ 0 };
};

// Immutable layout on a line that never receives stores, so readers never bounce it.
struct alignas( CACHE_LINE ) ShmLayout
{
    uint64_t m_capacity; // power of two
    uint64_t m_maxMsg;   // tail reserve: a message never straddles the wrap
};

static_assert( decltype( ShmControl::m_writePos )::is_always_lock_free );

// Writer hot path (single writer per channel): copy into the free region, then publish.
bool shm_write( ShmControl& ctrl, uint8_t* data, const ShmLayout& layout,
                const void* src, uint64_t len ) noexcept
{
    uint64_t const mask = layout.m_capacity - 1;
    uint64_t const pos = ctrl.m_writePos.load( std::memory_order_relaxed );
    uint64_t const head = pos & mask;
    if( len == 0 || len > layout.m_maxMsg || head + len > layout.m_capacity )
        return false;
    std::memcpy( data + head, src, len );
    ctrl.m_writePos.store( pos + len, std::memory_order_release );
    return true;
}

// Reader hot path: read one complete message at the caller-owned read position.
bool shm_read( const ShmControl& ctrl, const uint8_t* data, const ShmLayout& layout,
               uint64_t& readPos, void* dst, uint64_t len ) noexcept
{
    uint64_t const w = ctrl.m_writePos.load( std::memory_order_acquire );
    if( w - readPos < len )
        return false;
    std::memcpy( dst, data + ( readPos & ( layout.m_capacity - 1 ) ), len );
    readPos += len;
    return true;
}
```

---

## 水灵·玄武 — Observability & Profiling (润下)

### Latency Measurement Harness

Per-order segment stamps with a monotonic-clock default and a serializing RDTSC opt-in for sub-microsecond intervals.

```cpp
// Requires: <array>, <cstddef>, <cstdint>, <ctime>

namespace clock
{

// Monotonic nanoseconds for deltas; CLOCK_REALTIME is NTP-adjustable and corrupts interval math.
inline uint64_t read_ns() noexcept
{
    timespec ts{};
    clock_gettime( CLOCK_MONOTONIC, &ts );
    return uint64_t( ts.tv_sec ) * 1000000000u + uint64_t( ts.tv_nsec );
}

// Serializing RDTSC: lfence on both sides keeps the read inside the measured region.
inline uint64_t read_tsc() noexcept
{
    uint32_t lo, hi;
    asm volatile( "lfence; rdtsc; lfence" : "=a"( lo ), "=d"( hi ) );
    return uint64_t( lo ) | ( uint64_t( hi ) << 32 );
}

} // namespace clock

enum class OrderObs : size_t
{
    Trigger,
    InsertBegin,
    RiskBegin,
    RiskEnd,
    VendorApiBegin,
    VendorApiEnd,
    ResponseBegin,
    OnMessageEnd,
    MAX
};

struct OrderLatency
{
    std::array<uint64_t, size_t( OrderObs::MAX )> m_stamps{};

    void mark( OrderObs obs, uint64_t t ) noexcept { m_stamps[size_t( obs )] = t; }
    bool isEmpty( OrderObs obs ) const noexcept { return m_stamps[size_t( obs )] == 0; }
    uint64_t segment( OrderObs from, OrderObs to ) const noexcept
    {
        return m_stamps[size_t( to )] - m_stamps[size_t( from )];
    }
    void reset() noexcept { m_stamps.fill( 0 ); }
};

// O(1) per-order access: the stamp array is indexed by local order id.
template<size_t MAX_ORDERS>
class LatencyHarness
{
public:
    OrderLatency& order( size_t localOrderId ) noexcept { return m_orders[localOrderId]; }
    const OrderLatency& order( size_t localOrderId ) const noexcept { return m_orders[localOrderId]; }
    void resetAll() noexcept
    {
        for( auto& o : m_orders )
            o.reset();
    }
private:
    std::array<OrderLatency, MAX_ORDERS> m_orders{};
};
```

---

## Supplementary — Instruction-Level (Cross-Cutting)

### SIMD Price Normalization

Vectorized conversion of double prices to fixed tick units (AVX2, four lanes), with a scalar tail.

```cpp
// Requires: <cstdint>, <cstddef>, <immintrin.h>

// Normalize non-negative prices to tick units: dst[i] = round( src[i] * scale ).
// The SIMD path rounds to nearest-even; the scalar tail adds 0.5 before truncation.
// int32 lanes cover typical instrument precision; AVX-512DQ adds double->int64 lanes.
void normalize_prices( const double* src, int32_t* dst, size_t n, double scale ) noexcept
{
    __m256d const s = _mm256_set1_pd( scale );
    size_t i = 0;
    for( ; i + 4 <= n; i += 4 )
    {
        __m256d const p = _mm256_mul_pd( _mm256_loadu_pd( src + i ), s );
        __m256d const r = _mm256_round_pd( p, _MM_FROUND_TO_NEAREST_INT | _MM_FROUND_NO_EXC );
        _mm_storeu_si128( reinterpret_cast<__m128i*>( dst + i ), _mm256_cvtpd_epi32( r ) );
    }
    for( ; i < n; ++i )
        dst[i] = static_cast<int32_t>( src[i] * scale + 0.5 );
}
```

---

*Rounds 1–2 complete: 木灵·青龙 / 火灵·朱雀 / 土灵·麒麟 / 金灵·白虎 / 水灵·玄武 / Supplementary.*
