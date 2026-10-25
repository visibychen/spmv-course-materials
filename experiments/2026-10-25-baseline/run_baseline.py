#!/usr/bin/env python3
"""Build untouched upstream sources and record reproducible SpMV measurements.

Run inside WSL. No Git write operations are performed. Large data and builds
are intentionally ignored by the experiments/.gitignore file.
"""
import argparse
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import random
import re
import statistics
import subprocess
import tarfile
import time
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
MATERIALS = ROOT.parent.parent
CORE = MATERIALS.parent / "csrspmv"
BUILD = ROOT / "build"
DATA = ROOT / "data"
RAW = ROOT / "raw"
N = 12_000_000
K = 8
SEED = 0x20261025
THREADS = [1, 2, 4, 8, 12, 24]
COMMON = ["-O3", "-march=native", "-g", "-Wall", "-iquote", "src", "-fopenmp"]
VARIANTS = {
    "strict": [],
    "novec": ["-fno-tree-loop-vectorize", "-fno-tree-slp-vectorize"],
    "fastmath_diagnostic": ["-ffast-math"],
}
PATTERN = re.compile(r"csr_matrix_int32_spmv: ([0-9.]+) seconds (\d+) multiplications (\d+) flops")


def stamp():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def capture(command, **kwargs):
    return subprocess.run(command, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, check=True, **kwargs).stdout


def omp_env(threads):
    env = os.environ.copy()
    # Remove inherited overrides before setting every experiment choice.
    for key in list(env):
        if key.startswith(("OMP_", "GOMP_")):
            del env[key]
    env.update(OMP_NUM_THREADS=str(threads), OMP_DYNAMIC="FALSE",
               OMP_PLACES="cores", OMP_PROC_BIND="spread",
               OMP_WAIT_POLICY="PASSIVE", LC_ALL="C")
    return env


def binary(variant):
    return BUILD / variant / "csrspmv"


def prepare():
    for folder in (BUILD, DATA, RAW):
        folder.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(CORE), "diff", "--quiet", "HEAD"], check=True)
    commit = capture(["git", "-C", str(CORE), "rev-parse", "HEAD"]).strip()
    archive = subprocess.check_output(["git", "-C", str(CORE), "archive", "HEAD"])
    provenance = {"recorded_at": stamp(), "source_commit": commit,
                  "source_status_before": capture(["git", "-C", str(CORE), "status", "--porcelain=v1"]),
                  "remote_urls": capture(["git", "-C", str(CORE), "remote", "-v"]),
                  "builds": {}}
    for variant, extra in VARIANTS.items():
        destination = BUILD / variant
        destination.mkdir(exist_ok=True)
        # git archive contains only the clean tracked source, never local outputs.
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            for member in tar.getmembers():
                if member.name.startswith("/") or ".." in Path(member.name).parts:
                    raise ValueError("unsafe source archive path")
            tar.extractall(destination)
        report = ROOT / f"vectorization-{variant}.txt"
        if report.exists():
            report.unlink()
        flags = COMMON + extra + [f"-fopt-info-vec-all={report}"]
        command = ["make", "-B", "CC=gcc", "CFLAGS=" + " ".join(flags)]
        (ROOT / f"build-{variant}.log").write_text(capture(command, cwd=destination), encoding="utf-8")
        (ROOT / f"optimizer-{variant}.txt").write_text(
            capture(["gcc", "-Q"] + COMMON + extra + ["--help=optimizers"]), encoding="utf-8")
        (ROOT / f"assembly-{variant}.txt").write_text(
            capture(["objdump", "-d", "-l", "--disassemble=csr_matrix_int32_spmv", str(binary(variant))]), encoding="utf-8")
        sources = {str(p.relative_to(destination)): sha(p)
                   for p in sorted((destination / "src").glob("*")) if p.suffix in (".c", ".h")}
        provenance["builds"][variant] = {"command": command, "cwd": str(destination),
            "flags": flags, "binary_sha256": sha(binary(variant)), "source_sha256": sources}
        print(f"built {variant}", flush=True)
    for name in ("generate_matrix", "omp_probe"):
        cmd = ["gcc", "-O2", "-Wall", "-Wextra", str(ROOT / f"{name}.c"), "-o", str(BUILD / name)]
        if name == "omp_probe":
            cmd.append("-fopenmp")
        capture(cmd)
    write_json(ROOT / "provenance.json", provenance)
    commands = {
        "uname": ["uname", "-a"], "lscpu": ["lscpu"],
        "topology": ["lscpu", "-e=CPU,CORE,SOCKET,NODE"],
        "memory": ["free", "-b"], "compiler": ["gcc", "--version"],
        "make": ["make", "--version"], "disk": ["df", "-h", str(ROOT)],
        "kernel_perf": ["perf", "--version"],
    }
    environment = {"recorded_at": stamp(), "commands": {}, "omp_environment": omp_env(1)}
    # Store relevant environment only; do not export unrelated user credentials.
    environment["omp_environment"] = {k: v for k, v in environment["omp_environment"].items()
                                       if k.startswith(("OMP_", "GOMP_")) or k == "LC_ALL"}
    for name, cmd in commands.items():
        try:
            environment["commands"][name] = capture(cmd)
        except (subprocess.CalledProcessError, FileNotFoundError) as error:
            environment["commands"][name] = str(error)
    for threads in THREADS:
        environment[f"placement_{threads}"] = capture([str(BUILD / "omp_probe")], env=omp_env(threads))
    environment["proc_meminfo"] = Path("/proc/meminfo").read_text()
    environment["reported_L3_bytes"] = int(Path("/sys/devices/system/cpu/cpu0/cache/index3/size").read_text().strip().rstrip("K")) * 1024
    environment["numpy_version"] = capture(["python3", "-c", "import numpy; print(numpy.__version__)"]).strip()
    write_json(ROOT / "environment.json", environment)


