# Dashboard Features

> Companion to the live demo. Read once before the presentation; flip
> back here in Q&A if anyone asks "what is that button doing?"
>
> Every UI element on the dashboard is listed here with: **what it is**,
> **what it computes**, **what to say about it**, **what questions it
> answers**.

---

## 0. The dashboard at a glance

The Streamlit app has **five tabs**:

| Tab | Purpose | Live demo? |
|---|---|---|
| **Predict** | Score one host's behaviour, with explainer + counterfactual | Yes — the main act |
| **Model metrics** | Threshold slider + cost-matrix calculator + model leaderboard | Yes — the deep-dive |
| **Architecture** | The pipeline diagram and the rubric mapping | Optional close |
| **How it works** | Plain-English narration of the system for new viewers | Skip on stage |
| **Live monitor** | Streaming-simulator replay of the gold sample against the deployed API | **Yes — the grand finale** |

Plus a **sidebar** that's always visible: API status, model name, feature
count, preset dropdown, and project framing.

---

## 1. Sidebar

### 1.1 — API status badge

A coloured card at the top of the sidebar.
- **`[ ONLINE ]`** with mint-green border = the FastAPI service answered
  `/health` within 3 seconds and `model_loaded: true`. Shows the model
  name (`lightgbm_model`) and the feature count (`43`).
- **`[ OFFLINE ]`** with red border = the API URL is unreachable. The
  card tells you how to launch it (`uvicorn app.api_app:app ...`).

**What to say if asked:** *"That's a live health check against the EC2
container — it polls `/health` every page load. The badge proves the
model is loaded, not just that the process is alive."*

### 1.2 — Quick presets dropdown

Seven scenarios in two groups:
1. **Calibrated to real gold rows** (these are what the demo uses):
   - `Demo HIGH risk - real row (P=0.745)`
   - `Demo MEDIUM risk - real row (P=0.275)`
   - `Demo LOW risk - real row (P=0.072)`
2. **Synthetic illustrative scenarios** (kept for historical comparison):
   - `Quiet workstation`, `Busy admin host`, `Suspicious - failed-logon
     storm`, `Suspicious - lateral movement`

**What it computes:** When you pick a preset, every value in the input
form is populated from that preset's feature dict (others go to 0).

**What to say if asked why the presets exist:** *"A blank form is a
bad demo. These presets are real rows from the gold table that I
pre-scored against the deployed model — the probabilities in the
preset names are what the model actually returns, not my guesses."*

### 1.3 — System framing text

