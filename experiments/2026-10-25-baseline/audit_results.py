#!/usr/bin/env python3
"""Verify source/data integrity and cross-check the recorded experiment artifacts."""
import csv
import json
from pathlib import Path
import subprocess
import run_baseline as b

checks = {}
provenance = json.loads((b.ROOT / "provenance.json").read_text())
manifest = json.loads((b.ROOT / "matrix.json").read_text())
protocol = json.loads((b.ROOT / "protocol.json").read_text())

head = b.capture(["git", "-C", str(b.CORE), "rev-parse", "HEAD"]).strip()
assert head == provenance["source_commit"]
subprocess.run(["git", "-C", str(b.CORE), "diff", "--quiet", "HEAD"], check=True)
status = b.capture(["git", "-C", str(b.CORE), "status", "--porcelain=v1"])
assert status == provenance["source_status_before"] == ""
checks["original_core_commit_and_clean_worktree_preserved"] = True

for variant, info in provenance["builds"].items():
    assert b.sha(b.binary(variant)) == info["binary_sha256"]
    for name, digest in info["source_sha256"].items():
        assert b.sha(b.CORE / name) == digest
        assert b.sha(b.BUILD / variant / name) == digest
    assert (b.BUILD / variant / "Makefile").read_bytes() == (b.CORE / "Makefile").read_bytes()
checks["all_three_build_sources_makefiles_and_binary_hashes_match"] = True

assert b.sha(b.DATA / "large_random.mtx") == manifest["matrix_sha256"]
assert b.sha(b.DATA / "large_expected.f32") == manifest["expected_sha256"]
assert b.sha(b.ROOT / "generate_matrix.c") == manifest["generator_sha256"]
assert (b.DATA / "large_random.mtx").stat().st_size == manifest["matrix_bytes"]
assert manifest["rows"] == b.N and manifest["nonzeros"] == b.N*b.K
checks["large_matrix_and_reference_and_generator_checksums_match"] = True

with (b.ROOT / "measurements.csv").open() as f:
    records = list(csv.DictReader(f))
assert len(records) == 24
for row in records:
    tag = row["tag"]
    stdout = (b.RAW / f"{tag}.stdout.txt").read_text()
    match = b.PATTERN.search(stdout)
    command = json.loads((b.RAW / f"{tag}.command.json").read_text())
    resources = json.loads((b.RAW / f"{tag}.resource.json").read_text())
    assert command["returncode"] == resources["exit_status"] == 0
    assert float(match[1]) == float(row["kernel_seconds"])
    assert int(match[2]) == int(row["repeat"]) == protocol["common_repeat"]
    assert int(match[3]) == int(row["flops"]) == 2*b.N*b.K*int(row["repeat"])
    assert abs(float(row["gflops"]) - int(row["flops"])/float(row["kernel_seconds"])/1e9) < 1e-10
    assert command["environment"]["OMP_NUM_THREADS"] == row["threads"]
    assert command["environment"]["OMP_PROC_BIND"] == "spread"
    assert command["environment"]["OMP_PLACES"] == "cores"
    assert command["environment"]["OMP_DYNAMIC"] == "FALSE"
    assert (b.RAW / f"{tag}.stderr.txt").read_text() == ""
checks["all_24_formal_records_match_raw_commands_stdout_resources_and_work"] = True

for filename, count in (("correctness-small.json", 13), ("correctness-large.json", 2)):
    cases = json.loads((b.ROOT / filename).read_text())
    assert len(cases) == count
    assert all(case["passed"] and case["max_absolute_error"] == 0 for case in cases)
checks["all_15_correctness_records_pass"] = True

for threads in (12, 24):
    rows = (b.RAW / f"balance-t{threads}.txt").read_text().splitlines()[1:]
    assert len(rows) == threads
    for line in rows:
        tid, nrows, nnz = map(int, line.split())
        assert 1 <= tid <= threads and nrows == b.N//threads and nnz == b.N*b.K//threads
checks["measured_thread_row_and_nonzero_loads_are_equal"] = True

for path in (b.DATA / "large_random.mtx", b.binary("strict"), b.RAW / "baseline-perf.data"):
    subprocess.run(["git", "-C", str(b.MATERIALS), "check-ignore", "--quiet", str(path)], check=True)
subprocess.run(["git", "-C", str(b.MATERIALS), "diff", "--check"], check=True)
checks["large_inputs_builds_perf_binary_ignored_and_tracked_diff_has_no_whitespace_errors"] = True

profile = json.loads((b.ROOT / "profile.json").read_text())
assert profile["returncode"] == profile["perf-report.txt"]["returncode"] == profile["perf-annotate-spmv.txt"]["returncode"] == 0
assert "Total Lost Samples: 0" in (b.ROOT / "perf-report.txt").read_text()
checks["separate_perf_profile_and_readable_reports_succeeded"] = True

artifacts = {}
for name in ("run_baseline.py", "generate_matrix.c", "omp_probe.c", "profile_baseline.py",
             "measurements.csv", "summary.csv", "protocol.json", "provenance.json"):
    artifacts[name] = b.sha(b.ROOT / name)
b.write_json(b.ROOT / "audit.json", {"audited_at": b.stamp(), "checks": checks,
    "artifact_sha256": artifacts, "core_status_after": status,
    "materials_git_status": b.capture(["git", "-C", str(b.MATERIALS), "status", "--short"]),
    "note": "Read-only Git inspection only; no add, commit, branch, push or remote writes performed."})
print(json.dumps(checks, ensure_ascii=False, indent=2))
