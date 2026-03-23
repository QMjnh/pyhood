"""Re-validate all 20 kept autoresearch strategies with auto_adjust=False."""

import sys
sys.path.insert(0, '.')

from pyhood.backtest.engine import Backtester
from pyhood.backtest.strategies import ema_crossover, macd_crossover

# All 20 strategies with their old test Sharpe ratios
STRATEGIES = [
    # AAPL
    {"ticker": "AAPL", "type": "EMA", "params": (8, 9), "old_sharpe": 1.2115},
    {"ticker": "AAPL", "type": "EMA", "params": (8, 10), "old_sharpe": 1.1584},
    {"ticker": "AAPL", "type": "EMA", "params": (6, 13), "old_sharpe": 1.1290},
    {"ticker": "AAPL", "type": "EMA", "params": (7, 15), "old_sharpe": 0.8777},
    {"ticker": "AAPL", "type": "EMA", "params": (5, 30), "old_sharpe": 0.5565},
    # BTC-USD
    {"ticker": "BTC-USD", "type": "MACD", "params": (16, 24, 13), "old_sharpe": 0.1182},
    {"ticker": "BTC-USD", "type": "MACD", "params": (10, 30, 13), "old_sharpe": 0.0734},
    {"ticker": "BTC-USD", "type": "MACD", "params": (8, 30, 13), "old_sharpe": 0.0617},
    {"ticker": "BTC-USD", "type": "MACD", "params": (8, 30, 11), "old_sharpe": 0.0229},
    {"ticker": "BTC-USD", "type": "EMA", "params": (5, 40), "old_sharpe": 0.0086},
    # QQQ
    {"ticker": "QQQ", "type": "EMA", "params": (3, 29), "old_sharpe": 0.5914},
    {"ticker": "QQQ", "type": "EMA", "params": (3, 21), "old_sharpe": 0.5634},
    {"ticker": "QQQ", "type": "EMA", "params": (5, 25), "old_sharpe": 0.3419},
    {"ticker": "QQQ", "type": "EMA", "params": (5, 20), "old_sharpe": 0.3087},
    {"ticker": "QQQ", "type": "MACD", "params": (8, 35, 7), "old_sharpe": 0.3592},
    # SPY
    {"ticker": "SPY", "type": "MACD", "params": (8, 30, 11), "old_sharpe": 0.6015},
    {"ticker": "SPY", "type": "MACD", "params": (8, 26, 13), "old_sharpe": 0.3690},
    {"ticker": "SPY", "type": "EMA", "params": (5, 15), "old_sharpe": 0.3414},
    # TSLA
    {"ticker": "TSLA", "type": "EMA", "params": (7, 20), "old_sharpe": 1.3707},
    {"ticker": "TSLA", "type": "EMA", "params": (5, 50), "old_sharpe": 0.4629},
]

# Cache fetched data per ticker
ticker_data = {}

def get_candles(ticker):
    if ticker not in ticker_data:
        print(f"  Fetching {ticker} data (auto_adjust=False)...")
        bt = Backtester.from_yfinance(ticker, period="10y")
        ticker_data[ticker] = bt.candles
        print(f"  Got {len(bt.candles)} candles for {ticker}")
    return ticker_data[ticker]

def split_data(candles, train_pct=0.50, test_pct=0.25):
    """Same split as autoresearch runner: 50/25/25"""
    n = len(candles)
    train_end = int(n * train_pct)
    test_end = train_end + int(n * test_pct)
    return candles[:train_end], candles[train_end:test_end], candles[test_end:]

def make_strategy(s):
    if s["type"] == "EMA":
        return ema_crossover(fast=s["params"][0], slow=s["params"][1])
    elif s["type"] == "MACD":
        return macd_crossover(fast=s["params"][0], slow=s["params"][1], signal=s["params"][2])

def format_name(s):
    if s["type"] == "EMA":
        return f"EMA Crossover ({s['params'][0]}/{s['params'][1]})"
    elif s["type"] == "MACD":
        return f"MACD ({s['params'][0]}/{s['params'][1]}/{s['params'][2]})"

print("=" * 100)
print("REVALIDATION: 20 Kept Strategies with auto_adjust=False (unadjusted prices)")
print("=" * 100)
print()

results = []

for s in STRATEGIES:
    candles = get_candles(s["ticker"])
    train, test, validate = split_data(candles)
    
    strategy_fn = make_strategy(s)
    name = format_name(s)
    
    # Run on test split
    bt_test = Backtester(test, initial_capital=10000.0)
    test_result = bt_test.run(strategy_fn, name)
    
    # Run on validate split too
    bt_val = Backtester(validate, initial_capital=10000.0)
    val_result = bt_val.run(strategy_fn, name)
    
    new_sharpe = test_result.sharpe_ratio
    new_return = test_result.total_return
    val_sharpe = val_result.sharpe_ratio
    
    still_valid = new_sharpe > 0.3 and new_return > 0
    delta = new_sharpe - s["old_sharpe"]
    
    results.append({
        "ticker": s["ticker"],
        "name": name,
        "old_sharpe": s["old_sharpe"],
        "new_sharpe": new_sharpe,
        "delta": delta,
        "new_return": new_return,
        "val_sharpe": val_sharpe,
        "trades": test_result.total_trades,
        "valid": still_valid,
    })
    
    status = "✅ VALID" if still_valid else "❌ INVALID"
    print(f"  {s['ticker']:8s} {name:30s} old={s['old_sharpe']:.4f}  new={new_sharpe:.4f}  Δ={delta:+.4f}  ret={new_return:.1f}%  trades={test_result.total_trades}  {status}")

print()
print("=" * 100)
print(f"{'Ticker':<10} {'Strategy':<30} {'Old Sharpe':>11} {'New Sharpe':>11} {'Delta':>8} {'Return%':>8} {'Val Sharpe':>11} {'Trades':>7} {'Status':>10}")
print("-" * 100)

valid_count = 0
for r in results:
    status = "✅ VALID" if r["valid"] else "❌ FAIL"
    if r["valid"]:
        valid_count += 1
    print(f"{r['ticker']:<10} {r['name']:<30} {r['old_sharpe']:>11.4f} {r['new_sharpe']:>11.4f} {r['delta']:>+8.4f} {r['new_return']:>7.1f}% {r['val_sharpe']:>11.4f} {r['trades']:>7} {status:>10}")

print("-" * 100)
print(f"\nSUMMARY: {valid_count}/{len(results)} strategies still valid (test Sharpe > 0.3 AND return > 0%)")
print()

# Flag flips
flips = [r for r in results if r["old_sharpe"] > 0 and r["new_sharpe"] <= 0]
if flips:
    print("⚠️  STRATEGIES THAT FLIPPED POSITIVE → NEGATIVE:")
    for r in flips:
        print(f"  {r['ticker']} {r['name']}: {r['old_sharpe']:.4f} → {r['new_sharpe']:.4f}")
else:
    print("✅ No strategies flipped from positive to negative Sharpe")

# Big movers
print("\n📊 BIGGEST CHANGES (|delta| > 0.1):")
big = sorted(results, key=lambda r: abs(r["delta"]), reverse=True)
for r in big:
    if abs(r["delta"]) > 0.1:
        print(f"  {r['ticker']} {r['name']}: {r['old_sharpe']:.4f} → {r['new_sharpe']:.4f} (Δ={r['delta']:+.4f})")
