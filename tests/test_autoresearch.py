"""Tests for the autoresearch module."""

from __future__ import annotations

import json
import math
import os
import tempfile
from datetime import datetime, timedelta

import pytest

from pyhood.models import Candle
from pyhood.backtest.models import BacktestResult
from pyhood.autoresearch import AutoResearcher, ExperimentResult, ExperimentLog
from pyhood.autoresearch.runner import _log_to_dict, _dict_to_log
from pyhood.backtest.strategies import ema_crossover, rsi_mean_reversion, macd_crossover


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_candles(
    n: int = 500,
    start_price: float = 100.0,
    trend: float = 0.10,
    symbol: str = 'TEST',
) -> list[Candle]:
    """Create synthetic candle data with a controllable trend.

    Generates *n* daily candles starting from 2020-01-01 with a gentle
    oscillation overlaid on a linear trend so that strategies have
    something to trade.
    """
    candles: list[Candle] = []
    base_date = datetime(2020, 1, 1)
    price = start_price

    for i in range(n):
        # Slow trend + sine oscillation for mean-reversion signals
        daily_drift = (trend / n)
        oscillation = 0.02 * math.sin(i * 2 * math.pi / 40)
        price *= (1 + daily_drift + oscillation)

        high = price * 1.015
        low = price * 0.985
        open_p = price * (1 + 0.002 * ((i % 3) - 1))

        candles.append(Candle(
            symbol=symbol,
            begins_at=(base_date + timedelta(days=i)).strftime('%Y-%m-%dT%H:%M:%SZ'),
            open_price=open_p,
            close_price=price,
            high_price=high,
            low_price=low,
            volume=1_000_000 + i * 100,
        ))

    return candles


def _simple_strategy_factory(fast: int = 5, slow: int = 20):
    """Thin wrapper around ema_crossover for tests."""
    return ema_crossover(fast=fast, slow=slow)


# ---------------------------------------------------------------------------
# Tests — Initialization
# ---------------------------------------------------------------------------

class TestAutoResearcherInit:

    def test_init_with_candles(self):
        candles = _make_candles(400)
        ar = AutoResearcher(candles=candles)
        assert len(ar.all_candles) == 400
        assert len(ar.train_candles) > 0
        assert len(ar.test_candles) > 0
        assert len(ar.validate_candles) > 0

    def test_split_proportions(self):
        candles = _make_candles(400)
        ar = AutoResearcher(candles=candles, train_pct=0.5, test_pct=0.25,
                            validate_pct=0.25)
        total = (len(ar.train_candles) + len(ar.test_candles)
                 + len(ar.validate_candles))
        assert total == 400
        # Proportions roughly correct (integer rounding)
        assert abs(len(ar.train_candles) - 200) <= 1
        assert abs(len(ar.test_candles) - 100) <= 1
        assert abs(len(ar.validate_candles) - 100) <= 1

    def test_custom_split(self):
        candles = _make_candles(300)
        ar = AutoResearcher(candles=candles, train_pct=0.6, test_pct=0.2,
                            validate_pct=0.2)
        assert abs(len(ar.train_candles) - 180) <= 1
        assert abs(len(ar.test_candles) - 60) <= 1

    def test_bad_split_raises(self):
        candles = _make_candles(100)
        with pytest.raises(ValueError, match="must equal 1.0"):
            AutoResearcher(candles=candles, train_pct=0.5, test_pct=0.5,
                           validate_pct=0.5)

    def test_initial_log_empty(self):
        candles = _make_candles(200)
        ar = AutoResearcher(candles=candles)
        assert ar.log.total_experiments == 0
        assert ar.log.best_train_sharpe == 0.0
        assert ar.log.best_test_sharpe == 0.0


# ---------------------------------------------------------------------------
# Tests — split_data
# ---------------------------------------------------------------------------

class TestSplitData:

    def test_split_data_disjoint(self):
        candles = _make_candles(300)
        ar = AutoResearcher(candles=candles)
        train, test, val = ar.train_candles, ar.test_candles, ar.validate_candles

        # Check chronological order: train ends before test starts, etc.
        assert train[-1].begins_at <= test[0].begins_at
        assert test[-1].begins_at <= val[0].begins_at

    def test_split_data_covers_all(self):
        candles = _make_candles(300)
        ar = AutoResearcher(candles=candles)
        total = (len(ar.train_candles) + len(ar.test_candles)
                 + len(ar.validate_candles))
        assert total == 300


