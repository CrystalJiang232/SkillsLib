# 五灵应象决 / Five Spirits Checklist

HFT & Low-Latency Systems Optimization — quick verification checklist for the Five Spirits framework.

---

## 木灵·青龙 — Memory & Cache (生发)

### NUMA Affinity
- [ ] `numactl --hardware` to inspect the topology
- [ ] `numactl --cpunodebind=0 --membind=0 ./app` to bind to the local node
- [ ] Use `numa_run_on_node()` in code for programmatic control
- [ ] Dual-socket systems: partition work, threads 0..N/2 on socket 0, N/2..N on socket 1
- [ ] Use `mbind()` to pin memory allocation to specific nodes

### Memory Pools
- [ ] Pre-allocate fixed-size blocks at startup to remove malloc/free from the hot path
- [ ] Thread-local pools to remove contention
- [ ] `mmap(MAP_HUGETLB)` for hugepage-backed memory pools
- [ ] Slab allocation for heterogeneous object sizes
- [ ] Override the STL allocator with a custom allocator

### Cache Optimization
- [ ] `alignas(64)` to prevent false sharing
- [ ] Structure of Arrays (SoA) instead of Array of Structures (AoS)
- [ ] `__builtin_prefetch()` to prefetch multiple cache lines
- [ ] Hugepages (2MB/1GB) to reduce TLB misses
- [ ] `mlockall(MCL_CURRENT|MCL_FUTURE)` to lock memory and prevent page faults

### Verification Commands
```bash
numactl --hardware                    # NUMA topology
watch cat /proc/interrupts            # interrupt distribution
cat /proc/meminfo | grep Huge         # hugepage status
perf stat -e cache-misses,cache-references  # cache hit rate
```

---

## 火灵·朱雀 — Lock-free & Concurrency (炎上)

### Lock-free Basics
- [ ] `std::atomic` with appropriate memory ordering
- [ ] Understand the difference between `memory_order_relaxed` / `acquire` / `release` / `seq_cst`
- [ ] CAS (Compare-And-Swap) loops for update operations
- [ ] SPSC/MPSC queues for inter-thread communication

### Memory Ordering
- [ ] On x86, `acquire/release` is free (guaranteed by hardware)
- [ ] `seq_cst` emits an expensive `mfence`; use sparingly
- [ ] ABA protection: tagged pointers (version counter)
- [ ] Place each atomic variable on its own cache line

### Advanced Patterns
- [ ] LMAX Disruptor pattern: circular buffer + sequence numbers
- [ ] Wait-free algorithms: bounded steps guaranteed
- [ ] Read-Copy-Update (RCU) for read-heavy workloads
- [ ] Cache-line padding to prevent false sharing of atomics

### Verification
```bash
# Inspect the assembly output of atomic operations
g++ -S -O2 -std=c++20 your_code.cpp
# Verify memory ordering is correct
```

---

## 土灵·麒麟 — Scheduling & Isolation (承载)

### CPU Isolation
- [ ] Kernel parameter `isolcpus=2,3` or `isolcpus=2-5` to isolate cores
- [ ] Combine with `nohz_full` (disable ticks while idle) and `rcu_nocbs`
- [ ] `taskset -c 2 ./app` to pin threads to isolated cores
- [ ] Configure interrupt affinity: `irqbalance` + `IRQBALANCE_BANNED_CPUS`
- [ ] Verify: `watch cat /proc/interrupts` confirms interrupts moved off

### Real-time Scheduling
- [ ] `SCHED_FIFO` (no time quantum) or `SCHED_RR` policy
- [ ] Real-time priorities 1-99 always preempt CFS tasks
- [ ] Inspect policy: `ps -o pid,comm,cls,rtprio -p <PID>`
- [ ] Tune `sched_rt_period_us` and `sched_rt_runtime_us` (default 95% CPU)
- [ ] Linux 6.12+: EEVDF replaces CFS for better latency guarantees

### Thread Affinity
- [ ] `sched_setaffinity()` or `pthread_setaffinity_np()` for fine-grained control
- [ ] `SetThreadAffinityMask()` (Windows)
- [ ] Disable hyperthreading or pin one logical core per physical core
- [ ] NUMA-aware affinity: bind threads to cores on the same socket as their memory
- [ ] Verify: `sched_getcpu()` in code confirms the current CPU

### Verification Commands
```bash
taskset -c 0,1 ./app                  # bind at startup
ps -o pid,comm,cls,rtprio -p <PID>    # inspect scheduling policy
cat /proc/interrupts                  # interrupt distribution
cat /sys/devices/system/cpu/isolated  # inspect isolated CPUs
```

---

## 金灵·白虎 — Kernel & Bypass (肃杀)

### PREEMPT_RT
- [ ] Apply the PREEMPT_RT patch so kernel code is preemptible
- [ ] Convert spinlocks to sleeping locks (rt_mutex)
- [ ] Thread interrupt handlers
- [ ] Worst-case latency drops from milliseconds to tens of microseconds
- [ ] Trade-off: RT throttling can starve non-RT tasks; use SCHED_DEADLINE

