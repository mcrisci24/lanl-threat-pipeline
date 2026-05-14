# Speaker Script — LANL ML Final Project Presentation

# 14 Slides \| \~45-55 seconds per slide \| 11-12 minutes total

------------------------------------------------------------------------

## Slide 1 — Title

**"Predicting Cyber Attacks One Hour Early"**

"Good morning. I'm going to show you a machine learning system that predicts whether a computer will be compromised by an attacker in the next hour — before the attack happens, not while it's happening. This is a system is built on real enterprise telemetry from a US government laboratory."

*[\~40 sec]*

------------------------------------------------------------------------

## Slide 2 — The Research Question

**"The Prediction Problem"**

"The research question is: given how a computer behaved in the current one-hour window — how many logins, which destinations it connected to, how many bytes it sent — will that same computer show attacker activity in the NEXT hour? We predict the future window, not the current one. That design choice is critical and I'll explain why in a moment. Red-team activity means a ground-truth attacker event from the LANL red-team label file. I aggregate the data to the computer-hour level, so each row represents one computer’s behavior during one hour. In the model, a positive label means that the same computer appears in the red-team activity stream in the next one-hour window. So the target is not simply, “Does this current row look suspicious?” Instead, it asks, “Does this computer’s current behavior predict a labeled attacker event in the next hour?” This creates a binary supervised learning label: 1 means red-team activity occurs for that computer in the next hour; 0 means it does not."

*[\~50 sec]*

------------------------------------------------------------------------

## Slide 3 — Dataset

**"Los Alamos National Laboratory — Real Enterprise Telemetry"**

"The data comes from Los Alamos National Laboratory — a real US government research facility, not Kaggle. 58 days of corporate network activity: 11 gigabytes across five streams — authentication logs, network flows, DNS lookups, process events, and ground-truth red-team labels from a sanctioned penetration test. After aggregation into one-hour computer windows, we have 13.9 million rows. 596 of them are actual attacks. That is a 0.004% positive rate — a needle-in-a-haystack problem."

*[\~55 sec]*

------------------------------------------------------------------------

## Slide 5 — Data Cleaning, EDA & Feature Engineering

**"From Raw Logs to 43 Features"**

"Cleaning was done in Apache Spark: explicit schemas to prevent silent type coercions, timestamp casting, whitespace trimming. The output is clean Parquet files. Feature engineering aggregated each computer's events into 43 behavioral signals per hour — authentication counts, failure rates, unique destinations, bytes per flow, DNS diversity. EDA revealed several correlated feature pairs: auth_total and auth_inbound_count have r=0.91, flagged as partially redundant. We retained both because correlation doesn't equal redundancy in a tree model — LightGBM's feature importance confirmed these had near-zero split gain. All 43 features were retained."

*[\~60 sec]*

------------------------------------------------------------------------

## Slide 6— Literature Review

**"What's Been Done Before — and What We Did Differently"**

"Most prior work on LANL uses unsupervised anomaly detection — autoencoders, isolation forests — because labelled data is scarce. Turcotte et al. 2018 described the dataset. Kent 2016 used graph-based anomaly scoring. He and Garcia 2009 established PR AUC as the correct primary metric under severe class imbalance. Our departure: we treat this as supervised binary classification and use all 596 ground-truth labels directly. That gives us interpretable predictions, a measurable precision-recall trade-off, and the ability to tune the decision threshold to a business cost matrix. The cost is that 596 positives is thin — we handle that explicitly in the modelling."

*[\~60 sec]*

------------------------------------------------------------------------

## Slide 7 — Benchmark Model

**"Benchmark: Logistic Regression — and Why Accuracy is Wrong"**

"The benchmark for binary classification is logistic regression. I fit it with class_weight balanced inside a median-impute, standard-scale pipeline. Before I show you the benchmark results, I need to address the metric. On a dataset that is 99.996% negative, a model that predicts 'safe' for every single row achieves 99.9957% accuracy and catches zero attacks. Accuracy is meaningless here. The correct primary metric is PR AUC — area under the precision-recall curve — because it is directly sensitive to false positives under imbalance. The random baseline PR AUC for this dataset is 0.0000429 — literally the positive rate. The LR benchmark scores 0.00111 on the test set — 26 times better than random. That's the floor we need to beat."

*[\~65 sec]*

------------------------------------------------------------------------

## Slide 8 — ML Models & Hyperparameters

**"Four Candidates, Head to Head"**

"I trained four models: logistic regression as the baseline, balanced random forest, XGBoost with scale_pos_weight set to the class ratio, and LightGBM with class_weight balanced. For tree models: 400 estimators, learning rate 0.08, subsample 0.85, L2 regularization 1.0. LightGBM uses 63 leaves. All four use the same preprocessing pipeline. Hyperparameters were selected by manual search on the validation set — full grid search is computationally prohibitive on 13.9 million rows. I varied estimator count, depth, learning rate, and regularization, picked the values that maximized validation PR AUC, then locked them and evaluated on test."

*[\~55 sec]*

------------------------------------------------------------------------

## Slide 9 — Train / Validation / Test Split

**"60/20/20 Stratified Split — and Why Not k-Fold"**

"The split is 60/20/20 stratified random, giving roughly 119 positives in each set. Why not k-fold? This is time-ordered security data. Standard k-fold shuffles rows before splitting, which can leak future behavioral patterns into training. I implemented a strict chronological split and tested it — but the red-team campaign is concentrated in the final weeks, so a chronological split places nearly all 596 positives in training and leaves validation and test with near-zero positives. Every metric becomes NaN. The stratified split with the lead() target construction is the correct resolution: positive rates are proportional, and within-row temporal leakage is prevented at the feature-engineering step."

