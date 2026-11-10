# register/: the shared questionnaire

`parameters.tsv` is the questionnaire every language's register answers (`shared/register.py`, kind `feature`): one row per
question, with its allowed codes, group and source. Built by `onboard/register.py parameters` from:

- Grambank v1.0.2 (195 features; Skirgård et al. 2023, https://grambank.clld.org), CC BY 4.0
- WALS Online (Dryer & Haspelmath 2013, https://wals.info), CC BY 4.0
- AUTOTYP (Bickel et al., https://github.com/autotyp/autotyp-data), CC BY 4.0
- APiCS Online (Michaelis et al. 2013, https://apics-online.info), CC BY 4.0
- our own `MT-` rows (the onboarding steps' measurable facts), CC0

The rows hold the questions only, never a language's answers. The answers live in each language's register: private before
the freeze, the language repository's `.tanakh/register/` after it (internal-docs/review-feedback-data-plan-2026-11-10.md).
