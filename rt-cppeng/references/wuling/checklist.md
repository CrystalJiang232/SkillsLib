# 五灵应象决 — High-Performance Systems Quick Checklist

> 以五灵之名，应天地之象。此卷为 HFT 与高性能系统优化之速查。

> Pass 1 additions (x2trader `atomic_queue/` + `CpuPinning.h`); [P2] items are Consider-level, context-dependent.

> Pass 2 additions (x2trader `core/` + `msg_parser`); [P2] items are Consider-level.

---

## 木灵·青龙 — Memory & Cache (生发)

### Latency Path Separation (supplementary)

- [ ] Distinguish hot/warm/cold paths
- [ ] No dynamic memory allocation on the hot path
- [ ] Use `[[likely]]`/`[[unlikely]]` or equivalent branch hints
- [ ] Keep exception handling out of the hot path
- [ ] Asynchronous logging

### Cache & Locality

- [ ] Check shared data structures for false sharing
- [ ] `alignas(64)` on critical structs
- [ ] Cache-friendly array traversal order
- [ ] Evaluate AoS vs. SoA layout
- [ ] Prefetch inserted into compute-heavy loops
- [ ] Producer/consumer hot fields on separate cache lines (head/tail)
- [ ] Immutable ring metadata on a line that never receives stores
- [ ] Power-of-two ring size with mask-based indexing
- [ ] Contention-aware index remapping for MPMC rings [P2]
- [ ] Robin-hood hash map with allocator seam (huge-page ready) [P2]
- [ ] Stack-buffer serialization — zero heap allocation on hot path
- [ ] Batch zero-copy parsing of packed frames (stride walk)
- [ ] O(1) indexed per-order timestamp array (no map lookup)

---

## 火灵·朱雀 — Lock-free & Concurrency (炎上)

- [ ] Lock-free structures (SPSC/MPMC queue) on the hot path
- [ ] Minimal memory ordering on atomic operations
- [ ] RCU or version snapshots for read-mostly data
- [ ] Thread count matched to hardware topology (not blind scaling)
- [ ] No false-shared atomic variables
- [ ] SPSC fast path without RMW instructions where topology allows
- [ ] Spin-waits use speculative relaxed loads + ISA pause, not repeated CAS
- [ ] Relaxed bookkeeping + acquire/release handoff (minimal ordering)
- [ ] Bounded/exponential backoff on contended spins [P2]
- [ ] Fair vs unfair spinlock chosen deliberately (latency vs starvation) [P2]
- [ ] Bounded fixed-size ring (deterministic queueing delay)
- [ ] Direct-call dispatch where producer/consumer share the thread
- [ ] variant/visitor or index-switch dispatch (no vtable) [P2]
- [ ] CRTP message handlers (static dispatch)
- [ ] Per-key (per-instrument) locking instead of global lock

---

## 土灵·麒麟 — Scheduling & Isolation (承载)

- [ ] Critical threads pinned to cores
- [ ] `isolcpus` or cgroups isolation
- [ ] Interrupts redirected away from critical cores
- [ ] Pinning performed once inside the thread (affinity inherited by children)
- [ ] isolcpus target verified via /proc/cmdline or /sys/devices/system/cpu/isolated
- [ ] Cpuset/cgroup restrictions checked (silent narrowing / EINVAL)
- [ ] Thread creation vs pinning order deliberate (affinity inherited)
- [ ] Thread-per-role topology with bounded sleep backoff
- [ ] Idle-triggered warm-up dispatch during trading

---

## 金灵·白虎 — Kernel & Bypass (肃杀)

- [ ] Kernel bypass evaluated (DPDK/RDMA/io_uring)
- [ ] Zero-copy data paths where applicable
- [ ] Shared-memory ring IPC channels (zero-copy, same-host)
- [ ] Length-prefixed framing for replay/parsing

---

## 水灵·玄武 — Observability & Profiling (润下)

- [ ] Stable clock source selected (`tsc`)
- [ ] Latency measurement with hardware timestamps
- [ ] Sampling-based profiling with bounded overhead
- [ ] Per-order segment latency instrumentation (staged stamps)
- [ ] CLOCK_MONOTONIC for latency deltas (not REALTIME)
- [ ] RDTSC usage verified: pinned core, turbo controlled, lfence [P2]

---

## Supplementary — Instruction-Level (Cross-Cutting)

- [ ] SIMD assessed for numeric-heavy regions
- [ ] Conditional branches converted to branchless where possible
- [ ] Compiler output verified (godbolt) matches expectations
- [ ] Loop unrolling/vectorization considered

---

## Diagnostic Commands

```bash
# CPU topology and cache info
lscpu && cat /proc/cpuinfo | grep -E "processor|physical id|core id"
cat /sys/devices/system/cpu/cpu0/cache/index*/{size,type,level}

# NUMA status
numactl --hardware
numastat -m

# Interrupt distribution
cat /proc/interrupts

# Clock source
cat /sys/devices/system/clocksource/clocksource0/available_clocksource
cat /sys/devices/system/clocksource/clocksource0/current_clocksource

# Kernel scheduler parameters
cat /proc/sys/kernel/sched_*

# Network stack tuning parameters
cat /proc/sys/net/core/*
cat /proc/sys/net/ipv4/tcp_*
```

---

## Pending

- [ ] Concrete thresholds (latency budgets, cache-miss targets)
- [ ] Profiling tool quick reference (perf, eBPF, Intel VTune)
- [ ] Venue/broker-specific deployment checklists

---

*Pass 1 + Pass 2 (core/msg_parser) folded above; thresholds, profiling quick reference, and venue checklists still pending — designated growth area.*