def execute(variant, threads, repeat, tag, matrix=None, output=None, source=None, record=True):
    matrix = matrix or DATA / "large_random.mtx"
    cmd = [str(binary(variant)), "--verbose", "--matrix-format=f32",
           "--source-vector-format=f32", "--destination-vector-format=f32",
           f"--repeat={repeat}", str(matrix)]
    if output is not None:
        cmd.append(f"--destination-vector={output}")
    if source is not None:
        cmd.append(f"--source-vector={source}")
    resource_file = RAW / f"{tag}.resource.json"
    wrapped = ["/usr/bin/time", "-f", '{"wall_seconds":%e,"user_seconds":%U,"system_seconds":%S,"max_rss_kib":%M,"major_faults":%F,"minor_faults":%R,"exit_status":%x}',
               "-o", str(resource_file)] + cmd
    started = stamp()
    begin = time.monotonic()
    result = subprocess.run(wrapped, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=omp_env(threads), timeout=1200)
    (RAW / f"{tag}.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (RAW / f"{tag}.stderr.txt").write_text(result.stderr, encoding="utf-8")
    write_json(RAW / f"{tag}.command.json", {"command": cmd, "environment": {
        k: v for k, v in omp_env(threads).items() if k.startswith("OMP_") or k == "LC_ALL"},
        "started_at": started, "finished_at": stamp(), "returncode": result.returncode})
    if result.returncode:
        raise RuntimeError(f"{tag} failed: {result.stderr[-2000:]}")
    match = PATTERN.search(result.stdout)
    if not match:
        raise RuntimeError(f"missing kernel timing: {tag}")
    seconds, actual_repeat, flops = float(match[1]), int(match[2]), int(match[3])
    if actual_repeat != repeat:
        raise AssertionError((tag, repeat, actual_repeat))
    resources = json.loads(resource_file.read_text())
    row = {"tag": tag, "variant": variant, "threads": threads, "repeat": repeat,
           "kernel_seconds": seconds, "seconds_per_spmv": seconds / repeat,
           "gflops": flops / seconds / 1e9, "flops": flops,
           "process_wall_seconds": resources["wall_seconds"],
           "max_rss_kib": resources["max_rss_kib"], "major_faults": resources["major_faults"],
           "started_at": started}
    converted = re.search(r"csr_matrix_int32_from_matrix_market: [0-9.]+ seconds \d+ rows \d+ columns (\d+) nonzeros", result.stdout)
    if not converted or flops != 2 * int(converted[1]) * repeat:
        raise AssertionError(f"unexpected f32 operation count: {tag}")
    print(f"{tag}: kernel={seconds:.6f}s per_spmv={seconds/repeat:.6f}s GFLOP/s={row['gflops']:.4f} wall={time.monotonic()-begin:.1f}s", flush=True)
    if record:
        path = ROOT / "measurements.csv"
        exists = path.exists()
        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(row))
            if not exists:
                writer.writeheader()
            writer.writerow(row)
    return row


