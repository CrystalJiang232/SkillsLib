# 五灵应象决 — HFT Optimization Patterns

> 以五灵之名，应天地之象。此卷藏纳高频交易与高性能系统之优化模式。

> Pass 1 (`atomic_queue/` + `CpuPinning.h`): distilled patterns below; verification references kept in-session, skill files dependency-free.

> Pass 2 (`core/` + `msg_parser`): production patterns for bounded queues, dispatch, IPC, and timing — added below.

> Pass 3 (option B: qd_ipc_trader + x2counterfront + x2dropcopy): gateway, batching, partitioning, and monitoring patterns — added below.

---

## 木灵·青龙 — Memory & Cache (生发)

### Pattern: Hot/Warm/Cold Path Separation

**Context:** Code paths are tiered by execution frequency and latency sensitivity.

**Problem:** Mixed paths let the cold path pollute the hot path's cache and branch predictor.

**Solution:** Physically separate the paths and add compiler branch hints.

```cpp
// Pending implementation — growth area
```

---

### Pattern: Deterministic Allocation

**Context:** Avoid dynamic memory allocation on the hot path.

**Problem:** `malloc`/`free` introduce nondeterministic latency and lock contention.

**Solution:** Pre-allocated pools, ring buffers, stack allocation.

```cpp
// Pending implementation — growth area
```

---

### Pattern: Cache Line Alignment

**Context:** Data structures shared across threads.

**Problem:** False sharing causes cache-line ping-pong.

**Solution:** Explicit per-architecture cache-line alignment with padding isolation; prefer a portable interference-size constant over a hardcoded value when portability matters.

```cpp
alignas( CACHE_LINE_SIZE ) std::atomic<unsigned> head_ = {};
alignas( CACHE_LINE_SIZE ) std::atomic<unsigned> tail_ = {};
```

**Implementation notes:**
- Place each cross-thread mutable field on its own cache line: head (writer) and tail (reader) must not share a line, or every store invalidates the peer's copy.
- Derive `CACHE_LINE_SIZE` per architecture (x86/ARM 64, POWER 128, s390 256) instead of assuming 64.
- Keep immutable ring metadata (size, element pointer) on a line that never receives stores, so readers never bounce it.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Contention-Aware Index Mapping

**Context:** Multi-producer/multi-consumer rings where peers touch consecutive slots.

**Problem:** Adjacent slot accesses land on the same cache line, recreating false sharing at the element level.

**Solution:** Power-of-two ring size plus a bit swap between the within-line index and the line index, so consecutive elements map to different cache lines.

```cpp
constexpr unsigned remap_index_with_mix( unsigned index, unsigned mix ) {
    return index ^ mix ^ ( mix << BITS );
}
```

**Implementation notes:**
- Requires a power-of-two buffer; round the capacity up and use mask-based indexing.
- Benefit is contention-dependent: mostly relevant for MPMC access patterns; marginal for SPSC. Benchmark before adopting.
- Severity: Consider [P2]; medium confidence — effect varies by workload and architecture.

---

### Pattern: Robin-Hood Hash Map with Allocator Seam

**Context:** Hot-path key/value lookups (account, instrument, order maps).

**Problem:** `std::unordered_map` has poor locality and unpredictable iteration; allocation strategy is baked into the container.

**Solution:** Wrap a robin-hood hash map and parameterize the allocator so huge-page allocation can be swapped in without touching call sites.

```cpp
template<typename Key, typename Value, typename Allocator = std::allocator<std::pair<Key, Value>>>
struct X2Map {
    using inner_t = tsl::robin_map<Key, Value, std::hash<Key>, std::equal_to<Key>, Allocator>;
    // full pass-through API: find/emplace/erase/at/iterators
};
```

**Implementation notes:**
- Robin-hood hashing improves cache locality versus chained hashing in typical workloads; benchmark in the target environment (published speedups vary widely).
- Severity: Consider [P2]; medium confidence — environment-dependent.

---

### Pattern: Stack-Buffer Message Packing

**Context:** Serializing messages to a persistence or IPC channel on a hot path.

**Problem:** Per-message heap allocation adds nondeterministic latency and fragmentation.

**Solution:** Pack into a fixed stack buffer whose size is computed from the message type at compile time.

```cpp
char  msgBuffer[ipcMessageSize<MSGT>()] = { 0 };
MSGT* msgPtr;
IpcPackage::packMessage( msgBuffer, MSGT::Type, msgPtr );
*msgPtr = msg;
m_pChannel->write( msgBuffer, sizeof( msgBuffer ) );
```

**Implementation notes:**
- Zero heap allocation on the serialization path; the payload goes from the stack straight into the shared-memory channel.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Shared-Memory Ring with Batch Zero-Copy Parsing

**Context:** High-rate market data ingestion from another process.

**Problem:** Per-message framing and copying tax the receive path.

**Solution:** Read packed multi-message frames from a memory-mapped ring; walk the batch by element stride and advance a single read cursor.

```cpp
while( m_buffer->showData( data, m_readPos ) ) {
    const VariableLenData* vld = m_buffer->unpack_data( data );
    for( auto idx = 0; idx < msg->head.itemCount; idx++ ) {
        QuoteSnapshot* quote = reinterpret_cast<QuoteSnapshot*>( msg->data + idx * msg->head.itemByte );
        handleQuote( quote );
    }
    m_readPos += vld->length;
}
```

**Implementation notes:**
- One framing check amortizes across many quotes; parsing is reinterpret-cast with no per-message copy.
- When the ring is empty, the loop yields briefly (microsecond sleep) instead of spinning hot.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Indexed Per-Order Timestamp Array

**Context:** Per-order latency instrumentation on the hot path.

**Problem:** Map-based timestamp storage adds allocation and hashing to every measurement.

**Solution:** A fixed array indexed by the trader-local order ID holds all observation stamps.

