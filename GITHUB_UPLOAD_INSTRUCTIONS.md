# GitHub publication instructions

This folder is the **public release candidate**. Upload its **extracted contents**, not the ZIP archive, and do not upload the original `sibyl_v2` or Windows `findeceptagent` project.

## Before publishing

1. Read `docs/PUBLICATION_CHECKLIST.md`; particularly confirm the MIT + CC BY 4.0 license terms and historical local Linux paths.
2. Run locally in the extracted folder, in this order:

```bash
python verify_manifest.py
python validation/verify_benchmark_validation.py
python reproduce_all.py
```

3. Create a GitHub repository, preferably private during the final review. GitHub Desktop or standard git will upload the 26 MB canonical collection more reliably than the browser uploader. Example after creating an **empty** repository on GitHub:

```bash
git init -b main
git add .
git commit -m "Release reproducible research data and code"
git remote add origin https://github.com/OWNER/REPOSITORY.git
git push -u origin main
```

Replace `OWNER/REPOSITORY` with the actual repo and authenticate with your configured GitHub account. Do **not** copy the literal example URL. If a repository already contains a README or commits, clone it and copy this release's contents into the clone instead.

4. Make the repository public after completing the final publication checklist. Check that GitHub Actions reports a successful verification run, or test manually from a fresh clone.
5. Update the manuscript with the **real, tested public repository URL**.

Suggested Data and Code Availability wording:

> The analysis-ready datasets, frozen experimental designs, anonymized benchmark-validation choices, and code required to reproduce the reported statistical analyses are available at [INSERT VERIFIED PUBLIC REPOSITORY URL]. The release contains parsed outcomes rather than the full original model-provider API-response envelopes. Reproduction does not require querying the models.
