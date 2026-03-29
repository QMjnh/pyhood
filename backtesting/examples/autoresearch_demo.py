#!/usr/bin/env python3
"""AutoResearch demo — automated strategy discovery on SPY.

Fetches 10 years of SPY data, sweeps EMA crossover and MACD parameters,
validates the best findings, and prints a full report.

Requires: pip install yfinance
"""

from autoresearch import AutoResearcher
from backtest.strategies import ema_crossover, macd_crossover


def main():
    print('=' * 70)
    print('  AutoResearch Demo — SPY 10yr')
    print('=' * 70)
    print()

    # 1. Create researcher (fetches data once)
    print('[1/5] Fetching SPY 10-year data…')
    researcher = AutoResearcher(
        ticker='SPY',
        total_period='10y',
        min_trades=5,  # Relaxed for demo
        top_n=3,
    )
    print(f'  Train: {len(researcher.train_candles)} bars')
    print(f'  Test:  {len(researcher.test_candles)} bars')
    print(f'  Valid: {len(researcher.validate_candles)} bars')
    print()

    # 2. EMA crossover sweep
    print('[2/5] Sweeping EMA Crossover: fast=[5,7,9,11,13,15], slow=[15,20,25,30,40,50]')
    ema_results = researcher.multi_param_sweep(
        ema_crossover,
        {'fast': [5, 7, 9, 11, 13, 15], 'slow': [15, 20, 25, 30, 40, 50]},
        strategy_name='EMA Crossover',
    )
    kept_ema = [r for r in ema_results if r.kept]
    print(f'  Tested {len(ema_results)} combinations, kept {len(kept_ema)}')
    print()

    # 3. MACD sweep
    print('[3/5] Sweeping MACD: fast=[8,10,12,14], slow=[20,24,26,30], signal=[7,9,11]')
    macd_results = researcher.multi_param_sweep(
        macd_crossover,
        {'fast': [8, 10, 12, 14], 'slow': [20, 24, 26, 30], 'signal': [7, 9, 11]},
        strategy_name='MACD',
    )
    kept_macd = [r for r in macd_results if r.kept]
    print(f'  Tested {len(macd_results)} combinations, kept {len(kept_macd)}')
    print()

    # 4. Validate best findings
    print('[4/5] Validating top 3 strategies on held-out data…')
    validated = researcher.validate_best(n=3)
    for v in validated:
        val_sharpe = v.validate_result.sharpe_ratio if v.validate_result else 'N/A'
        print(f'  {v.strategy_name}: validate sharpe={val_sharpe}')
    print()

    # 5. Full report
    print('[5/5] Full report:')
    print()
    researcher.report()

    # Save results
    out_path = 'autoresearch_results.json'
    researcher.save(out_path)
    print(f'\nResults saved to {out_path}')


if __name__ == '__main__':
    main()