```cpp
using StampPerOrderType = std::array<uint64_t, Observations::MAX>;
using TimeStampArrayType = std::array<StampPerOrderType, MaxSupportedOrders>;
```

**Implementation notes:**
- O(1) index addressing, no allocation, no hashing; stamps are zeroed after logging to avoid double-reporting.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

### Pattern: Bounded Response Batching (Pack-Until-Full)

**Context:** Forwarding many query-result records to downstream TCP clients.

**Problem:** One send per record multiplies syscalls and packets.

**Solution:** Accumulate records into one package; flush when the buffer is full, then re-pack and continue.

```cpp
for( auto& item : vecField ) {
    if( !packageMsg.encodeField( item ) ) {
        ptrDerived->sendPackage( packageMsg );
        packageMsg.encodeHead( stHead ); packageMsg.encodeRspInfo( stRspInfo );
        packageMsg.encodeField( item );
    }
}
packageMsg.setEndFlag(); ptrDerived->sendPackage( packageMsg );
```

**Implementation notes:**
- Constraint: batch size is bounded by the buffer (pack-until-full); never use time-based coalescing on latency paths.
- Account for Nagle buffering; flush at end-of-response so latency stays bounded.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Fixed-Index Position Accounting

**Context:** Per-instrument position state updated on every fill/cancel notification.

**Problem:** Map-based state adds lookups and allocation to the fill path.

**Solution:** Position state lives in arrays indexed by direction/offset-flag enums; fills and frees are O(1) arithmetic.

```cpp
void onFill( int ref, OffsetFlagType oflag, DirectionType dir, int volume ) {
    changeFrozenPosition( ref, oflag, dir, -volume );
    changePosition( oflag, dir, volume );
}
```

**Implementation notes:**
- Close priority (yesterday-before-today) is a switch over the offset flag; no maps or allocations on the fill path.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Fixed-Size Hint Buffers

**Context:** Building risk-counter keys from instrument hints on the notification path.

**Problem:** Heap allocation per notification adds jitter and fragmentation.

**Solution:** A fixed-size stack buffer with a bounded copy (6 bytes for options).

```cpp
char strHint[16] = "";
if( pInstrument->ProductClass == YD_PC_Options ) { std::memcpy( strHint, pInstrument->InstrumentHint, 6 ); strHint[6] = '\0'; }
```

**Implementation notes:**
- Avoids allocation on the notification path; benefit scales with notification volume — benchmark before adopting elsewhere.
- Severity: Consider [P2]; medium confidence — workload-dependent.

---

### Pattern: Data-Oriented Design

**Context:** Hot arrays of structs.

**Problem:** AoS (Array of Structs) layout underutilizes cache lines.

**Solution:** SoA (Struct of Arrays) or hybrid layouts.

```cpp
// Pending implementation — growth area
```

---

### Pattern: NUMA-Aware Allocation

**Context:** Multi-socket servers.

**Problem:** Cross-NUMA access multiplies latency.

**Solution:** `numactl --interleave`, `mbind`, first-touch allocation strategy.

```cpp
// Pending implementation — growth area
```

---

### Pattern: Single-Slot Handler Allocator

**Context:** Async frameworks (asio-style) allocate temporary handler state per asynchronous operation on connection hot paths.

**Problem:** One heap allocation per handler/event on the hot path fragments memory and adds latency.

**Solution:** Reuse one preallocated slot per connection for the next handler; when the slot is busy, fall back to the global heap so the design stays correct under concurrency.

```cpp
class HandlerAllocator
{
public:
    void* allocate( size_t size )
    {
        if( !m_inUse && size <= sizeof( m_storage ) )
        {
            m_inUse = true;
            return &m_storage;
        }
        return ::operator new( size );
    }

    void deallocate( void* ptr ) noexcept
    {
        if( ptr == &m_storage )
            m_inUse = false;
        else
            ::operator delete( ptr );
    }

private:
    alignas( std::max_align_t ) std::byte m_storage[1024];
    bool m_inUse = false;
};
```

**Implementation notes:**
- The framework guarantees deallocation occurs before the next handler in the chain runs, so the slot is ready for reuse (asio allocation contract).
- A shared allocator across concurrent operations must be thread-safe; per-connection instances avoid that requirement.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Huge-Page Shared-Memory Buffer

**Context:** Large cross-process buffers (market-data rings, persistence areas) in the hundreds of MB.

**Problem:** 4K pages multiply TLB misses on every ring walk and add page-fault cost during warm-up.

**Solution:** Allocate the shared segment with `shmget(..., SHM_HUGETLB)` and fall back to plain shared memory when huge pages are unavailable; size the reservation via `vm.nr_hugepages`.

```cpp
int id = shmget( key, size, IPC_CREAT | IPC_EXCL | SHM_HUGETLB | 0777 );
if( id == -1 )
    id = shmget( key, size, IPC_CREAT | IPC_EXCL | 0777 ); // fallback
```

**Implementation notes:**
- Verify `HugePages_Total`/`HugePages_Free` before counting on the huge-page path; reservation is boot-time or sysctl-driven.
- Preallocate large buffer pools off the hot path; allocating many multi-MB buffers can take seconds.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Bit-Packed Composite Identifiers

**Context:** Hot-path keys that carry multiple fields (order ref + strategy id; instrument code).

**Problem:** Composite string keys or multi-field structs compared field-by-field cost allocation, hashing, and cache space.

**Solution:** Pack the fields into one integer at the boundary and extract with shifts/masks; the key is passed by value and compared with a single integer compare.

```cpp
inline int64_t packOrderRef( int32_t ref, int strategyId ) noexcept
{
    return ( int64_t( ref ) << Log2MaxStrategy ) | strategyId;
}
inline int getStrategyIdFromOrderRef( int64_t ref ) noexcept
{
    return int( ref & MaxStrategyId );
}
```

