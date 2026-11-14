"""Bounce-scalper for make.fun competition btc-race-24h-20261113-2314.

Strategy (long-only, one asset CBBTC, $1,000 paper):
  A sharp one-minute drop in cbBTC is usually a single large sell pushing the
  pool price below where it settles: on the dev window, 11 of the 12 drops of
  0.25% or more were followed by a positive one-minute return, and 9 of 12
  reached +0.30% within 30 minutes. This bot buys exactly those dislocations
  and exits on a fixed take-profit, a tight stop, or a 60-bar timeout --
  nothing else. It never chases rallies and never holds through the drift:
  on the dev window BTC fell 4.91% and every shipped baseline lost money,
  while this bot stayed in cash ~97% of the window.

  Entry (decided on a bar's close, filled at the next bar's open):
    - 1-minute close drop >= 45 bps: buy 50% of cash, take-profit +60 bps.
    - 1-minute close drop in [25, 45) bps: buy 20% of cash, take-profit +40 bps.
    - Otherwise: no trade.
  Exit (whole position, decided on a bar's close):
    - close >= entry close * (1 + take-profit), or
    - close <= entry close * (1 - 30 bps), or
    - 60 bars have passed since the entry bar.
  Sizing is small on purpose: a full-size round trip pays ~26 bps in fees,
  slippage and pool impact, so a 20-50% size keeps the round-trip cost near
  15-20 bps while the take-profit is 40-60 bps.

  Determinism: integer arithmetic on the bars' integer closes only. No
  randomness, no wall clock, no environment, no files, no network. Two runs
  on the same bars produce the same orders.

  Validated with the kit's own grader (grade-local, process driver):
  dev-window net PnL +$2.43, 8 round trips (16 trades), max drawdown 0.31%,
  fees $1.52. Baselines on the same window: buy-and-hold -$52.59,
  momentum -$49.23, ema-cross -$109.38, rsi-bollinger -$65.83,
  adx-momentum -$50.31, hold-cash $0.00 (0 trades, fails the gate).
  See FINDINGS.md for the full walk-forward / block analysis and the
  honest limits of this edge (8 trades: it is a small, noisy edge).
"""

import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
)
import makefun_bars

SYMBOL = "CBBTC"

# Entry thresholds, in basis points of the previous bar's close.
SMALL_DROP_BPS = 25
BIG_DROP_BPS = 45
# Position size as a share of cash at the decision.
SMALL_SIZE_NUM, SMALL_SIZE_DEN = 1, 5  # 20%
BIG_SIZE_NUM, BIG_SIZE_DEN = 1, 2  # 50%
# Exits, in basis points of the entry bar's close.
SMALL_TP_BPS = 40
BIG_TP_BPS = 60
STOP_BPS = 30
MAX_HOLD_BARS = 60
# Cap on how far a fill may move from the close the order was decided on.
MAX_SLIPPAGE_BPS = 100

# Module state, reset only by a fresh process (one run = one process).
_prev_close = None
_entry_close = None
_entry_seq = -1
_entry_tp_bps = 0


def on_batch(state, batch):
    """Decide this batch's orders (at most one) from the CBBTC bar it carries."""
    global _prev_close, _entry_close, _entry_seq, _entry_tp_bps

    bar = None
    for b in batch.get("bars", []):
        if b.get("symbol") == SYMBOL:
            bar = b
            break
    if bar is None:
        return []
    close = int(bar["c"])

    orders = []
    held = state.positions.get(SYMBOL)
    if held is not None and _entry_close is not None:
        # Exit: take-profit, stop-loss, or the 60-bar timeout.
        if (
            close * 10000 >= _entry_close * (10000 + _entry_tp_bps)
            or close * 10000 <= _entry_close * (10000 - STOP_BPS)
            or state.seq - _entry_seq >= MAX_HOLD_BARS
        ):
            orders.append(
                {
                    "side": "sell",
                    "symbol": SYMBOL,
                    "qty": held.qty,
                    "max_slippage_bps": MAX_SLIPPAGE_BPS,
                }
            )
            _entry_close = None
    elif held is None and not state.warming_up and _prev_close is not None:
        # Entry: a sharp one-minute drop. Size and take-profit scale with it.
        drop_bps = (_prev_close - close) * 10000 // _prev_close
        if drop_bps >= BIG_DROP_BPS:
            size_num, size_den, tp_bps = BIG_SIZE_NUM, BIG_SIZE_DEN, BIG_TP_BPS
        elif drop_bps >= SMALL_DROP_BPS:
            size_num, size_den, tp_bps = (
                SMALL_SIZE_NUM,
                SMALL_SIZE_DEN,
                SMALL_TP_BPS,
            )
        else:
            size_num = size_den = tp_bps = 0
        if tp_bps:
            notional = state.cash * size_num // size_den
            min_notional = int(state.hello["fees"]["min_notional_quote_units"])
            if notional >= min_notional and notional > 0:
                orders.append(
                    {
                        "side": "buy",
                        "symbol": SYMBOL,
                        "notional_quote_units": notional,
                        "max_slippage_bps": MAX_SLIPPAGE_BPS,
                    }
                )
                _entry_close = close
                _entry_seq = state.seq
                _entry_tp_bps = tp_bps

    _prev_close = close
    return orders


makefun_bars.run(on_batch)
