#!/usr/bin/env python3
"""Analytical storage/padding estimates and existing baseline comparisons.

This script does not implement or benchmark any optimized SpMV kernel.
It reads the archived baseline metadata and calculates explicitly stated models.
"""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASELINE = ROOT.parent.parent / "experiments" / "2026-10-25-baseline"


def padding(lengths, chunk, sorting_scope=1):
    lengths = list(lengths)
    if sorting_scope > 1:
        ordered = []
        for i in range(0, len(lengths), sorting_scope):
            ordered.extend(sorted(lengths[i:i+sorting_scope], reverse=True))
        lengths = ordered
    slots = sum(chunk * max(lengths[i:i+chunk], default=0)
                for i in range(0, len(lengths), chunk))
    nnz = sum(lengths)
    return {"rows": len(lengths), "nnz": nnz, "chunk": chunk,
            "sorting_scope": sorting_scope, "slots": slots,
            "padding_multiplier": slots/nnz if nnz else None}


def main():
    manifest = json.loads((BASELINE / "matrix.json").read_text())
    with (BASELINE / "summary.csv").open() as f:
        rows = list(csv.DictReader(f))
    grouped = {(r["variant"], int(r["threads"])): r for r in rows}
    controls = []
    for threads in (1, 12):
        default = float(grouped[("strict", threads)]["median_ms"])
        novec = float(grouped[("novec", threads)]["median_ms"])
        controls.append({"threads": threads, "strict_median_ms": default,
                         "novec_median_ms": novec,
                         "observed_time_reduction_percent": (default-novec)/default*100,
                         "scope": "existing baseline only; not a newly optimized implementation"})
    uniform = []
    m, k = manifest["rows"], manifest["nnz_per_row"]
    for c in (8, 16):
        slices = (m+c-1)//c
        slots = slices*c*k
        # Deliberately explicit model: keep CSR resident; int64 slice offsets
        # AND int64 widths; no row_map or per-row lengths for this uniform case.
        metadata_bytes = 8*(slices+1) + 8*slices
        data_bytes = slots*8  # f32 values + int32 column indices
        uniform.append({"chunk": c, "slices": slices, "slots": slots,
                        "padding_multiplier": slots/manifest["nonzeros"],
                        "derived_value_index_bytes": data_bytes,
                        "modeled_slice_metadata_bytes": metadata_bytes,
                        "modeled_resident_CSR_plus_SELL_plus_xy_bytes":
                            manifest["csr_bytes"] + data_bytes + metadata_bytes
                            + manifest["x_bytes"] + manifest["y_bytes"],
                        "not_included": "allocator overhead, inspector/tuning temporary arrays; generic unequal-row maps/lengths"})
    cases = {
        "uniform8_C8": padding([8]*64, 8),
        "uniform8_C16": padding([8]*64, 16),
        "one_giant_row_C8": padding([1_000_000] + [1]*7, 8),
        "mixed_no_sort": padding([1024, 4, 4, 4]*16, 8),
        "mixed_sort_scope64": padding([1024, 4, 4, 4]*16, 8, 64),
        "all_empty": padding([0]*17, 8),
        "tail_17_rows": padding([8]*17, 8),
    }
    assert uniform[0]["padding_multiplier"] == uniform[1]["padding_multiplier"] == 1
    assert 7.99 < cases["one_giant_row_C8"]["padding_multiplier"] < 8
    assert cases["mixed_sort_scope64"]["padding_multiplier"] == 1
    assert cases["all_empty"]["padding_multiplier"] is None
    source_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in (BASELINE / "matrix.json", BASELINE / "summary.csv")}
    output = {
        "analysis_date": "2026-10-25", "kind": "analytical_estimate_not_new_benchmark",
        "source_artifact_sha256": source_hashes, "existing_controls": controls,
        "uniform_baseline_storage_estimates": uniform,
        "padding_counterexamples": cases,
        "break_even_condition": "T1<T0 and R>P/(T0-T1); P includes inspect, conversion and tuning",
        "unmeasured": ["optimized kernel time", "conversion time", "actual peak RSS of an optimized implementation",
                       "performance effect of sorting", "DRAM bandwidth ceiling"],
    }
    (ROOT / "feasibility.json").write_text(json.dumps(output, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"storage_estimates": uniform, "padding_counterexamples": cases}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
