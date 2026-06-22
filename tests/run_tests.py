#!/usr/bin/env python3
"""Correctness and benchmark tests for the concurrent grep utility."""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GREP_BIN = ROOT / "grep"
DATASET = ROOT / "dataset"
VERIFY_DIR = DATASET / "verify"
BENCHMARK_DIR = DATASET / "benchmark"


def reference_count(path: Path, pattern: str, ignore_case: bool = False) -> int:
    data = path.read_bytes()
    if ignore_case:
        data = data.lower()
        pattern = pattern.lower()

    count = 0
    start = 0
    plen = len(pattern)
    if plen == 0:
        return 0

    while True:
        idx = data.find(pattern.encode("latin-1"), start)
        if idx == -1:
            break
        count += 1
        start = idx + plen
    return count


def run_grep(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(GREP_BIN), *args],
        cwd=cwd or ROOT,
        capture_output=True,
        text=True,
    )


def extract_total(output: str) -> int | None:
    for line in output.splitlines():
        if "Total occurrences found:" in line and "so far" not in line:
            match = re.search(r"Total occurrences found:\s*(\d+)", line)
            if match:
                return int(match.group(1))
    return None


def extract_per_file_counts(output: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for line in output.splitlines():
        match = re.search(r"Found (\d+) occurrences in (.+)$", line)
        if match:
            counts[match.group(2)] = int(match.group(1))
    return counts


def build_grep() -> None:
    sources = [
        "main.cpp",
        "file_processor.cpp",
        "logger.cpp",
        "thread_safe.cpp",
    ]
    cmd = [
        "g++",
        "-std=c++17",
        "-pthread",
        "-O2",
        *[str(ROOT / s) for s in sources],
        "-o",
        str(GREP_BIN),
    ]
    print("Building grep...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError("Build failed")


def generate_verify_dataset() -> None:
    gen = DATASET / "generator_verify"
    if not gen.exists():
        subprocess.run(
            ["g++", "-std=c++17", "-O2", "generator_verify.cpp", "-o", "generator_verify"],
            cwd=DATASET,
            check=True,
        )
    print("Generating verification datasets...")
    subprocess.run([str(gen)], cwd=DATASET, check=True)


def generate_benchmark_dataset() -> None:
    gen = DATASET / "generator_benchmark"
    if not gen.exists():
        subprocess.run(
            ["g++", "-std=c++17", "-pthread", "-O2", "generator_benchmark.cpp", "-o", "generator_benchmark"],
            cwd=DATASET,
            check=True,
        )
    print("Generating benchmark datasets (8 x 2MB)...")
    subprocess.run([str(gen)], cwd=DATASET, check=True)


def test_basic_search() -> None:
    path = VERIFY_DIR / "basic.txt"
    expected = reference_count(path, "hello")
    result = run_grep(["hello", str(path)])
    assert result.returncode == 0, result.stderr
    actual = extract_total(result.stdout)
    assert actual == expected, f"basic.txt: expected {expected}, got {actual}"


def test_case_insensitive() -> None:
    path = VERIFY_DIR / "case.txt"
    expected = reference_count(path, "hello", ignore_case=True)
    result = run_grep(["-i", "hello", str(path)])
    assert result.returncode == 0
    actual = extract_total(result.stdout)
    assert actual == expected, f"case.txt -i: expected {expected}, got {actual}"


def test_empty_and_nomatch() -> None:
    empty = VERIFY_DIR / "empty.txt"
    result = run_grep(["hello", str(empty)])
    assert result.returncode == 0
    assert extract_total(result.stdout) == 0

    nomatch = VERIFY_DIR / "nomatch.txt"
    result = run_grep(["needle", str(nomatch)])
    assert result.returncode == 0
    assert extract_total(result.stdout) == 0


def test_chunk_boundary() -> None:
    path = VERIFY_DIR / "boundary.bin"
    expected = reference_count(path, "abc")
    result = run_grep(["abc", str(path)])
    assert result.returncode == 0
    actual = extract_total(result.stdout)
    assert actual == expected, f"boundary.bin: expected {expected}, got {actual}"
    assert expected == 2, "boundary fixture should contain exactly 2 abc matches"


def test_multi_file() -> None:
    files = [VERIFY_DIR / "multi_a.txt", VERIFY_DIR / "multi_b.txt"]
    expected = sum(reference_count(f, "needle") for f in files)
    result = run_grep(["needle", *[str(f) for f in files]])
    assert result.returncode == 0
    actual = extract_total(result.stdout)
    assert actual == expected, f"multi-file: expected {expected}, got {actual}"

    per_file = extract_per_file_counts(result.stdout)
    for f in files:
        assert per_file.get(str(f)) == reference_count(f, "needle")


def test_replace_mode() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "replace.txt"
        shutil.copy(VERIFY_DIR / "replace.txt", src)
        result = run_grep(["-r", "bar", "foo", str(src)])
        assert result.returncode == 0
        content = src.read_text()
        assert content.count("bar") == 4
        assert "foo" not in content


def test_help() -> None:
    result = run_grep(["--help"])
    assert result.returncode == 0
    assert "USAGE" in result.stderr or "USAGE" in result.stdout


def run_correctness_tests() -> None:
    tests = [
        ("basic search", test_basic_search),
        ("case insensitive", test_case_insensitive),
        ("empty and no-match", test_empty_and_nomatch),
        ("chunk boundary", test_chunk_boundary),
        ("multi-file", test_multi_file),
        ("replace mode", test_replace_mode),
        ("help", test_help),
    ]

    passed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except AssertionError as exc:
            print(f"  FAIL  {name}: {exc}")
        except Exception as exc:
            print(f"  ERROR {name}: {exc}")

    print(f"\nCorrectness: {passed}/{len(tests)} passed")
    if passed != len(tests):
        sys.exit(1)


def run_benchmark() -> None:
    files = sorted(BENCHMARK_DIR.glob("*.txt"))
    if not files:
        print("No benchmark files found; skipping benchmark.")
        return

    pattern = "test"
    expected = sum(reference_count(f, pattern) for f in files)
    args = [pattern, *[str(f) for f in files]]

    start = time.perf_counter()
    result = run_grep(args)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert result.returncode == 0, result.stderr
    actual = extract_total(result.stdout)
    assert actual == expected, f"benchmark count mismatch: expected {expected}, got {actual}"

    total_mb = sum(f.stat().st_size for f in files) / (1024 * 1024)
    print(f"\nBenchmark ({len(files)} files, {total_mb:.1f} MB total, pattern '{pattern}'):")
    print(f"  Reference count : {expected}")
    print(f"  Grep count      : {actual}")
    print(f"  Wall time       : {elapsed_ms:.1f} ms")


def main() -> None:
    os.chdir(ROOT)
    build_grep()
    generate_verify_dataset()
    print("\nRunning correctness tests...")
    run_correctness_tests()
    generate_benchmark_dataset()
    run_benchmark()
    print("\nAll tests passed.")


if __name__ == "__main__":
    main()
