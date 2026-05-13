# Demo Script — ML Final Project Live Dashboard Walk-Through
# Runs after Slide 9 (Results) or after Slide 12 (end). Budget: 2–3 minutes.

---

## Pre-Demo Setup (before you present)
1. Open https://lanlthreat.streamlit.app in a browser tab
2. Verify sidebar shows `[ ONLINE ]` with mint-green border
3. Have the Predict tab open, preset dropdown visible
4. Do NOT start the Live monitor — do that live

---

## Step 1 — Show the prediction interface (~30 sec)

Click the sidebar preset: **"Demo HIGH risk - real row (P=0.745)"**

Say: *"This is a real row from the dataset. 4 authentication events, 1 destination, 12 outbound network flows. Looks quiet. Let's ask the model."*

Click **"Predict next-window risk."**

Point to the red gauge: *"74.5% probability of an attack in the next hour. The needle is in the red zone."*

---

## Step 2 — Show the explainer (~30 sec)

Point to the SHAP bar chart on the right:

*"Why? The red bars are the features pushing risk up. The model is weighting the outbound flow pattern and the low authentication diversity — focused, targeted, low-noise. That's the reconnaissance fingerprint. Not 400 failed logins. 4 quiet ones."*

---

## Step 3 — Show medium risk contrast (~20 sec)

Switch preset to **"Demo MEDIUM risk - real row (P=0.275)"**. Click Predict.

*"Same question, different computer. 15 auth events, 6 different destinations, 2 user accounts. 27.5% — elevated but not certain. Could be an admin. Could be lateral movement starting. The model is appropriately uncertain."*

---

## Step 4 — Show low risk (~15 sec)

Switch to **"Demo LOW risk - real row (P=0.072)"**. Click Predict.

*"7 successful logins, 10 processes across 6 different process types. 7.2%. The model says: diverse, routine activity is the benign admin pattern."*

---

## Step 5 — Show the threshold slider in Model Metrics tab (~20 sec)

Click **Model metrics** tab. Drag threshold slider from 0.5 to 0.1.

*"At threshold 0.5, the model catches almost nothing — most rows never score that high. At 0.1, you see the true positives come in. The threshold is a business decision — the cost-matrix calculator turns it into an optimization."*

---

## Step 6 — Live monitor (optional grand finale, ~45 sec)

Click **Live monitor** tab. Click **Start stream.**

*"This is the scoring engine under sustained load. Every dot is a real HTTP call to the model on EC2. The stream is a simulator — a gold CSV replaying at 1.25 events per second. Watch the chart build."*

After 10 seconds, click **Inject HIGH-risk row.**

*"I just sent the attack fingerprint to the live API. There's the red dot — the alert fires immediately. In production you'd swap the CSV replayer for a Kinesis consumer. The model and API don't change."*

---

## What NOT to say during the demo
- Do NOT say "the streaming is real" — it is a simulator. The dashboard says so. You say so too.
- Do NOT apologize for the low PR AUC number — you have the 909× lift answer ready.
- Do NOT fumble on k-fold — you have the temporal/stratified explanation ready.
