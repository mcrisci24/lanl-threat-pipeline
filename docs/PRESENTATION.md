# LANL Threat Prediction Pipeline — Presentation Deck and Speaker Script

> 12 slides, ~10 minutes spoken, plus a Q&A appendix.
> Each slide block has: **slide content** (what to put on the slide),
> **visual** (what to draw), and **speaker notes** (what to say).

---

## SLIDE 1 — Title

**Slide content**
- LANL Threat Prediction Pipeline
- An AWS-first distributed data pipeline that predicts next-window red-team activity
- Team: _(names)_
- Course: Distributed Computing for Data Science — Project 2

**Visual**
- Subtle network-graph or terminal-style background.
- Live URL and GitHub URL at the bottom of the slide for the grader.

**Speaker notes**
"This is an end-to-end distributed data pipeline built on the Los Alamos
National Laboratory enterprise telemetry dataset. The goal is a hosted
web application that answers a real, time-aware predictive question - and
the whole thing is wired together with S3, EMR, MLflow, FastAPI, and
Streamlit on AWS. I'll walk you through the question, the architecture,
the model, and the live app."

---

## SLIDE 2 — The prediction question

**Slide content**
- Question: *"Given a computer's behavior in the **current** event-time window,
  will that same computer show **red-team activity in the next window**?"*
- Why "next window" matters: keeps the model from peeking at the answer
- Target column: `target_redteam_next_window`

**Visual**
- Two adjacent rectangles labeled "Window t" and "Window t+1".
- Features come from t (auth, flows, dns, proc).
- Label = red-team activity in t+1.
- Arrow from t -> t+1 with text "predict ahead, not describe the present".

**Speaker notes**
"The framing is the most important decision in the whole project. We're
not labeling the current window - that would basically be a description.
We're predicting the *next* window. That's an actual operational question
a SOC analyst would care about: 'is this host about to be a problem?'
And it turns out you have to design carefully to make sure the model
doesn't accidentally see the answer."

---

## SLIDE 3 — The data

**Slide content**
- LANL multi-source telemetry: **auth, flows, dns, proc, redteam**
- ~11 GB compressed; relative event time
- Each source has its own row grain
- Why LANL: real data engineering problem, not a pre-cleaned CSV

**Visual**
- Five stacked file icons labeled with each source, sizes next to them.
- An arrow into a single S3 bucket.

**Speaker notes**
"LANL's enterprise telemetry is five separate event streams - auth events,
network flows, DNS lookups, process events, and the ground-truth red-team
labels. They're big, they're messy, and crucially they all describe
different aspects of the same hosts. So this isn't a 'train a classifier
on a flat table' project - the data engineering is the project."

---

## SLIDE 4 — Architecture

**Slide content**
- Bronze (S3 raw) -> Silver (EMR PySpark) -> Gold (EMR PySpark) -> Model -> API -> UI
- Three distributed stages: S3 storage, EMR transformation, EC2 serving
- Spec requires at least two; we have three

**Visual**
- Use the ASCII pipeline from `docs/ARCHITECTURE.md` rendered as a polished
  diagram. Highlight in green the three boxes that are "distributed".

**Speaker notes**
"Raw files land in S3. EMR PySpark transforms bronze to silver, then silver
to gold. The gold table feeds a scikit-learn training job that tracks every
run in MLflow. The winning model is served from FastAPI on EC2 and the UI
is a Streamlit app. The rubric asks for at least two distributed stages -
we have three: S3 for storage, EMR for transformation, and EC2 for serving."

---

## SLIDE 5 — Medallion in plain English

**Slide content**
- **Bronze:** raw, immutable - 'unloaded at the dock'
- **Silver:** typed, cleaned, source-grain - 'ingredients washed and labeled'
- **Gold:** aggregated by `(computer, time_window)` - 'the dish, ready to serve'

**Visual**
- Three horizontal cards in bronze / silver / gold colors with the metaphors.

**Speaker notes**
"Medallion can sound abstract, so I think of it as a refinery. Bronze is
the receiving dock - we don't touch the data, we just preserve it. Silver
is where we clean and type each stream but keep its original row grain.
Gold is where we change the row grain - now one row is one computer in
one time window. That's the natural unit of risk."

---

## SLIDE 6 — The signature design: future-window target, no leakage

**Slide content**
- Target = next window's red-team activity (built with Spark `lead()`)
- Current-window red-team columns are dropped before training
- Training script *asserts* no leakage column survived

**Visual**
- Code snippet:
  ```python
  W = Window.partitionBy("computer").orderBy("time_window")
  target_redteam_next_window = lead(redteam_current_flag, 1).over(W)
  ```
- Bullet: "Anti-cheating defense in code, not just in assumptions."

**Speaker notes**
"This is the decision I'd defend hardest. Our first model accidentally let
red-team counts leak through, and validation F1 was almost perfect - which
is the universal sign of leakage. So we rebuilt the target as the *next*
window's activity, removed the current-window red-team columns, and added
an assertion in training that fails the job if any of them sneak back in.
That dropped the metrics to honest numbers."

---

## SLIDE 7 — The model + MLflow

**Slide content**
- scikit-learn pipeline (median impute + standard scale + classifier)
- Models: logistic regression baseline + random forest
- Time-aware 60/20/20 split (NOT random)
- MLflow: tracking + Model Registry, alias **Production**
- Metrics: precision, recall, F1, ROC AUC, **PR AUC**

**Visual**
- Side-by-side metric table for LR vs RF with the test PR AUC highlighted.

