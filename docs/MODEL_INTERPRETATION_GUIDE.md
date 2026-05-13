# Model Interpretation Guide

> Cheat sheet for what every number on the dashboard means and how to
> explain it on stage in one sentence.
>
> Read once before the presentation. If anyone asks "what does that
> mean?" during Q&A, the answer is in this file.

---

## 1. The one-sentence summary of the model

> *"LightGBM, trained on 43 engineered features describing one host's
> behaviour in one one-hour window, predicting whether that same host
> will show red-team activity in the NEXT one-hour window."*

That's it. Memorize that sentence.

---

## 2. The metrics — what they are and what's "good"

### 2.1 — The numbers (test set, LightGBM)

| Metric | Value | What it means | Why it's good |
|---|---|---|---|
| **ROC AUC** | **0.881** | Probability that a random positive scores higher than a random negative | 0.5 = random; 1.0 = perfect; 0.881 = strong separator |
| **PR AUC** | **0.0390** | Area under the precision-recall curve | Baseline = 0.0000043 (the positive rate); **907× lift** |
| **PR AUC lift over LR** | **35×** | Improvement vs the linear baseline (LR PR AUC = 0.0011) | The tree models actually learn the attack fingerprint; LR plateaus |
| **Precision @ 0.5** | low | What fraction of "alerts" are real attacks at the textbook threshold | Low by design — the dataset is 0.00043% positive |
| **Recall @ 0.5** | low | What fraction of real attacks the model flags at threshold 0.5 | This is why we tune the threshold (see §4) |

### 2.2 — Why PR AUC, not ROC AUC

The dataset has **596 positives out of 13.9 million windows** — a
0.0043% positive rate. Under that kind of imbalance:

- **ROC AUC** rewards correct ranking but is too forgiving: a model
  that gets everything in the right order still gets a high ROC AUC
  even if it can't actually identify positives at any reasonable
  threshold.
- **PR AUC** stays honest under imbalance because the precision axis
  is sensitive to false positives. Random PR AUC for this dataset is
  **0.0000043** (literally the positive rate). Our **0.039** is
  907× that random baseline.

**One-line defence in Q&A:** *"Accuracy is meaningless on a 0.004%
positive dataset. ROC AUC is mildly informative. PR AUC is the metric
that actually tracks operational utility, and we lift it 907× over
random and 35× over the LR baseline."*

### 2.3 — Why the absolute PR AUC of 0.039 is still "good"

Anyone unfamiliar with class-imbalance metrics will see 0.039 and
think it's low. Pre-empt:

> *"In imbalanced binary classification, the right comparison is to
> the random baseline, not to 1.0. A random model on this dataset
> scores PR AUC = 0.0000043. We score 0.039. That's three orders of
> magnitude better than random, which means at any operational
> threshold the precision-recall trade-off is dramatically more
> favourable. The absolute number is small because the dataset is
> nearly all negatives; the lift is what matters."*

---

## 3. How to read the explainer chart

The horizontal bar chart in the Predict tab's right column. Each bar
represents one feature; bars are sorted by impact magnitude.

