#!/usr/bin/env python3
"""Ground-truth benchmark harness for resume statistics."""

import json
import os
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GREP = ROOT / "grep"
SEQ = ROOT / "tests" / "sequential_baseline"
DATASET = ROOT / "dataset"
SMALL_DIR = DATASET / "small"
BENCHMARK_DIR = DATASET / "benchmark"
LARGE_FILE = DATASET / "large_single" / "1.txt"
MEDIUM_DIR = DATASET / "medium"
RESULTS_JSON = ROOT / "tests" / "benchmark_results.json"
RESULTS_MD = ROOT / "tests" / "BENCHMARK_RESULTS.md"

RUNS = 7
PATTERN = "test"


def build() -> None:
    subprocess.run(
        ["g++", "-std=c++17", "-pthread", "-O2", "main.cpp", "file_processor.cpp", "logger.cpp", "thread_safe.cpp", "-o", str(GREP)],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        ["g++", "-std=c++17", "-O2", "tests/sequential_baseline.cpp", "-o", str(SEQ)],
        cwd=ROOT,
        check=True,
    )


def ensure_small_dataset() -> list[Path]:
    SMALL_DIR.mkdir(parents=True, exist_ok=True)
    gen = DATASET / "generator_small"
    if not gen.exists():
        subprocess.run(
            ["g++", "-std=c++17", "-pthread", "-O2", "generator_small.cpp", "-o", "generator_small"],
            cwd=DATASET,
            check=True,
        )
    if not list(SMALL_DIR.glob("*.txt")):
        print("Generating small dataset (16 x 500KB)...")
        subprocess.run([str(gen)], cwd=DATASET, check=True)
    return sorted(SMALL_DIR.glob("*.txt"))


def ensure_benchmark_dataset() -> list[Path]:
    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
    gen = DATASET / "generator_benchmark"
    if not gen.exists():
        subprocess.run(
            ["g++", "-std=c++17", "-pthread", "-O2", "generator_benchmark.cpp", "-o", "generator_benchmark"],
            cwd=DATASET,
            check=True,
        )
    if not list(BENCHMARK_DIR.glob("*.txt")):
        print("Generating benchmark dataset (8 x 2MB)...")
        subprocess.run([str(gen)], cwd=DATASET, check=True)
    return sorted(BENCHMARK_DIR.glob("*.txt"))


def ensure_medium_dataset() -> list[Path]:
    MEDIUM_DIR.mkdir(parents=True, exist_ok=True)
    if not list(MEDIUM_DIR.glob("*.txt")):
        print("Generating medium dataset (16 x 8MB)...")
        words = (DATASET / "10000_most_common").read_text().splitlines()
        import random
        random.seed(42)
        target = 8 * 1024 * 1024
        for i in range(1, 17):
            path = MEDIUM_DIR / f"{i}.txt"
            written = 0
            with path.open("w") as out:
                while written < target:
                    chunk = " ".join(random.choice(words) for _ in range(500)) + "\n"
                    out.write(chunk)
                    written += len(chunk)
            print(f"  wrote {path.name}")
    return sorted(MEDIUM_DIR.glob("*.txt"))


def ensure_large_single_file() -> Path:
    LARGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not LARGE_FILE.exists():
        print("Generating 64MB single file...")
        words = (DATASET / "10000_most_common").read_text().splitlines()
        import random
        random.seed(42)
        target = 64 * 1024 * 1024
        written = 0
        with LARGE_FILE.open("w") as out:
            while written < target:
                chunk = " ".join(random.choice(words) for _ in range(200)) + "\n"
                out.write(chunk)
                written += len(chunk)
    return LARGE_FILE


def total_bytes(files: list[Path]) -> int:
    return sum(f.stat().st_size for f in files)


def run_seq(files: list[Path]) -> tuple[int, float]:
    result = subprocess.run(
        [str(SEQ), PATTERN, *[str(f) for f in files]],
        capture_output=True,
        text=True,
        check=True,
    )
    count = int(re.search(r"count=(\d+)", result.stdout).group(1))
    ms = float(re.search(r"time_ms=([\d.]+)", result.stdout).group(1))
    return count, ms


def run_grep(files: list[Path]) -> tuple[int, float]:
    start = time.perf_counter()
    result = subprocess.run(
        [str(GREP), "-q", PATTERN, *[str(f) for f in files]],
        capture_output=True,
        text=True,
        check=True,
    )
    wall_ms = (time.perf_counter() - start) * 1000

    count_match = re.search(r"MATCH_COUNT=(\d+)", result.stdout)
    time_match = re.search(r"TIME_MS=([\d.]+)", result.stdout)
    count = int(count_match.group(1)) if count_match else -1
    internal_ms = float(time_match.group(1)) if time_match else wall_ms

    return count, internal_ms


def run_gnu_grep(files: list[Path]) -> tuple[int, float]:
    start = time.perf_counter()
    total = 0
    for f in files:
        result = subprocess.run(
            ["grep", "-o", PATTERN, str(f)],
            capture_output=True,
            text=True,
        )
        total += len([line for line in result.stdout.splitlines() if line])
    ms = (time.perf_counter() - start) * 1000
    return total, ms