**Implementation notes:**
- Reserve enough high bits for the ref space and low bits for the id space; `static_assert` the ranges at compile time.
- Decode once at the boundary (ingest/init); the hot path never touches text.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

## 火灵·朱雀 — Lock-free & Concurrency (炎上)

### Pattern: Lock-Free Queue (SPSC)

**Context:** Single-producer single-consumer (e.g., market data → strategy).

**Problem:** Locked queues add contention and context switches.

**Solution:** Fixed-size ring buffer + atomic indices, with a branch between the SPSC fast path and the MPMC path.

```cpp
if( Derived::spsc_ ) {
    while( ATOMIC_QUEUE_UNLIKELY( q_element.load( X ) != NIL ) )
        if( Derived::maximize_throughput_ ) spin_loop_pause();
    q_element.store( element, R );
} else {
    for( T expected = NIL; ATOMIC_QUEUE_UNLIKELY(
             !q_element.compare_exchange_strong( expected, element, R, X ) ); expected = NIL ) {
        do spin_loop_pause();
        while( Derived::maximize_throughput_ && q_element.load( X ) != NIL );
    }
}
```

**Implementation notes:**
- The SPSC path uses only atomic loads/stores — no read-modify-write instructions — improving throughput significantly; exclusivity is guaranteed by topology.
- The MPMC path pays for CAS/exchange only where multiple writers/readers actually exist; the wait loop polls with relaxed loads instead of repeating CAS, avoiding read-for-ownership (RFO) cache-line traffic.
- A per-slot state machine (`EMPTY/STORING/STORED/LOADING`) decouples the handshake from the payload so non-atomic element types can be moved in/out.
- Separate the non-blocking contract (`try_push`/`try_pop`) from blocking policy (a retry decorator), so each call site chooses its own backoff.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: RCU (Read-Copy-Update)

**Context:** Read-heavy shared data (config tables, instrument metadata).

**Problem:** Reader-writer locks add read-side latency.

**Solution:** Version snapshots + deferred reclamation.

```cpp
// Pending implementation — growth area
```

---

### Pattern: Minimal Memory Ordering

**Context:** Hot-path atomic bookkeeping (indices, counters) versus data handoff.

**Problem:** The default sequentially-consistent ordering serializes more than the algorithm needs.

**Solution:** Establish the minimal ordering guarantee for each atomic: relaxed for bookkeeping, acquire/release only where data is published/claimed. Name the orders as constants so intent is reviewable.

```cpp
auto constexpr A = std::memory_order_acquire;
auto constexpr R = std::memory_order_release;
auto constexpr X = std::memory_order_relaxed;
```

**Implementation notes:**
- Document the acquire/release pairs across threads: producer publishes payload before a release store; consumer acquire-loads, then reads the payload.
- On strongly-ordered ISAs (x86) acquire/release is nearly free; on weak-memory ISAs (ARM/POWER) it compiles to barrier instructions — still cheaper than seq_cst.
- Relaxed misuse is the most common lock-free correctness error; verify every ordering choice against the happens-before relationship it must establish.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Bounded Deterministic Queue

**Context:** The message bus between strategy threads, IPC ingest, and the dispatcher.

**Problem:** Unbounded concurrent queues convert downstream slowness into unbounded latency and memory growth.

**Solution:** A fixed-size atomic ring whose capacity is a deliberate deployment decision.

```cpp
#define ATOMIC_QUEUE_SIZE 1024
class MsgQueue {
    atomic_queue::AtomicQueue2<MsgTypeT, ATOMIC_QUEUE_SIZE> m_queue;
};
```

**Implementation notes:**
- A bounded ring bounds queuing delay and memory under backpressure; full-queue behavior must be designed (reject or backpressure).
- The replaced unbounded design is preserved under `#if 0` as migration documentation.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Variable-Length Ring with Fill-Block Wrap

**Context:** Fixed-capacity rings carrying variable-length records (log messages, IPC frames) with one writer.

**Problem:** Variable-length records either force a max-size slot (wasted space) or require splitting across the wrap boundary (copy).

**Solution:** Reserve a zero-length "fill block" at the cycle end: the writer places a header with `size == 0` and restarts at position 0; the reader skips the marker.

```cpp
if( allocBlock >= m_freeBlock && tail != 0 )
{
    m_data[m_head].Type = 0;
    m_data[m_head].Size = 0; // fill block: "nothing here, restart at 0"
    m_head = 0;
    m_freeBlock = tail;
}
```

**Implementation notes:**
- The reader must treat `size == 0` as "skip to the start", not as a zero-length message.
- Combined with write-then-commit cursor publishing, the hot path stays allocation-free.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Direct-Call Dispatch — No Queue

**Context:** Producer and consumer run on the same thread.

**Problem:** A queue between them only adds copy/move, atomic index traffic, and cache-line churn.

**Solution:** Replace the queue with a direct visitor call; pop becomes a no-op.

```cpp
template<typename T>
void pushMessage( T&& data ) { m_MsgVisitor( std::forward<T>( data ) ); }
template<typename T>
bool popMessage( T& ) { return true; }
```

**Implementation notes:**
- Eliminates queue overhead entirely when the extra hop is unnecessary; keep the same interface so call sites do not change.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Variant + Visitor Dispatch

**Context:** Type-erased message handling on the dispatch hot path.

**Problem:** Virtual dispatch adds indirection and inhibits inlining of the per-message action.

**Solution:** Carry messages as a `std::variant` and dispatch with an overloaded visitor; trim the visitor to the product's actual message set with SFINAE.

```cpp
int operator()( const OnRtnOrderMsg& msg ) { m_ior.onMessage( msg ); return 0; }
template<typename MSGT = MsgTypeT>
std::enable_if_t<isVariantMember<OnRspQryOrderMsg, MSGT>::value, int>
operator()( const OnRspQryOrderMsg& msg ) { m_ctl.onMessage( msg ); return 0; }
```

