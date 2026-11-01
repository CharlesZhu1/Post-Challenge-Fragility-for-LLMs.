# Three-reviewer benchmark validation (77 financial scenarios)

The original `validation/expert_gold_validation` source ZIP contains three completed reviewer files and one per-seed summary. The staging release contains two derived CSV files: anonymized reviewer-choice records (`validation/benchmark_votes_anonymized.csv`) and a per-scenario consensus table (`validation/benchmark_consensus.csv`). Reviewer identities, free-text comments and the full original private source files are not included.

## Independently checked facts

- All 3 reviewer source files cover the same 77 distinct `seed_id` values, which exactly match the frozen 77-scenario inventory.
- The 231 reviewer choices (A/B/C/D) reproduce the original per-seed review summary, without any mismatches.
- **65/77** scenarios have three-way unanimity. **76/77** have at least two agreeing annotators. The resulting majority equals the frozen gold label on **76/77**; the remaining scenario has three different votes and **no majority**, not a majority contrary to gold.
- **Fleiss' κ = 0.8357601957**, with observed pairwise agreement 0.8917748918, on all 77 scenarios.
- The frozen 70-scenario Study 2 selection matches 70 entries in the 77-scenario inventory, without changes to scenario content. Seven excluded scenarios have overlapping option roles; **do not conflate role ambiguity with a missing majority label**.

## Interpretation and limitations

- The old benchmark inventory's `not_human_certified` flags are historical metadata; they have not been silently edited or reclassified by this addition. These separate annotation files are evidence of a later validation activity.
- **Reviewer 1's 77 choices all match the benchmark gold options.** The reviewer files alone do not establish reviewer credentials, independence, blinding, or the exact timing of validation relative to benchmark construction. Confirm these facts before describing the labels as independently expert-certified in a paper or README.
- The deidentified vote table preserves stable annotator numbering for calculation, but does not include names or direct contact details. Publication of even anonymized ratings should still receive appropriate author and data-rights approval.
- There is no evidence in these four input CSVs for reviewer rationales, confidence ratings or adjudication of the no-majority example: `g4_123S_adverse_document_summarization_19`.

## Reproduce these checks

From the repository root, run:

```bash
python validation/verify_benchmark_validation.py
```

Python standard library only; no model API calls, no network access. See `validation/benchmark_validation_summary.json` for exact agreement values.
