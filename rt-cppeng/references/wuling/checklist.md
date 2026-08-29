# 五灵应象决 — High-Performance Systems Quick Checklist

> 以五灵之名，应天地之象。此卷为 HFT 与高性能系统优化之速查。

> Pass 1 additions (`atomic_queue/` + `CpuPinning.h`); [P2] items are Consider-level, context-dependent.

> Pass 2 additions (`core/` + `msg_parser`); [P2] items are Consider-level.

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
- [ ] Fixed-array price book instead of `std::map` on the hot path [P1]
- [ ] Single-slot handler allocator reuse for async handlers [P1]
- [ ] Bit-packed fixed-size identifiers (no string keys on the hot path) [P1]
- [ ] Fixed-layout wire structs: explicit bit widths/padding with size static_asserts (bit-field layout is implementation-defined) [P2]
- [ ] Huge pages for large shared buffers (`SHM_HUGETLB` with fallback) [P2]
- [ ] Shared cursors use atomics with acquire/release; `volatile` is not a synchronization primitive [P1]
- [ ] Ring watermark/sequence guard against silent overwrite [P1]

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
- [ ] Spin-wait ladder chosen per site: relaxed-load spin + ISA pause for sub-µs waits → bounded/exponential backoff → brief sleep only when wake cost < sleep benefit (timer slack controlled) → park/block for long waits; `yield()` in a loop is not a sleep [P2]
- [ ] Bounded fixed-size ring (deterministic queueing delay) [P1]
- [ ] Variable-length ring with fill-block wrap (zero-copy cycle restart) [P2]
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
- [ ] Length-checked bounded unpack for external/truncated input [P1]
- [ ] Batched multicast receive (`recvmmsg`) with drop counter (`SO_RXQ_OVFL`) [P2]
- [ ] Multicast receive-loop discipline: drain until `EAGAIN`/`EWOULDBLOCK` with a starvation guard; `SO_REUSEADDR` for multi-instance joins, `SO_REUSEPORT` for load-split; bounded reconnect re-applies options and re-joins the group [P2]
- [ ] Fixed receive buffer reused across async receives; received length passed to the decoder, never a bare pointer [P1]
- [ ] TCP heartbeat echo + idle reaping [P1]
- [ ] Shared-memory risk-limit push [P1]
- [ ] Busy poll configured where driver-supported (`net.core.busy_poll`/`busy_read`, `SO_BUSY_POLL`) [P2]
- [ ] `tcp_notsent_lowat` tuned for write-queue writability [P2]
- [ ] NIC IRQ/RSS placement verified (interrupts off critical cores, RSS queues, irqbalance off; `SO_INCOMING_CPU` to pin flows to RX-queue CPUs where supported) [P2]
- [ ] Socket/buffer sizing reviewed (`rmem_max`/`wmem_max`/`netdev_max_backlog`) [P2]
- [ ] PFC/ECN/DCB evaluated for lossless fabric (RoCE/RDMA) [P2]

---

## 水灵·玄武 — Observability & Profiling (润下)

- [ ] Stable clock source selected (`tsc`) [P1]
- [ ] Latency measurement with hardware timestamps [P1]
- [ ] Sampling-based profiling with bounded overhead [P1]
- [ ] Per-order segment latency instrumentation (staged stamps) [P1]
- [ ] Ingest timestamp with steady_clock at the first receive boundary [P1]
- [ ] CLOCK_MONOTONIC for latency deltas (not REALTIME) [P1]
- [ ] RDTSC usage verified: pinned core, turbo controlled, lfence [P2]
- [ ] Catch-up gating for notification pipelines [P1]
- [ ] Deferred-formatting log pipeline (thread-local capture, background consumer) [P1]
- [ ] Edge-triggered threshold alerts [P2]
- [ ] Signal handlers set a lock-free atomic/flag only; latency-ring dumps and logging happen on a worker thread [P1]
- [ ] Latency distribution measured via percentiles/histograms (p50/p99/p999), not averages [P1]
- [ ] Profiling/diagnostic tooling used per `prof-tools.md` (perf/eBPF/VTune/flame graphs; status commands) [P1]

---

## Supplementary — Instruction-Level (Cross-Cutting)

- [ ] SIMD assessed for numeric-heavy regions [P1]
- [ ] Conditional branches converted to branchless where possible [P2]
- [ ] Compiler output verified (godbolt) matches expectations [P1]
- [ ] Loop unrolling considered (profile-driven only) [P2]

---

## Pending

- [ ] Concrete thresholds (latency budgets, cache-miss targets) [P1]
- [ ] Venue/broker-specific deployment checklists [P1]

---

*Pass 1–3 folded above; 水灵 profiling rows added. External tooling and status content
(profiling quick reference, diagnostic commands, kernel-bypass evaluation, network-stack tuning,
isolation/clock-source status) moved to `prof-tools.md` (2026-08-25). Concrete thresholds and
venue checklists remain pending — designated growth area.*
