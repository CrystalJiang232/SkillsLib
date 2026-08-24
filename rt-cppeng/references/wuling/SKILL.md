# 五灵应象决 / Five Spirits Resonance — HFT & Systems Optimization Archive

**Trigger Phrase:** `五灵应象决`

> 以五灵之名，应天地之象。此密室藏纳高频交易与高性能系统优化之心法，兼收 Linux 内核调优之法。与鹏啸天雷相辅相成，不覆旧典，专精一隅。

---

## Activation Protocol

When the user input contains the trigger phrase `五灵应象决` (or an equivalent HFT / low-latency / systems-optimization request), activate this chamber:

1. Load this file as the chamber index.
2. Load the specialized reference files under `references/wuling/`.
3. Keep the general references (`references/patterns.md`, etc.) searchable — the two layers complement each other.
4. Tag output with「【鹏啸天雷·五灵应象决】」.

### Context Shift

| Dimension | Roc Thunder (general) | Five Spirits (chamber) |
|:---|:---|:---|
| **Focus** | C++ modernization, code quality | HFT low latency, high-performance systems |
| **Scope** | C++ language features | C++ + Linux kernel + hardware affinity |
| **Goal** | Maintainability, clarity | Deterministic latency, throughput, stability |
| **Trade-off** | Clarity > performance | Performance > clarity (on the hot path) |

---

## Five Spirits Framework

The canonical five-spirit system, shared with `../checklist-hft.md`:

| Spirit | Element | Optimization domain | Core concern |
|:---|:---|:---|:---|
| **木灵·青龙** | 生发 | Memory & Cache | cache line, false sharing, prefetch, NUMA, memory pools |
| **火灵·朱雀** | 炎上 | Lock-free & Concurrency | lock-free, memory ordering, RCU, SPSC/MPSC queues |
| **土灵·麒麟** | 承载 | Scheduling & Isolation | CPU pinning, isolation, real-time scheduling, IRQ affinity |
| **金灵·白虎** | 肃杀 | Kernel & Bypass | PREEMPT_RT, DPDK, RDMA/RoCE, eBPF/XDP |
| **水灵·玄武** | 润下 | Observability & Profiling | perf, eBPF tracing, flame graphs, RDTSC, low-overhead probes |

---

## Workflow

1. **Detect** — identify the trigger phrase `五灵应象决` or an HFT/low-latency/system-optimization request.
2. **Contextualize** — confirm the semantics fit (HFT / high-performance / low-latency / systems optimization).
3. **Load** — load this file and the `references/wuling/` files.
4. **Analyze** — review the code or system configuration across the five spirits.
5. **Synthesize** — output structured suggestions tagged with the relevant spirit.

---

## Reference Materials

**Chamber references:**
- `patterns.md` — HFT optimization patterns (pass 1–3 + B-task + 水灵 profiling complete — atomic_queue/CpuPinning + core/msg_parser + option B-derived; Round B 2026-08-24: deferred-format logging, handler allocator, huge-page buffer, fill-block ring, bit-packed IDs)
- `checklist.md` — high-performance systems quick checklist (pass 1–3 + B-task + 水灵 profiling complete — atomic_queue/CpuPinning + core/msg_parser + option B-derived; Round B rows added 2026-08-24)
- `flagship.md` — flagship code examples (rounds 1–2 complete — 五灵·锦标 / 五灵·蓬山)
- Kernel and bypass topics are covered under 金灵·白虎 in `patterns.md` / `checklist.md` (no separate `kernel.md`).

**General references (still available):**
- `../patterns.md` — modern C++ patterns
- `../checklist.md` — C++ review checklist
- `../flagship.md` — flagship code

---

## Severity Levels

Reuse the Roc Thunder severity system, adjusted for performance-critical systems:

| Level | Priority | Criteria | Example |
|-------|----------|----------|---------|
| **Critical** | P0 | Deterministic latency breakage, system-level performance traps | Cross-NUMA memory access, syscall in the hot path |
| **Recommended** | P1 | Significant performance improvement opportunity | Cache-line alignment, hot/cold path separation |
| **Consider** | P2 | Micro-optimization or context-dependent | Software prefetch, loop unrolling, branchless conversion |

---

## Output Format

```markdown
【鹏啸天雷·五灵应象决】

## File: `src/market_data.cpp`

### Line 42 — Critical [火·朱雀]
**Current:**
```cpp
std::mutex mtx;
std::lock_guard<std::mutex> lock(mtx);
order_book.update(price, qty);
```

**Rationale:**
Mutex in hot path introduces unbounded latency. Lock contention under high market data volume will cause jitter unacceptable for HFT.

**Guidance:**
Verify if this update can be moved to a lock-free structure (e.g., RCU, atomic snapshot) or if the critical section can be eliminated entirely. Check if the order book can be sharded by symbol to reduce contention.

---

### Line 87 — Recommended [木·青龙]
**Current:**
```cpp
struct Order {
    uint64_t id;
    double price;      // 8 bytes
    uint32_t qty;      // 4 bytes
    uint8_t side;      // 1 byte
};  // Likely 24+ bytes with padding
```

**Rationale:**
Suboptimal field ordering causes unnecessary padding. In cache-sensitive hot paths, this increases cache line pressure.

**Guidance:**
Reorder fields by size (largest to smallest): `id` (8), `price` (8), `qty` (4), `side` (1) → 21 bytes, potentially packed to 24. Verify if `price` can be fixed-point (int64_t) to eliminate floating-point overhead in comparisons.
```

---

*Pass 1–3 (atomic_queue/CpuPinning, core/msg_parser, option B), the B-task (kernel bypass / network tuning), and the 水灵 profiling round folded; flagship rounds 1–2 complete; Round B (2026-08-24) folded scan-derived, web-verified patterns and checklist rows. Thresholds, profiling quick reference, and venue checklists remain pending — designated growth area.*
