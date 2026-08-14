# 五灵应象决 — HFT Optimization Patterns

> 以五灵之名，应天地之象。此卷藏纳高频交易与高性能系统之优化模式。

> Pass 1 (x2trader `atomic_queue/` + `CpuPinning.h`): distilled patterns below; verification references kept in-session, skill files dependency-free.

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

## 金灵·白虎 — Kernel & Bypass (肃杀)

### Pending: Kernel Bypass (DPDK / RDMA / io_uring)

- [ ] Evaluate DPDK/RDMA/io_uring for the workload
- [ ] Zero-copy paths and memory registration

### Pending: Network Stack Tuning

- [ ] sysctl tuning (busy poll, `tcp_notsent_lowat`)
- [ ] PFC/ECN configuration

---

## 水灵·玄武 — Observability & Profiling (润下)

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

### Pending: Jitter Measurement & Profiling Methods

- [ ] Define latency budgets and measurement methodology
- [ ] Establish sampling rates and overhead targets

---

*Pass 1 (atomic_queue/CpuPinning) folded; 金灵/水灵 sections and flagship pending — designated growth area.*
