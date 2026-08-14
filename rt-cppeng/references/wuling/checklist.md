# 五灵应象决 — High-Performance Systems Quick Checklist

> 以五灵之名，应天地之象。此卷为 HFT 与高性能系统优化之速查。

> Pass 1 additions (x2trader `atomic_queue/` + `CpuPinning.h`); [P2] items are Consider-level, context-dependent.

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

---

## 土灵·麒麟 — Scheduling & Isolation (承载)

- [ ] Critical threads pinned to cores
- [ ] `isolcpus` or cgroups isolation
- [ ] Interrupts redirected away from critical cores
- [ ] Pinning performed once inside the thread (affinity inherited by children)
- [ ] isolcpus target verified via /proc/cmdline or /sys/devices/system/cpu/isolated
- [ ] Cpuset/cgroup restrictions checked (silent narrowing / EINVAL)

---

## 金灵·白虎 — Kernel & Bypass (肃杀)

- [ ] Kernel bypass evaluated (DPDK/RDMA/io_uring)
- [ ] Zero-copy data paths where applicable

---

## 水灵·玄武 — Observability & Profiling (润下)

- [ ] Stable clock source selected (`tsc`)
- [ ] Latency measurement with hardware timestamps
- [ ] Sampling-based profiling with bounded overhead

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

*Pass 1 (atomic_queue/CpuPinning) folded above; thresholds, profiling quick reference, and venue checklists still pending — designated growth area.*
