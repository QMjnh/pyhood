"""
Pyhood Backtesting Dashboard v1
Streamlit + Plotly dark-themed backtesting UI.
"""
import sys
import os
import sqlite3
import json
from pathlib import Path

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Path setup ──────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "tv_scraper"))
sys.path.insert(0, str(ROOT))

from backtest.engine import BacktestConfig, run_backtest
from backtest.data import fetch_equity, fetch_alpaca
from backtest.strategies.ibs_spy import generate_signals as ibs_signals
from backtest.strategies.rsi_70_momentum import generate_signals as rsi70_signals
from backtest.strategies.donchian_breakout import generate_signals as donchian_signals

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Pyhood Backtest", page_icon="📈", layout="wide")

# ── Inline strategies ───────────────────────────────────────────────────────

def ema_crossover_signals(df: pd.DataFrame, params=None) -> pd.DataFrame:
    p = params or {}
    fast = p.get("fast", 9)
    slow = p.get("slow", 21)
    df = df.copy()
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    signal = np.where(ema_fast > ema_slow, 1, 0)
    df["signal"] = pd.Series(signal, index=df.index).shift(1).fillna(0).astype(int)
    return df


def macd_crossover_signals(df: pd.DataFrame, params=None) -> pd.DataFrame:
    p = params or {}
    fast = p.get("fast", 12)
    slow = p.get("slow", 26)
    signal_period = p.get("signal_period", 9)
    df = df.copy()
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    signal = np.where(macd_line > signal_line, 1, 0)
    df["signal"] = pd.Series(signal, index=df.index).shift(1).fillna(0).astype(int)
    return df


STRATEGIES = {
    "IBS": {"fn": ibs_signals, "params": {"low_ibs": 0.2, "high_ibs": 0.8, "max_bars": 30}},
    "RSI > 70 Momentum": {"fn": rsi70_signals, "params": {}},
    "Donchian Breakout": {"fn": donchian_signals, "params": {"length": 20}},
    "EMA Crossover": {"fn": ema_crossover_signals, "params": {"fast": 9, "slow": 21}},
    "MACD Crossover": {"fn": macd_crossover_signals, "params": {"fast": 12, "slow": 26, "signal_period": 9}},
}


# ── Helper: fetch data ─────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner="Fetching data...")
def load_data(ticker: str, source: str, interval: str, years: int) -> pd.DataFrame:
    interval_map_yf = {"1d": "1d", "1h": "1h", "15m": "15m", "5m": "5m"}
    interval_map_alp = {"1d": "1d", "1h": "1h", "15m": "15min", "5m": "5min"}
    if source == "yfinance":
        return fetch_equity(ticker, interval=interval_map_yf[interval], years=years)
    else:
        return fetch_alpaca(ticker, interval=interval_map_alp[interval], years=years)


# ── Helper: run a strategy ──────────────────────────────────────────────────

def run_strategy(df, strategy_name, params, capital, position_pct):
    strat = STRATEGIES[strategy_name]
    sig_df = strat["fn"](df.copy(), params)
    config = BacktestConfig(
        initial_capital=capital,
        position_size_pct=position_pct,
        slippage_pct=0.01,
        commission_per_trade=1.0,
    )
    return run_backtest(sig_df, config)


# ── Helper: build charts ───────────────────────────────────────────────────

def build_price_chart(df, result):
    """Candlestick + trade markers + equity + drawdown."""
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.5, 0.3, 0.2],
        vertical_spacing=0.03,
        subplot_titles=("Price + Trades", "Equity Curve", "Drawdown"),
    )
    # Candlesticks
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        name="Price", increasing_line_color="#00cc96", decreasing_line_color="#ef553b",
    ), row=1, col=1)

    # Trade markers
    if result.trades:
        buy_dates = [t.entry_date for t in result.trades]
        buy_prices = [t.entry_price for t in result.trades]
        sell_dates = [t.exit_date for t in result.trades]
        sell_prices = [t.exit_price for t in result.trades]
        colors = ["#00cc96" if t.pnl > 0 else "#ef553b" for t in result.trades]

        fig.add_trace(go.Scatter(
            x=buy_dates, y=buy_prices, mode="markers",
            marker=dict(symbol="triangle-up", size=10, color="#00cc96", opacity=0.7),
            name="Buy",
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=sell_dates, y=sell_prices, mode="markers",
            marker=dict(symbol="triangle-down", size=10, color=colors, opacity=0.7),
            name="Sell",
        ), row=1, col=1)

    # Equity curve
    fig.add_trace(go.Scatter(
        x=result.equity_curve.index, y=result.equity_curve.values,
        name="Equity", line=dict(color="#636efa", width=2),
    ), row=2, col=1)

    # Drawdown
    fig.add_trace(go.Scatter(
        x=result.drawdown_curve.index, y=result.drawdown_curve.values * 100,
        name="Drawdown %", fill="tozeroy",
        line=dict(color="#ef553b", width=1),
        fillcolor="rgba(239,85,59,0.3)",
    ), row=3, col=1)

    fig.update_layout(
        template="plotly_dark", height=900,
        xaxis_rangeslider_visible=False,
        showlegend=False,
        margin=dict(l=50, r=20, t=40, b=30),
    )
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="$", row=2, col=1)
    fig.update_yaxes(title_text="%", row=3, col=1)
    return fig