**Implementation notes:**
- No vtable or heap indirection on the hot path; compile-time type-list trimming shrinks dispatch cost.
- Caveat: `std::visit` cost is implementation-dependent; a manual index switch can be faster on small message sets.
- Severity: Consider [P2]; medium confidence — implementation-dependent.

---

### Pattern: CRTP Message Handlers

**Context:** Framing and parse loops shared across IPC, replay, and offline parsing.

**Problem:** A base-class handler with virtual methods forces indirect calls on every frame.

**Solution:** Inherit from `MessageHandler<T>` (curiously recurring template) so the loop calls the derived method statically.

```cpp
class TradeMessageHandler : public MessageHandler<TradeMessageHandler> { /* handleMessageImpl */ };
```

**Implementation notes:**
- Static polymorphism gives the compiler full visibility into the dispatch; zero vtable indirection.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Atomic Order-ID with Warm-Up Rollback

**Context:** A shared trader-local order counter serving multiple producer threads.

**Problem:** A mutex-protected counter serializes producers and adds contention.

**Solution:** One atomic counter for all producers; filtered warm-up orders reclaim their slot.

```cpp
m_traderLocalOrderID.compare_exchange_strong( traderLocalOID, traderLocalOID - 1 );
```

**Implementation notes:**
- No lock on the allocation path; warm-up traffic does not leak ID space.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Fine-Grained Per-Instrument Locking

**Context:** Shared per-instrument state updated from order and trade paths.

**Problem:** A global lock serializes unrelated instruments and widens critical sections.

**Solution:** Lock only the exact instrument's data for the mutation window.

```cpp
std::unique_lock lock( instrData.getLock() );
```

**Implementation notes:**
- Concurrent orders on different instruments never contend; the lock is held only for the exact mutation window.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

### Pattern: Instance-Per-Thread Producer Partitioning

**Context:** Multiple producers submitting orders concurrently.

**Problem:** Shared producer state serializes submissions and adds contention.

**Solution:** Each producer thread owns its own API instance; producers never share mutable state.

```cpp
std::shared_ptr<Trader> trader( TraderApi::CreateTraderApi( cfg, 0, index ), ... );
trader->Run();
while( !traderSPI.getTradeReady() ) { std::this_thread::sleep_for( std::chrono::seconds( 1 ) ); }
```

**Implementation notes:**
- Partitioning by instance removes cross-producer contention by construction; the only shared resource is the counter behind the API.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Batched Insert-Then-Cancel

**Context:** A strategy that submits and cancels many orders per tick.

**Problem:** Interleaving inserts and cancels amplifies per-call overhead.

**Solution:** Collect order refs in a pre-reserved vector, dispatch all inserts, then run the cancel sweep.

```cpp
std::vector<OrderRefType> orderRefs;
orderRefs.reserve( m_instrumentIDs.size() );
for( auto id : m_instrumentIDs ) { m_order.InstrumentID = id; orderRefs.push_back( m_trader->ReqInsertOrder( &m_order ) ); }
for( auto orderRef : orderRefs ) { if( orderRef > 0 && cfg.getIsLimitOrder() ) m_trader->ReqCancelOrder( orderRef ); }
```

**Implementation notes:**
- Separates the insert burst from the cancel sweep and avoids reallocation on the per-tick path.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Thin Decode-Forward Mediation Layer

**Context:** A gateway between trading clients and a vendor counter.

**Problem:** Gateway business logic on the order path adds latency and drift risk.

**Solution:** Decode the request body, forward to the vendor API, return the error code; session id doubles as correlation id.

```cpp
const char* pBodyBuffer = packageMsg.getBodyBuffer();
if( pBodyBuffer ) { InputOrderField stInputOrder = *(InputOrderField*)pBodyBuffer; ret = m_api->insertOrder( &stInputOrder, sessionId ); }
return ret;
```

**Implementation notes:**
- A forwarding gateway adds no business logic on the hot path; validation lives in the counter or the client.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Single-Threaded Event Loop for Bounded Connections

**Context:** A TCP gateway with few downstream connections.

**Problem:** Multi-threaded event dispatch adds synchronization complexity without benefit at low connection counts.

**Solution:** Run one asio io_context on one thread; scale to a pool only when connection count grows.

```cpp
m_pThread = std::make_shared<std::thread>( [this]() { m_ioContext.run(); } );
```

**Implementation notes:**
- Precondition: downstream connection count is low; revisit with an io_context pool (or multiple io_contexts) when it grows.
- Single-thread run avoids synchronization complexity and enables asio single-thread optimizations.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Read-Mostly Session Registry with Shared Locking

**Context:** Per-counter session maps read on every notification, written only on connect/disconnect.

**Problem:** A plain mutex serializes the broadcast path against rare connection churn.

**Solution:** shared_mutex: broadcasts take the read lock; connect/disconnect take the write lock.

```cpp
void pushSession( int sessionId, const std::shared_ptr<TcpConnection>& pConnection ) {
    writeLock locker( m_mtx ); m_tcpSession[sessionId] = pConnection;
}
template<typename Field, int FunctionID>
void sendSinglePackageMsg( ... ) {
    readLock locker( m_mtx );
    for( const auto& item : m_tcpSession ) { ... sendPackage( ... ); }
}
```

**Implementation notes:**
- Notifications dominate over connection churn; concurrent readers proceed without blocking each other.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Order Dedup by System Order ID

**Context:** Drop-copy streams that may deliver duplicate order notifications.

**Problem:** Repeated notifications corrupt position accounting.

**Solution:** Deduplicate by the exchange system order id before touching position state.

```cpp
if( m_setOrderSysID.find( pOrder->OrderSysID ) == m_setOrderSysID.end() ) {
    m_setOrderSysID.insert( pOrder->OrderSysID );
    m_mapData[pInstrument->InstrumentID].open( pOrder->OrderRef, offsetFlag, direction, pOrder->OrderVolume );
}
```

