# Publish this scaffold to the BioNanomics GitHub organization

**Proposed repository:** `BioNanomics/celegans-nsparc-dispim-benchmark`  
**Description:** `C. elegans embryogenesis: Nikon NSPARC versus published diSPIM benchmark`  
**Initial visibility recommendation:** **private** until the lab manager reviews the protocol and BioNanomics chooses licensing and release policies.

## Minimal workflow for the ChatGPT-connected GitHub account

1. Visit [GitHub's prefilled creation form](https://github.com/new?owner=BioNanomics&name=celegans-nsparc-dispim-benchmark&description=C.+elegans+embryogenesis%3A+NSPARC+versus+diSPIM+benchmark&visibility=private).
2. Verify **Owner: BioNanomics** and **Repository name: celegans-nsparc-dispim-benchmark**; choose private/public intentionally.
3. Click **Create repository**. Leave the "Add a README," `.gitignore`, and license initializers unchecked, because this package already includes README and .gitignore and the license decision is pending.
4. After creation, tell the connected assistant that the repository exists. The GitHub connection can then add and commit files. No terminal work is required.

## Alternative: publish the ZIP manually using git

After downloading/extracting the ZIP and creating the empty remote repository:

```bash
cd celegans-nsparc-dispim-benchmark
git init -b main
git add .
git commit -m "Initial C. elegans NSPARC-diSPIM experiment scaffold"
git remote add origin https://github.com/BioNanomics/celegans-nsparc-dispim-benchmark.git
git push -u origin main
```

The command-line approach requires configured Git/GitHub authentication and that the authenticated user has repository write permission. Repo creation remains a separate GitHub permission.

## Before making it public

- Review reported publication conditions and BV514/JIM113 strain distinctions.
- Select a software/docs license (see `LICENSE-DECISION.md`).
- Keep raw microscopy images and unreleased data outside Git.
- Confirm personnel, instrument, strain and lab SOP details with the lab manager.