**Speaker notes**
"We deliberately picked a benchmark and a stronger model. Both are wrapped
in a scikit-learn Pipeline with imputation and scaling so retraining is one
function call. Every run goes to MLflow - the metrics, the parameters, the
artifact, even the leakage columns we removed. The winning run gets aliased
'Production' in the registry. We report PR AUC because the positive class
is rare; a model that always predicts benign could be 99 % accurate and
100 % useless."

---

## SLIDE 8 — The API

**Slide content**
- FastAPI on EC2
- `GET /health` `GET /model_info` `GET /features`
- `POST /predict` `POST /batch_predict`
- Missing features default to 0 (no observed activity)
- OpenAPI docs at `/docs`

**Visual**
- Screenshot of the `/docs` Swagger UI.
- A small JSON example request and response side by side.

**Speaker notes**
"FastAPI gives us a real, introspectable API for free. /health isn't just
'the process is up' - it confirms the model loaded. /model_info exposes
the metrics so the UI can show how good the model is. /predict accepts
the gold-table feature shape; missing features default to zero because
zero means 'no observed activity'. There's also a /batch_predict for
replays."

---

## SLIDE 9 — The UI

**Slide content**
- Streamlit app with four tabs: **Predict / Metrics / Architecture / How it works**
- Preset scenarios for an instant demo
- Verdict card with color-coded risk band
- Probability chart + filtered table of what we fed the model

**Visual**
- Screenshot of the Predict tab with a preset loaded and the verdict card
  showing.

**Speaker notes**
"The UI is built for someone who has never heard of LANL. There are preset
scenarios in the sidebar - 'Quiet workstation', 'Failed-logon storm',
'Lateral movement' - so the demo never starts on a blank form. The verdict
card translates the probability into plain English. The Metrics tab shows
the model's test scores, and the Architecture and How-It-Works tabs let
you defend the pipeline without leaving the app."

---

## SLIDE 10 — Hosting + the test script

**Slide content**
- API: FastAPI on EC2, public URL
- UI: Streamlit Cloud / Hugging Face Spaces (free tier, cold-start warning in README)
- `test_project.py` at repo root, runs with `python test_project.py`
- Checks: /health, /model_info, /features, /predict (full + sparse + flat)
- Exits 0 on success, 1 on any failure

**Visual**
- Terminal screenshot showing the test script running and printing PASS.

**Speaker notes**
"The graded URL goes through the live FastAPI service. test_project.py at
the repo root is what the grader runs - it hits every endpoint, validates
the response shapes, accepts both the modern and the legacy payload
shapes, and exits zero on success. The README mentions the cold-start
delay on free-tier hosting so the first request isn't mistaken for a
failure."

---

## SLIDE 11 — The pivot story

**Slide content**
- Started on Databricks; free-tier storage couldn't carry 11 GB
- Pivoted to AWS-first **without dropping the architecture**
- All MLflow / medallion / distributed-compute requirements preserved
- Engineering lesson: change the host, keep the design

**Visual**
- Two-column side-by-side table:
  | Original (Databricks)         | Final (AWS)                |
  | DBFS / Unity Catalog Volumes  | S3                         |
  | Delta Lake                    | Parquet on S3              |
  | Databricks Workspace          | EMR PySpark                |
  | Databricks Model Serving      | FastAPI on EC2             |
  | Databricks MLflow             | MLflow (tracking+registry) |

**Speaker notes**
"We started on Databricks - it was the path of least resistance from class.
But the free tier didn't have writable managed storage for a dataset this
size. Instead of breaking the architecture, we kept the design and moved
to the AWS equivalents. Every requirement - distributed compute, medallion,
MLflow, live endpoint - is still there. The host changed; the engineering
didn't."

---

## SLIDE 12 — Limitations and future work

**Slide content**
- Single dataset; generalization not validated
- Relative event time only (no diurnal features)
- No streaming layer yet (bonus opportunity: Kinesis -> Spark Structured Streaming)
- Future: automated retraining on a schedule (EventBridge + EMR Steps)

**Visual**
- A short bullet list, clean layout.

**Speaker notes**
"Two honest caveats. One: this is one enterprise's telemetry, so the model
might not transfer cleanly to another network. Two: time is relative
seconds, not real clock time, so we can't add diurnal features yet. The
bonus track we'd take next is a streaming layer with Kinesis or Kafka so
the prediction service can score new windows in near-real time, and an
EventBridge schedule that re-trains the model weekly."

---

## APPENDIX — Q&A talking points

- *"Why predict the next window instead of the current one?"*
  Predicting the current window mixes up describing and predicting -
  the model can see signals from the same window the label came from.
  Next-window keeps the model honest.

- *"How do you prevent leakage?"*
  Three layers: (1) the target is built with a Spark `lead`, never
  `current_window`; (2) all `redteam_*` current columns are dropped
  before training; (3) `assert_no_leakage()` fails the training run
  if any of them survived.

- *"Why scikit-learn after Spark?"*
  Spark handles the data engineering at scale. By the time we hit the
  gold table, the row count is small enough for single-node sklearn.
  Right tool, right phase.

- *"Why PR AUC and not accuracy?"*
  The positive class is rare. A trivial model that always predicts
  benign can hit 99% accuracy. PR AUC reflects whether the model can
  actually catch the rare positives.

- *"What if the live URL fails during grading?"*
  The README links the cloud setup steps; `run_local_demo.py` can
  rebuild the model from the local CSV verification path and start the
  API in one command. Plan B exists.

- *"Why three distributed stages and not Databricks-style?"*
  See slide 11. The spec lets us pick from a menu of options for each
  layer; we picked S3 + EMR + EC2 because they're stable on the free
  tier and the architecture story doesn't change.