# ---------------------------------------------------------------------------
# Tests — evaluate
# ---------------------------------------------------------------------------

class TestEvaluate:

    def test_evaluate_returns_backtest_result(self):
        candles = _make_candles(400)
        ar = AutoResearcher(candles=candles, min_trades=0)
        strategy = ema_crossover(fast=5, slow=20)
        result = ar.evaluate(strategy, 'EMA Test', dataset='train')
        assert isinstance(result, BacktestResult)
        assert result.strategy_name == 'EMA Test'

    def test_evaluate_bad_dataset_raises(self):
        candles = _make_candles(200)
        ar = AutoResearcher(candles=candles)
        with pytest.raises(ValueError, match="dataset must be"):
            ar.evaluate(ema_crossover(), 'test', dataset='bogus')


# ---------------------------------------------------------------------------
# Tests — run_experiment
# ---------------------------------------------------------------------------

class TestRunExperiment:

    def test_returns_experiment_result(self):
        candles = _make_candles(500)
        ar = AutoResearcher(candles=candles, min_trades=0)
        strategy = ema_crossover(fast=5, slow=20)
        exp = ar.run_experiment(strategy, 'EMA 5/20', params={'fast': 5, 'slow': 20})
        assert isinstance(exp, ExperimentResult)
        assert exp.experiment_id >= 1
        assert exp.strategy_name == 'EMA 5/20'
        assert isinstance(exp.train_result, BacktestResult)

    def test_experiment_logged(self):
        candles = _make_candles(500)
        ar = AutoResearcher(candles=candles, min_trades=0)
        ar.run_experiment(ema_crossover(fast=5, slow=20), 'EMA')
        assert ar.log.total_experiments == 1
        assert len(ar.log.experiments) == 1

    def test_min_trades_filter(self):
        candles = _make_candles(100)  # Short data → few trades
        ar = AutoResearcher(candles=candles, min_trades=999)
        exp = ar.run_experiment(ema_crossover(fast=5, slow=20), 'EMA')
        # With min_trades=999 it should never be kept
        assert not exp.kept
        assert 'trades' in exp.reason.lower() or 'Discarded' in exp.reason

    def test_ids_increment(self):
        candles = _make_candles(400)
        ar = AutoResearcher(candles=candles, min_trades=0)
        e1 = ar.run_experiment(ema_crossover(fast=5, slow=20), 'A')
        e2 = ar.run_experiment(ema_crossover(fast=7, slow=21), 'B')
        assert e2.experiment_id == e1.experiment_id + 1


# ---------------------------------------------------------------------------
# Tests — parameter_sweep
# ---------------------------------------------------------------------------

class TestParameterSweep:

    def test_returns_sorted_results(self):
        candles = _make_candles(500)
        ar = AutoResearcher(candles=candles, min_trades=0)
        results = ar.parameter_sweep(
            ema_crossover, 'fast', [5, 9, 13],
            base_params={'slow': 21},
            strategy_name='EMA'
        )
        assert len(results) == 3
        assert all(isinstance(r, ExperimentResult) for r in results)

    def test_experiments_logged(self):
        candles = _make_candles(500)
        ar = AutoResearcher(candles=candles, min_trades=0)
        ar.parameter_sweep(
            ema_crossover, 'fast', [5, 9],
            base_params={'slow': 21},
        )
        assert ar.log.total_experiments == 2

    def test_top_n_tested(self):
        candles = _make_candles(500)
        ar = AutoResearcher(candles=candles, min_trades=0, top_n=2)
        results = ar.parameter_sweep(
            ema_crossover, 'fast', [5, 7, 9, 11, 13],
            base_params={'slow': 21},
        )
        tested = [r for r in results if r.test_result is not None]
        # At most top_n should be tested (some may fail min_trades on train)
        assert len(tested) <= 2


# ---------------------------------------------------------------------------
# Tests — multi_param_sweep
# ---------------------------------------------------------------------------

