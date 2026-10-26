#!/usr/bin/env python3
"""Recompute a v2 review from existing measurements. No SpMV runs or Git writes."""
from collections import defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXP = ROOT / "experiments/2026-10-26-v2"


def med(group, field):
    return median(float(r[field]) for r in group)


def main():
    source = EXP / "measurements.csv"
    records = list(csv.DictReader(source.open(encoding="utf-8", newline="")))
    groups = defaultdict(list)
    for row in records:
        key = (row["phase"], row["matrix"], int(row["threads"]),
               int(row["repeat"]), row["variant"])
        groups[key].append(row)
    cases = []
    for (phase, matrix, threads, repeat, variant), opt in sorted(groups.items()):
        if phase not in {"screen", "heldout", "large"} or variant != "v2-auto":
            continue
        base = groups[(phase, matrix, threads, repeat, "original")]
        base_total, opt_total = med(base, "total_s"), med(opt, "total_s")
        base_e, opt_e, opt_p = (med(base, "execute_s"), med(opt, "execute_s"),
                                med(opt, "prepare_s"))
        saving_per_call = (base_e - opt_e) / repeat
        # Illustrative local linear model only: E/R also contains team startup.
        # This is not a measured threshold for a different repetition count.
        break_even = (math.floor(opt_p / saving_per_call) + 1
                      if saving_per_call > 0 else None)
        cases.append({
            "phase": phase, "matrix": matrix, "requested_threads": threads,
            "repeat": repeat, "samples_original": len(base), "samples_v2": len(opt),
            "original_total_ms": 1000 * base_total,
            "v2_total_ms": 1000 * opt_total,
            "v2_time_change_percent": 100 * (opt_total / base_total - 1),
            "original_over_v2": base_total / opt_total,
            "original_execute_ms": 1000 * base_e,
            "v2_execute_ms": 1000 * opt_e,
            "v2_prepare_ms": 1000 * opt_p,
            "prepare_share_percent_median_of_process_ratios":
                100 * median(float(r["prepare_s"]) / float(r["total_s"]) for r in opt),
            "v2_row_scan_ms": 1000 * med(opt, "row_scan_s"),
            "v2_column_validation_ms": 1000 * med(opt, "column_validation_s"),
            "v2_policy_ms": 1000 * med(opt, "policy_s"),
            "selected": sorted({r["selected"] for r in opt}),
            "actual_threads": sorted({int(r["actual_threads"]) for r in opt}),
            "partition": sorted({r["partition"] for r in opt}),
            "local_linear_break_even_R_illustration": break_even,
            "raw_commands_original": [r["command_file"] for r in base],
            "raw_commands_v2": [r["command_file"] for r in opt],
        })
    # One condition per matrix: no triple counting large at R=1/9/100.
    slice12 = [c for c in cases if c["requested_threads"] == 12
               and (c["matrix"] != "large" or c["repeat"] == 9)]
    assert len(slice12) == 32
    counts = {"faster_over_5_percent": 0, "within_plus_minus_5_percent": 0,
              "slower_over_5_percent": 0}
    for c in slice12:
        delta = c["v2_time_change_percent"]
        name = ("faster_over_5_percent" if delta < -5 else
                "slower_over_5_percent" if delta > 5 else
                "within_plus_minus_5_percent")
        counts[name] += 1
    assert sum(counts.values()) == 32
    result = {
        "date": "2026-10-26 Asia/Shanghai",
        "kind": "retrospective analysis; no new performance samples",
        "input": str(source.relative_to(ROOT)),
        "input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "process_records": len(records),
        "primary_decision": json.loads((EXP / "decision.json").read_text()),
        "one_condition_per_matrix_T12": {
            "n": len(slice12), "counts": counts,
            "rule": "screen/heldout/large; original vs v2-auto; large R9 only; other R as recorded",
            "interpretation": "descriptive median thresholds, not significance tests or a user workload distribution",
        },
        "cautions": [
            "total is median of each process P+E+cleanup; component medians need not sum to it",
            "only the original large experiment has adjacent randomized process pairs and paired intervals",
            "local linear break-even illustrations reuse E/R at the measured R; startup/cache/R changes invalidate extrapolation",
            "no finite illustrative break-even if measured optimized execute median is not faster",
            "v2 heldout inputs are now development evidence for v2.1, not new v2.1 holdout inputs",
        ],
        "cases": cases,
    }
    (HERE / "diagnosis.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    columns = ["phase", "matrix", "requested_threads", "repeat", "samples_original", "samples_v2",
               "original_total_ms", "v2_total_ms", "v2_time_change_percent", "original_over_v2",
               "original_execute_ms", "v2_execute_ms", "v2_prepare_ms",
               "prepare_share_percent_median_of_process_ratios", "v2_row_scan_ms",
               "v2_column_validation_ms", "v2_policy_ms", "selected", "actual_threads", "partition",
               "local_linear_break_even_R_illustration"]
    with (HERE / "case-review.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for c in cases:
            writer.writerow({k: ";".join(map(str, c[k])) if isinstance(c[k], list) else c[k]
                             for k in columns})
    print(json.dumps({"records": len(records), "comparison_conditions": len(cases),
                      "T12_one_condition_per_matrix": counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