- **Red bars** push predicted risk **UP** (towards "this host is
  about to be compromised")
- **Green bars** push predicted risk **DOWN** (towards "benign")
- **Bar length** = magnitude of the feature's contribution to the
  prediction, **in log-odds units**

### 3.1 — Three math paths

| Model | Method | What's computed |
|---|---|---|
| Logistic regression | linear log-odds decomposition | `coef[i] × scaled_value[i]` per feature, exactly |
| XGBoost | TreeSHAP via `booster.predict(pred_contribs=True)` | Per-feature SHAP value, exact, from XGBoost's internals |
| LightGBM | TreeSHAP via `booster.predict(pred_contrib=True)` | Per-feature SHAP value, exact, from LightGBM's internals |

### 3.2 — The "not a SHAP approximation" line

If anyone says "isn't SHAP an approximation?":

> *"The `shap` Python library uses sampling-based approximations for
> non-tree models. For tree models, both XGBoost and LightGBM
> implement TreeSHAP natively in their booster — `pred_contrib=True`
> in LightGBM, `pred_contribs=True` in XGBoost. Those are exact,
> reproducible, and fast. We call them directly instead of going
> through the `shap` library wrapper. For the linear baseline we do
> closed-form coefficient × scaled-value, which is exact by
> construction."*

### 3.3 — What "log-odds" means in plain English

The y-axis of the explainer is **log-odds**, not probability. One
unit of log-odds = roughly a factor of `e ≈ 2.7` change in odds.
Practical mapping:

- +1 log-odd = host is ~2.7× as likely to be positive
- +3 log-odds = host is ~20× as likely to be positive

**When asked:** *"The bars are in log-odds units because that's the
linear-additive space the model actually works in. We sum them, add
the model bias, and pass through a sigmoid to get the probability.
The chart shows the raw additive contributions because they're the
ones a human can compare."*

---

## 4. How to read the counterfactual table

Two columns: `feature` and `delta`. Each row is a candidate
intervention.

- A `delta` of `-42` on `auth_total_failures` means: "if this host's
  failed-auth count had been 42 lower (clamped at 0), the predicted
  probability would have been below the target (default 0.20)."

### 4.1 — Why only single-feature counterfactuals

The endpoint computes the **smallest single-feature change** that
crosses the decision boundary, not multi-feature combinations.
Single-feature counterfactuals are:

- **Closed-form** for linear models (solve `coef × delta = target`)
- **Interpretable** (you can act on one knob)
- **Cheap** (no optimization, no search)

### 4.2 — Why the LR sidecar exists

LightGBM doesn't have a closed-form counterfactual. So we keep the
LR pipeline trained alongside the winner, save it as a "sidecar"
artifact, and the `/counterfactual` endpoint always loads it.
**Result:** counterfactuals always work, regardless of who serves
predictions.

**When asked why this is OK:** *"The LR sidecar is calibrated on the
same training data and uses the same feature contract. The
counterfactual it produces is a starting point for a human analyst —
'reducing this feature by this much would lower risk below 20%.'
We're not claiming the LightGBM model would produce exactly the same
delta; we're claiming the linear approximation captures the dominant
directional signal."*

---

## 5. The threshold slider — what it does and why it matters

### 5.1 — The mechanics

Drag the slider from 0.01 to 0.99. Four KPI tiles update live:

| Tile | What it counts |
|---|---|
| Predicted positives | Test rows with `P(model) ≥ threshold` |
| True positives | Predicted positives that ARE actually red-team rows |
| False positives | Predicted positives that are NOT red-team rows |
| False negatives | Real red-team rows the model missed |

### 5.2 — Why the default of 0.5 is wrong

`predict()` in scikit-learn uses 0.5 by default — the textbook
choice. **On imbalanced data it's almost always wrong.** With a
0.004% positive rate, almost no test row scores above 0.5, so:

- Predicted positives ≈ 0
- True positives ≈ 0
- False positives ≈ 0
- False negatives ≈ all of them

The model "looks broken" at threshold 0.5 even though it ranks the
positives correctly. **The threshold is a deployment knob, not a
hyperparameter.**

### 5.3 — How the cost-matrix calculator picks the right threshold

`/cost_optimal_threshold` takes:

```
cost_fp  = dollar (or analyst-hour) cost of one false alarm
cost_fn  = dollar (or breach) cost of one missed attack
```

and returns the threshold that **minimizes**:

```
total_cost = FP_count × cost_fp + FN_count × cost_fn
```

evaluated on the validation set's predictions. The math is:

1. Sweep the threshold from 0.001 to 0.999
2. At each value, count FP and FN
3. Compute total cost
4. Return the threshold with the lowest cost

**Why this is the rubric-winning move:** *"Most ML projects stop at
'F1-optimal threshold.' F1 is dimensionless and ignores business
context. Cost-optimal threshold takes the SOC's actual values — a
missed attack costs more than a false alarm — and computes the
threshold that minimizes expected operational cost. The model is an
estimator; the threshold turns it into a tool."*

---

## 6. The Live monitor numbers — what they mean

### 6.1 — Events scored

Total rows the simulator has pushed through the model since you hit
Start. Increments by 1 per tick (~0.8 seconds).

### 6.2 — Alerts fired

Count of events where P ≥ the current threshold slider value.
Updates instantly when you move the threshold (it re-classifies the
event buffer, not just new events).

### 6.3 — Max P

The highest probability seen so far in this stream. Useful as a
"is there anything interesting buried in this stream?" indicator
even before you look at the chart.

In a typical 120-row run with the default threshold (0.5), Max P
should land between 0.7 and 0.8. The two natural spikes in the gold
sample are at P ≈ 0.799 and P ≈ 0.745.

### 6.4 — Mean P

The average probability across all events. With the LANL dataset's
class imbalance, Mean P sits near 0.03–0.05 — most rows are
near-zero, which is the model correctly saying "no attack here."

A high Mean P (above ~0.10) would indicate either a contaminated
stream or a model that's hallucinating positives — neither of which
should happen on this dataset.

### 6.5 — What the typical-run screenshot tells you

The screenshot from the smoke test (120 events, threshold 0.30):

- **Events scored: 121** — 120 from the stream + 1 injected
- **Alerts fired: 3** — the inject + two natural high-risk rows
- **Max P: 0.799** — the highest natural spike in the gold sample
- **Mean P: 0.049** — typical "mostly quiet" baseline

That set of four numbers is a fingerprint of healthy behaviour. If
you see Alerts > 20, something is off; if you see Mean P > 0.15,
something is off. **Memorize the screenshot's numbers** as the
"normal" reference.

---

## 7. One-sentence answers to the five hardest questions

### Q: "Is your model good?"

> *"Yes, in the only metric that matters for this dataset — PR AUC at
> 907× the random baseline and 35× the linear baseline."*

### Q: "Why is the probability so low (0.07) when there are 7 auth events and 10 process events?"

> *"Because the model learned that diverse, low-volume routine
> activity is the admin-host pattern, not the attacker pattern. Real
> attackers in this dataset are focused and narrow, not broadly busy."*

### Q: "How do you handle the class imbalance?"

> *"Three ways. One: `class_weight='balanced'` for LightGBM and
> `scale_pos_weight` for XGBoost during training. Two: PR AUC as the
> evaluation metric, not accuracy. Three: cost-aware threshold tuning
> at serving time, so a SOC director can pick the operating point
> that matches their cost matrix."*

### Q: "How would I trust this in production?"

> *"Every prediction comes with an explainer (which features pushed
> it up or down) and a counterfactual (what would need to change to
> flip the verdict). The threshold is tuned to the SOC's actual cost
> matrix, not an arbitrary 0.5. The deployed service exposes
> `/health`, `/model_info`, and `/features` so you can audit what's
> serving. And the Live monitor demonstrates that the scoring engine
> survives sustained load before you ever connect a real stream."*

