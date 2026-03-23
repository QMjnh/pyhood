"""Data models for TradingView scraper."""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
import json


@dataclass
class Strategy:
    """TradingView strategy metadata."""
    title: str
    url: str
    author: str
    boost_count: int
    type_label: str
    script_url: str
    scraped_at: str = None
    
    def __post_init__(self):
        if self.scraped_at is None:
            self.scraped_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Strategy':
        return cls(**data)


@dataclass
class BacktestMetrics:
    """Backtest performance metrics."""
    net_profit: Optional[float] = None
    net_profit_percent: Optional[float] = None
    max_drawdown: Optional[float] = None
    max_drawdown_percent: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    profit_factor: Optional[float] = None
    total_trades: Optional[int] = None
    win_rate_percent: Optional[float] = None
    avg_trade: Optional[float] = None
    buy_hold_return: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BacktestMetrics':
        return cls(**data)


@dataclass
class BacktestResult:
    """Complete backtest result for a strategy on a ticker."""
    strategy_url: str
    strategy_title: str
    ticker: str
    metrics: BacktestMetrics
    tested_at: str = None
    success: bool = True
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.tested_at is None:
            self.tested_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['metrics'] = self.metrics.to_dict()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BacktestResult':
        metrics_data = data.pop('metrics', {})
        metrics = BacktestMetrics.from_dict(metrics_data)
        return cls(metrics=metrics, **data)


class DataManager:
    """Handles saving and loading data to/from JSON files."""
    
    @staticmethod
    def save_strategies(strategies: List[Strategy], filepath: str) -> None:
        """Save strategies to JSON file."""
        data = [strategy.to_dict() for strategy in strategies]
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    @staticmethod
    def load_strategies(filepath: str) -> List[Strategy]:
        """Load strategies from JSON file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return [Strategy.from_dict(item) for item in data]
        except FileNotFoundError:
            return []
    
    @staticmethod
    def save_backtest_results(results: List[BacktestResult], filepath: str) -> None:
        """Save backtest results to JSON file."""
        data = [result.to_dict() for result in results]
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    @staticmethod
    def load_backtest_results(filepath: str) -> List[BacktestResult]:
        """Load backtest results from JSON file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return [BacktestResult.from_dict(item) for item in data]
        except FileNotFoundError:
            return []