**Implementation notes:**
- Constraint: the dedup set must stay bounded for the notification volume; evict or scope it per day/session as needed.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

## 土灵·麒麟 — Scheduling & Isolation (承载)

### Pattern: CPU Pinning & Isolation

**Context:** Deterministic scheduling for critical threads.

**Problem:** Kernel scheduler migrations and interrupt preemption.

**Solution:** Pin each critical thread once, at thread start, to a verified isolated core; combine `isolcpus` with the affinity API.

```cpp
const int res = pthread_setaffinity_np( pthread_self(), sizeof( cpuset ), &cpuset );
```

**Implementation notes:**
- Pin inside the thread itself: child threads inherit the creator's affinity mask, so pinning the creator is not enough.
- Verify the target core against the isolated-CPU list and warn loudly when it is not isolated; config sources and isolation knobs: see `prof-tools.md`.
- A negative core value maps to "pin to all non-isolated cores", i.e., explicitly cancel pinning.
- Respect `hardware_concurrency` bounds when choosing a target.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Pin Order vs Thread Creation

**Context:** Multi-threaded trader with a pinned dispatch thread.

**Problem:** Affinity is inherited by child threads, so creating workers before or after pinning silently changes their masks.

**Solution:** Create unpinned worker threads before pinning the current thread, or pin each thread explicitly inside itself.

```cpp
m_dumpThread = std::make_unique<std::thread>( &Dispatcher::dumpThread, this );
pinThread();
```

**Implementation notes:**
- The dump thread is created before `pinThread()` precisely so it does not inherit the dispatcher's pinned mask.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Thread-Per-Role Topology

**Context:** Latency-critical process with several distinct duties.

**Problem:** Mixing roles in one thread lets one path starve another; a thread per role makes each path's timing predictable.

**Solution:** Dedicated threads per role (dispatcher pinned, market receiver unpinned, IPC reader, dumper), each with its own bounded idle behavior.

```cpp
// market receiver: unpin (all non-isolated cores), poll ring, 1us sleep when empty
pinToCores( -1 );
// dumper / IPC: 1ms sleep when idle
```

**Implementation notes:**
- Bounded sleeps avoid burning a core on empty polls while keeping wake latency in the microsecond range.
- Role isolation keeps market-data ingestion, order dispatch, and persistence from interfering with each other.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Idle-Triggered Warm-Up Dispatch

**Context:** The dispatch path goes cold during trading gaps.

**Problem:** Cold caches, branch predictors, and vendor state add latency to the next real order.

**Solution:** When the queue stays empty past a calibrated interval during trading, dispatch a warm-up message to keep the path hot.

```cpp
else if( ( TimingInfoT::Rdtsc::read() - emptyStart >= m_warmUpTickInterval ) && m_exchangeStatusManager.isTrading() ) {
    std::visit( visitConsumer, m_outgoingOrderRouter.getWarmUpMessage() );
    emptyStart = TimingInfoT::Rdtsc::read();
}
```

**Implementation notes:**
- The idle threshold is calibrated once at startup by busy-waiting a configured interval and measuring the tick delta.
- In ULTRA mode strategies own their warm-up; the internal warm-up path is compiled out.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

### Pattern: Per-Instance Core Pinning from Config

**Context:** Multiple quote/trader producer pairs in one process.

**Problem:** Without per-instance affinity, producers migrate between cores.

**Solution:** Each API pair is created with its own cpu id from the config vector.

```cpp
std::shared_ptr<QuoteApi> api( QuoteApi::Create( cfg.getCPUID()[index], cfg.getMemoryKey() ), ... );
```

**Implementation notes:**
- One core per producer keeps ticks and order submission on a dedicated, isolated CPU.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Startup Readiness Barrier

**Context:** Bringing up several producer instances.

**Problem:** Parallel startup races login and risks half-initialized producers.

**Solution:** Bring producers up sequentially; each waits for trade-ready before the next is created.

```cpp
trader->Run();
while( !traderSPI.getTradeReady() ) { std::this_thread::sleep_for( std::chrono::seconds( 1 ) ); }
```

**Implementation notes:**
- Deterministic startup with bounded wait; tune the sleep for the vendor's login latency.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Timestamp-Throttled Periodic Checks

**Context:** Monitoring tasks that must not scale with event rate.

**Problem:** Running checks on every event burns CPU.

**Solution:** Schedule on a timer and self-throttle by elapsed time since the last run.

```cpp
if( ( getCurrentTimestamp() - m_lastNetPositionCheckTimestamp ) < seconds ) { return; }
m_lastNetPositionCheckTimestamp = getCurrentTimestamp();
```

**Implementation notes:**
- Bounded monitoring overhead independent of tick rate; verify intervals are small enough to catch violations in time.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

## 金灵·白虎 — Kernel & Bypass (肃杀)

### Pattern: Shared-Memory Ring IPC Channels

**Context:** Cross-process market data, order IPC, and message persistence.

**Problem:** Socket-based transport adds per-message system calls and kernel copies.

**Solution:** Memory-mapped ring channels (`MMapBuffer`/`ShmBuffer` + `ShmChannel`) with `O_RDONLY`/`O_WRONLY` endpoints.

```cpp
std::make_unique<ShmChannel<ShmBuffer<ShmBase>, IpcMessageHandler, O_RDONLY>>( serviceStr, *this );
```

**Implementation notes:**
- Same-host zero-copy transport; latency is bounded by memory access plus the poll/sleep loop rather than the socket stack.
- Requires explicit synchronization and crash/restart recovery (mount vs create semantics).
- Publish cursors must be `std::atomic` with release/acquire handshakes; `volatile` cursors rely on x86 store ordering and are not portable. A watermark/sequence guard lets a lagging reader detect silent overwrite instead of reading stale slots.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Length-Prefixed Framing for Replay

