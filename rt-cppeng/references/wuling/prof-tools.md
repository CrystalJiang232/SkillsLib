# 五灵应象决 — External Tools & System Status Reference

> 以五灵之名，应天地之象。此卷收纳平台相关、依赖硬件/系统配置、或经 Shell 调用的外部工具与
> 状态分析内容。C++ 内部模式保留在 `patterns.md` / `flagship.md`。

## 1. Profiling Tools Quick Reference

> Overhead figures are qualitative; concrete budgets are venue-specific (see Pending in
> checklist.md). Commands are generic — verify against the target host and tool version.

### perf — Sampling & Hardware Counters (baseline)

| Aspect | Reference |
|---|---|
| Purpose | Statistical sampling and hardware counter collection for CPU attribution |
| Key commands | `perf stat -a -A` (counters, per-CPU), `perf record -g -F 99` (sampled profile), `perf report`, `perf top` (realtime), `perf list`, `perf annotate` |
| Overhead | Low, frequency-limited; the kernel throttles sampling at a default maximum of 15 kHz (`kernel.perf_event_max_sample_rate`) |
| Cache-line contention (optional) | `perf c2c record` / `perf c2c report` — C2C/HITM analysis for false sharing |

### eBPF tracing (bpftrace / bcc)

| Aspect | Reference |
|---|---|
| Purpose | Dynamic tracing of kernel and user functions with verifier safety |
| Key commands | `bpftrace -l 'tracepoint:syscalls:*'` (list probes), one-liners (`tracepoint:raw_syscalls:sys_enter { @[comm] = count(); }`), `profile:hz:99` stack sampling; bcc for fuller C programs |
| Overhead | Runs in-kernel (no context switch); near-zero while probes are idle; tracepoints cost less than kprobes (pre-inserted nop sleds, stable ABI); place probes carefully on hot paths |
| Requirements | Kernel 4.9+ (5.8+ for BTF/CO-RE); root or CAP_BPF + CAP_PERFMON |

### Intel VTune Profiler

| Aspect | Reference |
|---|---|
| Purpose | IDE-driven hotspots, call trees, and system-wide CPU views |
| Modes | User-mode sampling: ~5% overhead, 10 ms interval, application-only, no sampling drivers; hardware event-based sampling: minimum collection overhead, system-wide, needs sampling drivers or Perf*, 1 ms default interval |
| Views | Summary, Bottom-up, Top-down Tree, Caller/Callee, Platform |

### Flame graphs

| Aspect | Reference |
|---|---|
| Purpose | Visualize sampled call stacks |
| Generation | Folded stacks from `perf record -g` or bpftrace `profile:hz:99`, then a stackcollapse script |
| Semantics | y-axis = stack depth; x-axis spans the sample population (not time) |

### Cross-tool guidance

- perf is the universal baseline (sampling + counters + c2c); eBPF adds verifier-safe dynamic
  tracing; VTune adds IDE call-tree/system-wide views; flame graphs are the visualization layer.
- Sampling collects a subset of events (low-overhead default); tracing collects every event and
  costs more. Tracepoints default to a sampling period of 1 (every event) — set `-F`/`-c`
  explicitly.
- eBPF overhead is bounded and near-zero while probes are not firing; uprobes cross the
  user/kernel boundary.
- Tool selection by question: "where is CPU spent?" → perf + flame graphs; "what is the event
  distribution / why did this happen?" → bpftrace/eBPF; "deep call-tree with an IDE workflow?" →
  VTune.

## 2. Diagnostic & Status Commands

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

## 3. System Tuning & Isolation

### Network Stack Tuning

**Context:** Remote paths use the kernel TCP stack (select-based dispatch); stack defaults favor
throughput and fairness over latency.

**Problem:** Default sysctls and interrupt handling add wakeup latency, delayed writability, and
interrupt noise on latency-sensitive sockets.

**Solution:** Apply measured, deployment-specific tuning of busy polling, write-queue semantics,
interrupt/RSS placement, and buffer sizing.

```cpp
int busyPoll = 50;   // microseconds; needs driver/NAPI busy-poll support
setsockopt( fd, SOL_SOCKET, SO_BUSY_POLL, &busyPoll, sizeof( busyPoll ) );
int lowat = 1024;    // unsent bytes before poll/epoll reports writable
setsockopt( fd, IPPROTO_TCP, TCP_NOTSENT_LOWAT, &lowat, sizeof( lowat ) );
```

**Implementation notes:**
- Busy poll: `net.core.busy_poll` / `net.core.busy_read` (microseconds, system-wide) or per-socket
  `SO_BUSY_POLL`; requires driver/NAPI busy-polling support.