def metrics_row(result):
    cols = st.columns(7)
    pnl_color = "green" if result.net_profit >= 0 else "red"
    metrics = [
        ("Total P&L", f"${result.net_profit:,.2f}", pnl_color),
        ("CAGR", f"{result.cagr:.2f}%", None),
        ("Max DD", f"{result.max_drawdown:.2f}%", "red"),
        ("Sharpe", f"{result.sharpe:.2f}", None),
        ("Profit Factor", f"{result.profit_factor:.2f}", None),
        ("Win Rate", f"{result.win_rate:.1f}%", None),
        ("Trades", f"{result.total_trades}", None),
    ]
    for col, (label, val, color) in zip(cols, metrics):
        if color:
            col.markdown(f"**{label}**<br><span style='color:{color};font-size:1.3em'>{val}</span>", unsafe_allow_html=True)
        else:
            col.metric(label, val)


def trade_table(result):
    if not result.trades:
        st.info("No trades generated.")
        return
    rows = []
    for t in result.trades:
        bars = 0
        try:
            bars = (t.exit_date - t.entry_date).days
        except Exception:
            pass
        rows.append({
            "Entry": t.entry_date.strftime("%Y-%m-%d") if hasattr(t.entry_date, "strftime") else str(t.entry_date),
            "Exit": t.exit_date.strftime("%Y-%m-%d") if hasattr(t.exit_date, "strftime") else str(t.exit_date),
            "Dir": "Long" if t.direction == 1 else "Short",
            "Entry $": f"{t.entry_price:.2f}",
            "Exit $": f"{t.exit_price:.2f}",
            "P&L $": f"{t.pnl:.2f}",
            "P&L %": f"{t.pnl_pct:.2f}%",
            "Bars": bars,
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════════
# PAGE 1: Strategy Backtester
# ═══════════════════════════════════════════════════════════════════════════

def page_backtester():
    st.header("📈 Strategy Backtester")

    # ── Sidebar inputs ──
    with st.sidebar:
        st.subheader("Settings")
        ticker = st.text_input("Ticker", value="SPY")
        source = st.selectbox("Data Source", ["yfinance", "Alpaca"])
        timeframe = st.selectbox("Timeframe", ["1d", "1h", "15m", "5m"])
        years = st.slider("Years of Data", 1, 35, 5)
        strategy_name = st.selectbox("Strategy", list(STRATEGIES.keys()))
        capital = st.number_input("Initial Capital ($)", value=100000, step=10000)
        position_pct = st.slider("Position Size (%)", 1, 100, 100)

        # Dynamic params
        st.subheader("Strategy Parameters")
        default_params = STRATEGIES[strategy_name]["params"].copy()
        params = {}
        if strategy_name == "IBS":
            params["low_ibs"] = st.slider("Low IBS Threshold", 0.05, 0.5, default_params["low_ibs"], 0.05)
            params["high_ibs"] = st.slider("High IBS Threshold", 0.5, 0.95, default_params["high_ibs"], 0.05)
            params["max_bars"] = st.slider("Max Bars Held", 5, 60, default_params["max_bars"])
        elif strategy_name == "RSI > 70 Momentum":
            pass  # no tunable params in current impl
        elif strategy_name == "Donchian Breakout":
            params["length"] = st.slider("Channel Length", 5, 50, default_params["length"])
        elif strategy_name == "EMA Crossover":
            params["fast"] = st.slider("Fast EMA", 3, 50, default_params["fast"])
            params["slow"] = st.slider("Slow EMA", 10, 200, default_params["slow"])
        elif strategy_name == "MACD Crossover":
            params["fast"] = st.slider("MACD Fast", 5, 30, default_params["fast"])
            params["slow"] = st.slider("MACD Slow", 15, 50, default_params["slow"])
            params["signal_period"] = st.slider("Signal Period", 3, 20, default_params["signal_period"])

        run_btn = st.button("🚀 Run Backtest", type="primary", use_container_width=True)

    # ── Main area ──
    if run_btn:
        try:
            df = load_data(ticker, source, timeframe, years)
            result = run_strategy(df, strategy_name, params, capital, position_pct)
            st.session_state["last_result"] = result
            st.session_state["last_df"] = df
        except Exception as e:
            st.error(f"Error: {e}")
            return

    if "last_result" in st.session_state:
        result = st.session_state["last_result"]
        df = st.session_state["last_df"]
        metrics_row(result)
        st.plotly_chart(build_price_chart(df, result), use_container_width=True)
        with st.expander("📋 Trade Log", expanded=False):
            trade_table(result)
    else:
        st.info("Configure settings in the sidebar and click **Run Backtest**.")


# ═══════════════════════════════════════════════════════════════════════════
# PAGE 2: Strategy Comparison
# ═══════════════════════════════════════════════════════════════════════════

def page_comparison():
    st.header("⚔️ Strategy Comparison")

    with st.sidebar:
        st.subheader("Comparison Settings")
        ticker = st.text_input("Ticker", value="SPY", key="cmp_ticker")
        source = st.selectbox("Data Source", ["yfinance", "Alpaca"], key="cmp_source")
        timeframe = st.selectbox("Timeframe", ["1d", "1h", "15m", "5m"], key="cmp_tf")
        years = st.slider("Years", 1, 35, 5, key="cmp_years")
        capital = st.number_input("Capital ($)", value=100000, step=10000, key="cmp_cap")
        selected = st.multiselect("Strategies (2-4)", list(STRATEGIES.keys()),
                                  default=["IBS", "EMA Crossover"])
        run_cmp = st.button("🚀 Compare", type="primary", use_container_width=True)

    if run_cmp:
        if len(selected) < 2:
            st.warning("Select at least 2 strategies.")
            return
        try:
            df = load_data(ticker, source, timeframe, years)
        except Exception as e:
            st.error(f"Data error: {e}")
            return

        results = {}
        for name in selected:
            try:
                results[name] = run_strategy(df, name, STRATEGIES[name]["params"], capital, 100)
            except Exception as e:
                st.warning(f"{name} failed: {e}")

        if not results:
            return

        # Overlay equity curves
        fig = go.Figure()
        colors = ["#636efa", "#00cc96", "#ef553b", "#ffa15a"]
        for i, (name, res) in enumerate(results.items()):
            fig.add_trace(go.Scatter(
                x=res.equity_curve.index, y=res.equity_curve.values,
                name=name, line=dict(color=colors[i % len(colors)], width=2),
            ))
        fig.update_layout(template="plotly_dark", height=500, title="Equity Curves",
                          yaxis_title="$", margin=dict(l=50, r=20, t=50, b=30))
        st.plotly_chart(fig, use_container_width=True)

        # Metrics table
        rows = []
        for name, res in results.items():
            rows.append({
                "Strategy": name,
                "Net P&L": f"${res.net_profit:,.2f}",
                "CAGR %": f"{res.cagr:.2f}",
                "Max DD %": f"{res.max_drawdown:.2f}",
                "Sharpe": f"{res.sharpe:.2f}",
                "PF": f"{res.profit_factor:.2f}",
                "Win Rate %": f"{res.win_rate:.1f}",
                "Trades": res.total_trades,
            })
        mt = pd.DataFrame(rows)
        st.dataframe(mt, use_container_width=True, hide_index=True)

        # Highlight best
        best_sharpe = max(results, key=lambda k: results[k].sharpe)
        best_pf = max(results, key=lambda k: results[k].profit_factor)
        best_cagr = max(results, key=lambda k: results[k].cagr)
        st.success(f"🏆 Best Sharpe: **{best_sharpe}** | Best PF: **{best_pf}** | Best CAGR: **{best_cagr}**")


# ═══════════════════════════════════════════════════════════════════════════
# PAGE 3: Autoresearch Results
# ═══════════════════════════════════════════════════════════════════════════

def page_autoresearch():
    st.header("🔬 Autoresearch Results")

    db_path = ROOT / "autoresearch_results" / "autoresearch_memory.db"
    if not db_path.exists():
        st.error(f"DB not found: {db_path}")
        return

    conn = sqlite3.connect(str(db_path))
    df = pd.read_sql_query("SELECT * FROM experiments ORDER BY id", conn)
    conn.close()

    if df.empty:
        st.info("No experiments found.")
        return

    # Sidebar filters
    with st.sidebar:
        st.subheader("Filters")
        tickers = ["All"] + sorted(df["ticker"].unique().tolist())
        sel_ticker = st.selectbox("Ticker", tickers, key="ar_ticker")
        show_only_kept = st.checkbox("Show only kept", value=False)

    filtered = df.copy()
    if sel_ticker != "All":
        filtered = filtered[filtered["ticker"] == sel_ticker]
    if show_only_kept:
        filtered = filtered[filtered["kept"] == 1]

    # Summary
    total = len(filtered)
    kept = filtered["kept"].sum()
    failed = total - kept
    st.markdown(f"**{total}** experiments | ✅ **{kept}** kept | ❌ **{failed}** failed")

    # Table
    display_cols = ["id", "ticker", "strategy_name", "kept", "train_sharpe", "test_sharpe",
                    "overfit_gap", "train_return", "test_return", "train_max_drawdown",
                    "test_max_drawdown", "train_win_rate", "test_win_rate", "reason"]
    avail_cols = [c for c in display_cols if c in filtered.columns]
    display = filtered[avail_cols].copy()

    # Color kept/failed
    def highlight_kept(row):
        if row.get("kept", 0) == 0:
            return ["background-color: rgba(239,85,59,0.2)"] * len(row)
        return [""] * len(row)

    styled = display.style.apply(highlight_kept, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # Detail expander
    st.subheader("Strategy Detail")
    sel_id = st.selectbox("Select experiment ID", filtered["id"].tolist())
    row = filtered[filtered["id"] == sel_id].iloc[0]

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Train Metrics**")
        st.write(f"- Sharpe: {row.get('train_sharpe', 'N/A')}")
        st.write(f"- Return: {row.get('train_return', 'N/A')}")
        st.write(f"- Max DD: {row.get('train_max_drawdown', 'N/A')}")
        st.write(f"- Win Rate: {row.get('train_win_rate', 'N/A')}")
        st.write(f"- PF: {row.get('train_profit_factor', 'N/A')}")
        st.write(f"- Trades: {row.get('train_trades', 'N/A')}")
    with col2:
        st.markdown("**Test Metrics**")
        st.write(f"- Sharpe: {row.get('test_sharpe', 'N/A')}")
        st.write(f"- Return: {row.get('test_return', 'N/A')}")
        st.write(f"- Max DD: {row.get('test_max_drawdown', 'N/A')}")
        st.write(f"- Win Rate: {row.get('test_win_rate', 'N/A')}")
        st.write(f"- PF: {row.get('test_profit_factor', 'N/A')}")
        st.write(f"- Trades: {row.get('test_trades', 'N/A')}")

    # Overfit indicator
    train_s = row.get("train_sharpe")
    test_s = row.get("test_sharpe")
    if train_s and test_s and not pd.isna(train_s) and not pd.isna(test_s) and train_s != 0:
        gap = (train_s - test_s) / abs(train_s) * 100
        color = "red" if gap > 50 else "orange" if gap > 25 else "green"
        st.markdown(f"**Overfit Gap:** <span style='color:{color};font-size:1.2em'>{gap:.1f}%</span> (train {train_s:.2f} → test {test_s:.2f})", unsafe_allow_html=True)

    # Params
    try:
        params = json.loads(row.get("params_json", "{}"))
        st.json(params)
    except Exception:
        pass

    # Regime breakdown
    try:
        regime = json.loads(row.get("regime_breakdown_json", "{}"))
        if regime:
            st.subheader("Regime Breakdown")
            regime_df = pd.DataFrame(regime).T
            st.dataframe(regime_df, use_container_width=True)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
# Navigation
# ═══════════════════════════════════════════════════════════════════════════

PAGES = {
    "📈 Strategy Backtester": page_backtester,
    "⚔️ Strategy Comparison": page_comparison,
    "🔬 Autoresearch Results": page_autoresearch,
}

with st.sidebar:
    st.title("Pyhood")
    page = st.radio("Navigation", list(PAGES.keys()), label_visibility="collapsed")

PAGES[page]()
