# Release candidate verification and remaining owner review

The final publication candidate was tested using an independent local git repository and a freshly cloned checkout. The following commands passed from the clean clone without model API calls:

```bash
python verify_manifest.py
python validation/verify_benchmark_validation.py
python reproduce_all.py
```

The statistical output comparisons passed all four components (Study 1, Study 2, Study 3 sequential, controlled history). The benchmark validation produced Fleiss' kappa 0.8357601957, with 65 unanimous, 76 majority-label, and 76 majority/gold-agreement scenarios out of 77.

Automated heuristics over the candidate found **zero** common-format OpenAI, GitHub, Google or AWS tokens, PEM private keys, authorization bearer tokens, email addresses, Windows user-profile paths or IPv4 addresses. There are historical Linux home-directory references, including in immutable frozen metadata and original source-code provenance. These are **not credentials**, but the repository owner should approve their publication.

**Known scope limitation:** This release includes analysis-ready parsed outcomes and experimental designs, not a complete raw provider API-response archive. Original raw reviewer CSVs are not included; only anonymized choices and consensus are. Old scenario-inventory `not_human_certified` flags are preserved. Reviewer independence and expert qualifications are not demonstrated by the vote files alone.

**Rights and licensing:** The project representative indicated publication permission, and the candidate supplies MIT terms for code and CC BY 4.0 terms for data as the proposed default. The rights-holder/maintainer must ensure this permission allows sublicensing on those terms and that no confidential or third-party restricted material is included.

**Publication itself is not complete:** A human owner must review the remaining scope and privacy risks, upload the extracted files, check the public repository, and insert the actual GitHub URL into the paper.