def bench(label: str, files: list[Path]) -> dict:
    bytes_total = total_bytes(files)
    mb = bytes_total / (1024 * 1024)

    seq_times: list[float] = []
    grep_times: list[float] = []
    gnu_times: list[float] = []
    counts: dict[str, int] = {}

    print(f"\n=== {label} ({len(files)} files, {mb:.1f} MB) ===")

    for i in range(RUNS):
        seq_count, seq_ms = run_seq(files)
        grep_count, grep_ms = run_grep(files)
        gnu_count, gnu_ms = run_gnu_grep(files)

        counts["sequential"] = seq_count
        counts["grep"] = grep_count
        counts["gnu"] = gnu_count

        seq_times.append(seq_ms)
        grep_times.append(grep_ms)
        gnu_times.append(gnu_ms)
        print(f"  run {i+1}: seq={seq_ms:.1f}ms grep={grep_ms:.1f}ms gnu={gnu_ms:.1f}ms counts={seq_count}/{grep_count}/{gnu_count}")

    if counts["sequential"] != counts["grep"] or counts["grep"] != counts["gnu"]:
        raise RuntimeError(f"count mismatch in {label}: {counts}")

    seq_median = statistics.median(seq_times)
    grep_median = statistics.median(grep_times)
    gnu_median = statistics.median(gnu_times)

    speedup_vs_seq = seq_median / grep_median if grep_median > 0 else 0
    throughput_mbps = mb / (grep_median / 1000) if grep_median > 0 else 0

    return {
        "label": label,
        "files": len(files),
        "total_mb": round(mb, 2),
        "match_count": counts["grep"],
        "runs": RUNS,
        "sequential_ms_median": round(seq_median, 2),
        "grep_pipeline_ms_median": round(grep_median, 2),
        "gnu_grep_ms_median": round(gnu_median, 2),
        "speedup_vs_sequential": round(speedup_vs_seq, 2),
        "speedup_vs_gnu_grep": round(gnu_median / grep_median, 2) if grep_median > 0 else 0,
        "throughput_mb_per_s": round(throughput_mbps, 1),
        "hardware_threads": os.cpu_count(),
    }


def write_report(results: list[dict]) -> None:
    RESULTS_JSON.write_text(json.dumps(results, indent=2))

    lines = [
        "# Grep Benchmark Results (ground truth)",
        "",
        f"Machine: {os.cpu_count()} hardware threads, pattern `{PATTERN}`, {RUNS} runs (median reported).",
        "",
        "| Workload | Data | Matches | Sequential (ms) | Concurrent grep (ms) | GNU grep (ms) | Speedup vs sequential | Throughput (MB/s) |",
        "|----------|------|---------|-----------------|----------------------|---------------|------------------------|-------------------|",
    ]

    for r in results:
        lines.append(
            f"| {r['label']} | {r['total_mb']} MB / {r['files']} files | {r['match_count']} | "
            f"{r['sequential_ms_median']} | {r['grep_pipeline_ms_median']} | {r['gnu_grep_ms_median']} | "
            f"{r['speedup_vs_sequential']}x | {r['throughput_mb_per_s']} |"
        )

    lines.extend([
        "",
        "## Resume-ready bullets (copy/paste, numbers are measured)",
        "",
    ])

    multi = next((r for r in results if "8MB each" in r["label"]), results[-2])
    single = next((r for r in results if "single-file" in r["label"]), results[-1])

    lines.append(
        f"- Achieved **{multi['speedup_vs_sequential']}x speedup** over a sequential baseline on "
        f"**{multi['total_mb']} MB** across **{multi['files']} files** ({multi['hardware_threads']}-thread CPU, "
        f"{multi['match_count']} matches verified)."
    )
    lines.append(
        f"- Delivered **{multi['speedup_vs_gnu_grep']}x faster** pattern counting than GNU grep on the same "
        f"{multi['total_mb']} MB workload ({multi['grep_pipeline_ms_median']} ms vs {multi['gnu_grep_ms_median']} ms median)."
    )
    lines.append(
        f"- Parallel **std::async** byte-range chunking yielded **{single['speedup_vs_sequential']}x intra-file speedup** "
        f"on a **{single['total_mb']} MB** file ({single['grep_pipeline_ms_median']} ms vs "
        f"{single['sequential_ms_median']} ms sequential)."
    )
    lines.append(
        f"- Sustained **{multi['throughput_mb_per_s'] / 1000:.1f} GB/s** effective scan throughput "
        f"({multi['throughput_mb_per_s']} MB/s) on the producer-consumer pipeline."
    )

    lines.extend([
        "",
        "## Methodology",
        "",
        "- **Sequential baseline**: single-threaded C++ scanner with identical match semantics (`tests/sequential_baseline.cpp`).",
        "- **GNU grep baseline**: `grep -o <pattern> <files>` occurrence count.",
        "- **Concurrent grep**: quiet mode (`-q`) to measure pipeline time without progress reporter overhead.",
        "- **Timing**: median of 7 runs on this machine (`os.cpu_count()` hardware threads).",
        "- **Verification**: all tools produced identical match counts on every workload.",
        "",
        "Reproduce: `python3 tests/benchmark_stats.py`",
    ])

    RESULTS_MD.write_text("\n".join(lines) + "\n")
    print(f"\nWrote {RESULTS_MD} and {RESULTS_JSON}")


def main() -> None:
    os.chdir(ROOT)
    build()

    small_files = ensure_small_dataset()
    bench_files = ensure_benchmark_dataset()
    medium_files = ensure_medium_dataset()
    large_file = ensure_large_single_file()

    results = [
        bench("16-file multi-file (500KB each)", small_files),
        bench("16-file multi-file (8MB each)", medium_files),
        bench("8-file benchmark (2MB each)", bench_files),
        bench("64MB single-file intra-file", [large_file]),
    ]

    write_report(results)
    print("\nSummary:")
    for r in results:
        print(
            f"  {r['label']}: {r['speedup_vs_sequential']}x vs sequential, "
            f"{r['throughput_mb_per_s']} MB/s, grep={r['grep_pipeline_ms_median']}ms"
        )


if __name__ == "__main__":
    main()
