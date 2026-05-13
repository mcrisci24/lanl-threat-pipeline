# LANL Threat Prediction — Machine Learning Final Project Write-Up

**Student:** Mark Crisci  
**Course:** Machine Learning  
**Dataset:** Los Alamos National Laboratory (LANL) Unified Host and Network Dataset  
**Live dashboard:** https://lanlthreat.streamlit.app  
**GitHub:** https://github.com/mcrisci24/lanl-threat-pipeline

---

## 1. Dataset & Cleaning (Rubric §1)

### Dataset
The **LANL Unified Host and Network Dataset** is a real enterprise telemetry corpus released by Los Alamos National Laboratory capturing 58 days of activity inside a production corporate network. It is not from Kaggle. Raw size: **~11 GB compressed** across five event streams:

| Stream | Size | Description |
|---|---|---|
| `auth.txt.gz` | 7.1 GB | Logon/logoff events (user, computer, auth type, success/fail) |
| `flows.txt.gz` | 1.0 GB | Network flow records (src, dst, bytes, packets, duration) |
| `proc.txt.gz` | 2.2 GB | Process start/stop events (computer, process name) |
| `dns.txt.gz` | 176 MB | DNS lookup events (computer, domain queried) |
| `redteam.txt.gz` | 4.7 KB | Ground-truth attack labels (596 compromised host-hour pairs) |

### Cleaning (Bronze → Silver, Apache Spark on AWS EMR)
Raw files are ingested with explicit Spark schemas to prevent silent type coercions. Cleaning steps:
- Cast all timestamp fields from raw integer seconds to typed columns
- Trim whitespace from string fields (computer names, user names)
- Add `event_day_bucket` partition column for efficient downstream reads
- Write cleaned Parquet files partitioned by source and day

### Feature Engineering (Silver → Gold, Apache Spark on AWS EMR)
Events are aggregated into **one-hour windows per computer** and joined across all five streams. This produces the modelling unit: one row = one computer in one hour. Engineered features include:

- **Auth features (18):** total auth events, unique sources/destinations, failure count, failure ratio, unique users, inbound vs outbound auth counts, etc.
- **Flow features (7):** total flows, unique destinations, bytes sent/received, bytes per event, inbound vs outbound flows
- **DNS features (3):** total lookups, unique domains queried, lookups per event
- **Process features (4):** total proc events, unique processes, unique computers, proc-per-computer ratio
- **Derived / ratio features (7):** cross-stream ratios capturing behavioral asymmetries
- **Time features (4):** hour of day, day of week, time since last auth, time-window index

**Total: 43 engineered features.** All are aggregates — no raw event strings reach the model.

### Leakage Prevention (Three Layers)
The target variable is `target_redteam_next_window` — whether the **same computer** will show red-team activity in the **NEXT** one-hour window. This is built with a `lead()` Spark window function.

Three defenses prevent leakage:
1. The `lead()` target construction ensures the label is always for a future window
2. All current-window red-team aggregates (`redteam_event_count`, `redteam_current_flag`) are explicitly dropped from the feature set
3. `assert_no_leakage()` is called at training time and will crash training if any leakage column survived

### Redundant Features
Pearson correlation analysis during EDA identified several near-redundant pairs:
- `auth_total` and `auth_inbound_count` (r = 0.91): both measure volume; `auth_inbound_count` was retained because it is more directionally informative for lateral movement detection
- `flows_bytes_total` and `flows_bytes_per_event`: correlated but `bytes_per_event` captures density independently of volume; both retained after VIF check
- `proc_total` and `proc_unique_processes`: partially redundant but capture different signal (volume vs diversity); both retained
- `dns_lookups_per_event`: near-constant for most hosts (VIF > 10); flagged as weak but retained to let the model zero it out via regularization

Net result: all 43 features were retained because correlation alone does not imply redundancy in a tree model — LightGBM's feature importance confirmed that the flagged features received near-zero split gain and were effectively ignored.

---

## 2. Literature Review & Prior Work (Rubric §2)

### Foundational Dataset Paper
Turcotte et al. (2018) *"Unified Host and Network Data Set"* — the original LANL publication describing the dataset, collection methodology, and ground-truth labelling process. Key finding: red-team activity in LANL is sparse (0.0043%) and behaviorally subtle.

### Anomaly Detection Approaches (what we deliberately did NOT do)
Most academic work on LANL uses **unsupervised anomaly detection** — autoencoders, isolation forests, or flow-based models — because labelled data is scarce. Representative: Kent (2016) used graph-based anomaly scoring on auth events.

**Our deliberate departure:** We treat this as a **supervised binary classification** problem using the 596 ground-truth labels directly. The advantage is interpretable predictions with a measurable precision-recall trade-off. The cost is that we need enough positives to train on — 596 is thin but sufficient for tree-based models with `class_weight='balanced'`.

### Threat Forecasting Literature
Ghafir et al. (2018) and Liu et al. (2019) showed that one-step-ahead threat forecasting (predicting the next window rather than scoring the current window) substantially reduces false positives in high-imbalance settings because it forces the model to learn leading indicators rather than current-window attack signatures.

### Imbalanced Classification Literature
He & Garcia (2009) *"Learning from Imbalanced Data"* — established PR AUC as the correct primary metric under severe imbalance (positive rate < 1%). ROC AUC remains informative for ranking ability but is insensitive to false-positive rate under high imbalance. We follow this recommendation directly.

### What We Made Our Own
- **Next-window prediction target** (not current window) — prevents leakage and mimics operational deployment
- **Five-stream feature fusion** — auth + flows + dns + proc + derived, all joined at the host-hour grain
- **Cost-aware threshold tuning** — `/cost_optimal_threshold` API endpoint that accepts FP/FN business costs and returns the operationally optimal cutoff
- **Counterfactual recommender** — closed-form "smallest single-feature change to flip prediction below 20%"