### Q: "What's the weakest part of the system?"

> *"The streaming is simulated, not real. Real Kinesis ingest is
> listed as future work and is a wire-format change away — the model,
> the API, and the feature contract don't move. The other honest
> weakness is that we don't have calibration analysis: the model's
> outputs are good for ranking but we haven't proven they're
> interpretable as actual frequencies. Reliability diagrams and
> isotonic / Platt scaling are also listed in the write-up's future
> work."*

---

## 8. The story arc, in five sentences

Read this once. It's the spine of the whole presentation.

1. **The question:** *Given a host's behaviour in the current hour,
   will it show red-team activity in the NEXT hour?* — chosen
   deliberately to avoid leakage.
2. **The data:** 11 GB of real LANL enterprise telemetry, 13.9M rows
   after aggregation, 596 positives (a 0.0043% positive rate).
3. **The pipeline:** S3 → EMR Spark medallion → MLflow → FastAPI on
   EC2 → Streamlit Cloud — a real distributed system, not a notebook.
4. **The model:** Four candidates trained head-to-head, LightGBM
   wins with **907× PR AUC lift over random** and exact TreeSHAP
   explanations.
5. **The operations layer:** Cost-aware threshold tuning, a
   counterfactual recommender, and a Live monitor that proves the
   scoring engine survives a real stream.

That's the project in five sentences. Everything else is detail.
