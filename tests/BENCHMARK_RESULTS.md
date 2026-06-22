# Grep Benchmark Results (ground truth)

Machine: 16 hardware threads, pattern `test`, 7 runs (median reported).

| Workload | Data | Matches | Sequential (ms) | Concurrent grep (ms) | GNU grep (ms) | Speedup vs sequential | Throughput (MB/s) |
|----------|------|---------|-----------------|----------------------|---------------|------------------------|-------------------|
| 16-file multi-file (500KB each) | 7.82 MB / 16 files | 1487 | 5.06 | 2.29 | 24.13 | 2.21x | 3417.6 |
| 16-file multi-file (8MB each) | 128.03 MB / 16 files | 24485 | 64.62 | 22.0 | 252.03 | 2.94x | 5819.8 |
| 8-file benchmark (2MB each) | 16.01 MB / 8 files | 3075 | 11.86 | 5.29 | 32.71 | 2.24x | 3027.4 |
| 64MB single-file intra-file | 64.0 MB / 1 files | 12297 | 43.64 | 11.62 | 90.18 | 3.76x | 5508.2 |

## Resume-ready bullets (copy/paste, numbers are measured)

- Achieved **2.94x speedup** over a sequential baseline on **128 MB** across **16 files** (16-thread CPU, 24,485 matches verified).
- Delivered **11.5x faster** pattern counting than GNU grep on the same 128 MB workload (22 ms vs 252 ms median).
- Parallel **std::async** byte-range chunking yielded **3.76x intra-file speedup** on a **64 MB** file (11.6 ms vs 43.6 ms sequential).
- Sustained **5.8 GB/s** effective scan throughput (5,820 MB/s) on the producer-consumer pipeline.

## Methodology

- **Sequential baseline**: single-threaded C++ scanner with identical match semantics (`tests/sequential_baseline.cpp`).
- **GNU grep baseline**: `grep -o <pattern> <files>` occurrence count.
- **Concurrent grep**: quiet mode (`-q`) to measure pipeline time without progress reporter overhead.
- **Timing**: median of 7 runs on this machine (16 hardware threads).
- **Verification**: all tools produced identical match counts on every workload.

Reproduce: `make benchmark` or `python3 tests/benchmark_stats.py`
