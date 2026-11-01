# Maintainer's final public-release checklist

The project representative has confirmed permission to release the research data and anonymized reviewer votes. The release scope is **analysis-ready datasets rather than complete provider-response envelopes**. Code and data licenses are supplied in the repository root.

Before making the GitHub repository public, the maintainer should confirm:

- [ ] The permission covers all included financial scenarios, records, and anonymized annotations under the selected MIT/CC BY 4.0 terms.
- [ ] The manuscript title and author attribution are accurate in the public repository and associated paper citation.
- [ ] The historical `/home/charles/sibyl_v2` path references retained in source/freeze metadata are acceptable to publish.
- [ ] No secret, personal, confidential, or third-party-restricted content is present, including in synthetic prompt text; the automated regex screen is **not** a guarantee.
- [ ] The paper's tables/figures agree with `expected/`, and its data-availability statement describes the parsed-outcome rather than full raw-envelope scope.
- [ ] The GitHub public repository passes `verify_manifest.py`, `validation/verify_benchmark_validation.py`, and `reproduce_all.py` after a clean clone (or its GitHub Actions workflow passes).
- [ ] Only after public visibility and reproducibility have been verified is the actual repository URL inserted into the paper.

Original raw provider envelopes, local private ZIP archives, `.env`, and external provider secrets must never be added to this repository. If previously exposed API credentials still exist, revoke and rotate them.
