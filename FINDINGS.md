# Findings: BTC 24h race bot (btc-race-24h-20261113-2314)

Competition: "Race a BTC trading bot live for 24 hours" — trade cbBTC/USDC
1-minute bars, $1,000 paper, long only, 4 bps fee + 2 bps slippage + pool
price impact per fill (~26 bps per full-size round trip). Dev gate: net PnL
> $0 on the frozen 24h dev window. Race window: the unseen 24h after the
deadline. Prize $250 to the 10 highest net PnLs on the race window.

Primary sources: the kit itself (`RULES.txt` read end to end, `kit.json`,
`dataset/bars/CBBTC.ndjson.gz` + `dataset/samples/CBBTC.ndjson.gz`,
`sdk/makefun_bars.py`, the six shipped baselines, and the harness source
`harness/harness-src.tar.gz` — the fill math in `sim/bars/engine.ts` was
replicated exactly in a local backtester (`~/workspace/makefun/btc-work/
backtest.py`), which reproduces the kit grader's buy-and-hold result to the
micro-USDC (-$52.586916, 1 trade).

## The dev window is a falling, low-volatility grind

- 1,440 bars, 0 gaps. Close $71,408.76 -> $67,900.67: **-4.91%**.
- 1-minute close returns: mean -0.0035%, std 0.0786%. |return| > 0.2% on
  only 2.8% of minutes; > 0.5% on 0.1%.
- Return autocorrelation at lags 1-60 minutes: -0.03 to +0.04 — essentially
  zero. No exploitable trend or mean reversion at the 1-minute scale.
- Every shipped baseline loses: buy-and-hold -$52.59 (1 trade),
  momentum -$49.23 (1), ema-cross -$109.38 (58 trades, $21.88 fees),
  rsi-bollinger -$65.83 (11), adx-momentum -$50.31 (20), hold-cash $0.00
  (0 trades — fails the dev gate and the >=1-trade guardrail).

## What was tested and rejected

- Dip-buying vs trailing highs (N=30/60/120, dips 0.4-1.2%): best -$10.13.
  Dips keep dipping in a downtrend; forward returns after drops are
  negative on average at 15-120 min horizons.
- Z-score mean reversion (N=30/60/120, z<-1.5/-2/-2.5): best -$6.44.
- Momentum-up entries (5/15/30-min returns 0.15-0.3%): best -$8.62.
- Bollinger/RSI-style and trailing-stop exits: all negative; trailing exits
  were consistently worse than fixed take-profits.
- Breakout leg (new 240-bar high): fires 3 times on dev, all false — it
  turned the final bot from +$2.43 into -$2.99. Rejected.
- Tight take-profits (0.15-0.30%) and sell-on-first-up-bar: all negative —
  the round-trip cost (~15-20 bps at small size) eats the immediate bounce.

## The one signal that survives: the sharp-drop bounce

A 1-minute close drop of 0.25%+ is a ~3-sigma event (12 in 1,440 bars).
After those 12 drops the next minute's return was positive 11 of 12 times
(mean +0.15%), and 9 of 12 reached +0.30% above the fill within 30 minutes.
Mechanism: a single large sell pushes the pool price below where it settles;
the fill at the next bar's open already gives back ~+0.09% on average, and
the bounce continues for tens of minutes. It is the only condition in the
scan whose forward returns beat the ~26 bps round-trip cost.

Final rule (integer bps on integer closes, no floats, no clock):
- drop >= 45 bps in one minute: buy 50% of cash, TP +60 bps.
- drop in [25, 45) bps: buy 20% of cash, TP +40 bps.
- Exit whole position: TP, or -30 bps stop, or 60 bars elapsed.
- max_slippage_bps 100 on every order.

## Walk-forward / block validation (local backtester, exact fill math)

Full dev window: **net PnL +$2.43, 8 round trips (16 trades), max
drawdown 0.31%, fees $1.52**. In cash ~97% of the window.
- First half (720 bars): +$1.33. Second half: +$1.10. Positive both halves.
- Per 4h block (standalone $1,000 each): +0.1, +0.6, 0.0, +0.5, +0.8, 0.0.
- Neighbouring parameters stay positive: big size 40% -> +$2.25,
  60% -> +$2.55; small size 15% -> +$2.35, 25% -> +$2.42; stop 40 bps ->
  +$2.17. (By contrast the small-TP parameter is load-bearing: TP 45 bps
  for the small tier gives -$1.77 — see Limits.)
- Leave-one-block-out: no single 4h block contributes more than ~$0.90 of
  the +$2.43, and removing the single best trade (bar 402, the -0.66% drop
  that recovered +1.44%) leaves the bot at about +$0.90 — still positive,
  but thin.

Note on data limits: `dataset/samples/` covers only the dev window itself
(41,058 samples, first timestamp = window start), so no earlier 24h windows
exist in the kit to validate on. The "walk-forward" above is therefore
within-window: halves and 4h blocks, not out-of-sample days. This is
recorded honestly because it is the binding limit on how much the result
can be trusted.

## Limits — read before trusting this bot

1. Eight trades is a tiny sample. The edge is real in the microstructure
   (the 11/12 positive next-minute returns) but the dollar outcome on any
   single day is dominated by 1-3 trades. On the race window the honest
   expectation is roughly $0 to +$3, with a real chance of a small loss if
   a bought dip keeps falling through the -30 bps stop.
2. If the race window has no 1-minute drop >= 25 bps, the bot trades 0
   times and fails the >=1-trade guardrail. On the dev window such drops
   occurred 13 times (one every ~2 hours); a quiet race day could starve it.
3. If the race window rallies strongly, trend-following entries would beat
   this bot by a wide margin; this bot will sit mostly in cash and score
   near zero. That is a deliberate choice: near-zero with tiny drawdown
   beats a large loss when most entries lose (as all baselines did on dev),
   and the prizes pay the 10 highest net PnLs whatever their sign.
4. Parameter sensitivity: TP and max-hold are load-bearing (see above).
   The chosen values are the centre of the positive pocket, not its edge.
