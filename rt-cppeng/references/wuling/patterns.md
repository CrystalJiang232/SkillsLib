# 五灵应象决 — HFT Optimization Patterns

> 以五灵之名，应天地之象。此卷藏纳高频交易与高性能系统之优化模式。

> Pass 1 (x2trader `atomic_queue/` + `CpuPinning.h`): distilled patterns below; verification references kept in-session, skill files dependency-free.

> Pass 2 (x2trader `core/` + `msg_parser`): production patterns for bounded queues, dispatch, IPC, and timing — added below.

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
while( m_MMapBuffer->showData( data, m_readPos ) ) {
    const memory::VariableLenData* vld = m_MMapBuffer->unpack_data( data );
    for( auto idx = 0; idx < msg->head.itemCount; idx++ ) {
        AM_QuoteE* quoteE = reinterpret_cast<AM_QuoteE*>( msg->data + idx * msg->head.itemByte );
        handleQuoteE( quoteE );
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
- Read the real machine configuration (`isolcpus=` from `/proc/cmdline`, or `/sys/devices/system/cpu/isolated`) and verify the target core; warn loudly when the target is not isolated.
- A negative core value maps to "pin to all non-isolated cores", i.e., explicitly cancel pinning.
- Respect `hardware_concurrency` bounds and cpuset/cgroup restrictions — the effective mask can be silently narrowed.
- `isolcpus` alone is not full isolation; pair with nohz_full/rcu_nocbs and IRQ affinity as the deployment requires.
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
- Severity: Recommended [P1]; externally cross-verified (references in-session).

---

### Pending: Kernel Bypass (DPDK / RDMA / io_uring)

- [ ] Evaluate DPDK/RDMA/io_uring for the workload
- [ ] Zero-copy paths and memory registration

### Pending: Network Stack Tuning

- [ ] sysctl tuning (busy poll, `tcp_notsent_lowat`)
- [ ] PFC/ECN configuration

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

---

### Pending: Latency Measurement & Profiling

- [ ] Hardware timestamps and RDTSC timing
- [ ] perf/eBPF profiling with bounded overhead

### Pending: Timer & Clock Source Selection

- [ ] Prefer a stable `tsc` clocksource where available
- [ ] Evaluate `clock_gettime` vs. RDTSC on the hot path

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

---

### Pending: Jitter Measurement & Profiling Methods

- [ ] Define latency budgets and measurement methodology
- [ ] Establish sampling rates and overhead targets

---

*Pass 1 + Pass 2 (core/msg_parser) folded; flagship and kernel-bypass/network-tuning details pending — designated growth area.*
