# Professor Q&A — ML Final Project

Hard questions and honest answers. Read before presenting.

---

## On k-fold

**Q: Why didn't you use k-fold cross-validation?**

> "Two reasons. First, this is time-ordered security telemetry. Standard k-fold shuffles rows randomly, which can place future behavioral patterns into training — a form of temporal leakage. Second, I implemented a strict chronological split and tested it: because the red-team campaign is concentrated in the final weeks of the 58-day window, a chronological 60/20/20 split places nearly all 596 attack labels in training and leaves validation and test with near-zero positives — every metric becomes undefined. My resolution was a stratified random split that ensures proportional positive rates across all three sets, combined with a `lead()` target construction that prevents within-row temporal leakage. Hyperparameters were selected on the validation set — one round of manual tuning, conceptually the inner loop of nested k-fold without the resampling step."

---

## On the PR AUC number

**Q: Your PR AUC is 0.039 — that seems really low.**

> "The correct comparison for PR AUC under class imbalance is not 'how close to 1.0 is it' but 'how much better is it than a random classifier.' A random classifier on this dataset scores PR AUC equal to the positive rate: 596 / 13,900,000 = 0.0000429. Our model scores 0.039 — that is 909 times better than random, and 35 times better than the logistic regression baseline. The absolute number is small because 99.996% of the data is negative. The lift is what matters operationally."

---

## On why not accuracy

**Q: What's the model's accuracy?**

> "99.9957%, and it's meaningless. A model that predicts 'never an attack' on every row achieves that exact accuracy while catching zero actual attacks. I use PR AUC as the primary metric because it is directly sensitive to false positives under imbalance, and ROC AUC as a secondary ranking metric."

---

## On using supervised vs unsupervised

**Q: Most LANL work uses anomaly detection — why supervised?**

> "Because we have 596 ground-truth labels and we chose to use them. Unsupervised anomaly detection doesn't require labels but produces scores with no interpretable threshold and no precision-recall trade-off you can tune. By treating this as supervised binary classification, we get a model we can explain feature-by-feature using TreeSHAP, a threshold we can tune to a business cost matrix, and a counterfactual recommender that tells an analyst exactly what would need to change to lower the risk. The trade-off is that 596 positives is thin — we handle it with `class_weight='balanced'` and PR AUC as the primary metric."

---

## On the dataset not being Kaggle

**Q: Where did the data come from?**

> "Los Alamos National Laboratory released it as a research dataset — Turcotte et al., 2018. It is real enterprise telemetry from a US government research facility: 58 days of authentication, network flow, DNS, and process events, plus ground-truth red-team labels from a sanctioned penetration test. It is publicly available at csr.lanl.gov/data/cyber1/. It is not from Kaggle and it has not been pre-cleaned or pre-split."

---

## On the train/test split size

**Q: You have 119 positives in the test set — isn't that too few?**

> "It is thin, yes. It's also unavoidable: 596 total positives across 13.9 million rows, stratified 60/20/20, gives 119 per set. The PR AUC metric is robust to small positive counts because it integrates over the full precision-recall curve rather than evaluating at a single threshold. ROC AUC is similarly threshold-independent. Both are appropriate for this regime."

---

## On the benchmark model

**Q: Why logistic regression as the benchmark?**

> "The rubric specifies: 'logistic regression if predicting categorical/binary outcomes.' This is a binary classification problem. Logistic regression is the correct minimum-complexity baseline. It establishes the floor: if a complex model can't beat logistic regression on the right metric, the complexity isn't worth it. LightGBM beats LR by 35× on test PR AUC — the complexity is clearly worth it."

---

## On the GenAI extra credit

**Q: Did you do the GenAI comparison?**

> "No. I did not run Karpathy's autoresearch repository, OpenClaw, Google Data Science, or Perplexity Labs against this dataset. I am not claiming the 10% extra credit."

---

## On ROC AUC vs PR AUC disagreement

**Q: Random Forest has lower test ROC AUC (0.748) but your best model is also picked by ROC AUC — do the two metrics always agree?**

> "No, and this dataset illustrates the divergence. LR has the second-highest test ROC AUC (0.820) but the lowest test PR AUC among models that actually discriminate (0.00111 vs LightGBM's 0.039). ROC AUC is forgiving under imbalance because the true-negative rate dominates the denominator — a model can rank most things correctly yet still have terrible precision at any threshold. PR AUC stays honest because precision is directly sensitive to false positives. I use PR AUC as the decision criterion and ROC AUC as corroborating evidence."

---

## On the distributed infrastructure

**Q: How much of this is ML and how much is distributed computing?**

> "The ML project is the research question, the four-model comparison, the imbalanced metrics, the feature engineering, and the explainability layer. The distributed infrastructure — S3, EMR Spark, EC2, MLflow — is the deployment vehicle. For this course, the relevant ML content is: supervised binary classification, benchmark vs candidate models, PR AUC on imbalanced data, stratified split, validation-based tuning, and TreeSHAP interpretation. The infrastructure is context, not the point."