def load_vector(path):
    import numpy as np
    with path.open() as f:
        header = f.readline().strip()
        if header != "%%MatrixMarket vector array real general":
            raise AssertionError(header)
        for line in f:
            if not line.startswith("%"):
                size = int(line)
                break
        result = np.loadtxt(f, dtype=np.float64, ndmin=1)
    if result.size != size:
        raise AssertionError((size, result.size))
    return result


def smoke():
    import numpy as np
    checks = []
    # Rectangular, unsorted coordinates, repeated coordinates, an empty row,
    # negative values and nonuniform x exercise indexing and accumulation.
    entries = [(4, 6, 1.5), (0, 5, -2), (2, 1, 0.5), (0, 0, 3),
               (3, 2, -1.25), (2, 1, 0.75), (4, 0, -0.5), (3, 4, 2)]
    a = np.zeros((5, 7), dtype=np.float32)
    for r, c, value in entries:
        a[r, c] += value
    x = np.array([1, -2, 0.5, 3, -1, 2, 0.25], dtype=np.float32)
    m = DATA / "correctness.mtx"
    m.write_text("%%MatrixMarket matrix coordinate real general\n5 7 8\n" +
                 "".join(f"{r+1} {c+1} {v}\n" for r, c, v in entries))
    v = DATA / "correctness_x.mtx"
    v.write_text("%%MatrixMarket vector array real general\n7\n" + "\n".join(map(str, x)) + "\n")
    for variant in VARIANTS:
        for threads in (1, 12):
            for repeat in (1, 7):
                tag = f"check-{variant}-t{threads}-r{repeat}"
                out = DATA / f"{tag}.mtx"
                execute(variant, threads, repeat, tag, matrix=m, output=out, source=v, record=False)
                actual = load_vector(out)
                expected = (a @ x).astype(np.float64) * repeat
                np.testing.assert_array_equal(actual, expected)
                checks.append({"case": tag, "elements": len(expected), "max_absolute_error": float(np.max(np.abs(actual-expected))), "passed": True})
    # Also independently read the generator's small matrix and check it with
    # a nonuniform vector, rather than trusting only its row-sum sidecar.
    generated = DATA / "generator_small.mtx"
    expected_path = DATA / "generator_small.f32"
    capture([str(BUILD / "generate_matrix"), str(generated), str(expected_path), "101", str(K), str(SEED)])
    coo = np.loadtxt(generated, comments="%", skiprows=3, ndmin=2)
    dense = np.zeros((101, 101), dtype=np.float32)
    for r, c, value in coo:
        dense[int(r)-1, int(c)-1] += value
    np.testing.assert_array_equal(dense.sum(axis=1), np.fromfile(expected_path, dtype=np.float32))
    gx = np.array([(i % 11 - 5) * 0.25 for i in range(101)], dtype=np.float32)
    vector = DATA / "generator_small_x.mtx"
    vector.write_text("%%MatrixMarket vector array real general\n101\n" + "\n".join(map(str, gx)) + "\n")
    out = DATA / "generator_small_result.mtx"
    execute("strict", 12, 3, "check-generator-independent", matrix=generated, source=vector, output=out, record=False)
    np.testing.assert_array_equal(load_vector(out), (dense @ gx).astype(np.float64) * 3)
    checks.append({"case": "independent_generator_check", "elements": 101, "max_absolute_error": 0, "passed": True})
    write_json(ROOT / "correctness-small.json", checks)


def generate():
    matrix, expected = DATA / "large_random.mtx", DATA / "large_expected.f32"
    manifest_path = ROOT / "matrix.json"
    if matrix.exists() or expected.exists():
        if not (matrix.exists() and expected.exists() and manifest_path.exists()):
            raise RuntimeError("incomplete dataset exists; inspect before regenerating")
        old = json.loads(manifest_path.read_text())
        if old["matrix_sha256"] != sha(matrix) or old["expected_sha256"] != sha(expected):
            raise RuntimeError("dataset checksum mismatch")
        print("reusing verified dataset", flush=True)
        return
    cmd = [str(BUILD / "generate_matrix"), str(matrix), str(expected), str(N), str(K), str(SEED)]
    print(f"generating {N:,} x {N:,}, {N*K:,} entries ...", flush=True)
    started = time.monotonic()
    capture(cmd)
    manifest = {"created_at": stamp(), "generator_version": 1,
                "generator_sha256": sha(ROOT / "generate_matrix.c"), "command": cmd,
                "rows": N, "columns": N, "nnz_per_row": K, "nonzeros": N*K,
                "seed_decimal": SEED, "seed_hex": hex(SEED), "field": "real", "numeric_precision": "f32",
                "distribution": "one pseudorandom column per equal-width column segment per row; sorted unique columns",
                "values": "q/4, q=1..7, selected from high bits of mix64; exact binary fractions",
                "source": "locally generated synthetic data; no external dataset",
                "generator_license": "MIT (see LICENSE-generator.txt)",
                "density": K/N, "sparsity": 1-K/N,
                "matrix_bytes": matrix.stat().st_size, "matrix_sha256": sha(matrix),
                "expected_sha256": sha(expected), "expected_dtype": "little-endian float32",
                "csr_bytes": 8*(N+1) + 8*N*K, "x_bytes": 4*N, "y_bytes": 4*N,
                "generation_and_hashing_seconds": time.monotonic()-started}
    write_json(manifest_path, manifest)
    print(f"generated {matrix.stat().st_size/1e9:.3f} GB; sha256={manifest['matrix_sha256']}", flush=True)


