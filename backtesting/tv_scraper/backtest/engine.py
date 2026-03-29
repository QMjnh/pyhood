#!/Users/nyra/Projects/pyhood/.venv/bin/python
"""
Core backtesting engine — pandas-based, realistic costs.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd


@dataclass
class Trade:
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    direction: int  # 1 = long, -1 = short
    entry_price: float
    exit_price: float
    size: float  # dollar notional
    pnl: float
    pnl_pct: float
    commission: float
    slippage_cost: float


@dataclass
class BacktestResult:
    net_profit: float = 0.0
    cagr: float = 0.0
    max_drawdown: float = 0.0
    profit_factor: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    sharpe: float = 0.0
    sortino: float = 0.0
    avg_trade_pnl: float = 0.0
    max_win: float = 0.0
    max_loss: float = 0.0
    equity_curve: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    drawdown_curve: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    trades: List[Trade] = field(default_factory=list)


@dataclass
class BacktestConfig:
    initial_capital: float = 100_000.0
    position_size_pct: float = 1.0  # % of equity per trade
    fixed_qty: float = 0.0  # if > 0, use fixed quantity instead of pct
    point_value: float = 1.0  # contract multiplier (e.g. 10000 for NG mini)
    slippage_pct: float = 0.01  # 0.01% per trade
    commission_per_trade: float = 1.0  # flat $ per trade
    commission_pct: float = 0.0  # % of trade value (e.g. 0.1 = 0.1%)
    use_trailing_stop: bool = False
    trailing_atr_mult: float = 2.0
    enter_at_open: bool = True  # Pine default: enter at next bar open
    process_orders_on_close: bool = False  # Pine: execute at bar close instead


def _calc_commission(trade_value: float, config: BacktestConfig) -> float:
    """Calculate total commission for a trade (flat + percentage)."""
    return config.commission_per_trade + abs(trade_value) * config.commission_pct / 100


def _calc_pnl(direction: int, entry_price: float, exit_price: float,
              entry_size: float, config: BacktestConfig) -> float:
    """Calculate raw PnL (before commission) for a trade."""
    if config.fixed_qty > 0:
        # Fixed quantity: PnL = qty * point_value * price_diff
        price_diff = (exit_price - entry_price) if direction == 1 else (entry_price - exit_price)
        return config.fixed_qty * config.point_value * price_diff
    else:
        # Percentage of equity: PnL = notional * return
        if direction == 1:
            return (exit_price - entry_price) * (entry_size / entry_price)
        else:
            return (entry_price - exit_price) * (entry_size / entry_price)


def run_backtest(
    df: pd.DataFrame,
    config: Optional[BacktestConfig] = None,
) -> BacktestResult:
    """
    Run a vectorised-then-iterative backtest.

    Required columns in *df*:
        open, high, low, close, signal (1 / -1 / 0)
    Optional:
        atr — needed when use_trailing_stop is True
    """
    if config is None:
        config = BacktestConfig()

    df = df.copy()
    df = df.dropna(subset=["close"])

    if "signal" not in df.columns:
        raise ValueError("DataFrame must contain a 'signal' column")

    equity = config.initial_capital
    position = 0  # 1 long, -1 short, 0 flat
    entry_price = 0.0
    entry_date = None
    entry_size = 0.0  # dollar size
    trail_stop = None
    trail_stopped_dir = 0  # prevent re-entry in same direction after trail stop

    equities = []
    trades: List[Trade] = []

    for i, (idx, row) in enumerate(df.iterrows()):
        signal = int(row["signal"]) if not np.isnan(row["signal"]) else 0
        price = row["close"]
        open_price = row.get("open", price)
        atr_val = row.get("atr", np.nan)

        # ---- Check trailing stop while in position ----
        if config.use_trailing_stop and position != 0 and not np.isnan(atr_val):
            trail_dist = config.trailing_atr_mult * atr_val
            if position == 1:
                new_trail = row["high"] - trail_dist
                if trail_stop is None:
                    trail_stop = new_trail
                else:
                    trail_stop = max(trail_stop, new_trail)
                if row["low"] <= trail_stop:
                    exit_price = trail_stop
                    signal = 0  # force flat
                    slip = exit_price * config.slippage_pct / 100
                    exit_price -= slip
                    comm = _calc_commission(entry_size, config)
                    pnl_raw = _calc_pnl(position, entry_price, exit_price, entry_size, config)
                    pnl = pnl_raw - comm
                    trades.append(Trade(
                        entry_date=entry_date, exit_date=idx,
                        direction=position,
                        entry_price=entry_price, exit_price=exit_price,
                        size=entry_size, pnl=pnl,
                        pnl_pct=pnl / entry_size * 100 if entry_size else 0,
                        commission=comm, slippage_cost=slip * (entry_size / entry_price) if entry_size else 0,
                    ))
                    equity += pnl
                    trail_stopped_dir = 1  # was long
                    position = 0
                    trail_stop = None
                    entry_price = 0.0
                    equities.append(equity)
                    continue
            elif position == -1:
                new_trail = row["low"] + trail_dist
                if trail_stop is None:
                    trail_stop = new_trail
                else:
                    trail_stop = min(trail_stop, new_trail)
                if row["high"] >= trail_stop:
                    exit_price = trail_stop
                    signal = 0
                    slip = exit_price * config.slippage_pct / 100
                    exit_price += slip
                    comm = _calc_commission(entry_size, config)
                    pnl_raw = _calc_pnl(position, entry_price, exit_price, entry_size, config)
                    pnl = pnl_raw - comm
                    trades.append(Trade(
                        entry_date=entry_date, exit_date=idx,
                        direction=position,
                        entry_price=entry_price, exit_price=exit_price,
                        size=entry_size, pnl=pnl,
                        pnl_pct=pnl / entry_size * 100 if entry_size else 0,
                        commission=comm, slippage_cost=slip * (entry_size / entry_price) if entry_size else 0,
                    ))
                    equity += pnl
                    trail_stopped_dir = -1  # was short
                    position = 0
                    trail_stop = None
                    entry_price = 0.0
                    equities.append(equity)
                    continue

        # Reset trail_stopped_dir when signal changes direction or goes flat
        if trail_stopped_dir != 0 and signal != trail_stopped_dir:
            trail_stopped_dir = 0

        # ---- Position management based on signal ----
        if signal != position:
            # Close existing position
            if position != 0:
                # Use strategy-provided exit price if available, otherwise close
                exit_price = row.get("exit_price", np.nan)
                if np.isnan(exit_price):
                    exit_price = price
                slip = exit_price * config.slippage_pct / 100
                if position == 1:
                    exit_price -= slip
                else:
                    exit_price += slip
                comm = _calc_commission(entry_size, config)
                pnl_raw = _calc_pnl(position, entry_price, exit_price, entry_size, config)
                pnl = pnl_raw - comm
                trades.append(Trade(
                    entry_date=entry_date, exit_date=idx,
                    direction=position,
                    entry_price=entry_price, exit_price=exit_price,
                    size=entry_size, pnl=pnl,
                    pnl_pct=pnl / entry_size * 100 if entry_size else 0,
                    commission=comm, slippage_cost=slip * (entry_size / entry_price) if entry_size else 0,
                ))
                equity += pnl
                position = 0
                trail_stop = None

            # Open new position
            if signal != 0:
                position = signal
                if config.process_orders_on_close:
                    # Pine process_orders_on_close: enter at current bar close
                    entry_price = price
                elif config.enter_at_open:
                    # Pine default: enter at next bar's open (signal bar's open)
                    entry_price = open_price
                else:
                    entry_price = price
                slip = entry_price * config.slippage_pct / 100
                if position == 1:
                    entry_price += slip
                else:
                    entry_price -= slip
                entry_date = idx
                entry_size = equity * config.position_size_pct / 100
                trail_stop = None

        equities.append(equity)

    # Close any open position at end
    if position != 0 and len(df) > 0:
        last = df.iloc[-1]
        exit_price = last["close"]
        slip = exit_price * config.slippage_pct / 100
        if position == 1:
            exit_price -= slip
        else:
            exit_price += slip
        comm = _calc_commission(entry_size, config)
        pnl_raw = _calc_pnl(position, entry_price, exit_price, entry_size, config)
        pnl = pnl_raw - comm
        trades.append(Trade(
            entry_date=entry_date, exit_date=df.index[-1],
            direction=position,
            entry_price=entry_price, exit_price=exit_price,
            size=entry_size, pnl=pnl,
            pnl_pct=pnl / entry_size * 100 if entry_size else 0,
            commission=comm, slippage_cost=slip * (entry_size / entry_price) if entry_size else 0,
        ))
        equity += pnl

    # Build equity curve
    eq_series = pd.Series(equities, index=df.index[: len(equities)])
    if len(eq_series) == 0:
        return BacktestResult()

    # Drawdown
    peak = eq_series.cummax()
    dd = (eq_series - peak) / peak
    max_dd = abs(dd.min()) if len(dd) > 0 else 0.0

    # Metrics
    total_trades = len(trades)
    if total_trades == 0:
        return BacktestResult(
            equity_curve=eq_series,
            drawdown_curve=dd,
        )

    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]
    gross_profit = sum(t.pnl for t in wins) if wins else 0.0
    gross_loss = abs(sum(t.pnl for t in losses)) if losses else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    win_rate = len(wins) / total_trades * 100

    net_profit = equity - config.initial_capital

    # CAGR
    days = (eq_series.index[-1] - eq_series.index[0]).days
    years = days / 365.25 if days > 0 else 1.0
    cagr = ((equity / config.initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0.0

    # Sharpe & Sortino (annualised)
    bar_returns = eq_series.pct_change().dropna()
    if len(bar_returns) > 1:
        # Estimate bars per year from data
        total_bars = len(eq_series)
        bars_per_year = total_bars / years if years > 0 else 252
        ann_factor = math.sqrt(bars_per_year)
        mean_r = bar_returns.mean()
        std_r = bar_returns.std()
        sharpe = (mean_r / std_r) * ann_factor if std_r > 0 else 0.0
        downside = bar_returns[bar_returns < 0].std()
        sortino = (mean_r / downside) * ann_factor if downside > 0 else 0.0
    else:
        sharpe = 0.0
        sortino = 0.0

    pnls = [t.pnl for t in trades]
    return BacktestResult(
        net_profit=net_profit,
        cagr=cagr,
        max_drawdown=max_dd * 100,
        profit_factor=profit_factor,
        win_rate=win_rate,
        total_trades=total_trades,
        sharpe=sharpe,
        sortino=sortino,
        avg_trade_pnl=np.mean(pnls),
        max_win=max(pnls) if pnls else 0.0,
        max_loss=min(pnls) if pnls else 0.0,
        equity_curve=eq_series,
        drawdown_curve=dd,
        trades=trades,
    )


def print_results(result: BacktestResult, strategy_name: str = "") -> None:
    """Pretty-print backtest results."""
    header = f"=== {strategy_name} ===" if strategy_name else "=== Backtest Results ==="
    print(f"\n{header}")
    print(f"  Net Profit:    ${result.net_profit:>12,.2f}")
    print(f"  CAGR:          {result.cagr:>10.2f}%")
    print(f"  Max Drawdown:  {result.max_drawdown:>10.2f}%")
    print(f"  Profit Factor: {result.profit_factor:>10.2f}")
    print(f"  Win Rate:      {result.win_rate:>10.1f}%")
    print(f"  Total Trades:  {result.total_trades:>10d}")
    print(f"  Sharpe Ratio:  {result.sharpe:>10.2f}")
    print(f"  Sortino Ratio: {result.sortino:>10.2f}")
    print(f"  Avg Trade PnL: ${result.avg_trade_pnl:>12,.2f}")
    print(f"  Max Win:       ${result.max_win:>12,.2f}")
    print(f"  Max Loss:      ${result.max_loss:>12,.2f}")
