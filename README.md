# grep

A concurrent grep-like utility in C++. Counts substring matches across files, with optional find-and-replace. Built while going through a concurrency guide the point was to learn producer-consumer pipelines, worker pools, and parallel file search.

## Build

```bash
make
```

Needs g++ with C++17 and pthread support. Produces a `./grep` binary in the project root.

## Usage

Search for a pattern in one or more files:

```bash
./grep "hello" file1.txt file2.txt
```

Common flags:

```
  -i, --ignore-case      case-insensitive matching
  -q, --quiet            no progress spam (useful for timing)
  -r, --replace <text>   find-and-replace mode (single-threaded)
  -h, --help
```

Replace mode is separate from the parallel search path, it reads line by line and writes a temp file, same idea as a basic sed workflow.

## How it works (short version)

Search mode spins up a few long-lived worker threads (one per hardware core). Files go into a work queue; workers pull paths off the queue and search each file.

For a large file, the worker splits it into 4 MB byte ranges and searches each range with `std::async`. Ranges overlap by `pattern.length - 1` bytes so matches sitting on a chunk boundary aren't missed or counted twice.

Logging goes through another queue. Workers push strings there; a single consumer thread prints them. That way search threads don't fight over stdout.

There's also a reporter thread that prints running totals every 100 ms, unless you pass `-q`.

## Tests

```bash
make test
```

Builds the binary, generates small verification fixtures, runs correctness checks against a Python reference counter, then runs a quick benchmark on generated data.

Fixtures for edge cases (empty files, chunk boundaries, etc.) live under `dataset/verify/` after generation.

## Benchmarks

```bash
make benchmark
```

Compares the parallel build against a sequential C++ baseline and GNU `grep -o`. Results land in `tests/benchmark_results.json` and `tests/BENCHMARK_RESULTS.md`.

The numbers are from my 16-core machine with cached file data. Speedup vs the sequential baseline is the meaningful comparison (~3x on multi-file workloads, ~4x on a single 64 MB file). The gap vs `grep -o` is mostly because grep is single-threaded and prints every match as a line.

Dataset generators are in `dataset/`:

- `generator_small.cpp` 16 × 500 KB files
- `generator_benchmark.cpp`  8 × 2 MB files  
- `generator_large.cpp`  8 × 500 MB files (slow, edit sizes if your disk/CPU complains)
- `generator_verify.cpp`  deterministic fixtures for tests

Generated data isn't in git (see `.gitignore`).

## Notes

- Matching is literal substring search (`std::string::find`), not regex.
- `-n` and `-v` are parsed but not fully wired up in the search path yet.
