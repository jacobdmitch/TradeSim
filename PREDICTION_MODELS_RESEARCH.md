# Prediction Models Research — Fit for TradeSim

Date: 2026-05-30. Question: would LSTM, an LSTM+XGBoost hybrid, or a Transformer
(e.g. HELFormer) be a better prediction engine than the current transparent
momentum + SMA + RSI heuristic?

Short answer: not right now, for this setup. The academic results are real but
are mostly about price-level fitting on liquid majors (BTC/ETH), are sensitive
to methodology, and largely evaporate after realistic trading costs. For a ~$23
single-position bot rotating thin Coinbase alt pairs on a 10-minute cron, the
added complexity, compute, and overfitting risk are not justified by the
marginal directional edge these models actually deliver.

The detail below is meant to be even-handed: these architectures genuinely help
in well-resourced settings. The argument is about *fit to our constraints*, not
about whether the models are good in general.

---

## The three candidates

### 1. LSTM (recurrent net for time series)
- **What it is:** a recurrent neural network that retains long-range structure
  in sequences; the long-standing default for financial time-series.
- **Reported performance:** strong on RMSE/MAPE for *price level*. But the metric
  that matters for trading is *directional accuracy*, and there it's modest —
  surveyed results land around 52–58% (barely above a coin flip on crypto).
- **Cost to run:** needs a training pipeline, careful windowing, and periodic
  retraining; GPU preferred for training (CPU inference of a small pre-trained
  net is fine). Prone to overfitting and look-ahead leakage if not validated
  with strict walk-forward testing.

### 2. LSTM + XGBoost hybrid
- **What it is:** LSTM handles the temporal price sequence; XGBoost (gradient-
  boosted trees) folds in tabular/auxiliary features — sentiment, on-chain
  metrics, macro indicators. Papers report the hybrid beats either alone on
  RMSE/MAPE (e.g. ~31% RMSE improvement over plain LSTM on BTC/ETH).
- **Cost to run:** highest data burden of the three — you must source, clean, and
  time-align sentiment/on-chain/macro feeds without leakage. Two models to train
  and maintain.
- **Note:** the *XGBoost half* is the pragmatic, CPU-friendly part. The LSTM half
  is the heavy, fragile part. That distinction matters for our recommendation.

### 3. Transformer / HELFormer
- **What it is:** attention-based architecture; HELFormer pairs Holt–Winters
  decomposition with a Transformer to predict next-day BTC close.
- **Reported performance:** headline numbers are eye-popping — R² ≈ 1.0, MAPE
  ≈ 0.0148%, and a backtest of ~925% return (≈3× buy-and-hold) with a Sharpe
  near 18.
- **Reality check:** an R² of ~1.0 and a Sharpe of ~18 predicting next-day *price
  level* are textbook signs of (a) predicting the level rather than the return —
  tomorrow's price ≈ today's price, so high R² is trivial and not tradable — and/
  or (b) backtest optimism (look-ahead, no costs, favorable window). Treat these
  as upper bounds from idealized conditions, not expected live results.

---

## Why none is a better fit *here*

1. **The edge that matters is small.** Across the literature, crypto *directional*
   accuracy clusters around 50–58%. Impressive RMSE/MAPE/R² figures describe how
   closely a model traces the price line, not whether it calls the next move. A
   ~54% directional model is genuinely useful only if costs are low and turnover
   is controlled.

2. **Costs erase the edge — exactly our problem.** Studies that apply realistic
   per-trade costs (~0.5%) show profitability becomes fragile; one LSTM with high
   reported accuracy still *lost* money (~-$2.50 on $100 over two weeks) once costs
   were included. Our round trip is ~1.2% before spread. A model would need a
   large, consistent directional edge to clear that on every rotation — larger
   than these models reliably show.

3. **Results are methodology-sensitive.** A peer-reviewed comparison of deep models
   for BTC direction had to run a dedicated study on how random seed and window
   size swing accuracy — i.e. the same model gives materially different results
   depending on arbitrary choices. That is the opposite of what you want governing
   real money on a tiny account.

4. **Trained on the wrong universe.** These papers use BTC/ETH with long, liquid,
   clean histories. TradeSim trades thin alts (DIMO ≈ $9k/day volume) where data is
   noisier, shorter, and wider-spread — the regime where deep nets overfit most and
   transfer least.

5. **Compute/ops mismatch.** Our engine is a stateless 10-minute Render cron with
   CPU and an ephemeral filesystem. Deep nets want training infrastructure, a
   feature store (for the hybrid), retraining cadence, and model versioning. Heavy
   relative to the payoff at $23.

---

## Comparison at a glance

| Model | Edge that matters (direction) | Data/compute burden | Overfit / look-ahead risk | Fit for TradeSim now |
|---|---|---|---|---|
| Current heuristic (momentum+SMA+RSI) | transparent, modest | trivial (CPU, no training) | low (no fitting) | baseline |
| LSTM | ~52–58% reported | training pipeline, GPU pref. | high | low |
| LSTM + XGBoost hybrid | best RMSE, direction still modest | highest (needs sentiment/on-chain) | high | low |
| Transformer / HELFormer | headline numbers look level-fit | high | very high (R²≈1 is a red flag) | low |

---

## Recommendation (ranked by expected ROI on our setup)

1. **Cut turnover and fee drag first.** The biggest determinant of net return on a
   $23 account is how often it trades, not predictor sophistication. Raising the
   rotation threshold so it switches only on a clearly larger edge will likely beat
   any model swap. Evaluate this against the overnight dry-run data before building
   anything.

2. **Improve the existing transparent model cheaply.** Add a volatility/volume
   confirmation filter, require trend agreement on two horizons, or widen the hold
   band. These are interpretable, CPU-trivial, and low-risk.

3. **If we pursue ML, start with gradient-boosted trees (XGBoost/LightGBM), not a
   deep net.** Frame it as a classifier predicting P(up over the next N hours) from
   engineered features (the indicators we already compute, plus volume/volatility).
   It trains in seconds on CPU, fits the cron model, is far less prone to overfit
   than LSTM/Transformer, and is easy to validate. This is the practical half of the
   "LSTM+XGBoost hybrid" without the fragile half.

4. **Treat LSTM/Transformer as a later, optional experiment** — and only with strict
   walk-forward validation, predicting *returns/direction* (not price level), with
   our real fee model baked into the backtest. Otherwise the backtest will look like
   the 925%/R²≈1.0 papers and mislead us.

Bottom line: the lever for this bot is cost and turnover discipline, plus maybe a
light tree-based classifier — not a deep sequence model. Reassess if the account
grows materially or moves to liquid majors, where these models earn their keep.

---

## Sources
- LSTM + XGBoost (cited paper): https://arxiv.org/html/2506.22055v1
- HELFormer (Journal of Big Data): https://journalofbigdata.springeropen.com/articles/10.1186/s40537-025-01135-4
- Deep learning for Bitcoin price *direction* + trading profitability (Financial Innovation): https://jfin-swufe.springeropen.com/articles/10.1186/s40854-024-00643-1
- Deep learning crypto prediction comparative analysis (ACM DLT): https://dl.acm.org/doi/10.1145/3699966
- Technical indicators + DL price forecasting (Physica A): https://www.sciencedirect.com/science/article/abs/pii/S0378437125000111
