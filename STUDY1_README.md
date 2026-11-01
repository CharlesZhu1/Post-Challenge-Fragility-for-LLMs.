# Study 1 analysis notes

This repository's Study 1 analysis uses **minimized parsed-choice and assignment-status records**. It does not contain all raw model-provider response envelopes.

To rerun Study 1 alone:

```bash
python reproduce_study1.py
```

The script writes `STAGE1_RESULTS_V2.json` and `STAGE1_REPORT_V2.txt` in `control_protocol/extension_C_matched_three_model_v1/stage1_analysis/` and uses only local standard-library code. Its expected output is stored in `expected/`.

Study 1 covers 77 financial scenarios, with a prespecified 70-scenario clean-label sensitivity subset and seven role-ambiguous cases. The historical original script is retained in `provenance/`; the portable script changes only the hard-coded working-directory path. The separately retained GPT and Claude operational-state files contain the analysis-essential assignment outcomes, not original provider transport payloads.