A short paragraph explaining what the dashboard predicts ("next window,
not current window") and why that design choice matters.

---

## 2. Tab — Predict

This is the **main act** of the demo. Two-column layout: input form on
the left, results on the right.

### 2.1 — Input form (left column)

A scrollable form with **43 numeric inputs** grouped by source family
(`auth`, `flows`, `dns`, `proc`, `derived`, `time`, `other`). Each
group has a one-sentence caption explaining what those features mean
in plain English (defined in `FEATURE_GROUP_DESCRIPTIONS` in
`streamlit_app.py`).

**What every field defaults to:** 0. The API contract says missing
features default to 0, which is read as "no observed activity of that
kind."

**What to say:** *"This is one host's behaviour in one one-hour window
— 43 engineered features after the Spark gold-layer aggregation."*

### 2.2 — "Predict next-window risk" button

Sends the form values to `POST /predict` and waits for the response.
The response has three fields: `prediction` (0/1), `model_name`, and
`probability_redteam_next_window` (a float in [0,1]).

### 2.3 — Verdict card (right column)

A coloured banner with one of three states:
- **Low predicted risk** (mint green, P < 0.20)
- **Elevated predicted risk** (amber, 0.20 ≤ P < 0.60)
- **High predicted risk** (red glow, P ≥ 0.60)

The thresholds 0.20 / 0.60 here are **display thresholds for the
verdict colour** — they are NOT the operational alerting threshold,
which is set in the Model metrics tab.

### 2.4 — Plotly verdict gauge

A semi-circular dial showing the probability as a needle position from
0 to 1. Colour gradient matches the verdict card. The needle plus the
numeric probability label makes the prediction emotionally legible
("the needle is in the red zone").

### 2.5 — Probability split bar chart

Two horizontal bars: P(red-team next window) and 1 − P. Visualizes
how confident the model is.

### 2.6 — Explainer panel ("Why this prediction?")

A horizontal bar chart showing the top features pushing the prediction
**up** (red bars) and **down** (green bars). Comes from `POST /explain`.

Three different math paths depending on which model is serving:
- **Linear (LR)** → `coef × scaled_value` per feature (exact log-odds
  decomposition)
- **XGBoost** → `booster.predict(pred_contribs=True)` (exact TreeSHAP)
- **LightGBM** → `booster.predict(pred_contrib=True)` (exact TreeSHAP)

**Critical distinction for Q&A:** This is **not** a `shap` library
approximation. It's exact contributions from the booster's own
internals, which is faster and reproducible.

### 2.7 — Counterfactual recommender ("How to lower this risk")

A small table from `POST /counterfactual`. For the LR sidecar model,
it computes the **smallest single-feature change** that would bring
the predicted probability below a target (default 0.20).

**Two columns:** feature name and required delta. E.g.
`auth_total_failures: -42` means "reduce failed-auth count by 42 to
push risk under 20%."

**What to say if asked why LR for counterfactuals:** *"Linear models
have a closed-form solution for counterfactuals — you solve for the
single coefficient that crosses the decision boundary. Tree models
don't. We keep the LR pipeline as a 'sidecar' that loads alongside
whichever model wins, so the counterfactual endpoint works regardless
of who's serving predictions."*

---

## 3. Tab — Model metrics

### 3.1 — Model leaderboard table

Four rows: `logistic_regression_baseline`, `random_forest_model`,
`xgboost_model`, `lightgbm_model`. Five columns: ROC AUC, PR AUC,
precision, recall, F1.

The winner row is highlighted. Numbers come from each model's saved
`metrics.json` (written by `jobs/train_model.py`).

### 3.2 — Threshold slider (interactive)

A slider from 0.01 to 0.99 — drag it and four KPI tiles below update
**live**: predicted positives, true positives, false positives, false
negatives. The math is done client-side from the test-set
predictions cached in session state, so it's instant.

**What it answers:** "What happens to the alert volume if I set my
operational threshold to X?"

**Demo trick:** Drag through 0.5 → 0.1 → 0.01 → 0.8 in that order.
Each value tells a different story:
- 0.5 — the textbook default (terrible recall on this dataset)
- 0.1 — sweet spot (good recall, manageable FP)
- 0.01 — paranoid mode (catch everything, drown in noise)
- 0.8 — confident only (low alerts but you'll miss attacks)

### 3.3 — Cost-matrix calculator

Three numeric inputs: `cost_fp` (cost of one false alarm), `cost_fn`
(cost of one missed attack), and a Compute button. Hitting Compute
POSTs to `/cost_optimal_threshold`, which returns the threshold that
minimizes `FP × cost_fp + FN × cost_fn` on the validation PR curve.

**Default values:** 100 / 100000 (a missed attack costs 1000× a false
alarm). Realistic for a SOC.

**What to say:** *"The threshold problem isn't a hyperparameter — it's
a business decision. The API exposes the cost function as an endpoint,
and the dashboard surfaces it as a form. A SOC director who has never
seen a confusion matrix can use this."*

### 3.4 — PR curve plot

A static plot from `GET /threshold_analysis` showing precision and
recall vs. threshold across the validation set, plus the F1-optimal
threshold marked with a vertical line.

---

## 4. Tab — Architecture

A pipeline diagram (ASCII art) showing the bronze → silver → gold →
training → serving → UI flow, with the cloud provider for each stage:
S3, EMR, MLflow, EC2, Streamlit Cloud.

Below the diagram: a short list of the project's distributed-computing
properties (the three rubric-required layers) and the wow-factor
features (XAI + counterfactual + threshold tuning + Live monitor).

**Use it as the closing visual** if you have 30 seconds at the end.

---

## 5. Tab — How it works

Plain-English narration of the system for someone who's never seen ML
or distributed computing before. Five short paragraphs: the question,
the input, the transformation, the leakage trick, the model. Skip on
stage; useful for the link the grader might click later.

---

## 6. Tab — Live monitor (the grand finale)

### 6.1 — Intro caption

A short paragraph explaining that this is a streaming **simulator**,
not a real Kinesis consumer. **Always honest in the UI.** Audience
can read it themselves while you talk.

### 6.2 — Four control buttons

| Button | What it does | What it calls |
|---|---|---|
| **Start stream** | Loads N gold rows, batch-scores them all up front, starts the ticker | `POST /batch_predict` once, then internal ticker |
| **Pause** | Stops the ticker but keeps the chart and events buffer | (none) |
| **Reset** | Clears the events buffer, resets cursor to 0 | (none) |
| **Inject HIGH-risk row** | Sends the HIGH preset features to /predict, appends to events | `POST /predict` |

### 6.3 — Two sliders

- **Pool size** (30–300, default 120) — how many gold rows to replay.
  At ~1.25 events/sec, 120 rows = ~90 seconds of demo. Set before Start.
- **Alert threshold** (0.05–0.95, default 0.50) — probability above
  which a row turns red and counts as an alert. **Changes instantly,**
  even mid-stream, because the chart re-colours from the event buffer
  every tick.

### 6.4 — Four KPI tiles

- **Events scored** — total rows processed so far
- **Alerts fired** — count of rows ≥ threshold (delta annotated with
  current threshold)
- **Max P** — highest probability seen so far in this stream
- **Mean P** — average probability seen so far

These tiles tell the operator "is the system seeing anything unusual?"
at a glance, without reading the chart.

### 6.5 — Trajectory chart

A Plotly scatter+line plot. X-axis = event sequence (0, 1, 2, ...);
Y-axis = P(red-team next window) from 0 to 1.

- **Mint-green dots** — below half the threshold (clearly benign)
- **Amber dots** — between half-threshold and threshold (watching)
- **Red dots** — above threshold (alerted)
- **White-bordered, oversized red dot** — an injected event
- **Dashed red horizontal line** — the current alert threshold

Hover any dot to see `seq`, `host`, and `P`. Injected dots have an
extra `INJECTED` flag in the hover text.

### 6.6 — Alert banner

A red, gradient-filled banner above the chart that ALWAYS shows the
**most recent** alert (most recent row with P ≥ threshold). Tag
`[STREAM]` for organic alerts, `[INJECTED]` for inject-button alerts.

Disappears if no events in the buffer are above threshold — useful
for showing "all clear" after a Reset.

### 6.7 — Recent alerts expander

A collapsed expander below the chart that opens to show the last 20
alerts as a table (Seq / Host / P / Injected?). Audit-trail for the
demo; nobody needs to open it on stage but it's there if asked.

### 6.8 — "How this is implemented" expander

The Q&A safety net. Open it on stage if anyone asks how the simulator
works under the hood — it has the architecture diagram, the production
path, and the honest disclaimer all in one place.

---

## 7. The 30-second elevator pitch for the dashboard

> *"Five-tab Streamlit app. Predict tab scores one host's behaviour
> with explainable AI and a counterfactual recommender. Model metrics
> tab has an interactive threshold slider plus a cost-matrix
> calculator that takes business costs and returns the operationally
> optimal cutoff. Architecture tab shows the medallion pipeline. Live
> monitor tab replays the gold sample through the deployed API at one
> event per second — a streaming simulator that proves the scoring
> engine survives sustained load. Every tab talks to a real FastAPI
> service in a Docker container on EC2."*

If you can say that in one breath, you're ready for the demo.