### Kernel Bypass
- [ ] **DPDK**: userspace NIC drivers + polling, 10–100M packets/sec
- [ ] **RDMA/RoCE**: true zero-copy + CPU bypass, NIC reads/writes memory directly
- [ ] **Solarflare OpenOnload/AMD TCPDirect**: optimized kernel bypass, TCP-compatible
- [ ] **AF_XDP**: Linux-native bypass via eBPF
- [ ] Latency comparison: kernel stack 50–200µs vs. DPDK 2–20µs

### Network Tuning
- [ ] Disable Nagle's algorithm
- [ ] Enable busy polling
- [ ] PFC (Priority Flow Control) for lossless Ethernet
- [ ] ECN for congestion notification
- [ ] Pre-register memory (pin pages) for RDMA

### eBPF/XDP
- [ ] Kernel-level packet processing with JIT-compiled user logic
- [ ] Millions of packets/sec while retaining kernel safety
- [ ] Zero-copy to userspace

### Verification Commands
```bash
# DPDK status
dpdk-devbind.py --status

# RDMA status
ibv_devinfo
ib_write_bw  # bandwidth test

# Network parameters
sysctl net.ipv4.tcp_notsent_lowat
sysctl net.core.busy_poll
```

---

## 水灵·玄武 — Observability & Profiling (润下)

### perf Analysis
- [ ] `perf record -g ./app` → `perf report -g 'graph,0.5,caller'`
- [ ] `perf annotate` for instruction-level analysis
- [ ] Flame graphs: `perf script | ./stackcollapse-perf.pl | ./flamegraph.pl`
- [ ] Hardware events: `perf stat -e cycles,instructions,cache-misses,branch-misses`
- [ ] Off-CPU analysis: `perf sched record` shows where threads block

### eBPF Tracing
- [ ] `funccount` and `offcputime` to identify syscall latency
- [ ] Kernel-level event capture with zero copy to userspace
- [ ] Continuous profiling overhead of only 0.5–2% (vs. perf's 5–15%)
- [ ] XDP with eBPF for high-performance packet processing

### Low-overhead Probes
- [ ] RDTSC (Read Time-Stamp Counter) for nanosecond timing
- [ ] Lock-free SPSC queues for data export
- [ ] Per-thread buffers to avoid contention
- [ ] Sampling-based profiling (e.g., 1% of trades)
- [ ] Asynchronous logging through lock-free ring buffers

### Hardware Timestamps
- [ ] NIC hardware timestamps (Solarflare/AMD Onload, Mellanox VMA)
- [ ] Nanosecond-precision event ordering
- [ ] Distributed tracing across the whole tick-to-trade pipeline
- [ ] Differential profiling: compare "fast" and "slow" execution paths

### Intel PT (Processor Trace)
- [ ] Capture every instruction with minimal overhead
- [ ] Instruction-level replay of execution
- [ ] Used for root cause analysis

### Verification Commands
```bash
perf record -g ./app                  # record call graphs
perf report -g 'graph,0.5,caller'     # view the report
perf stat -e cache-misses ./app       # count cache misses
perf sched record                     # Off-CPU analysis
```

---

## 综合验证 — Latency Testing

### Automated Latency Test Framework
- [ ] Load generator: replay captured market data at production rates
- [ ] SUT (System Under Test): the trading engine
- [ ] Measurement harness: hardware timestamps capture end-to-end latency
- [ ] Measure P99/P99.9/P99.99 latency percentiles (not averages)

### Regression Verification
- [ ] Latency regression testing: verify P99 latency does not degrade
- [ ] Deterministic replay testing with captured market data
- [ ] Canary deployment with traffic mirroring
- [ ] A/B testing framework comparing old vs. new strategy performance
- [ ] Automated rollback trigger based on P&L divergence

### Shadow Trading
- [ ] Run new code in parallel with production without executing orders
- [ ] Compare decision timestamps
- [ ] Differential analysis ensures only intended behavior changes

---

## 快速诊断流程 — Rapid Diagnostics

### Latency Spike Triage
1. **Check context switches**: `perf sched record` → inspect thread migrations
2. **Check interrupt storms**: `watch cat /proc/interrupts` → confirm IRQ distribution
3. **Check cache misses**: `perf stat -e cache-misses` → verify hit rate
4. **Check remote NUMA access**: `numastat` → inspect cross-node memory access

### Production Environment Checklist
- [ ] `isolcpus` configured correctly with no kernel threads on isolated cores
- [ ] `nohz_full` and `rcu_nocbs` enabled
- [ ] Real-time priority threads bound to isolated cores
- [ ] Interrupts moved to non-isolated cores
- [ ] Memory using hugepages and locked
- [ ] Networking using kernel bypass (DPDK/RDMA) or optimized
- [ ] Probes use sampling-based profiling with overhead < 2%

---

*Five Spirits — checklist v1.0 (2026-04-20)*