**Context:** Offline parsing and startup replay of dumped IPC messages.

**Problem:** Without framing metadata, the parser cannot locate the next message or tolerate version drift.

**Solution:** Walk length-prefixed frames; each header carries the type and total length.

```cpp
while( pos - start < len ) {
    const IpcMessage* pIpcMsg = reinterpret_cast<const IpcMessage*>( pos );
    parseMsg( pIpcMsg );
    pos += pIpcMsg->m_msgLength;
}
```

**Implementation notes:**
- A single type+length header makes framing trivial and version-tolerant.
- Validate every frame before decoding: reject a length that exceeds the remaining buffer and copy at most `min(available, expected)` bytes for untrusted input (bounded unpack).
- Severity: Recommended [P1]; externally cross-verified (references in-session).

### Pattern: TCP Heartbeat Echo + Idle Reaping

**Context:** Long-lived gateway connections.

**Problem:** Dead peers are not detected on the data path.

**Solution:** Echo heartbeats and reap sessions idle beyond twice the heartbeat interval on a steady timer.

```cpp
if( timeStamp - iter->second->getLastTimeStamp() >= 2 * CheckHeartTimeOut ) {
    iter->second->handleDisconnect( "heartbeat timeout." ); iter = m_tcpConnection.erase( iter );
}
```

**Implementation notes:**
- Connection health is enforced out-of-band on a steady timer, not on the data path.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Shared-Memory Risk-Limit Push

**Context:** Pushing risk-limit updates from a monitor process to the trader.

**Problem:** Socket delivery adds copies and syscalls for a tiny same-host message.

**Solution:** An O_WRONLY shared-memory channel with compile-time-sized stack buffers.

```cpp
m_writerChannelPtr = std::make_shared<ShmChannel<ShmBuffer<ShmBase>, void, O_WRONLY>>( std::string( "shm://mount@" ) + channelName, false );
template<typename MsgType> IpcWriter& writeMsg( const MsgType& msg, MessageType type ) {
    char msgBuffer[ipcMessageSize<MsgType>()]; MsgType* msgPtr;
    IpcPackage::packMessage( msgBuffer, type, msgPtr ); *msgPtr = msg;
    m_writerChannelPtr->write( msgBuffer, sizeof( msgBuffer ) ); return *this;
}
```

**Implementation notes:**
- Zero-copy same-host push with no heap allocation on the write path; same pattern family as the shm channels above.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

**External domain:** kernel bypass evaluation (DPDK/RDMA/io_uring) and network-stack tuning moved
to `prof-tools.md` (platform-specific / system-configuration content).

---

## 水灵·玄武 — Observability & Profiling (润下)

### Pattern: Per-Order Segment Latency Instrumentation

**Context:** Measuring the order lifecycle from strategy trigger to vendor response.

**Problem:** Coarse timestamps cannot attribute latency to specific stages.

**Solution:** A fixed set of observation points per order, stored in the O(1) indexed array, with per-segment deltas logged at response time.

```cpp
enum Observations : size_t {
    StrategyOrderID, ToBrokerOrderID, TickTriggerTime, TickOderInsertBegin, TickOderInsertEnd,
    TickRiskBegin, TickRiskEnd, TickVendorApiBegin, TickVendorApiEnd, TickVendorApiResBegin, TickOnMessageEnd, MAX
};
```

**Implementation notes:**
- Per-segment breakdowns (insert, find-instrument, risk, call, vendor-api, total, open) make hot spots visible without sampling.
- Stamps are zeroed after logging to avoid double-reporting.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Clock Abstraction with RDTSC Opt-In

**Context:** Tick-accurate interval measurement for warm-up calibration and latency.

**Problem:** Wall-clock reads are too coarse or unstable for sub-microsecond deltas.

**Solution:** A clock abstraction with a wall-clock default and a compile-time RDTSC mode.

```cpp
static uint64_t read() {
    uint32_t lo, hi;
    __asm__ volatile( "rdtsc" : "=a"( lo ), "=d"( hi ) );
    return static_cast<uint64_t>( lo ) | ( static_cast<uint64_t>( hi ) << 32 );
}
```

**Implementation notes:**
- rdtsc is not serializing: pair with lfence around the measured region for accurate fences.
- It counts reference cycles, not core cycles; ns conversion is only stable when the core is pinned and turbo behavior is controlled.
- Severity: Consider [P2]; medium confidence — measure, then trust.

---

### Pattern: Wall-Clock Stamping Pitfalls

**Context:** Interval measurement versus wall-clock display.

**Problem:** `CLOCK_REALTIME` is adjusted by NTP and counts suspend time, corrupting latency deltas.

**Solution:** Use `CLOCK_MONOTONIC` (or `MONOTONIC_RAW`) for latency deltas; reserve `REALTIME` for wall-clock display and scheduling.

```cpp
// prefer for deltas:
clock_gettime( CLOCK_MONOTONIC, &time );
```

**Implementation notes:**
- Audit existing code for interval math based on `REALTIME`; wall-clock timestamps remain fine for display.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

### Pattern: Catch-Up Gating for Notification Pipelines

**Context:** Drop-copy monitors that must not alert before their state is complete.

**Problem:** Alerts during initial replay are false alarms.

**Solution:** Suppress notifications until the initial state has been replayed; reset the gate on re-login after disconnects.

```cpp
// notifyOrder/notifyTrade:
if( !m_hasCaughtUp ) { return; }
// on login: m_hasCaughtUp = false; on caught-up: m_hasCaughtUp = true;
```

**Implementation notes:**
- Alerts and summaries are only trustworthy once the pipeline has caught up with server state.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Edge-Triggered Threshold Alerts

**Context:** Risk and stop-loss threshold monitoring.

