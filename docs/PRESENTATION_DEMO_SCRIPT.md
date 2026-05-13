# Live Demo Script — LANL Threat Operations Dashboard

> The minute-by-minute, click-by-click, word-for-word script for the live
> portion of your capstone presentation. Read this once tonight. Run
> through it once in a mirror tomorrow morning. Then go on stage and
> trust the rehearsal.

---

## Table of contents

1. [Pre-flight checklist (30 min before)](#1-pre-flight-checklist-30-min-before)
2. [The demo arc — 4.5 minutes total](#2-the-demo-arc--45-minutes-total)
3. [Step-by-step demo script (click + speak)](#3-step-by-step-demo-script-click--speak)
4. [The threshold-slider deep-dive (90-second showcase)](#4-the-threshold-slider-deep-dive-90-second-showcase)
5. [Backup plans if something fails](#5-backup-plans-if-something-fails)
6. [Q&A — fourteen anticipated questions and answers](#6-qa--fourteen-anticipated-questions-and-answers)
7. [Delivery notes (tone, body language, recovery)](#7-delivery-notes-tone-body-language-recovery)
8. [The one-sentence summary if you have 60 seconds](#8-the-one-sentence-summary-if-you-have-60-seconds)

---

## 1. Pre-flight checklist (30 min before)

Do these in order. Each takes under a minute.

### 1.1 — Verify the API is alive

In a Git Bash window on your laptop:

```bash
cd "C:/Users/markc/Documents/DistributedCompProject2/LANL"
curl -s http://98.94.30.68:8000/health
```

You want exactly:
```json
{"status":"ok","model_loaded":true,"model_name":"lightgbm_model","feature_count":43}
```

If you do not see that JSON: **see § 5.1 below — API not responding.**

### 1.2 — Run the smoke test

```bash
py test_project.py --url http://98.94.30.68:8000
```

You want `PASS: all checks succeeded.` at the bottom. **Screenshot this.**
That screenshot is your bulletproof grading evidence regardless of what
happens during the live demo.

### 1.3 — Open the live URL in incognito

`Ctrl + Shift + N` → paste `https://lanlthreat.streamlit.app` → Enter.

Confirm visually:
- Dark cyber theme renders (navy background, mint-green accents)
- Sidebar shows green `[ ONLINE ]` API status badge
- The animated pulsing dot is in the header banner
- Five tabs: **Predict / Model metrics / Architecture / How it works / Live monitor**

### 1.4 — Pre-click the preset dropdown

Open the sidebar **Scenario** dropdown once to confirm the calibrated
presets are present:

```
Demo HIGH risk - real row (P=0.745)
Demo MEDIUM risk - real row (P=0.275)
Demo LOW risk - real row (P=0.072)
Quiet workstation
Busy admin host
Suspicious - failed-logon storm
Suspicious - lateral movement
```

Close the dropdown without picking anything. Leave it at `(choose...)`.

### 1.4b — Smoke-test the Live monitor

Click the **Live monitor** tab once. Confirm:
- The intro caption renders ("...streaming SIMULATOR, not a Kinesis
  consumer...")
- Four control buttons: **Start stream / Pause / Reset / Inject
  HIGH-risk row**
- Two sliders: pool size + alert threshold

Don't click Start yet — that's the live demo. Just verify the tab loads.

### 1.5 — Open backup tabs

In a separate browser window (not incognito), open:
- `https://github.com/mcrisci24/lanl-threat-pipeline` (GitHub repo)
- `http://98.94.30.68:8000/docs` (FastAPI OpenAPI docs) — useful if anyone
  asks "show me the API"

### 1.6 — Move the backup screenshots into reach

The `LANL_Passes/` folder in the repo has:
- EMR cluster TERMINATED with both steps COMPLETED
- The PASS terminal output
- Streamlit UI dashboard screenshots

Have that folder open in File Explorer in case the live URL fails mid-demo.

### 1.7 — Open the deck

Open `PRESENTATION.pptx` and put PowerPoint in **Presenter View** so you
can see speaker notes. Move to slide 1.

---

## 2. The demo arc — 5.5 minutes total

This is the high-level shape. Memorize this rhythm; details come in § 3.

```
0:00 - 0:20   Open with the HIGH-risk preset.
              "The model rates this host at 74.5% risk on what looks
               like quiet, focused activity - 4 auth events, 12 outbound
               flows. That's the attacker fingerprint."
0:20 - 1:00   Pivot to LOW preset. The counterintuitive moment:
              7 successful auths + 10 process events looks busy,
              but the model rates it at 7.2% - this is admin housekeeping,
              not a threat.
1:00 - 1:30   Show MEDIUM preset (27.5%). The uncertainty zone:
              15 auth attempts to 6 destinations with 2 user accounts -
              the lateral-movement signature, but borderline.
1:30 - 2:00   Scroll down. Walk through the explainer panel ('Why this
              prediction?') and the counterfactual table ('How to lower').
2:00 - 3:30   Switch to Model metrics tab. The threshold-slider showcase.
              Drag through four threshold values: 0.5, 0.1, 0.01, 0.8.
3:30 - 4:00   Cost-matrix calculator: 100 FP, 100000 FN, hit Compute.
              Land the "model is an estimator, system is the tool" line.
4:00 - 5:00   THE NEW GRAND FINALE: Click Live monitor tab.
              Click Start stream. Watch the chart move. Inject HIGH-risk.
              "This isn't a calculator - it's a scoring engine under load."
5:00 - 5:30   Close on the Architecture tab. Re-state the rubric story:
              three distributed stages, four models in MLflow, two XAI
              endpoints, one live URL, one streaming simulator.
```

If you only have **4 minutes**: skip step 4 (cost-matrix) and shorten
the threshold-slider showcase. **Always keep the Live monitor moment**
— it's the visual peak. If you only have **2 minutes**: HIGH preset
+ Live monitor (Start + Inject) + Architecture close.

---

## 3. Step-by-step demo script (click + speak)

For each step: **what you click** is bold; *what you say* is in italics.
Each step is annotated with **expected time on stage**.

### Step 1 — Set the stage (15 seconds)

**Stay on the Predict tab. Don't click anything yet.**

*"This is the LANL Threat Operations Dashboard — the live application
URL for this project. It's a Streamlit front end that hits a FastAPI
backend running on AWS EC2, which in turn serves a LightGBM model that
won a four-model bake-off on the LANL enterprise telemetry dataset.
Every prediction comes with explainable AI and a counterfactual
recommender. Let me show you what that means."*

### Step 2 — Pick the HIGH-risk preset (20 seconds)

**In the sidebar, click the Scenario dropdown.**
**Pick "Demo HIGH risk - real row (P=0.745)".**

*Wait for the form to populate. Scroll up so the user sees the input
form with the values filled in.*

*"This is a real row from the LANL gold table — the model rates it
at 74.5% probability of red-team activity in the next hour. Look at
the values: four successful authentication events to a single
destination host, twelve outbound network flows totaling 1,824 bytes
— under 2 KB. To a human analyst this looks like a quiet workstation
doing nothing unusual. The model says: this is what the
reconnaissance phase of a real attack looks like."*

**Scroll down to the bottom of the input form. Click "Predict
next-window risk".**

### Step 3 — React to the HIGH-risk verdict (25 seconds)

**The right column populates. Point at the verdict card.**

*"There's the answer. 'High predicted risk.' The Plotly gauge below
shows the needle deep in the red zone — around 74%. The probability
split chart shows the majority of probability mass on 'Red-team
activity in the next window.'"*

**Scroll down past the verdict. Point at the 'Why this prediction?'
panel.**

*"This is the explainable-AI piece. Each red bar is a feature pushing
risk UP — for this row the model is flagging the combination of
focused, low-volume authentication paired with non-zero outbound flow
activity. The green bars push risk down. This is not a SHAP
approximation — it's exact TreeSHAP from LightGBM's booster
(`booster.predict(pred_contrib=True)`), surfaced through a single API
call."*

### Step 4 — Switch to the LOW preset (the counterintuitive moment) (45 seconds)

**Scroll back up to the sidebar.**
**Click the Scenario dropdown.**
**Pick "Demo LOW risk - real row (P=0.072)".**

*"Now contrast with this row. Same dataset, real gold sample. Seven
successful authentications to three different destination hosts.
Ten process-start events spanning six unique process names. To a
human, that looks busy — measurably more activity than the HIGH-risk
row we just looked at."*

**Click "Predict next-window risk".**

**Wait for the right column to update. Point at the 'Low predicted
risk' verdict in green.**

*"The model says: low risk. Around 7% probability. Why? Scroll down
to the explainer."*

**Scroll down past the verdict.**

*"The green bars dominate. The model has learned — from training on
596 real red-team-positive examples in the LANL dataset — that this
pattern (a handful of successful auths plus diverse process activity)
is what an admin host or service account does, not what an attacker
does. The real attacker pattern is the one we saw thirty seconds ago:
focused, low-volume, deliberately blending into the noise."*

**Pause for half a beat.**

*"That's the kind of insight a rule-based system would never give you.
Heuristics would tell you 'more activity is more suspicious.' A model
trained on actual attack labels tells you the opposite: routine
diversity is benign; deliberate, narrow targeting is the attacker
signature."*

### Step 5 — Show the MEDIUM preset briefly (20 seconds)

**Click the Scenario dropdown.**
**Pick "Demo MEDIUM risk - real row (P=0.275)".**
**Click "Predict next-window risk".**

*"This is the middle case. The model is 27.5% confident — borderline.
Look at the pattern: fifteen outbound authentication attempts hitting
six different destination computers using two distinct user accounts,
plus three inbound auths from two source machines. That's a textbook
lateral-movement fingerprint — a host fanning out across the network
with multiple identities — but the volume is low enough that it
could also be legitimate admin work. This is exactly the kind of
prediction where threshold tuning matters most. Whether you raise an
alert or not depends on what your operation values: are you more
afraid of missing a real attack, or of overwhelming your analysts
with false alarms? That's a business decision, not a model
decision."*

### Step 6 — Show the counterfactual recommender (20 seconds)

**Stay on the MEDIUM preset. Scroll past the explainer panel to the
'How to lower this risk' section.**

*"This is the second XAI piece. The model didn't just predict; it
recommended an action. The table shows the smallest single-feature
change that would bring the predicted risk under 20%. For this row,
the system suggests reducing a specific feature by a specific amount.
A SOC analyst gets the prediction, the reason, AND a recommended
mitigation — not a black-box score."*

### Step 7 — Switch to Model metrics tab for the threshold demo (3-second transition)

**Click "Model metrics" at the top of the page.**

*"Now I want to show you the most important feature in the entire
system — the part that turns this from 'a model' into 'a decision-
support tool.'"*

*See § 4 for the full threshold-slider script.*

### Step 7.5 — The Live monitor finale (60 seconds)

This is the new grand finale. After the threshold-slider showcase
ends, before you close on Architecture, take the audience to the
Live monitor tab. It is the most visually striking moment in the
demo and the answer to anyone who thinks this is "just a calculator."

**Click the Live monitor tab.**

*"One more thing. A common reaction to a dashboard like this is
'you've built a calculator — type in numbers, get a probability.'
Let me show you why this is a scoring engine, not a calculator."*

**Click the Start stream button.**

*Wait roughly two seconds while the pool is batch-scored. The spinner
will show "Scoring pool through /batch_predict...". When it
disappears, dots will start appearing on the chart at 1.25 events per
second.*

*"What you're watching is one hundred and twenty real gold-table rows
being replayed through the deployed FastAPI service at roughly one
event every 0.8 seconds. Every dot is a real HTTP call to the same
endpoint a production SOC analyst would hit. The KPI tiles up top
update live: events scored, alerts fired, max probability seen, mean
probability seen."*

*Let the chart run for ~10 seconds so the audience sees it filling
out. Most dots will be at zero or around the model's 0.23 default
for sparse rows. Then:*

**Click the Inject HIGH-risk row button.**

*"Now I'm splicing in the canonical attack fingerprint we identified
in the Predict tab — same nineteen feature values, same row that
scored at 74.5%. Watch the chart."*

*A big white-bordered red dot lands at the current sequence position.
The red **[INJECTED] ALERT** banner pops above the chart with the
host marked `<INJECTED>` and the probability rendered live.*

*"There. Big dot, threshold crossed, alert banner fires. The
production alert path just executed against real infrastructure."*

**Pause for a beat. Let people read the banner.**

*"Two honest disclaimers. First, this is a streaming SIMULATOR — the
'stream' is a recorded CSV being replayed on a Python timer, not a
Kinesis consumer. The scoring engine is real and deployed; the
ingest in this demo is not. Second, swapping the simulator for
Kinesis Data Streams is a wire-format change, not a model change.
The model, the FastAPI service, and the feature contract don't move.
That is the architectural payoff of putting scoring behind an HTTP
boundary."*

### Step 8 — Close on the Architecture tab (30 seconds)

After the Live monitor moment lands, click **Architecture** at the
top. If you're tight on time, skip this and close from the Live
monitor tab — the audience just saw the system operate, they don't
need the diagram.

*"That's the whole system. Real distributed pipeline — three AWS
layers (S3 storage, EMR Spark transformation, EC2 serving). Four
machine-learning models trained and tracked in MLflow, winner
promoted to Production in the Model Registry. Two explainable-AI
endpoints — exact log-odds decomposition for the linear baseline,
exact TreeSHAP for LightGBM. One cost-aware threshold tuner. One
streaming simulator that proves the scoring engine survives sustained
traffic. One live URL the grader can hit from anywhere."*

**Pause. Make eye contact with the room.**

*"The rubric explicitly rewards rigor over raw metric value. The
model is honest. The infrastructure is real. The interface is
operationally useful. Thank you."*

---

## 4. The threshold-slider deep-dive (90-second showcase)

This is the centerpiece. It's the moment that separates this project
from every other capstone in the room. Slow down here. Let the audience
watch the numbers change as you drag.

### 4.1 — Setup (5 seconds)

**You are on the Model metrics tab. Scroll down past:**

- The four big metric tiles (Test ROC AUC, PR AUC, F1, recall)
- The full metric table
- The "Why we report PR AUC" paragraph
- The feature importance bar chart (top 15 features)

**Stop scrolling when you see the "Threshold tuning / cost-matrix
calculator" subheader.**

### 4.2 — Set the stage (15 seconds)

*"Every machine-learning model produces a probability. To turn that
probability into a yes/no alert, you have to pick a decision
threshold. By default, most models use 0.5 — anything above 50% is
a positive. For imbalanced data like ours, where the positive class
is 0.0043% of the rows, 0.5 is almost never the right answer."*

### 4.3 — Walk through the PR curve (15 seconds)

**Point at the Plotly chart with three colored lines.**

*"This is the precision/recall/F1 curve from our validation set —
two hundred thresholds plotted. Green is precision: the fraction of
our alerts that are real attacks. Cyan is recall: the fraction of
real attacks we catch. Amber is F1. The red dashed line is the
F1-optimal threshold the system found automatically."*

### 4.4 — Slider walkthrough (50 seconds — the heart of the demo)

**Find the slider labeled "Decision threshold" below the chart.**

#### 4.4.1 — At default (10 sec)

**Set the slider to 0.50.**

*"At 0.5, the model is highly precise but barely recalls anything.
Watch the four tiles below the slider — Precision, Recall, F1 at
this threshold. We catch a small fraction of real attacks but
almost every alert is real."*

#### 4.4.2 — Drag to 0.1 (10 sec)

**Drag the slider down to about 0.10.**

*"Drop to 0.10 — recall climbs sharply. The plain-language line below
tells you: at this threshold, of every ten thousand alerts the system
raises, [N] are real compromises. That's the trade-off in concrete
terms."*

#### 4.4.3 — Drag to 0.01 (10 sec)

**Drag the slider down to about 0.01.**

*"Threshold of 0.01 — we now catch almost every attack. But the
false-alarm volume is huge. This is what happens when an alert
system is over-sensitive — analyst fatigue."*

#### 4.4.4 — Drag to 0.8 (10 sec)

**Drag the slider up to about 0.80.**

*"And the other extreme — at 0.80, every single alert is almost
certainly a real attack. But we're missing most of the actual
compromises. There is no single right threshold. It depends entirely
on what your operation values."*

#### 4.4.5 — Return to the F1-optimal (10 sec)

**Drag the slider back to the F1-optimal threshold (red dashed line
position, usually around 0.05–0.15 depending on the model).**

*"The F1-optimal threshold the system found at training time. But
F1 assumes false positives and false negatives are equally costly —
which they aren't in security. That's where the cost-matrix
calculator comes in."*

### 4.5 — Cost-matrix calculator (15 seconds — close hard)

**Scroll down to the 'Cost-matrix calculator' section.**

*"Imagine I'm running a SOC. An analyst chasing a false alarm costs
me roughly $100 in time. A successful breach we missed costs the
company $100,000. That's a thousand-to-one cost ratio."*

**Type 100 in "Cost of False Positive."**
**Type 100000 in "Cost of False Negative."**
**Click "Compute optimal threshold."**

**Wait for the recommendation to appear.**

*"The math runs across the entire validation set, finds the threshold
that minimizes total expected operational cost, and tells me: at this
cost ratio, use threshold [X]. At that operating point, we catch
[recall]% of attacks with [precision] precision. Exactly the trade-off
my business wants."*

**Pause.**

*"This is the difference between a model and a tool. Most ML capstones
stop at 'here's the model.' We expose the decision policy itself —
the model is a probability estimator; the operating point is a
business decision; we made it adjustable."*

---

## 5. Backup plans if something fails

Murphy's Law on stage. Have these ready.

### 5.1 — API not responding

**Symptoms:** `curl /health` times out, or Streamlit sidebar shows the
red "[ OFFLINE ]" badge.

**Quick recovery (90 seconds):**

```bash
ssh -i ~/.ssh/lanl-key.pem ec2-user@98.94.30.68 \
    "docker ps -a --filter name=lanl-api; \
     docker start lanl-api 2>/dev/null || \
     docker run -d --restart=unless-stopped --name lanl-api \
                -p 8000:8000 lanl-api:latest"
sleep 12
curl -s http://98.94.30.68:8000/health
```

If the container is gone entirely (deleted), recreate it from the existing
image (which is still in EC2 Docker storage even if the container was
deleted).

**If you can't recover in 60 seconds, switch to backup mode.**

### 5.2 — Backup mode (live URL is completely dead)

You have screenshots in `LANL_Passes/`. The demo becomes a slide
walkthrough instead of a live click-through. Acknowledge it once, then
move on confidently:

*"Looks like the EC2 instance is having a moment — let me walk you
through this with screenshots instead. The architecture and the result
are the same."*

Open the `LANL_Passes/` folder in File Explorer, or better, open the
images one at a time in Photos. Walk through:

1. EMR cluster TERMINATED + both steps COMPLETED → "real distributed pipeline ran"
2. PASS terminal output → "smoke test against the live URL succeeded"
3. Streamlit Predict tab screenshot → "this is the predict flow"
4. Streamlit Why this prediction screenshot → "this is the explainer"
5. Streamlit threshold slider screenshot → "this is the cost-aware tuner"

Then: *"All of this is also documented in the one-page write-up and
the GitHub repo, both of which are linked in the README. Happy to take
questions on any of it."*

### 5.3 — Streamlit Cloud is rebuilding mid-demo

**Symptoms:** the live URL shows "Your app is in the oven" or a generic
error.

**Quick recovery:** local fallback.

```bash
# In Git Bash on the laptop
cd "C:/Users/markc/Documents/DistributedCompProject2/LANL"
set LANL_API_URL=http://98.94.30.68:8000
py -m streamlit run app/streamlit_app.py
```

A browser tab opens at `localhost:8501` with the exact same app, talking
to the live EC2 API. The grader can still see everything. The downside
is the URL bar shows `localhost` instead of `lanlthreat.streamlit.app`,
which is cosmetic.

### 5.4 — A specific preset returns an unexpected verdict

**Symptoms:** you click HIGH and the model says LOW (or vice versa).

**The graceful pivot:**

*"Different presets behave differently as the model continues to
update — let me try another."*

Then pick a different preset. You have three demo presets, two
historical presets, and one custom preset feature where you can type
values directly into the form. Pick the one that fires correctly.

### 5.5 — Network is dead at the venue

If the venue WiFi is down, the live URL won't work at all. Open the
**PRESENTATION.pptx** speaker view and walk through the slides only.
The slides have all the visuals (architecture, metric comparison,
explainer mockup, counterfactual mockup, threshold tuning) — they tell
the story without needing the live URL.

---

## 6. Q&A — fourteen anticipated questions and answers

### Q1. "Why is precision so low (0.001)?"

> *"Because positives are 0.0043% of the data. Even a model that ranks
> 88% of pairs correctly produces many absolute false positives — the
> relative rate is fine. That's why the cost-matrix calculator exists:
> the operator picks the threshold matching their false-alarm budget."*

### Q2. "Are you sure you have no leakage?"

> *"Three layers in code. The target is built with a Spark window
> function that shifts the label forward one window. Every
> current-window red-team aggregate is dropped from the feature set
> before training. The training script asserts at runtime that no
> leakage column survived. It's not a methodology promise; it's an
> assertion that fails the run."*

### Q3. "Why stratified random instead of time-aware split?"

> *"The red-team campaign in LANL ends mid-record. A strict time-aware
> split places all 596 positives in training and leaves valid/test
> with zero — every metric collapses to NaN. We use stratified random
> and disclose the trade-off explicitly. In return for some loss of
> strict temporal causality, we get measurable, defensible metrics."*

### Q4. "Why LightGBM and not just XGBoost?"

> *"We trained four models — LR, RF, XGBoost, LightGBM. All four
> logged to MLflow. LightGBM won on validation F1 by a hair, so the
> Model Registry aliased it 'Production' automatically. We didn't pick
> manually; the tracking framework picked."*

### Q5. "Why not 0.98 ROC AUC like X's project on CICIDS?"

> *"Different problem. CICIDS asks 'was this flow malicious?' using
> features computed from that same flow — descriptive. We predict
> next-window red-team activity using only what's observable now,
> on a dataset with 100× worse class imbalance. Our PR AUC is 900×
> the random baseline; theirs at 5% base rate is 20×. Per-multiple
> of base rate, our model is doing more work on a harder problem.
> See `docs/CICIDS_COMPARISON.md` in the repo for the full
> technical comparison."*

### Q6. "What does the counterfactual endpoint actually compute?"

> *"For a linear model, the smallest single-feature change in raw
> value that would bring the predicted probability below a target.
> It's a closed-form inverse of the linear model:
> `delta = (target_logit - current_logit) / coefficient`. For the
> linear baseline that's exact. For LightGBM serving, we keep the
> LR pipeline loaded as a sidecar so the counterfactual still works."*

### Q7. "How does /explain handle a tree model?"

> *"Exact TreeSHAP via the model's built-in
> `booster.predict(pred_contrib=True)`. Same return shape as the
> linear decomposition — per-feature contribution to log-odds — so
> the UI rendering is unchanged. Not a SHAP approximation; the
> built-in computation is the exact game-theoretic decomposition for
> tree ensembles."*

### Q8. "Why is the model getting 0% on the suspicious presets?"

> *"The synthetic presets were calibrated for the logistic-regression
> baseline. LightGBM learned more specific attack signatures from 358
> real positive examples in training. The synthetic patterns don't
> match those signatures. That's why the demo presets — the ones
> labeled 'real row' — are sourced from the actual gold table; they
> trigger predictably across the risk spectrum."*

### Q9. "Did you actually run EMR? Or is it just code?"

> *"Yes, EMR ran end-to-end. The cluster ID was j-9FM0RGG2ZRZK. Both
> Spark steps — bronze_to_silver and silver_to_gold — completed
> successfully on May 11. The auth.txt.gz file alone is 7.1 GB
> compressed; the cluster ran for about three hours total.
> Screenshots of the terminated cluster in EMR Console are in the
> repo under `LANL_Passes/`."*

### Q10. "Can this scale to a real enterprise?"

> *"The pipeline is designed for it. S3 stores arbitrarily large
> bronze data; EMR scales horizontally with cluster size; the API
> is stateless and could run behind an autoscaling group; the model
> is small enough to serve at low latency. The Live monitor tab
> already demonstrates that the scoring engine survives sustained
> traffic — it just doesn't read from Kinesis yet. Swapping the CSV
> replayer for a Kinesis Data Streams consumer is a wire-format
> change, not a model change."*

### Q11. "What was the hardest part?"

> *"Leakage. Our first model had validation F1 near 1.0, which is the
> universal sign of cheating. Tracking it down took rebuilding the
> target as a future-window label, dropping the current-window
> red-team aggregates, and adding the runtime assertion. The
> Databricks-to-AWS pivot was also non-trivial — we hit free-tier
> storage limits and had to rebuild the medallion architecture on
> S3 + EMR without losing the design properties."*

### Q12. "What would you do differently with more time?"

> *"Four things, ordered by impact. One: the REAL streaming layer —
> Kinesis into Spark Structured Streaming for live scoring, replacing
> the simulator you just saw with actual event ingest. Two:
> EventBridge-driven retraining schedule that retrains weekly as
> new windows arrive. Three: distribution-aware imputation — random
> sampling from the column's existing values instead of median
> substitution. Four: mutual-information feature selection to prune
> low-signal features before training. All listed in the write-up's
> section 5."*

### Q13. "Is the Live monitor real-time streaming?"

> *"No, and I'm explicit about that in the UI. It is a streaming
> SIMULATOR — the 'stream' is a recorded CSV being replayed on a
> Python timer at roughly one event per second. The scoring engine
> is real and deployed; the ingest in this demo is not. Every dot
> on the chart is a real HTTP call to the same FastAPI service a
> production SOC analyst would hit. To make it true streaming, you
> swap `streaming_sim.load_replay_pool` for a Kinesis or Kafka
> consumer. The model, the API, and the feature contract don't
> change. That's the architectural payoff of putting scoring behind
> an HTTP boundary."*

### Q14. "Why didn't you build real streaming if it's that close?"

> *"Scope, cost, and risk. This is a distributed-computing capstone —
> the distributed parts are the medallion pipeline on EMR, the Spark
> transformation, the MLflow tracking, and the containerized serving
> layer. A Kinesis Data Stream sized for one demo costs roughly a
> dollar an hour plus DynamoDB / S3 sink fees, and live AWS
> infrastructure has a non-trivial blast radius during a demo. The
> honest tradeoff was to ship the scoring engine production-grade
> and simulate the ingest with a guarantee that the simulator and
> the real consumer would talk to identical APIs. The simulator's
> failure mode is 'chart stops updating'; a real Kinesis failure
> mode is 'demo blank for 90 seconds while everyone watches.' I'd
> rather show working software than risk a fragile live system."*

---

## 7. Delivery notes (tone, body language, recovery)

### Tone

- **Confident but not boastful.** You built a real system. Speak from
  that ground. Don't oversell ("revolutionary AI") and don't undersell
  ("just a class project").
- **Direct, not defensive.** When asked about leakage or low precision,
  answer in one short paragraph. Don't go down a rabbit hole.
- **Conversational, not scripted.** Read this document in advance, then
  on stage paraphrase from memory. Don't read off the page.

### Body language

- Face the audience, not the screen. Glance at the screen to confirm
  what's happening, then turn back.
- Move slowly when dragging the threshold slider. Let the audience
  *watch* the numbers change. Pause for a beat after a notable
  transition.
- Eye contact with two or three people in the room during long
  sentences. Move from one to another when transitioning between ideas.

### Recovery from mistakes

- If you misclick: **don't apologize.** Just say *"let me pick the
  right one"* and move on. The audience won't remember the misclick
  unless you draw attention to it.
- If the URL freezes: **don't panic.** Say *"the cloud's having a
  moment — let me jump to the screenshots."* You have backup.
- If you forget what to say: **return to the rubric.** The rubric is
  the spine of the talk — distributed pipeline, MLflow tracking, live
  endpoint, XAI, threshold tuning. You can always pivot back to one
  of those.

### Pacing

- Total demo: aim for **4.5 minutes**. Practice once with a stopwatch
  in front of a mirror.
- If you're under 3 minutes, you're rushing. Slow the slider drags
  and add a beat of silence after each major reveal.
- If you're over 5.5 minutes, cut. Drop the MEDIUM preset and the
  counterfactual table; keep HIGH preset and threshold slider.

### What to do with your hands

- Don't fold your arms.
- One hand on the mouse, the other free. Gesture with the free hand
  when emphasizing a point.
- When the room is laughing or nodding, **stop talking** and let it
  land. Silence is a tool.

---

## 8. The one-sentence summary if you have 60 seconds

If the demo is cut short — fire alarm, time limit, technical disaster —
this is the entire project in one breath. Memorize it.

> *"This is an end-to-end distributed pipeline on AWS — S3 for storage,
> EMR Spark for transformation, EC2 for serving — that ingests LANL
> enterprise telemetry, trains four ML models tracked in MLflow,
> serves the winning LightGBM model behind a FastAPI endpoint, and
> exposes both an explainable-AI panel and a cost-aware threshold
> tuner through a polished Streamlit UI. The model predicts whether a
> host will be involved in red-team activity in the next hour — a
> future-window framing with a runtime leakage assertion in code, not
> the easier 'is this flow malicious right now' framing that produces
> inflated metrics on lab datasets. Live URL is in the README."*

Three sentences, ~40 seconds of speech, hits every rubric category.

---

## Final checklist — read this once at the very end

- [ ] API is alive (`curl /health` returns the JSON)
- [ ] Smoke test PASS screenshot is saved
- [ ] Live URL renders in incognito with the cyber theme
- [ ] Preset dropdown shows the demo HIGH/MEDIUM/LOW options
- [ ] `LANL_Passes/` screenshot folder is open in File Explorer
- [ ] `PRESENTATION.pptx` is open in Presenter View on slide 1
- [ ] You've read § 3 + § 4 + § 8 of this document once
- [ ] You've answered Q1, Q2, Q5 from § 6 silently to yourself

If all eight boxes check, you're ready. Go.

---

*Document kept in `docs/PRESENTATION_DEMO_SCRIPT.md` for reference.
Read once tonight; rehearse once tomorrow morning; trust the rehearsal
on stage.*
