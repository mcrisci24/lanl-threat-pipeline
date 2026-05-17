# ML Final Project — One-Page Summary

**Student:** Mark Crisci | **Dataset:** LANL Unified Host & Network Dataset (not Kaggle)

---

## Research Question
Given a computer's behavior in the **current** one-hour window, will it show red-team (attacker) activity in the **next** one-hour window?

## Dataset
- Source: Los Alamos National Laboratory enterprise telemetry — 58 days, ~11 GB compressed
- 5 streams: authentication, network flows, DNS, processes, red-team labels
- 13.9 million host-hour rows after aggregation
- **596 positives (0.0043% positive rate)** — severe class imbalance

## Cleaning & Feature Engineering
- Spark ETL: Bronze (raw) → Silver (cleaned Parquet) → Gold (43 engineered features per host-hour)
- Three-layer leakage prevention: `lead()` target, explicit column drops, `assert_no_leakage()` runtime check
- Redundant features identified via Pearson correlation (r > 0.90 pairs); all 43 retained (tree model handles correlated features via regularization)

## Literature Review
- Turcotte et al. (2018) — original LANL dataset paper
- He & Garcia (2009) — PR AUC as primary metric under imbalance
- Ghafir et al. (2018) — next-window forecasting reduces false positives
- **Our departure from prior work:** supervised classification (not unsupervised anomaly detection), using all 596 labels directly

## Benchmark
- Logistic Regression with `class_weight='balanced'`
- Test PR AUC = **0.00111** (26× random baseline of 0.0000429)
- Correct metric: PR AUC, not accuracy (which would be 99.996% for a "predict never" model)

## Split Strategy
- **60/20/20 stratified random split** (~119 positives in each set)
- k-fold not used: temporal data + 13.9M rows; chronological split tested but places all positives in training (NaN metrics on test). Stratified split with `lead()` target is the correct resolution.
- Hyperparameters selected via manual validation-set search (equivalent to single-round validation tuning)

## Model Comparison

| Model | Test ROC AUC | Test PR AUC | PR AUC Lift vs Random |
|---|---|---|---|
| Logistic Regression (baseline) | 0.820 | 0.00111 | 26× |
| Random Forest | 0.748 | 0.000322 | 7.5× |
| XGBoost | 0.879 | 0.03542 | 825× |
| **LightGBM (winner)** | **0.881** | **0.03905** | **909×** |

## Key Results
- LightGBM: **909× PR AUC lift over random**, **35× over LR baseline**
- Exact TreeSHAP explanations per prediction
- Cost-optimal threshold tuning: operationally configurable via FP/FN cost inputs
- Counterfactual recommender: "reduce failed-auth count by N to drop below 20% risk"

## Extra Credit (GenAI comparison)
**Not completed.**

## Deliverables
- `LANL_ML_Final_Project_Presentation.pptx` — 14-slide deck
- `speaker_script.md` — matched speaker notes
- `ml_project_writeup.md` — full rubric-aligned write-up
- `rubric_coverage_audit.md` — rubric-to-slide mapping