**Problem:** Level-triggered alerts spam on every poll while the condition holds.

**Solution:** Alert only on the rising edge of a crossing; restore state on the falling edge.

```cpp
static bool isLastTriggerThreshold = false;
bool isTrigger = GE( riskRatio, m_riskRatio ) || LE( profitRatio, m_stopLossRatio );
if( isLastTriggerThreshold && !isTrigger ) { isLastTriggerThreshold = false; }
if( !isLastTriggerThreshold && isTrigger ) { /* notify + send risk-limit IPC */ isLastTriggerThreshold = true; }
```

**Implementation notes:**
- Avoids alert spam while ensuring every crossing is reported.
- Caveat: the edge state here is a static local; use per-instance member state when multiple instances share a process.
- Severity: Consider [P2]; medium confidence — design observation.

---

### Pattern: Latency Measurement & Profiling

**Context:** Sub-microsecond latency work (order handling, drop-copy monitoring) must be measurable without distorting the path it measures.

**Problem:** Coarse wall clocks miss short segments, and every-event tracing adds enough overhead to change the result; unmeasured hot paths regress silently.

**Solution:** Layer two measurement styles. On the hot path, stamp staged observation points with hardware timestamps (serializing RDTSC) or a vDSO monotonic clock, then aggregate segment deltas off the path. For whole-process attribution, use sampling profiling and targeted eBPF probes instead of tracing everything (tooling: see `prof-tools.md`).

```cpp
// Reuse the flagship harness idiom: stamp fixed observation points on the
// hot path, then compute segment deltas off it.
order.mark( OrderObs::RiskBegin, clock::read_tsc() );
// ... risk computation ...
order.mark( OrderObs::RiskEnd, clock::read_tsc() );
// aggregate: order.segment( OrderObs::RiskBegin, OrderObs::RiskEnd )
```

**Implementation notes:**
- RDTSC requires a pinned core, controlled turbo, and lfence serialization; otherwise use `clock::read_ns()` (CLOCK_MONOTONIC via vDSO).
- Keep in-path instrumentation bounded: a few stamps per order, aggregated off the path; verify overhead against an uninstrumented baseline.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Timer & Clock Source Selection

**Context:** Interval timing on or near the hot path, with a stable, consistent timebase across the system.

**Problem:** The wrong clock distorts deltas: `CLOCK_REALTIME` is NTP-adjusted, HPET/ACPI_PM reads are far slower than TSC, and bare RDTSC without pinning and turbo control is not a stable clock.

**Solution:** Default to `CLOCK_MONOTONIC` through the vDSO (userspace, no syscall on modern kernels). Opt into RDTSC only for sub-microsecond intervals on a pinned core with lfence serialization. Verify the kernel clocksource before trusting tick-to-ns conversion.

```cpp
// default: vDSO-backed, no syscall on modern Linux
uint64_t ns = clock::read_ns(); // CLOCK_MONOTONIC

// hot-path opt-in: pinned core + controlled turbo
uint64_t ticks = clock::read_tsc(); // lfence; rdtsc; lfence
```

**Implementation notes:**
- Verify the kernel clocksource and the TSC/HPET/ACPI_PM cost order on the target host: see `prof-tools.md` (clock source status).
- `clock_gettime(CLOCK_MONOTONIC)` is exported through the vDSO on Linux — a function call plus a few memory accesses, not a syscall — but still costs more than a raw RDTSC.
- RDTSC counts reference cycles, not core cycles; tick-to-ns conversion is only stable with a pinned core and controlled frequency behavior.
- Reserve `CLOCK_REALTIME` for wall-clock display; never use it for latency deltas.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Deferred-Formatting Log Pipeline

**Context:** Logging on or near the hot path where formatting and I/O add latency.

**Problem:** Formatting in the caller thread (and synchronous I/O) turns every log call into a latency spike; locks around a shared sink serialize producers.

**Solution:** Two-stage logging: the hot path captures binary records (timestamp + packed args) into a thread-local ring and registers each call site's format string once; a dedicated consumer thread merges per-thread queues in timestamp order, formats, and writes off the path.

```cpp
// Producer hot path (per thread):
auto* msg = buffer.allocate( sizeof( Timestamp ) + calculateSize( args... ) );
msg->Type = logID; // static info registered once per call site
*(Timestamp*)msg->Content = read_ns();
pack( msg->Content + sizeof( Timestamp ), args... );
buffer.writeCommit();

// Consumer thread: min-heap over per-thread queues by head timestamp,
// then format + sink outside the producer path.
```

**Implementation notes:**
- Per-thread rings mean no lock on the logging fast path; the consumer drains each buffer in FIFO order and rebalances global order by timestamp.
- Preallocate buffer pools at startup; large per-thread buffers cost seconds to allocate.
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pattern: Jitter Measurement & Profiling Methods

**Context:** Tail latency and jitter, not averages, determine trading-system quality.

**Problem:** The mean hides heavy-tailed distributions, coarse sampling misses spikes, and unbudgeted instrumentation distorts the path it measures.

**Solution:** Measure distributions, not averages: record percentiles (p50/p99/p999) and log-spaced histograms of segment deltas, and track jitter as the spread or variation of consecutive samples. Set budgets as percentile targets aligned to venue/broker SLAs, and bound sampling rates and instrumentation overhead.

```cpp
// Illustrative: log2-spaced histogram bucket for a delta in nanoseconds.
// Accumulation happens off the hot path; resolution widens as delta grows.
uint32_t logBucket( uint64_t deltaNs ) noexcept
{
    return deltaNs == 0 ? 0u : uint32_t( 64 - __builtin_clzll( deltaNs ) );
}
void record( uint64_t deltaNs ) noexcept
{
    uint32_t b = logBucket( deltaNs );
    if( b < BUCKET_COUNT )
        ++m_buckets[b];
}
```

