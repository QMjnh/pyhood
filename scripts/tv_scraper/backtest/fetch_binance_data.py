#!/Users/nyra/Projects/pyhood/.venv/bin/python
"""Download BTC/USDT 4h klines from Binance public data."""
import io
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

CACHE_FILE = Path(__file__).parent / "cache" / "btcusdt_4h_binance_full.csv"


def download_btcusdt_4h() -> pd.DataFrame:
    if CACHE_FILE.exists():
        print(f"Loading cached data from {CACHE_FILE}")
        df = pd.read_csv(CACHE_FILE, parse_dates=["timestamp"], index_col="timestamp")
        return df
    
    base_url = "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/4h"
    all_dfs = []
    
    # BTC/USDT started Aug 2017
    for year in range(2017, 2026):
        for month in range(1, 13):
            if year == 2017 and month < 8:
                continue
            if year == 2026 and month > 2:
                break
            
            url = f"{base_url}/BTCUSDT-4h-{year}-{month:02d}.zip"
            try:
                r = requests.get(url, timeout=15)
                if r.status_code != 200:
                    print(f"  {year}-{month:02d}: HTTP {r.status_code}, skipping")
                    continue
                
                z = zipfile.ZipFile(io.BytesIO(r.content))
                csv_name = z.namelist()[0]
                df = pd.read_csv(z.open(csv_name), header=None)
                # Columns: open_time, open, high, low, close, volume, close_time, ...
                df = df[[0, 1, 2, 3, 4, 5]].copy()
                df.columns = ["timestamp", "open", "high", "low", "close", "volume"]
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                df = df.set_index("timestamp")
                for col in ["open", "high", "low", "close", "volume"]:
                    df[col] = df[col].astype(float)
                all_dfs.append(df)
                print(f"  {year}-{month:02d}: {len(df)} bars")
            except Exception as e:
                print(f"  {year}-{month:02d}: error - {e}")
    
    full = pd.concat(all_dfs)
    full = full[~full.index.duplicated(keep="first")]
    full = full.sort_index()
    
    # Filter out future dates
    full = full[full.index <= pd.Timestamp.now()]
    
    CACHE_FILE.parent.mkdir(exist_ok=True)
    full.to_csv(CACHE_FILE)
    print(f"\nTotal: {len(full)} bars from {full.index[0]} to {full.index[-1]}")
    return full


if __name__ == "__main__":
    df = download_btcusdt_4h()
    print(f"\n{len(df)} bars: {df.index[0]} → {df.index[-1]}")