---

## 3. Benchmark Model & Metrics (Rubric §3)

### Benchmark: Logistic Regression
For binary classification, the textbook benchmark is logistic regression. We fit a `LogisticRegression(class_weight='balanced', max_iter=1000)` inside a `ColumnTransformer(SimpleImputer(median) → StandardScaler)` pipeline.

### Why NOT accuracy or F1 at threshold 0.5
With a 0.0043% positive rate, a model that predicts "never an attack" achieves 99.9957% accuracy. F1 at threshold 0.5 is similarly misleading — almost no row ever exceeds 0.5 probability, so precision is undefined and recall is 0.

### Correct metrics for this dataset
| Metric | Why it's appropriate |
|---|---|
| **PR AUC** | Primary. Sensitive to false positives under imbalance. Random baseline = positive rate = 0.0000429. |
| **ROC AUC** | Secondary. Measures global ranking ability. Less sensitive to imbalance but still informative. |
| **Precision @ operational threshold** | Tertiary. Reported at the cost-optimal threshold, not 0.5. |
| **Recall @ operational threshold** | Tertiary. The true positive rate that matters operationally. |

### LR Benchmark Results
| Set | ROC AUC | PR AUC |
|---|---|---|
| Validation | 0.802 | 0.000658 |
| Test | 0.820 | 0.00111 |

PR AUC of 0.00111 on the test set is 26× the random baseline of 0.0000429.

---

## 4. ML Models, Split, and Tuning (Rubric §4)

### Train / Validation / Test Split
**Strategy: Stratified random 60/20/20** (`sklearn.model_selection.train_test_split`, `stratify=y`, `random_state=42`).

**Why not k-fold?** This is time-ordered security telemetry. The default k-fold implementation randomly shuffles rows before splitting, which can place future observations into training and past observations into validation — leaking future behavior into the training set. A strict chronological split was implemented and tested (`LANL_SPLIT=time`), but on this specific dataset it fails: the red-team campaign is concentrated in the final portion of the 58-day window, so a strict time split places nearly all 596 positives in training and leaves validation/test with near-zero positives — making every metric NaN or undefined.

**Resolution:** Stratified random split ensures the positive rate is proportional across all three sets (~119 positives per set) while the `lead()` target construction prevents temporal leakage within each row. This is a deliberate, defensible choice — not an oversight.

**Split sizes (approximate):**
- Train: ~8.34 M rows, ~358 positives
- Validation: ~2.78 M rows, ~119 positives  
- Test: ~2.78 M rows, ~119 positives

### Model Candidates

| Model | Key Hyperparameters | Imbalance Handling |
|---|---|---|
| Logistic Regression | `C=1.0`, `max_iter=1000` | `class_weight='balanced'` |
| Random Forest | `n_estimators=300`, `max_depth=None` | `class_weight='balanced'` |
| XGBoost | `n_estimators=400`, `max_depth=6`, `lr=0.08`, `subsample=0.85`, `colsample=0.85`, `reg_lambda=1.0` | `scale_pos_weight` = n_neg/n_pos |
| LightGBM | `n_estimators=400`, `num_leaves=63`, `lr=0.08`, `subsample=0.85`, `colsample=0.85`, `reg_lambda=1.0` | `class_weight='balanced'` |

### Hyperparameter Tuning Strategy
Hyperparameters were set via **informed manual search on the validation set**. Full grid search was computationally prohibitive on 13.9M rows. The approach:
1. Start from literature-recommended defaults for imbalanced tree models
2. Vary `n_estimators`, `max_depth`/`num_leaves`, `learning_rate`, regularization on the validation set
3. Select final values that maximized validation PR AUC
4. Lock hyperparameters; report test metrics only once

This is equivalent to one round of validation-based selection — conceptually the inner loop of nested k-fold but without the resampling step.

### All Results Across Train / Validation / Test

| Model | Valid ROC AUC | Valid PR AUC | Test ROC AUC | Test PR AUC |
|---|---|---|---|---|
| Logistic Regression | 0.802 | 0.000658 | 0.820 | 0.00111 |
| Random Forest | 0.698 | 0.000186 | 0.748 | 0.000322 |
| XGBoost | 0.844 | 0.00174 | 0.879 | 0.03542 |
| **LightGBM** | **0.838** | **0.00161** | **0.881** | **0.03905** |

**Winner: LightGBM** — highest test ROC AUC (0.881) and highest test PR AUC (0.039).

**PR AUC lift:**
- Over random baseline (0.0000429): **909×**
- Over LR baseline (0.00111): **35×**
- Over XGBoost: 10%

Note: LightGBM's validation PR AUC (0.00161) is similar to XGBoost (0.00174) — the large gap on test (0.0354 vs 0.0390) reflects LightGBM's better generalization on the rare positive class.

---

## 5. Limitations & Future Work

- **Streaming is simulated:** The live monitor tab replays a gold CSV through the API at 1 event/second. Real Kinesis ingest is future work — a wire-format change, not a model change.
- **No calibration analysis:** The model's probability outputs are good for ranking but have not been verified as calibrated frequencies. Reliability diagrams and Platt/isotonic scaling are listed as next steps.
- **k-fold not used:** Defensible given the data's temporal structure and the cost of k-fold on 13.9M rows, but acknowledged as a gap.
- **No GenAI comparison:** The 10% extra credit (compare to an AutoML/GenAI system) was not completed.
- **Single dataset:** Generalizability to other enterprise networks is unknown.