def large_check():
    import numpy as np
    expected = np.fromfile(DATA / "large_expected.f32", dtype=np.float32)
    results = []
    for threads, repeat in ((1, 1), (12, 3)):
        tag = f"check-large-t{threads}-r{repeat}"
        output = DATA / f"{tag}.mtx"
        execute("strict", threads, repeat, tag, output=output, record=False)
        actual = load_vector(output)
        reference = expected.astype(np.float64) * repeat
        np.testing.assert_array_equal(actual, reference)
        results.append({"case": tag, "elements": int(actual.size), "max_absolute_error": 0,
                        "passed": True, "output_sha256": sha(output)})
        print(f"verified all {actual.size:,} large-matrix result elements", flush=True)
    write_json(ROOT / "correctness-large.json", results)


def benchmark(samples):
    measurements = ROOT / "measurements.csv"
    if measurements.exists():
        raise RuntimeError("measurements.csv already exists; preserve the previous run instead of overwriting it")
    pilot = []
    for threads in (1, 12, 24):
        pilot.append(execute("strict", threads, 4, f"pilot-t{threads}", record=False))
    fastest = min(r["seconds_per_spmv"] for r in pilot)
    repeat = min(128, max(8, math.ceil(0.75 / fastest)))
    # A common repeat count keeps all thread/variant comparisons equivalent.
    write_json(ROOT / "protocol.json", {"created_at": stamp(), "samples": samples,
        "threads": THREADS, "common_repeat": repeat, "pilot": pilot,
        "target_fastest_kernel_seconds": 0.75, "random_order_seed": SEED,
        "timing_scope": "original main.c SpMV timer; excludes load/conversion/output; includes parallel-region entry/exit, per-iteration barriers and first iteration",
        "warmup": "no inserted warmup; original upstream execution retained; first iteration amortized by common repeats",
        "thread_policy": "OpenMP cores/spread, dynamic=false, wait=passive",
        "floating_point": "primary strict uses -O3 -march=native, no -ffast-math; original compiler fp-contract default recorded",
        "ablations": "novec at 1 and 12 threads; fastmath build is diagnostic only, never part of the timed baseline"})
    conditions = [("strict", t) for t in THREADS] + [("novec", t) for t in (1, 12)]
    rng = random.Random(SEED)
    for sample in range(1, samples+1):
        order = conditions.copy()
        rng.shuffle(order)
        for variant, threads in order:
            execute(variant, threads, repeat, f"sample{sample}-{variant}-t{threads}")
    # Original diagnostic mode reports row and nonzero ownership, with no kernel run.
    for threads in (12, 24):
        cmd = [str(binary("strict")), "--matrix-format=f32", "--count-nonzeros", str(DATA / "large_random.mtx")]
        (RAW / f"balance-t{threads}.txt").write_text(capture(cmd, env=omp_env(threads)))
        write_json(RAW / f"balance-t{threads}.command.json", {"command": cmd, "threads": threads})
    write_json(ROOT / "final-memory.json", {"recorded_at": stamp(), "meminfo": Path("/proc/meminfo").read_text()})


