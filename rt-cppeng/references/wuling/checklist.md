# 五灵应象决 — High-Performance Systems Quick Checklist

> 以五灵之名，应天地之象。此卷为 HFT 与高性能系统优化之速查。

> Pass 1 additions (x2trader `atomic_queue/` + `CpuPinning.h`); [P2] items are Consider-level, context-dependent.

> Pass 2 additions (x2trader `core/` + `msg_parser`); [P2] items are Consider-level.

> Pass 3 additions (option B: qd_ipc_trader + counterfront + dropcopy). Level field: [P1] Recommended (high confidence) / [P2] Consider (medium or context-dependent).

> Kernel-bypass evaluation + network-stack tuning pass: 金灵 rows below; [P2] items are Consider-level, deployment-specific.

---

## 木灵·青龙 — Memory & Cache (生发)

### Latency Path Separation (supplementary)

- [ ] Distinguish hot/warm/cold paths [P1]
- [ ] No dynamic memory allocation on the hot path [P1]
- [ ] Mark cold/rare paths with `[[likely]]`/`[[unlikely]]` hints to keep the hot loop compact [P1]
- [ ] Keep exception handling out of the hot path [P1]
- [ ] Asynchronous logging [P1]

### Cache & Locality

- [ ] Check shared data structures for false sharing [P1]
- [ ] `alignas(64)` on critical structs [P1]
- [ ] Cache-friendly array traversal order [P1]
- [ ] Evaluate AoS vs. SoA layout [P1]
- [ ] Prefetch inserted into compute-heavy loops [P2]
- [ ] Producer/consumer hot fields on separate cache lines (head/tail) [P1]
- [ ] Immutable ring metadata on a line that never receives stores [P1]
- [ ] Power-of-two ring size with mask-based indexing [P1]
- [ ] Contention-aware index remapping for MPMC rings [P2]
- [ ] Robin-hood hash map with allocator seam (huge-page ready) [P2]
- [ ] Stack-buffer serialization — zero heap allocation on hot path [P1]
- [ ] Batch zero-copy parsing of packed frames (stride walk) [P1]
- [ ] O(1) indexed per-order timestamp array (no map lookup) [P1]
- [ ] Bounded response batching (pack-until-full) [P1]
- [ ] Fixed-index position accounting (no maps on fill path) [P1]
- [ ] Fixed-size hint buffers [P2]

---

## 火灵·朱雀 — Lock-free & Concurrency (炎上)

- [ ] Lock-free structures (SPSC/MPMC queue) on the hot path [P1]
- [ ] Minimal memory ordering on atomic operations [P1]
- [ ] RCU or version snapshots for read-mostly data [P1]
- [ ] Thread count matched to hardware topology (not blind scaling) [P1]
- [ ] No false-shared atomic variables [P1]
- [ ] SPSC fast path without RMW instructions where topology allows [P1]
- [ ] Spin-waits use speculative relaxed loads + ISA pause, not repeated CAS [P1]
- [ ] Relaxed bookkeeping + acquire/release handoff (minimal ordering) [P1]
- [ ] Bounded/exponential backoff on contended spins [P2]
- [ ] Fair vs unfair spinlock chosen deliberately (latency vs starvation) [P2]
- [ ] Bounded fixed-size ring (deterministic queueing delay) [P1]
- [ ] Direct-call dispatch where producer/consumer share the thread [P1]
- [ ] variant/visitor or index-switch dispatch (no vtable) [P2]
- [ ] CRTP message handlers (static dispatch) [P1]
- [ ] Per-key (per-instrument) locking instead of global lock [P1]
- [ ] Instance-per-thread producer partitioning [P1]
- [ ] Batched insert-then-cancel [P1]
- [ ] Thin decode-forward gateway [P1]
- [ ] Single-threaded event loop for bounded connections [P1]
- [ ] Read-mostly session registry (shared lock) [P1]
- [ ] Order dedup by system order ID [P1]

---

## 土灵·麒麟 — Scheduling & Isolation (承载)

- [ ] Critical threads pinned to cores [P1]
- [ ] `isolcpus` or cgroups isolation [P1]
- [ ] Interrupts redirected away from critical cores [P1]
- [ ] Pinning performed once inside the thread (affinity inherited by children) [P1]
- [ ] isolcpus target verified via /proc/cmdline or /sys/devices/system/cpu/isolated [P1]
- [ ] Cpuset/cgroup restrictions checked (silent narrowing / EINVAL) [P1]
- [ ] Thread creation vs pinning order deliberate (affinity inherited) [P1]
- [ ] Thread-per-role topology with bounded sleep backoff [P1]
- [ ] Idle-triggered warm-up dispatch during trading [P1]
- [ ] Per-instance core pinning from config [P1]
- [ ] Startup readiness barrier [P1]
- [ ] Timestamp-throttled periodic checks [P1]

---

## 金灵·白虎 — Kernel & Bypass (肃杀)

- [ ] Kernel bypass evaluated (DPDK/RDMA/io_uring) [P1]
- [ ] Zero-copy data paths where applicable [P1]
- [ ] Shared-memory ring IPC channels (zero-copy, same-host) [P1]
- [ ] Length-prefixed framing for replay/parsing [P1]
- [ ] TCP heartbeat echo + idle reaping [P1]
- [ ] Shared-memory risk-limit push [P1]
- [ ] Busy poll configured where driver-supported (`net.core.busy_poll`/`busy_read`, `SO_BUSY_POLL`) [P2]
- [ ] `tcp_notsent_lowat` tuned for write-queue writability [P2]
- [ ] NIC IRQ/RSS placement verified (interrupts off critical cores, RSS queues, irqbalance off) [P2]
- [ ] Socket/buffer sizing reviewed (`rmem_max`/`wmem_max`/`netdev_max_backlog`) [P2]
- [ ] PFC/ECN/DCB evaluated for lossless fabric (RoCE/RDMA) [P2]

---

## 水灵·玄武 — Observability & Profiling (润下)

- [ ] Stable clock source selected (`tsc`) [P1]
- [ ] Latency measurement with hardware timestamps [P1]
- [ ] Sampling-based profiling with bounded overhead [P1]
- [ ] Per-order segment latency instrumentation (staged stamps) [P1]
- [ ] CLOCK_MONOTONIC for latency deltas (not REALTIME) [P1]
- [ ] RDTSC usage verified: pinned core, turbo controlled, lfence [P2]
- [ ] Catch-up gating for notification pipelines [P1]
- [ ] Edge-triggered threshold alerts [P2]
- [ ] Latency distribution measured via percentiles/histograms (p50/p99/p999), not averages [P1]

---

## Supplementary — Instruction-Level (Cross-Cutting)

- [ ] SIMD assessed for numeric-heavy regions [P1]
- [ ] Conditional branches converted to branchless where possible [P2]
- [ ] Compiler output verified (godbolt) matches expectations [P1]
- [ ] Loop unrolling considered (profile-driven only) [P2]

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

- [ ] Concrete thresholds (latency budgets, cache-miss targets) [P1]
- [ ] Profiling tool quick reference (perf, eBPF, Intel VTune) [P1]
- [ ] Venue/broker-specific deployment checklists [P1]

---

*Pass 1–3 folded above; kernel-bypass evaluation, network-stack tuning, and 水灵 profiling rows added. Concrete thresholds, a full profiling-tool quick reference, and venue checklists remain pending — designated growth area.*
