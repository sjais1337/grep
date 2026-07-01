# Grep Benchmark Results (ground truth)

Machine: 16 hardware threads, pattern `test`, 7 runs (median reported).

| Workload | Data | Matches | Sequential (ms) | Concurrent grep (ms) | GNU grep (ms) | Speedup vs sequential | Throughput (MB/s) |
|----------|------|---------|-----------------|----------------------|---------------|------------------------|-------------------|
| 16-file multi-file (500KB each) | 7.82 MB / 16 files | 1524 | 5.96 | 3.1 | 25.8 | 1.92x | 2520.6 |
| 16-file multi-file (8MB each) | 128.03 MB / 16 files | 24485 | 74.38 | 26.75 | 258.25 | 2.78x | 4786.0 |
| 8-file benchmark (2MB each) | 16.01 MB / 8 files | 3059 | 12.05 | 6.13 | 32.36 | 1.96x | 2611.4 |
| 64MB single-file intra-file | 64.0 MB / 1 files | 12297 | 44.7 | 14.17 | 93.6 | 3.15x | 4517.1 |

## Resume-ready bullets (copy/paste, numbers are measured)

- Achieved **2.78x speedup** over a sequential baseline on **128.03 MB** across **16 files** (16-thread CPU, 24485 matches verified).
- Delivered **9.65x faster** pattern counting than GNU grep on the same 128.03 MB workload (26.75 ms vs 258.25 ms median).
- Parallel **std::async** byte-range chunking yielded **3.15x intra-file speedup** on a **64.0 MB** file (14.17 ms vs 44.7 ms sequential).
- Sustained **4.8 GB/s** effective scan throughput (4786.0 MB/s) on the producer-consumer pipeline.

## Methodology

- **Sequential baseline**: single-threaded C++ scanner with identical match semantics (`tests/sequential_baseline.cpp`).
- **GNU grep baseline**: `grep -o <pattern> <files>` occurrence count.
- **Concurrent grep**: quiet mode (`-q`) to measure pipeline time without progress reporter overhead.
- **Timing**: median of 7 runs on this machine (`os.cpu_count()` hardware threads).
- **Verification**: all tools produced identical match counts on every workload.

Reproduce: `python3 tests/benchmark_stats.py`