def summarize():
    with (ROOT / "measurements.csv").open() as f:
        rows = list(csv.DictReader(f))
    protocol = json.loads((ROOT / "protocol.json").read_text())
    conditions = [("strict", t) for t in THREADS] + [("novec", t) for t in (1, 12)]
    expected_tags = {f"sample{s}-{variant}-t{threads}"
                     for s in range(1, protocol["samples"] + 1)
                     for variant, threads in conditions}
    if len(rows) != len(expected_tags) or {r["tag"] for r in rows} != expected_tags:
        raise AssertionError("missing, extra or duplicate formal measurement")
    for row in rows:
        match = PATTERN.search((RAW / f"{row['tag']}.stdout.txt").read_text())
        if not match or float(match[1]) != float(row["kernel_seconds"]):
            raise AssertionError(f"raw timing mismatch: {row['tag']}")
        if int(match[2]) != int(row["repeat"]) or int(match[3]) != int(row["flops"]):
            raise AssertionError(f"raw work count mismatch: {row['tag']}")
        if int(row["repeat"]) != protocol["common_repeat"] or int(row["flops"]) != 2*N*K*int(row["repeat"]):
            raise AssertionError(f"unexpected work count: {row['tag']}")
    groups = {}
    for r in rows:
        groups.setdefault((r["variant"], int(r["threads"])), []).append(r)
    summaries = []
    base = statistics.median(float(r["seconds_per_spmv"]) for r in groups[("strict", 1)])
    for (variant, threads), values in sorted(groups.items()):
        durations = [float(r["seconds_per_spmv"]) for r in values]
        median = statistics.median(durations)
        # An explicit logical-access model, NOT measured DRAM bandwidth:
        # values 4*nnz + indices 4*nnz + x 4*nnz + row_ptr 8*(N+1)
        # + y read/write 8*N. Cache-line amplification/reuse is not represented.
        modeled_bytes = 12*N*K + 8*(N+1) + 8*N
        summaries.append({"variant": variant, "threads": threads, "samples": len(values),
            "median_ms": median*1000, "min_ms": min(durations)*1000, "max_ms": max(durations)*1000,
            "median_gflops": 2*N*K/median/1e9, "speedup_vs_strict_1t": base/median,
            "parallel_efficiency": base/median/threads,
            "logical_access_model_GBps": modeled_bytes/median/1e9,
            "max_rss_GiB": max(int(r["max_rss_kib"]) for r in values)/1024**2})
    with (ROOT / "summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)
    write_json(ROOT / "summary.json", summaries)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    strict = [r for r in summaries if r["variant"] == "strict"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    t = [r["threads"] for r in strict]
    med = [r["median_ms"] for r in strict]
    axes[0].errorbar(t, med, yerr=[[r["median_ms"]-r["min_ms"] for r in strict],
                                 [r["max_ms"]-r["median_ms"] for r in strict]],
                     marker="o", capsize=4, color="#2563eb")
    axes[0].set(xlabel="OpenMP threads", ylabel="Milliseconds per SpMV (lower is better)")
    axes[1].plot(t, [r["speedup_vs_strict_1t"] for r in strict], "o-", color="#0d9488", label="Measured median")
    axes[1].plot(t, t, "--", color="#94a3b8", label="Ideal linear scaling")
    axes[1].set(xlabel="OpenMP threads", ylabel="Speedup over 1 thread")
    axes[1].legend()
    for ax in axes:
        ax.set_xticks(t)
        ax.grid(alpha=0.2)
    fig.suptitle("Untouched csrspmv baseline | 12M x 12M, 96M nonzeros, float32")
    fig.savefig(ROOT / "baseline.png", dpi=170)
    fig.savefig(ROOT / "baseline.svg")
    plt.close(fig)
    strict_map = {r["threads"]: r for r in strict}
    best = min(strict, key=lambda r: r["median_ms"])
    protocol = json.loads((ROOT / "protocol.json").read_text())
    table = "\n".join(
        f"| {r['threads']} | {r['median_ms']:.3f} | {r['min_ms']:.3f}–{r['max_ms']:.3f} | {r['median_gflops']:.4f} | {r['speedup_vs_strict_1t']:.2f}× | {r['parallel_efficiency']*100:.1f}% |"
        for r in strict)
    controls = "\n".join(
        f"| {r['threads']} | {strict_map[r['threads']]['median_ms']:.3f} | {r['median_ms']:.3f} | {r['median_ms']/strict_map[r['threads']]['median_ms']*100:.1f}% |"
        for r in summaries if r["variant"] == "novec")
    report = f"""# 原始 csrspmv 基线实测结果

实验日期：2026-10-25。汇总生成时间：{stamp()}。

## 正式基线

原始版本 `9352c865044f4c8b344d6fe5a277200a89f7a08b`，GCC 11.4.0，`-O3 -march=native -fopenmp`，未启用 fast-math。矩阵为 1200 万 × 1200 万、9600 万个非零元，f32。每个进程重复 {protocol['common_repeat']} 次，每组 {protocol['samples']} 个独立进程；以下为每次 SpMV 的统计。

| 线程数 | 中位耗时 / ms | 最小–最大 / ms | GFLOP/s | 相对 1 线程加速比 | 并行效率 |
| --- | --- | --- | --- | --- | --- |
{table}

本次原始代码各线程配置中，中位耗时最低的是 **{best['threads']} 线程，{best['median_ms']:.3f} ms/次，{best['median_gflops']:.4f} GFLOP/s**，相对原始代码单线程为 {best['speedup_vs_strict_1t']:.2f} 倍。这个加速比反映已有 OpenMP 随线程数的扩展，不能作为本人新增优化效果。

## 关闭自动向量化的对照

同一源码、矩阵、重复次数、线程绑定和测试轮次，仅增加 `-fno-tree-loop-vectorize -fno-tree-slp-vectorize`。

| 线程数 | 默认基线中位耗时 / ms | 关闭自动向量化 / ms | 关闭后 / 默认耗时 |
| --- | --- | --- | --- |
{controls}

GCC 的 f32 内层循环诊断和对应汇编均确认默认基线已包含向量化。每行 8 项进入 256 位 gather/乘法路径，求和仍为标量加法链。因此，应区分“生成了 SIMD 指令”与“对该负载一定有收益”；性能以表中数据为准。fast-math 只做编译诊断，没有作为正式优化参与此表。

## 正确性、资源与瓶颈判断

- 三个构建的 12 组小矩阵用例，以及 1 组生成器独立校验通过；包括非均匀 x、矩形矩阵、重复坐标、空行、负数和重复累加。
- 大矩阵在 1 线程重复 1 次、12 线程重复 3 次时，全量核对各 1200 万个输出元素，最大绝对误差为 0。参考语义是 `y = repeat × Ax`。
- 正式样本最大进程 RSS 为 {max(r['max_rss_GiB'] for r in summaries):.3f} GiB。该数值包含读入的坐标数据与 CSR 转换时的峰值，不是只有内核工作集。
- 各行均有 8 个非零元；原程序的 `--count-nonzeros` 分配结果见 `raw/balance-t12.txt`、`raw/balance-t24.txt`。这是行长均匀的负载，不能由本实验评估不均匀行长的调度优化。
- CSR 约 864 MB，x、y 各 48 MB，远超 WSL 报告的缓存规模；x 的列访问在全局分散。结果适合继续研究间接访存、缓存复用、gather 成本和线程扩展，而非用 tiny test 的耗时推断大矩阵表现。
- 线程扩展、向量化对照属于现象证据，不能单凭加速曲线就宣布“DRAM 带宽已饱和”。本次没有独立测得持续内存带宽上限，也没有生成正式 Roofline 图。
- `logical_access_model_GBps` 是 README 中定义的逻辑访问模型，不是硬件实测 DRAM 带宽；GFLOP/s 按每个非零元乘、加各一次计数。
- 运行于 WSL 和笔记本宿主机；未锁定宿主机频率，也未独占系统。三个样本的极差仅用于显示本次波动。结论限于本机、当前编译器、f32 和这一种矩阵分布。

## 文件索引

复现实验步骤和解释见 [README.md](README.md)。逐次数据见 [measurements.csv](measurements.csv)，汇总见 [summary.csv](summary.csv)，配置见 [protocol.json](protocol.json)，输入来源及校验和见 [matrix.json](matrix.json)。原始 stdout/stderr、命令与资源记录在 `raw/`。

![原始代码线程扩展与耗时](baseline.png)

可选 perf 采样与上述正式计时分开保存；若执行，采样解释另见 [采样分析.md](采样分析.md)，它不改变本表结果。
"""
    (ROOT / "结果分析.md").write_text(report, encoding="utf-8")
    print(json.dumps(summaries, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["all", "prepare", "generate", "large-check", "benchmark", "summarize"], default="all")
    parser.add_argument("--samples", type=int, default=3)
    args = parser.parse_args()
    if args.samples < 3:
        parser.error("use at least three independent process samples")
    if args.stage in ("all", "prepare"):
        prepare()
        smoke()
    if args.stage in ("all", "generate"):
        generate()
    if args.stage in ("all", "large-check"):
        large_check()
    if args.stage in ("all", "benchmark"):
        benchmark(args.samples)
    if args.stage in ("all", "summarize"):
        summarize()


if __name__ == "__main__":
    main()
