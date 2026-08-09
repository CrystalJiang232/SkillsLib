# 五灵应象决 — HFT Optimization Patterns

> 以五灵之名，应天地之象。此卷藏纳高频交易与高性能系统之优化模式。

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

**Solution:** `alignas(64)` explicit alignment and padding isolation.

```cpp
// Pending implementation — growth area
```

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

**Solution:** Ring buffer + atomic indices.

```cpp
// Pending implementation — growth area
```

---

### Pattern: RCU (Read-Copy-Update)

**Context:** Read-heavy shared data (config tables, instrument metadata).

**Problem:** Reader-writer locks add read-side latency.

**Solution:** Version snapshots + deferred reclamation.

```cpp
// Pending implementation — growth area
```

---

### Pending: Memory Barriers & Memory Ordering

- [ ] Establish the minimal ordering guarantees required for each atomic
- [ ] Document the acquire/release pairs across threads

---

## 土灵·麒麟 — Scheduling & Isolation (承载)

### Pattern: CPU Pinning & Isolation

**Context:** Deterministic scheduling for critical threads.

**Problem:** Kernel scheduler migrations and interrupt preemption.

**Solution:** `sched_setaffinity`, `isolcpus`, `irqbalance` tuning.

```cpp
// Pending implementation — growth area
```

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

---

### Pending: Jitter Measurement & Profiling Methods

- [ ] Define latency budgets and measurement methodology
- [ ] Establish sampling rates and overhead targets

---

*Skeleton — designated growth area for the learning-from-codebase pass.*
