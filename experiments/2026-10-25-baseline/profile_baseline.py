#!/usr/bin/env python3
"""Optional sampling of the untouched binary, separately from baseline timings.

Sampling reports contain file reading/conversion as well as SpMV. Interpret
the csr_matrix_int32_spmv symbol separately; no whole-process counter is
presented as an inner-kernel DRAM bandwidth measurement.
"""
import json
from pathlib import Path
import subprocess
import run_baseline as baseline

root = Path(__file__).resolve().parent
raw = root / "raw"
data = raw / "baseline-perf.data"
command = ["perf", "record", "-e", "cycles:u", "-e", "cache-misses:u", "-F", "199",
           "-o", str(data), "--", str(baseline.binary("strict")), "--verbose",
           "--matrix-format=f32", "--source-vector-format=f32", "--destination-vector-format=f32",
           "--repeat=128", str(root / "data" / "large_random.mtx")]
metadata = {"started_at": baseline.stamp(), "command": command, "threads": 12,
            "scope": "whole-process user-space sampling; annotation isolates SpMV; no measured DRAM bandwidth"}
print("starting separate perf sample (not included in measurements.csv)", flush=True)
result = subprocess.run(command, env=baseline.omp_env(12), text=True,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1200)
(raw / "profile.stdout.txt").write_text(result.stdout)
(raw / "profile.stderr.txt").write_text(result.stderr)
metadata["returncode"] = result.returncode
if result.returncode == 0:
    commands = {
        "perf-report.txt": ["perf", "report", "--stdio", "--no-children", "--percent-limit", "0.5",
                            "--sort", "dso,symbol", "--show-total-period", "-i", str(data)],
        "perf-annotate-spmv.txt": ["perf", "annotate", "--stdio", "--symbol", "csr_matrix_int32_spmv",
                                   "--percent-type", "local-hits", "--stdio-color", "never", "-i", str(data)],
    }
    for filename, cmd in commands.items():
        report = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (root / filename).write_text(report.stdout)
        metadata[filename] = {"command": cmd, "returncode": report.returncode}
else:
    metadata["limitation"] = "perf sampling unavailable; baseline timings and correctness checks remain valid"
metadata["finished_at"] = baseline.stamp()
baseline.write_json(root / "profile.json", metadata)
print(json.dumps(metadata, ensure_ascii=False, indent=2), flush=True)