*[\~60 sec]*

------------------------------------------------------------------------

## Slide 10 — Results Across All Sets

**"Model Leaderboard — Validation and Test"**

"Here are the results across all four models on both validation and test. Logistic regression: test ROC AUC 0.820, test PR AUC 0.00111. Random forest: 0.748 and 0.000322 — actually worse than logistic regression on PR AUC. XGBoost: 0.879 and 0.035. LightGBM: 0.881 and 0.039. LightGBM wins on both metrics. Its PR AUC of 0.039 is 909 times better than the random baseline and 35 times better than the logistic regression benchmark. The complexity is clearly worth it."

*[\~50 sec]*

------------------------------------------------------------------------

## Slide 11 — Winning Model Diagnostics: ROC and PR Curves

**"How LightGBM ranks rare attack behavior"**

"This slide shows the winning LightGBM model from two curve-based views. The ROC curves show global ranking ability: whether attack-like host-hours tend to receive higher scores than benign host-hours. On the held-out test set, LightGBM reaches a ROC-AUC of 0.881.

The precision-recall curves are more important for this project because the positive class is extremely rare: only about 0.0043% of rows are positives. That is why the PR curve looks visually compressed near the bottom. The important comparison is not whether PR-AUC is close to 1.0, but how much better it is than the random baseline. The test PR-AUC is 0.03905 compared with a random baseline of 0.000043, which is about 909 times better than random.

The conclusion is that LightGBM is not a magic attack oracle. It is a strong risk-ranking model. It moves rare red-team behavior much higher in the queue than random chance would."

*[\~60 sec]*

------------------------------------------------------------------------

## Slide 12 — Winning Model Diagnostics: Confusion Matrices

**"What happens at the selected threshold"**

"Now this slide shows the same model at a specific operating threshold: 0.10. The confusion matrix answers a different question than ROC-AUC or PR-AUC. The curves show ranking quality across many possible thresholds. The confusion matrix shows what happens when we choose one threshold and actually classify rows as attack or no attack.

On the test set, the model catches 28 of 119 attacks and misses 91. It also produces 57,535 false positives out of about 2.78 million host-hours. That sounds like a lot, and operationally it matters, because false positives become analyst workload. But it is still filtering a massive telemetry stream down to a much smaller set of high-risk rows.

This is why I frame the system as SOC triage, not autonomous detection. **A lower threshold catches more attacks but creates more alerts. A higher threshold reduces alert volume but misses more attacks. The threshold is a business and operational decision.**"

*[\~60 sec]*

------------------------------------------------------------------------

## Slide 13 — Model Interpretation

**"Why Did It Flag This Computer?"**

"LightGBM gives us exact per-feature contributions using TreeSHAP — the model's own internal calculation, not a sampling approximation. Red bars push predicted risk up, green bars push it down. On the HIGH risk preset: the model flags a computer with 4 outbound auth events to 1 destination and 12 network flows. It looks quiet. The model says: that pattern — focused, low-noise, targeted — is the reconnaissance fingerprint. Diverse, high-volume activity reads as a normal admin host. The counterfactual recommender adds: 'reduce outbound auth count by 2 and risk drops below 20%.' That's an actionable recommendation for a security analyst."

*[\~55 sec]*

------------------------------------------------------------------------

## Slide 14 — Threshold Tuning

**"The Threshold is a Business Decision, Not a Hyperparameter"**

"Scikit-learn defaults to threshold 0.5. On this dataset almost no row ever scores above 0.5, so the model appears to predict nothing. The threshold is actually a deployment knob. The system exposes a cost-optimal threshold calculator: give it the dollar cost of a false alarm and the cost of a missed attack, and it returns the threshold that minimizes total expected cost over the validation set. At cost_fp=100 and cost_fn=100,000 — a missed attack costs a thousand times a false alarm — the optimal threshold is around 0.10. That's the operationally correct cutoff. Dragging the threshold slider from 0.5 to 0.1 turns a model that looks broken into one that catches attacks."

*[\~55 sec]*

------------------------------------------------------------------------

## Slide 15 — Limitations & Stakeholder Recommendation

**"What I'd Tell a SOC Director"**

"Honest limitations: the streaming ingest is simulated, not a real Kinesis consumer. The model's probabilities are good for ranking but not calibrated as true frequencies — we'd want reliability diagrams and Platt scaling before quoting percentages. “The model’s biggest limitation is that this is a rare-event problem with only 596 positives. I used a stratified 60/20/20 split because a strict chronological split left validation and test with too few positives to evaluate, but that means the evaluation is not a perfect forward-in-time deployment simulation. LightGBM performs much better than random and much better than logistic regression, especially on PR-AUC, but the absolute PR-AUC is still low because the positive rate is only about 0.0043%. The confusion matrix also shows that at threshold 0.10, the model catches some attacks but misses many and still creates analyst workload. So I would not frame this as an autonomous attack detector. I would frame it as a SOC triage model that ranks risky host-hours for analyst review. Future work would include external validation, probability calibration, stronger temporal validation, sequence/graph features, and threshold tuning based on actual SOC capacity.”

*[\~55 sec]*

------------------------------------------------------------------------

**Total time: \~11 minutes with natural transitions. Cut Slide 10 detail if running long.**