**Implementation notes:**
- Report percentiles and the maximum alongside any mean; real latency distributions are heavy-tailed, and tail percentiles expose the risk averages hide.
- Methodology only: numeric budgets must come from venue/broker requirements (per-venue SLAs); do not hard-code unverified targets.
- Bound profiling overhead with frequency-limited sampling and in-kernel aggregation; tool selection and overhead notes: see `prof-tools.md`.
- Verify instrumentation overhead with a null-run comparison against an uninstrumented baseline.
- Severity: Recommended [P1] for the methodology; numeric budgets are venue/broker-specific and deferred.

---

## Supplementary — Instruction-Level (Cross-Cutting)

The patterns below are not bound to a single spirit; they apply across the hot path.

### Pattern: SIMD Vectorization

**Context:** Batch numeric computation (price normalization, risk calculation).

**Problem:** Scalar loops underutilize throughput.

**Solution:** AVX2/AVX-512 vectorization.

```cpp
// Pending implementation — growth area
```

---

### Pattern: Branchless Code

**Context:** Condition-heavy hot paths.

**Problem:** Branch mispredictions cause pipeline flushes.

**Solution:** Conditional moves, mask operations, lookup tables.

```cpp
// Pending implementation — growth area
```

### Cross-Cutting Guidance — Lock-Free & Systems (Pass 1)

External verification was performed for each item; skill files stay dependency-free and the references remain in-session. Severity: [P1] Recommended (high confidence), [P2] Consider (medium confidence, context-dependent).

- [P1] **Minimal memory ordering** — relaxed bookkeeping, acquire/release handoff; name the orders. Caveat: weak-memory ISAs pay with barriers; relaxed misuse is UB.
- [P1] **SPSC/MPSC over MPMC** — pay for CAS and fairness only where the flow genuinely needs it. Caveat: requires strict topology; ticket-lock fairness can worsen virtualization behavior (LWP/LHP).
- [P1] **Speculative-load spins** — poll with relaxed loads plus ISA pause; never repeat CAS/exchange in the wait. Caveat: x86-centric; test-and-test-and-set is a pessimization on some microarchitectures; `_mm_pause` adds ~140 cycles.
- [P1] **False-sharing isolation** — align cross-thread mutable fields to cache lines; keep immutable metadata on store-free lines. Caveat: footprint cost; use portable interference-size constants.
- [P1] **Power-of-two rings** — mask-based indexing instead of modulo. Caveat: capacity rounding can double memory.
- [P2] **Contention-aware index remapping** — cache-line bit swap for MPMC rings. Caveat: contention-dependent benefit; benchmark.
- [P1] **Pin-once at thread start** — verify isolcpus targets, warn on non-isolated cores. Caveat: isolcpus alone is incomplete isolation; cpuset can narrow the mask.
- [P2] **Decoupled try/blocking policy** — choose backoff per site. Caveat: fixed pause without backoff invites CAS storms under sustained contention; blocking primitives cost ~1-3 µs wakeup.

---

### Cross-Cutting Guidance — Pass 2 (core + msg_parser)

External verification performed per item; skill files stay dependency-free and the references remain in-session. Severity: [P1] Recommended (high confidence), [P2] Consider (medium confidence, context-dependent).

- [P1] **Bounded queues for latency determinism** — fixed-size rings bound queuing delay and memory under backpressure; unbounded queues hide saturation. Caveat: capacity must be sized to peak backlog, else design rejection/backpressure.
- [P2] **variant/visitor or index-switch dispatch** — avoid vtable indirection, but `std::visit` cost is implementation-dependent; a manual index switch can be faster on small message sets.
- [P1] **Fine-grained per-key locking** — per-key locks instead of a global lock; hold the critical section to the exact mutation window.
- [P1] **Stack-buffer serialization** — fixed-size buffers sized at compile time; zero allocation on the hot path.
- [P1] **Shared-memory ring IPC** — zero-copy, lower latency than sockets on the same host; requires explicit synchronization and crash recovery.
- [P1] **Deliberate pin vs thread creation order** — affinity is inherited; create unpinned workers before pinning, or pin each thread explicitly.
- [P2] **RDTSC for interval measurement** — pin + disable turbo + lfence before trusting tick→ns conversion; otherwise use `clock_gettime(CLOCK_MONOTONIC)`.
- [P2] **Robin-hood hash maps** — better locality than `std::unordered_map` in typical cases; benchmark in the target environment (published speedups vary widely).

### Cross-Cutting Guidance — Pass 3 (option B)

External verification performed per item; skill files stay dependency-free and the references remain in-session. Severity: [P1] Recommended (high confidence), [P2] Consider (medium confidence or context-dependent).

- [P1] **Single-threaded event loop for bounded connections** — avoids synchronization complexity and enables asio single-thread optimizations. Precondition: downstream connection count is low; scale to an io_context pool when it grows.
- [P1] **Bounded response batching** — pack-until-full reduces syscalls and packets. Constraint: batch size bounded and flush at end-of-response; never time-based coalescing on latency paths; account for Nagle.
- [P1] **Thin decode-forward gateway** — the forwarding layer adds no business logic; correlation rides the request id.
- [P1] **Instance-per-thread partitioning** — removes cross-producer shared state by construction.
- [P1] **Idempotent event handling** — dedup sets keep repeated vendor notifications from corrupting state. Constraint: dedup set bounded for the notification volume.
- [P2] **Static locals for instance state** — static vectors/flags in member functions are process-wide; prefer member state with multiple instances per process (design observation).
- [P2] **Timer-throttled monitoring** — elapsed-time guards bound overhead; verify threshold intervals catch violations in time.

---

*Pass 1–3 (atomic_queue/CpuPinning, core/msg_parser, option B) folded; flagship examples, kernel-bypass/network-tuning, and 水灵 profiling sections complete; concrete thresholds and a full profiling-tool quick reference remain pending — designated growth area.*
