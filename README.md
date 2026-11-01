# Post-Challenge Fragility of LLMs — Data and Code

This repository provides the **analysis-ready experimental data, frozen study designs, anonymized benchmark-validation votes, and Python code** needed to reproduce the reported statistical analyses in *Post-Challenge Fragility of LLMs: A Case Study in Financial Decision Tasks*.

**Scope:** This is an analysis-reproducibility release, **not** a full archive of original model-provider API responses. No live API calls are needed. The records and analyses are for frozen model versions `gpt-4o-mini-2024-07-18`, `gpt-5-mini-2025-08-07`, and `claude-sonnet-4-6`.

## Reproduce

Install Python **3.10 or later**. The analyses depend only on the Python standard library.

```bash
python verify_manifest.py
python validation/verify_benchmark_validation.py
python reproduce_all.py
```

`verify_manifest.py` should be run **before** reproducing results: analysis scripts overwrite their output files (Study 3 also updates `created_utc`). `reproduce_all.py` compares each recreated results JSON with the canonical JSON under `expected/`, ignoring only the Study 3 generation timestamp. The 10,000-draw bootstrap analyses may take several minutes. No API credentials, network calls, or service payments are required.

## Study coverage

| Dataset | Intended calls | Valid/completed | Reproduction |
|---|---:|---:|---|
| Study 1 — follow-up challenge responses | 3,696 | 3,695 | `reproduce_study1.py` |
| Study 2 — parent-state intervention | 3,780 | 3,775 | `run_stage3_analysis_v1.py` |
| Study 3 — sequential reversibility | 7,132 | 7,128 | `run_stage4_analysis_r1_v1.py` |
| Study 3 — controlled history | 1,260 | 1,260 | `run_controlled_history_analysis_v1.py` |

The 77-scenario Study 1 benchmark has a frozen 70-scenario clean-label sensitivity subset. Study 2 uses the exact frozen 70-scenario selection. Seven scenarios with overlapping option roles are not part of that 70-scenario selection.

## Repository map

- `control_protocol/extension_C_matched_three_model_v1/frozen/`: 77-scenario inventory
- `control_protocol/extension_C_matched_three_model_v1/runs/`: minimized Study 1 GPT records
- `control_protocol/extension_A_crossmodel_v1/`: minimized Study 1 Claude records and constants
- `control_protocol/extension_C_matched_three_model_v1/stage3_parent_state_intervention/`: Study 2 assignments, states, freeze, analysis and results
- `control_protocol/extension_C_matched_three_model_v1/stage4_reversibility_v1/`: Study 3 sequential collection, controlled-history assignments, and analysis
- `validation/`: anonymized annotations for 77 scenarios, per-scenario consensus, verification code
- `expected/`: expected statistical result JSON files
- `provenance/`: original analysis scripts and historical frozen metadata, preserved for research provenance (not executable entrypoints)
- `docs/`: reproducibility limitations, benchmark-annotation caveats, and data scope

## Benchmark annotation scope

The release includes three anonymized choices for each of the 77 scenarios and the calculation of Fleiss' κ = **0.835760**: 65/77 unanimous, 76/77 with a majority, and 76/77 with majority agreement to the frozen gold label. **One scenario has no majority.** The original frozen inventory contains historical `not_human_certified` fields; these are kept unchanged. The provided records do not independently establish annotator credentials, independence or blinding; see `docs/BENCHMARK_VALIDATION.md`.

## Data availability limitations

The published objects are **parsed outcomes and analysis inputs**, not full raw API transport envelopes. We do not claim that re-querying current external model APIs will return the same responses. The data include frozen model and prompt designs and saved assignment status, and the scripts recreate the published statistical outputs without model calls. See `docs/DATA_SCOPE_AND_LIMITATIONS.md` for missingness and protocol-amendment details. Some original provenance metadata contains the historical absolute Linux path of the experiment computer; this is not used by the portable entrypoint scripts.

## License

- **Python/code and documentation:** MIT (`LICENSE`).
- **Benchmark, derived data, anonymized annotations, and other release data:** Creative Commons Attribution 4.0 International (`LICENSE-DATA.md`).

Please cite the associated paper when using this resource.
