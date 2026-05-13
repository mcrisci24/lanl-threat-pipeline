# Streaming Notes

> Companion document for the **Live monitor** tab.
> Read once before the presentation; bring it back up if anyone asks
> "is this actually real-time?"

---

## 1. What this is — in one sentence

The Live monitor is a **streaming simulator** that replays rows from the
gold sample CSV through the deployed FastAPI service on a wall-clock
timer, so you can watch the model's behaviour over time instead of one
row at a time.

## 2. What this is NOT — in one sentence

It is **not** a Kinesis or Kafka consumer. The "stream" is a recorded
log being read back at 1.25 events/second (0.8 s per tick).

That's it. That's the entire honesty disclaimer. Read it out loud during
the demo if you have time; nobody will mind. They will mind if you
pretend it's a real stream and someone catches you in the Q&A.

---

## 3. Why a simulator and not the real thing

Three reasons, ordered by how compelling they are if pressed:

1. **The hard part is already done.** Real streaming pipelines have two
   moving parts: an **ingest layer** (Kinesis / Kafka / MSK) that
   delivers events, and a **scoring layer** that turns each event into
   a prediction. The scoring layer is what this project built — model,
   feature contract, FastAPI service, container image. The ingest layer
   is a wire protocol; it doesn't change what the model does.
2. **Cost.** A Kinesis Data Stream sized for one demo costs roughly a
   dollar an hour, plus DynamoDB / S3 sink fees. A capstone shouldn't
   burn money for a feature that adds zero new ML content.
3. **Risk.** Real streaming infrastructure has a non-trivial blast
   radius during a live demo (cluster cold-starts, IAM, network
   weirdness). The simulator's failure mode is "the chart stops
   updating," which is recoverable in one click.

If someone says *"this isn't real streaming"* the right answer is:
> Correct. The scoring engine is real and deployed; the ingest is a
> simulator. Swapping the simulator for Kinesis is a wire-format
> change, not a model change.

That's a defensible, accurate, professional answer. Use it.

---

## 4. Architecture — current vs. production

```
Current (this project)
----------------------
[ gold_computer_time_sample.csv ]
            |
            v
[ streaming_sim.load_replay_pool ]    <-- the simulator
            |
            v
[ /batch_predict on FastAPI on EC2 ]  <-- REAL (deployed, containerized)
            |
            v
[ Streamlit Live monitor tab ]        <-- REAL (running on Streamlit Cloud)
```

```
Production (the path forward)
-----------------------------
[ host telemetry agents ]
            |
            v
[ Kinesis Data Stream / Kafka ]       <-- replaces load_replay_pool
            |
            v
[ /batch_predict on FastAPI on EC2 ]  <-- UNCHANGED (this is the point)
            |
            v
[ DynamoDB or S3 alert sink ]         <-- new
            |
            v
[ SOC dashboard / SIEM ]              <-- new
```

The only files that change between "simulator" and "production" are:

| Layer                  | Simulator                           | Production                       |
|------------------------|-------------------------------------|----------------------------------|
| Source                 | `streaming_sim.load_replay_pool`    | Kinesis / Kafka consumer         |
| Cadence driver         | `st.fragment(run_every="0.8s")`     | Event arrival                    |
| Sink                   | In-memory list in `st.session_state`| DynamoDB / S3 / Splunk / SIEM    |
| Scoring layer          | **`/batch_predict` on FastAPI**     | **`/batch_predict` on FastAPI**  |
| Model artifact         | **`model_outputs/<best>.joblib`**   | **`model_outputs/<best>.joblib`**|
| Feature contract       | **`feature_names.json`**            | **`feature_names.json`**         |

Three rows change. Three rows do not. The three that don't change are
the entire ML system. The three that do change are plumbing.

---

## 5. Honest claims you can make

Anything **bolded** here is true and defensible.

- **"The model is deployed behind an HTTPS endpoint on a containerized
  FastAPI service running on EC2."** — true; see `deploy/Dockerfile`.
- **"The Live monitor pushes real HTTP traffic to that endpoint at
  roughly one event per second."** — true; check the EC2 access log
  during a demo run.
- **"The HIGH-risk inject button calls the same single-row `/predict`
  endpoint a SOC analyst would use."** — true; see
  `streaming_sim.score_one`.
- **"The scoring path is identical to what a production Kinesis
  consumer would call."** — true; that's the whole point of putting
  the model behind an HTTP boundary.

## 6. Honest claims you cannot make

Do not say any of these — they are not true:

- ~~"This is real-time streaming."~~ It is *simulated* real-time.
- ~~"We're consuming Kinesis."~~ We're not.
- ~~"This is production-grade."~~ The scoring layer is production-grade.
  The ingest layer is a demo simulator.

If you slip and say one of these, recover by saying:
> Sorry — to be precise, the *scoring engine* is production-grade. The
> ingest in this demo is a simulator. The two are decoupled by design.

---

## 7. Q&A prep — the three questions you will get

### Q1. "Could you actually run this against live data?"

> Yes. The scoring service is already containerized and stateless.
> Pointing a Kinesis Data Streams consumer at it requires writing
> roughly fifty lines of Python and provisioning a one-shard stream
> (about a dollar an hour). The model, the feature contract, and the
> API don't change. I'd estimate six to ten hours of work and zero
> additional ML risk.

### Q2. "Why didn't you build that?"

> Scope and risk. This is a capstone for a *Distributed Computing*
> course — the distributed parts are the medallion pipeline on EMR,
> the Spark transformation, the MLflow tracking, and the
> containerized serving layer. A Kinesis consumer would add cost and
> a fragile live-infrastructure dependency to the demo without adding
> new distributed-computing content. The honest tradeoff was to ship
> the scoring engine production-grade and simulate the ingest.

### Q3. "What's the latency budget?"

> Each `/batch_predict` call against the current LightGBM model
> returns in a single-digit millisecond range per row. A real
> streaming consumer would hit the same endpoint; per-event end-to-
> end latency would be dominated by the network round trip, not the
> model. For SOC use cases — alerting one window ahead — the model's
> latency is several orders of magnitude lower than the response
> window.

---

## 8. If the Live monitor breaks during the demo

In order of likelihood:

1. **API is cold-started on Streamlit Cloud.** First request takes
   5–10 seconds. Click Start, wait, and it'll catch up.
2. **Plotly chart didn't render.** Tab falls back to a dataframe of
   the last 20 events — the demo still works, just less pretty.
3. **`gold_computer_time_sample.csv` is missing.** Tab shows an
   error card explaining how to materialize it. Other four tabs
   still work; pivot to the Predict tab and run a preset by hand.
4. **Fragment auto-tick wedged.** Click Reset, then Start again.
   Worst case, reload the page — session state resets.

If everything else fails, the **Predict tab still works** and the
demo story is intact. The Live monitor is a wow-factor, not the
core deliverable. Don't burn presentation time fighting it on
stage.

---

## 9. One paragraph for the slide deck (if you want to add it)

> The dashboard ships with a **Live monitor** that replays the gold
> sample through the deployed FastAPI service at roughly one event per
> second. It is a streaming *simulator*, not a Kinesis consumer — the
> scoring engine is production-grade, the ingest in this demo is not.
> Swapping the simulator for Kinesis or Kafka is a wire-format change,
> not a model change. The button on the right (**Inject HIGH-risk
> row**) splices the canonical attack fingerprint into the stream on
> demand, demonstrating that the alert path fires when the threat
> profile appears unannounced.

Drop that into the deck verbatim if you want a tidy paragraph for a
"Wow #4 — live monitor" slide. Or leave it in this doc and reach for
it in Q&A.
