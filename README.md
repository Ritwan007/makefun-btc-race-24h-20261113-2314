# make.fun BTC 24h race bot

A bounce-scalper for the make.fun competition
`btc-race-24h-20261113-2314` ("Race a BTC trading bot live for 24 hours").

It trades cbBTC/USDC 1-minute bars with $1,000 of paper money, long only.
It buys only sharp one-minute drops (a large sell pushing the pool price
below where it settles) and exits on a fixed take-profit, a tight stop, or
a 60-bar timeout. Full design, measurements and honest limits: `FINDINGS.md`.

## Run

Python 3.13, standard library only. The kit's Python SDK shim is vendored
byte-identical under `vendor/`:

```
python3 main.py   # speaks agent-fun/bars-replay/v1 on stdin/stdout
```

## Local grade (from the unpacked kit directory)

```
node cli/makefun.mjs grade-local --kit . --bot /path/to/this/repo --driver process
```

Dev-window result: **net PnL +$2.43, 16 trades, max drawdown 0.31%**
(baselines on the same window: buy-and-hold -$52.59, ema-cross -$109.38,
best baseline $0.00 with 0 trades).

## License

MIT — see `LICENSE`.
