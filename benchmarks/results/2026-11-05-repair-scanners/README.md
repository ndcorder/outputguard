# Repair scanner measurements — 2026-11-05

These reports retain the measurements taken while repairing unquoted-key and
inner-quote handling in both ports. Inputs and expected outputs are checked by
`benchmarks/cases.json` before timing. Each runtime and phase ran serially.

`metadata.json` records source revisions, strategy hashes, fixture hashes, and
benchmark settings. Each report includes runtime, platform, CPU clock, sample
count, warmup count, environment snapshots, and median/minimum microseconds.

Key scans used 200 iterations per sample; inner-quote scans used 5. Both used
7 samples and 50 warmup iterations. Five iterations limit precision for very
short calls, so the table focuses on the 1,000-entry workloads. Times below
are median milliseconds per call, shown as before → after.

| Workload | Python 3.10 | Node 26 | Node 18 |
|---|---:|---:|---:|
| Quoted mappings | 0.940 → 0.059 | 0.253 → 0.007 | 0.268 → 0.006 |
| Bare keys | 0.494 → 0.691 | 0.130 → 0.091 | 0.143 → 0.097 |
| Nested bare keys | 0.987 → 1.564 | 0.279 → 0.172 | 0.342 → 0.189 |
| Clean string-valued objects | 105.438 → 3.601 | 305.410 → 0.390 | 373.225 → 0.474 |
| Objects needing inner-quote repair | 43.519 → 3.089 | 113.596 → 0.323 | 127.102 → 0.373 |
| Objects with existing escape pairs | 254.611 → 3.680 | 531.715 → 0.432 | 740.776 → 0.514 |

Python’s added key-position checks cost about 0.2–0.6 ms on the dense bare-key
workloads. Inner-quote scanning removes repeated output joins, which caused
growth beyond linear time as documents grew. The new scanner copies spans and
joins once.

Only workloads with identical expected output appear in both phases. Cases
covering new behavior, such as inner quotes in array/root strings or keys next
to comments, appear only in the after reports. Results describe these inputs
and this machine; compare phases within the same runtime.

Use the repository benchmark comparison command to compare a matching pair
of reports. The cases remain in the main corpus under `keys_cost_*` and
`inner_cost_*` for future regression checks.

`verification.json` records full-suite results, installed-package and CLI checks,
cross-runtime parity, artifact hashes, and audited runtime source hashes.
