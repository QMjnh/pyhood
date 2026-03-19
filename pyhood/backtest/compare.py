"""Utilities for comparing multiple backtest results."""

from __future__ import annotations

import math
from dataclasses import replace

from pyhood.backtest.models import BacktestResult


def benchmark_spy(results: list[BacktestResult]) -> list[BacktestResult]:
    """Enrich backtest results with S&P 500 (SPY) benchmark comparison.

    Fetches SPY data for each unique period, calculates SPY buy & hold return
    and Sharpe ratio, then computes alpha and verdict for each result.

    Args:
        results: List of BacktestResult objects to benchmark

    Returns:
        New list of BacktestResult instances with spy_return, spy_sharpe,
        spy_alpha, and verdict fields populated.
        Returns original results unchanged if yfinance is not installed.
    """
    if not results:
        return results

    try:
        import yfinance as yf
    except ImportError:
        return results

    # Cache SPY data per unique period string
    spy_cache: dict[str, tuple[float, float]] = {}  # period -> (spy_return, spy_sharpe)

    enriched = []
    for result in results:
        period = result.period
        if period not in spy_cache:
            spy_ret, spy_sh = _fetch_spy_metrics(yf, period)
            spy_cache[period] = (spy_ret, spy_sh)

        spy_ret, spy_sh = spy_cache[period]
        alpha = result.total_return - spy_ret

        if result.sharpe_ratio > spy_sh and result.total_return > spy_ret:
            verdict = '\u2705 Beats both'
        elif result.sharpe_ratio > spy_sh:
            verdict = '\u26a0\ufe0f Better risk-adjusted'
        else:
            verdict = '\u274c Underperforms'

        enriched.append(replace(
            result,
            spy_return=spy_ret,
            spy_sharpe=spy_sh,
            spy_alpha=alpha,
            verdict=verdict,
        ))

    return enriched


def _fetch_spy_metrics(yf, period: str) -> tuple[float, float]:
    """Fetch SPY return and Sharpe ratio for a date range.

    Args:
        yf: The yfinance module
        period: Period string like "2021-01-01 to 2026-03-16"

    Returns:
        Tuple of (spy_return_pct, spy_sharpe_ratio)
    """
    parts = period.split(" to ")
    if len(parts) == 2:
        start, end = parts[0].strip(), parts[1].strip()
    else:
        return 0.0, 0.0

    ticker = yf.Ticker("SPY")
    df = ticker.history(start=start, end=end)

    if df.empty or len(df) < 2:
        return 0.0, 0.0

    closes = df["Close"].values
    spy_return = ((closes[-1] - closes[0]) / closes[0]) * 100

    # Daily returns for Sharpe ratio (same formula as engine)
    daily_returns = []
    for i in range(1, len(closes)):
        if closes[i - 1] != 0:
            daily_returns.append((closes[i] - closes[i - 1]) / closes[i - 1])

    if daily_returns:
        mean_dr = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean_dr) ** 2 for r in daily_returns) / len(daily_returns)
        daily_std = math.sqrt(variance) if variance > 0 else 0
        spy_sharpe = (mean_dr / daily_std) * math.sqrt(252) if daily_std > 0 else 0.0
    else:
        spy_sharpe = 0.0

    return spy_return, spy_sharpe


def compare_backtests(results: list[BacktestResult]) -> str:
    """Format comparison table of multiple backtest results.

    Args:
        results: List of BacktestResult objects to compare

    Returns:
        Formatted string table comparing the strategies
    """
    if not results:
        return "No backtest results to compare."

    # Column headers
    headers = [
        "Strategy", "Symbol", "Period", "Total Return (%)", "Annual Return (%)",
        "Sharpe Ratio", "Max DD (%)", "Win Rate (%)", "Profit Factor",
        "Total Trades", "Alpha (%)"
    ]

    show_spy = results[0].spy_return is not None
    if show_spy:
        headers.extend(["SPY Return (%)", "SPY Alpha (%)", "Verdict"])

    # Build rows
    rows = []
    for result in results:
        row = [
            result.strategy_name,
            result.symbol,
            result.period,
            f"{result.total_return:.2f}",
            f"{result.annual_return:.2f}",
            f"{result.sharpe_ratio:.2f}",
            f"{result.max_drawdown:.2f}",
            f"{result.win_rate:.2f}",
            f"{result.profit_factor:.2f}" if result.profit_factor != float('inf') else "∞",
            str(result.total_trades),
            f"{result.alpha:.2f}"
        ]
        if show_spy:
            row.extend([
                f"{result.spy_return:.2f}" if result.spy_return is not None else "N/A",
                f"{result.spy_alpha:.2f}" if result.spy_alpha is not None else "N/A",
                result.verdict,
            ])
        rows.append(row)

    # Calculate column widths
    col_widths = []
    for i in range(len(headers)):
        max_width = len(headers[i])
        for row in rows:
            max_width = max(max_width, len(row[i]))
        col_widths.append(max_width + 2)  # Add padding

    # Format table
    lines = []

    # Header
    header_line = "|".join(header.ljust(col_widths[i]) for i, header in enumerate(headers))
    lines.append(header_line)

    # Separator
    separator = "|".join("-" * col_widths[i] for i in range(len(headers)))
    lines.append(separator)

    # Data rows
    for row in rows:
        row_line = "|".join(row[i].ljust(col_widths[i]) for i in range(len(row)))
        lines.append(row_line)

    return "\n".join(lines)


def rank_backtests(results: list[BacktestResult], by: str = "sharpe_ratio") -> list[BacktestResult]:
    """Sort results by a metric.

    Args:
        results: List of BacktestResult objects
        by: Metric to sort by. Options:
            - "total_return"
            - "annual_return"
            - "sharpe_ratio" (default)
            - "max_drawdown" (sorts by least negative)
            - "win_rate"
            - "profit_factor"
            - "alpha"

    Returns:
        Sorted list of BacktestResult objects (best first)
    """
    if not results:
        return results

    # Define sorting key and reverse flag for each metric
    sort_configs = {
        "total_return": (lambda r: r.total_return, True),
        "annual_return": (lambda r: r.annual_return, True),
        "sharpe_ratio": (lambda r: r.sharpe_ratio, True),
        "max_drawdown": (lambda r: r.max_drawdown, True),  # Less negative is better
        "win_rate": (lambda r: r.win_rate, True),
        "profit_factor": (
            lambda r: r.profit_factor if r.profit_factor != float('inf') else 999999,
            True
        ),
        "alpha": (lambda r: r.alpha, True),
        "spy_alpha": (lambda r: r.spy_alpha if r.spy_alpha is not None else float('-inf'), True)
    }

    if by not in sort_configs:
        raise ValueError(f"Unknown ranking metric: {by}. Available: {list(sort_configs.keys())}")

    key_fn, reverse = sort_configs[by]
    return sorted(results, key=key_fn, reverse=reverse)