- Write-queue control: `tcp_notsent_lowat` (sysctl) / `TCP_NOTSENT_LOWAT` (setsockopt, kernel >=
  3.12) bounds unsent bytes so poll/epoll reports writable sooner.
- Interrupts and RSS: disable `irqbalance`, pin NIC IRQs away from critical cores, spread queues
  with RSS, and verify via `/proc/interrupts`; consider `ethtool -C` adaptive interrupt coalescing.
- Buffers: size `net.core.rmem_max` / `wmem_max` / `netdev_max_backlog` for the workload; oversized
  defaults add latency.
- Lossless fabric: RoCE/RDMA requires per-priority PAUSE (PFC, IEEE 802.1Qbb, Xoff/Xon thresholds,
  watchdog) and ECN/DCQCN for congestion control.
- Verify every knob on the target host and measure before/after; keep settings in deployment
  configuration, not baked defaults.
- Severity: Consider [P2]; deployment-specific — measure first.

### Kernel Bypass Evaluation (DPDK / RDMA / io_uring)

**Context:** Remote market-data and order paths traverse the kernel network stack; same-host hot
paths already run on zero-copy shared-memory channels.

**Problem:** The kernel stack adds syscalls, copies, and interrupt-driven wakeups per packet;
default stack behavior targets throughput rather than latency.

**Solution:** Evaluate userspace NIC ownership (DPDK) or NIC-offloaded memory access (RDMA) only
when the NIC path itself is a measured bottleneck, and io_uring when syscall overhead dominates.
Keep same-host hot paths on shared-memory zero-copy channels.

```cpp
// DPDK: dedicated lcore owns the NIC and polls queues in user space
while( running ) {
    uint16_t n = rte_eth_rx_burst( port, queue, mbufs, BURST_SIZE );
    for( uint16_t i = 0; i < n; ++i ) { /* zero-copy mbuf processing */ }
}
// RDMA: register memory, post receives up front, then poll completions
ibv_reg_mr( pd, buf, len, IBV_ACCESS_LOCAL_WRITE );
ibv_post_recv( qp, &recvWr, &badWr );       // receives before sends
while( ibv_poll_cq( cq, maxWc, wc ) > 0 ) { /* handle completions */ }
// io_uring: shared SQ/CQ rings; SQPOLL can skip per-op enter syscalls
io_uring_queue_init( ringSz, &ring, 0 );
io_uring_prep_read_fixed( sqe, fd, buf, len, 0, bufIndex );
io_uring_submit( &ring );
io_uring_wait_cqe( &ring, &cqe );           // cqe->res: result or -errno
```

**Implementation notes:**
- DPDK: a poll-mode driver owns the NIC exclusively; EAL maps hugepage-backed memory, VFIO/UIO
  exposes NIC DMA buffers to user space, and a dedicated lcore pinned with `pthread_setaffinity_np`
  runs the polling loop.
- RDMA: memory must be registered with the NIC (`ibv_reg_mr`) and receive work queues posted
  before sends (`ibv_post_recv` then `ibv_post_send`); RoCE requires a lossless fabric (PFC/DCB)
  plus ECN/DCQCN congestion control.
- io_uring: rings are shared between kernel and user via `io_uring_setup` + `mmap`; registered
  buffers (`IORING_OP_READ_FIXED`/`WRITE_FIXED`) avoid repeated pinning; `IOSQE_IO_LINK` orders
  ops; CQ entries carry `user_data` for correlation.
- Each option trades portability and operational complexity for latency; adopt only after
  measurement shows the kernel path is the bottleneck.
- Code sketches are illustrative; verify against the target API versions before adoption.
- Severity: Evaluation Recommended [P1]; adoption Consider [P2], context-dependent.

### CPU Isolation Configuration

- `isolcpus` alone is not full isolation; pair with `nohz_full` / `rcu_nocbs` and IRQ affinity as
  the deployment requires.
- Read the real machine configuration (`isolcpus=` from `/proc/cmdline`, or
  `/sys/devices/system/cpu/isolated`) and verify the target core; warn loudly when the target is
  not isolated.
- Respect cpuset/cgroup restrictions — the effective affinity mask can be silently narrowed
  (EINVAL or a narrower mask than requested).

### Clock Source Status

- Verify `/sys/devices/system/clocksource/clocksource0/current_clocksource` shows `tsc`. The
  kernel prefers TSC, then HPET, then ACPI_PM; reading TSC is a register read, while HPET and
  ACPI_PM are substantially slower (cost order: TSC < HPET < ACPI_PM).

---

*External tools & system status hosted here since 2026-08-25; C++-internal patterns remain in
patterns.md / flagship.md.*
