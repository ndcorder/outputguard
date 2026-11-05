# Final repair measurements — 2026-11-05

The encoding, delimiter, and Markdown-wrapper fixes preserve structured payloads
through the default repair sequence. These paired reports retain their timing
tradeoffs, source hashes, and baseline revisions. Metadata is in `metadata.json`;
the final compatibility and package audit is in `verification.json`.

Each runtime and phase ran serially. Outputs were checked before CPU timing:
200 iterations per sample, seven samples, and 50 warmups. Feature-changing
cases appear only in after reports. Compare phases within the same runtime.

The following 1,000-entry workloads show median microseconds per call,
before → after.

| Workload | Python 3.10 | Node 26 | Node 18 |
|---|---:|---:|---:|
| encoding/late_signal | 44.94 → 1638.05 | 95.64 → 213.62 | 99.85 → 232.72 |
| closers/clean_numbers | 97.56 → 5.89 | 4.10 → 2.17 | 4.20 → 0.79 |
| closers/quoted_objects | 1028.92 → 1969.27 | 66.64 → 118.91 | 73.44 → 131.21 |
| closers/deep_objects | 453.84 → 1162.62 | 23.07 → 94.44 | 28.05 → 111.41 |
| fences/wrapper | 10.05 → 10.36 | 0.29 → 0.66 | 0.60 → 0.65 |
| fences/prose | 2.40 → 237.62 | 1.30 → 27.80 | 2.08 → 35.78 |
| fences/escaped_literal | 102.61 → 1.69 | 26.77 → 0.29 | 25.86 → 0.33 |

The source corpus retains these inputs under `encoding_cost_*`,
`closers_cost_*`, and `fences_cost_*` for future comparisons.

The final source passes 42,495 Python tests on Python 3.10/3.14 and 37,257
JavaScript tests on Node 18/26. Fresh npm production graphs pass 26,437 public
contracts on both Node versions, and real CLI processes agree on 215 contracts.
Python source archives are built from a clean checkout and exclude local agent
instructions and environment files. Details and artifact hashes are retained in
`verification.json`.