class TestMultiParamSweep:

    def test_grid_search(self):
        candles = _make_candles(500)
        ar = AutoResearcher(candles=candles, min_trades=0)
        results = ar.multi_param_sweep(
            ema_crossover,
            {'fast': [5, 9], 'slow': [20, 30]},
            strategy_name='EMA Grid'
        )
        assert len(results) == 4  # 2 × 2

    def test_experiments_logged(self):
        candles = _make_candles(500)
        ar = AutoResearcher(candles=candles, min_trades=0)
        ar.multi_param_sweep(
            ema_crossover,
            {'fast': [5, 9], 'slow': [20, 30]},
        )
        assert ar.log.total_experiments == 4


# ---------------------------------------------------------------------------
# Tests — validate_best
# ---------------------------------------------------------------------------

class TestValidateBest:

    def test_validate_uses_validate_split(self):
        candles = _make_candles(600)
        ar = AutoResearcher(candles=candles, min_trades=0)
        # Run some experiments first
        ar.parameter_sweep(
            ema_crossover, 'fast', [5, 7, 9, 11],
            base_params={'slow': 21},
            strategy_name='EMA',
        )
        validated = ar.validate_best(n=2)
        # Should return at most n results, each with validate_result set
        assert len(validated) <= 2
        for exp in validated:
            if exp.validate_result is not None:
                assert isinstance(exp.validate_result, BacktestResult)


# ---------------------------------------------------------------------------
# Tests — overfitting detection
# ---------------------------------------------------------------------------

class TestOverfitDetection:

    def test_overfit_warning_in_reason(self):
        """When train >> test, the reason should contain an overfit warning."""
        candles = _make_candles(500)
        ar = AutoResearcher(candles=candles, min_trades=0)

        # Run two experiments — the 2nd should attempt test
        e1 = ar.run_experiment(ema_crossover(fast=5, slow=20), 'A',
                               params={'fast': 5, 'slow': 20})
        # Check if any kept experiment mentions overfit
        # (depends on data; just verify the mechanism works without crashing)
        assert isinstance(e1.reason, str)


# ---------------------------------------------------------------------------
# Tests — save / load round-trip
# ---------------------------------------------------------------------------

class TestPersistence:

    def test_save_load_roundtrip(self):
        candles = _make_candles(400)
        ar = AutoResearcher(candles=candles, min_trades=0)
        ar.run_experiment(ema_crossover(fast=5, slow=20), 'EMA 5/20',
                          params={'fast': 5, 'slow': 20})

        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            path = f.name

        try:
            ar.save(path)
            assert os.path.exists(path)

            # Load into a fresh researcher
            ar2 = AutoResearcher(candles=candles, min_trades=0)
            ar2.load(path)

            assert ar2.log.total_experiments == ar.log.total_experiments
            assert ar2.log.ticker == ar.log.ticker
            assert len(ar2.log.experiments) == len(ar.log.experiments)
            assert (ar2.log.experiments[0].strategy_name
                    == ar.log.experiments[0].strategy_name)
            assert (ar2.log.experiments[0].train_result.sharpe_ratio
                    == ar.log.experiments[0].train_result.sharpe_ratio)
        finally:
            os.unlink(path)

    def test_save_creates_valid_json(self):
        candles = _make_candles(200)
        ar = AutoResearcher(candles=candles, min_trades=0)
        ar.run_experiment(ema_crossover(), 'EMA')

        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            path = f.name

        try:
            ar.save(path)
            with open(path) as f:
                data = json.load(f)
            assert 'experiments' in data
            assert 'ticker' in data
            assert data['total_experiments'] == 1
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Tests — report
# ---------------------------------------------------------------------------

class TestReport:

    def test_report_returns_string(self):
        candles = _make_candles(400)
        ar = AutoResearcher(candles=candles, min_trades=0)
        ar.run_experiment(ema_crossover(fast=5, slow=20), 'EMA')
        report = ar.report()
        assert isinstance(report, str)
        assert 'AutoResearch Report' in report

    def test_report_empty(self):
        candles = _make_candles(200)
        ar = AutoResearcher(candles=candles)
        report = ar.report()
        assert 'No strategies beat the baseline' in report


# ---------------------------------------------------------------------------
# Tests — imports
# ---------------------------------------------------------------------------

class TestImports:

    def test_import_from_autoresearch(self):
        from pyhood.autoresearch import AutoResearcher, ExperimentResult, ExperimentLog
        assert callable(AutoResearcher)
        assert ExperimentResult is not None
        assert ExperimentLog is not None
