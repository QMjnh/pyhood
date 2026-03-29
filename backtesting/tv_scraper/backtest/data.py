#!/Users/nyra/Projects/pyhood/.venv/bin/python
"""
Data fetcher — yfinance for equities/futures, ccxt for crypto, Alpaca for intraday.
Caches to local parquet files.
"""
from __future__ import annotations

import hashlib
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)


def _cache_key(name: str) -> Path:
    h = hashlib.md5(name.encode()).hexdigest()[:12]
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    return CACHE_DIR / f"{safe}_{h}.parquet"


def _load_cache(key: Path) -> Optional[pd.DataFrame]:
    if key.exists():
        try:
            return pd.read_parquet(key)
        except Exception:
            pass
    return None


def _save_cache(key: Path, df: pd.DataFrame) -> None:
    try:
        df.to_parquet(key)
    except Exception:
        pass


def fetch_equity(
    ticker: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    interval: str = "1d",
    years: int = 5,
) -> pd.DataFrame:
    """Fetch equity/ETF data via yfinance. Returns OHLCV DataFrame."""
    import yfinance as yf

    if end is None:
        end = datetime.now().strftime("%Y-%m-%d")
    if start is None:
        start = (datetime.now() - timedelta(days=years * 365)).strftime("%Y-%m-%d")

    cache_name = f"eq_{ticker}_{interval}_{start}_{end}"
    key = _cache_key(cache_name)
    cached = _load_cache(key)
    if cached is not None:
        return cached

    # For intraday intervals, yfinance requires period-based fetch
    if interval in ("1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"):
        # yfinance limits: 1h→730d, 15m→60d, 5m→60d, 1m→7d
        max_days = {"1h": 730, "60m": 730, "30m": 60, "15m": 60, "5m": 60, "2m": 60, "1m": 7}
        max_d = max_days.get(interval, 60)
        req_days = min(years * 365, max_d)
        period = f"{req_days}d"
        data = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=False)
    else:
        data = yf.download(ticker, start=start, end=end, interval=interval, progress=False, auto_adjust=False)
    if data.empty:
        raise ValueError(f"No data returned for {ticker}")

    # Flatten multi-level columns if present
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = [col[0] for col in data.columns]

    df = data[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = ["open", "high", "low", "close", "volume"]
    df = df.dropna()

    _save_cache(key, df)
    return df


def fetch_futures(
    ticker: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    interval: str = "1d",
    years: int = 5,
) -> pd.DataFrame:
    """Fetch futures data via yfinance (e.g. NQ=F, ES=F, NG=F)."""
    return fetch_equity(ticker, start, end, interval, years)


def fetch_crypto(
    symbol: str,
    exchange: str = "binance",
    start: Optional[str] = None,
    end: Optional[str] = None,
    timeframe: str = "1d",
    years: int = 5,
) -> pd.DataFrame:
    """Fetch crypto OHLCV via ccxt."""
    import ccxt

    if end is None:
        end_dt = datetime.now()
    else:
        end_dt = datetime.strptime(end, "%Y-%m-%d")
    if start is None:
        start_dt = end_dt - timedelta(days=years * 365)
    else:
        start_dt = datetime.strptime(start, "%Y-%m-%d")

    cache_name = f"crypto_{exchange}_{symbol}_{timeframe}_{start_dt:%Y%m%d}_{end_dt:%Y%m%d}"
    key = _cache_key(cache_name)
    cached = _load_cache(key)
    if cached is not None:
        return cached

    ex_class = getattr(ccxt, exchange)
    ex = ex_class({"enableRateLimit": True})

    since = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    all_ohlcv = []

    while since < end_ms:
        ohlcv = ex.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
        if not ohlcv:
            break
        all_ohlcv.extend(ohlcv)
        since = ohlcv[-1][0] + 1
        if len(ohlcv) < 1000:
            break

    if not all_ohlcv:
        raise ValueError(f"No crypto data for {symbol} on {exchange}")

    df = pd.DataFrame(all_ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.set_index("timestamp")
    df = df[df.index <= end_dt]

    _save_cache(key, df)
    return df


# ---------------------------------------------------------------------------
# Alpaca data fetcher — intraday & daily, stocks + crypto
# ---------------------------------------------------------------------------

_ALPACA_TF_MAP = {
    "1min": ("Minute", 1),
    "5min": ("Minute", 5),
    "15min": ("Minute", 15),
    "30min": ("Minute", 30),
    "1h": ("Hour", 1),
    "4h": ("Hour", 4),
    "1d": ("Day", 1),
}

_CRYPTO_TICKERS = {"BTC/USD", "ETH/USD", "BTC/USDT", "ETH/USDT", "BTCUSD", "ETHUSD"}


def _is_crypto(ticker: str) -> bool:
    normalized = ticker.upper().replace("-", "/")
    return normalized in _CRYPTO_TICKERS or "/" in ticker


def _normalize_crypto_ticker(ticker: str) -> str:
    t = ticker.upper().replace("-", "/")
    if "/" not in t:
        for base in ("BTC", "ETH"):
            if t.startswith(base):
                return f"{base}/{t[len(base):]}"
    return t


def fetch_alpaca(
    ticker: str,
    interval: str = "15min",
    years: int = 5,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> pd.DataFrame:
    """Fetch OHLCV data from Alpaca (stocks or crypto)."""
    from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest, CryptoBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

    if end is None:
        end_dt = datetime.now(timezone.utc)
    else:
        end_dt = datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if start is None:
        start_dt = end_dt - timedelta(days=int(years * 365.25))
    else:
        start_dt = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    is_crypto = _is_crypto(ticker)
    crypto_ticker = _normalize_crypto_ticker(ticker) if is_crypto else ticker

    cache_name = f"alpaca_{'crypto' if is_crypto else 'stock'}_{ticker}_{interval}_{start_dt:%Y%m%d}_{end_dt:%Y%m%d}"
    key = _cache_key(cache_name)
    cached = _load_cache(key)
    if cached is not None:
        print(f"  [cache hit] {cache_name}")
        return cached

    if interval not in _ALPACA_TF_MAP:
        raise ValueError(f"Unsupported interval: {interval}. Use: {list(_ALPACA_TF_MAP.keys())}")
    unit_name, amount = _ALPACA_TF_MAP[interval]
    unit = getattr(TimeFrameUnit, unit_name)
    tf = TimeFrame(amount, unit)

    print(f"  [alpaca] Fetching {ticker} {interval} from {start_dt:%Y-%m-%d} to {end_dt:%Y-%m-%d}...")

    if is_crypto:
        client = CryptoHistoricalDataClient()
        request = CryptoBarsRequest(
            symbol_or_symbols=crypto_ticker, timeframe=tf, start=start_dt, end=end_dt,
        )
        bars = client.get_crypto_bars(request)
    else:
        from alpaca.data.enums import DataFeed
        api_key = os.environ.get("ALPACA_API_KEY", "PKIUIIAGOU2INQV6GROSRWY2MZ")
        api_secret = os.environ.get("ALPACA_API_SECRET", "AH3JXoFQxVE8hSJnwzcNnDzm6YAwMZwWEForfrUr8eka")
        client = StockHistoricalDataClient(api_key, api_secret)
        request = StockBarsRequest(
            symbol_or_symbols=ticker, timeframe=tf, start=start_dt, end=end_dt,
            feed=DataFeed.IEX,  # Free tier uses IEX feed
        )
        bars = client.get_stock_bars(request)

    df = bars.df
    if df.empty:
        raise ValueError(f"No Alpaca data for {ticker} {interval}")

    if isinstance(df.index, pd.MultiIndex):
        df = df.droplevel("symbol")

    df = df[["open", "high", "low", "close", "volume"]].copy()
    df = df.dropna()

    if df.index.tz is not None:
        df.index = df.index.tz_convert("UTC")
    else:
        df.index = df.index.tz_localize("UTC")

    df = df[~df.index.duplicated(keep="first")]
    df = df.sort_index()
    print(f"  [alpaca] Got {len(df)} bars")

    _save_cache(key, df)
    return df


def fetch_alpaca_resampled(
    ticker: str,
    base_interval: str,
    target_interval: str,
    years: int = 5,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> pd.DataFrame:
    """Fetch at base_interval and resample to target_interval (e.g. 1h → 4h)."""
    df = fetch_alpaca(ticker, interval=base_interval, years=years, start=start, end=end)
    resampled = df.resample(target_interval).agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum",
    }).dropna()
    return resampled
