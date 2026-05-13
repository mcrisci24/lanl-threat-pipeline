# Rubric Coverage Audit — ML Final Project

Each section is 20% of the grade. Extra credit is 10%.

---

## Section 1 — Novel Non-Kaggle Dataset + Cleaning + EDA (20%)

| Requirement | Status | Where Covered |
|---|---|---|
| Dataset NOT from Kaggle | DONE | LANL Unified Host & Network Dataset — academic research release by Los Alamos National Laboratory |
| Data cleaning | DONE | Slide 3 (pipeline overview), `jobs/bronze_to_silver_emr.py` — schema casting, type coercion, whitespace trimming |
| EDA with plots | DONE | Slide 4 — class imbalance bar chart, feature correlation heatmap, auth failure rate distribution |
| Redundant features identified | DONE | Slide 4 — Pearson correlation analysis: auth_total vs auth_inbound_count (r=0.91), flows_bytes_total vs bytes_per_event; all 43 retained (tree model handles via regularization + near-zero split gain) |

**Gap:** EDA plots live in `presentation_assets/` and `gold_outputs/`. Slides reference them directly. If professor asks for the notebook, point to `jobs/train_model.py` which logs feature importances to MLflow.

---

## Section 2 — Literature Review / Prior Work (20%)

| Requirement | Status | Where Covered |
|---|---|---|
| Literature review conducted | DONE | Slide 5 |
| Prior work cited | DONE | Turcotte et al. 2018 (dataset paper), He & Garcia 2009 (PR AUC for imbalance), Ghafir et al. 2018 (next-window forecasting), Kent 2016 (graph anomaly on LANL) |
| Project made our own | DONE | Slide 5 — explicit contrast: prior work uses unsupervised anomaly detection; we use supervised binary classification with all 596 labels + next-window target to prevent leakage |

---

## Section 3 — Benchmark Model + Correct Metrics for Imbalanced Data (20%)

| Requirement | Status | Where Covered |
|---|---|---|
| Appropriate benchmark identified | DONE | Logistic Regression — correct choice for binary classification (Slide 6) |
| Correct metrics for imbalanced classification | DONE | Slide 6 and Slide 9 — PR AUC as primary metric; ROC AUC as secondary; NOT accuracy (99.996% for "never predict attack") |
| Benchmark results reported | DONE | Test PR AUC = 0.00111, Test ROC AUC = 0.820 |
| Explanation of why accuracy fails | DONE | Slide 6 — "A model that predicts 'safe' for every row is 99.9957% accurate and catches zero attacks" |

---

## Section 4 — ML Algorithm, Split, Tuning, Metrics Across All Three Sets (20%)

| Requirement | Status | Where Covered |
|---|---|---|
| ML algorithm chosen and justified | DONE | LightGBM — histogram-based GBDT, fast on large datasets, native `class_weight='balanced'` (Slide 7) |
| Proper train/validation/test split | DONE | 60/20/20 stratified random split, ~119 positives per set (Slide 8) |
| k-fold cross-validation | HONEST EXPLANATION BELOW | Slide 8 |
| Hyperparameter tuning | DONE | Manual validation-set search; hyperparameters documented (Slide 7) |
| Metrics across ALL THREE sets | DONE | Slide 9 — full table: valid ROC AUC, valid PR AUC, test ROC AUC, test PR AUC for all 4 models |

### k-fold explanation (honest):

> **k-fold was not used.** This is time-ordered security telemetry where events for a given computer are temporally correlated. Standard k-fold (which shuffles rows randomly before splitting) can place future observations into training and past observations into validation, leaking forward-looking behavioral patterns into the model. A strict chronological 60/20/20 split was implemented and evaluated, but it fails on this specific dataset: the red-team campaign is concentrated in the final portion of the 58-day window, placing nearly all 596 positives in the training set and leaving validation/test with near-zero positives (metrics become NaN/undefined).
>
> **Resolution:** Stratified random 60/20/20 split ensures proportional positive rates (~119 per set). The `lead()` construction of the target variable prevents within-row temporal leakage. This is a deliberate, documented choice — not an omission. Hyperparameters were selected via single-round validation-set tuning, which is conceptually equivalent to the "inner loop" of nested k-fold without the resampling step.

---

## Section 5 — Final Presentation (20%)

| Requirement | Status | Where Covered |
|---|---|---|
| 10–15 slides | DONE | 12 slides (within range) |
| 10 minutes | DONE | Speaker script allocates ~50 sec/slide = 10 min total |
| Stakeholder story | DONE | Framed as "SOC director briefing" — why it matters operationally, not academically |
| Results clearly presented | DONE | Slides 9–10 — model leaderboard, PR AUC lift, SHAP explanations |

---

## Extra Credit — GenAI Comparison (10%)

| Requirement | Status | Notes |
|---|---|---|
| Compare to GenAI/AutoML system end-to-end | **NOT COMPLETED** | Did not run Karpathy autoresearch, OpenClaw, Google Data Science, or Perplexity Labs against this dataset. Do not claim this credit. |

---

## Summary

| Section | Weight | Coverage |
|---|---|---|
| 1. Dataset + Cleaning + EDA | 20% | Full |
| 2. Literature Review | 20% | Full |
| 3. Benchmark + Imbalanced Metrics | 20% | Full |
| 4. ML Model + Split + Tuning + All-Set Metrics | 20% | Full (k-fold honestly explained) |
| 5. Presentation 10–15 slides | 20% | Full (12 slides) |
| Extra Credit GenAI | 10% | Not completed — do not claim |

**Expected base grade coverage: 100% of rubric items addressed.**
