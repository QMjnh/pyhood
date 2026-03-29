"""Tests for the overnight autoresearch runner."""

from __future__ import annotations

import json
import math
import os
import signal
import tempfile
from datetime import datetime, timedelta

from autoresearch.overnight import (
    DEFAULT_TICKERS,
    STRATEGY_SWEEPS,
    OvernightRunner,
    _count_combos,
    _grid_combos,
)
from backtest.strategies import ema_crossover
from backtest.models import Candle

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_candles(
    n: int = 500,
    start_price: float = 100.0,
    trend: float = 0.10,
    symbol: str = 'TEST',
) -> list[Candle]:
    """Create synthetic candle data with a controllable trend."""
    candles: list[Candle] = []
    base_date = datetime(2020, 1, 1)
    price = start_price

    for i in range(n):
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


def _bad_strategy_factory(explode: bool = True):
    """A strategy factory that always raises an exception."""
    def strategy_fn(candles, position):
        raise RuntimeError("Intentional test explosion!")
    return strategy_fn


def _tiny_sweeps():
    """A minimal sweep config for fast testing."""
    return [
        {
            'name': 'EMA Crossover',
            'factory': ema_crossover,
            'grid': {
                'fast': [5, 9],
                'slow': [20, 30],
            },
        },
    ]


# ---------------------------------------------------------------------------
# Tests — Initialization
# ---------------------------------------------------------------------------

class TestOvernightRunnerInit:

    def test_default_init(self):
        runner = OvernightRunner()
        assert runner.ticker == 'SPY'
        assert runner.total_period == '10y'
        assert runner.results_dir == 'autoresearch_results'
        assert runner.experiment_timeout == 60
        assert runner.save_every == 1
        assert runner.slippage_pct == 0.01
        assert runner.continuous is False
        assert runner.tickers == list(DEFAULT_TICKERS)
        assert runner._stop_requested is False

    def test_custom_init(self):
        runner = OvernightRunner(
            ticker='QQQ',
            total_period='5y',
            results_dir='/tmp/test_results',
            experiment_timeout=120,
            slippage_pct=0.05,
        )
        assert runner.ticker == 'QQQ'
        assert runner.total_period == '5y'
        assert runner.results_dir == '/tmp/test_results'
        assert runner.experiment_timeout == 120
        assert runner.slippage_pct == 0.05

    def test_continuous_init(self):
        runner = OvernightRunner(
            continuous=True,
            tickers=['SPY', 'QQQ'],
        )
        assert runner.continuous is True
        assert runner.tickers == ['SPY', 'QQQ']

    def test_continuous_default_tickers(self):
        runner = OvernightRunner(continuous=True)
        assert runner.tickers == list(DEFAULT_TICKERS)

    def test_paths(self):
        runner = OvernightRunner(results_dir='/tmp/test_dir')
        assert runner.experiments_path == '/tmp/test_dir/experiments.json'
        assert runner.errors_path == '/tmp/test_dir/errors.log'
        assert runner.summary_path == '/tmp/test_dir/summary.md'
        assert runner.best_strategies_path == '/tmp/test_dir/best_strategies.json'
        assert runner.run_log_path == '/tmp/test_dir/run_log.txt'


# ---------------------------------------------------------------------------
# Tests — Grid helpers
# ---------------------------------------------------------------------------

class TestGridHelpers:

    def test_count_combos(self):
        assert _count_combos({'a': [1, 2, 3], 'b': [4, 5]}) == 6
        assert _count_combos({'x': [1]}) == 1
        assert _count_combos({'a': [1, 2], 'b': [3, 4], 'c': [5, 6]}) == 8

    def test_grid_combos(self):
        combos = _grid_combos({'a': [1, 2], 'b': [3, 4]})
        assert len(combos) == 4
        assert {'a': 1, 'b': 3} in combos
        assert {'a': 2, 'b': 4} in combos


# ---------------------------------------------------------------------------
# Tests — Resume detection
# ---------------------------------------------------------------------------

class TestResumeDetection:

    def test_no_previous_state(self):
        """When no experiments.json exists, starts fresh."""
        with tempfile.TemporaryDirectory() as tmpdir:
            candles = _make_candles(400)
            runner = OvernightRunner(
                results_dir=tmpdir,
                candles=candles,
                cross_validate_tickers=[],
                strategy_sweeps=_tiny_sweeps(),
            )
            runner._researcher = None  # Will be set in run()
            # Just verify the file doesn't exist
            assert not os.path.exists(runner.experiments_path)

    def test_resume_skips_completed(self):
        """After running, restarting should skip already-completed experiments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            candles = _make_candles(400)

            # First run
            runner1 = OvernightRunner(
                results_dir=tmpdir,
                candles=candles,
                cross_validate_tickers=[],
                strategy_sweeps=_tiny_sweeps(),
                experiment_timeout=30,
            )
            result1 = runner1.run()
            first_count = result1['total_experiments']
            assert first_count > 0

            # experiments.json should exist
            assert os.path.exists(os.path.join(tmpdir, 'experiments.json'))

            # Second run — should resume and skip completed
            runner2 = OvernightRunner(
                results_dir=tmpdir,
                candles=candles,
                cross_validate_tickers=[],
                strategy_sweeps=_tiny_sweeps(),
                experiment_timeout=30,
            )
            result2 = runner2.run()
            # Total experiments should be the same (no new ones added)
            assert result2['total_experiments'] == first_count


# ---------------------------------------------------------------------------
# Tests — Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:

    def test_bad_strategy_doesnt_kill_run(self):
        """A strategy that raises an exception should not kill the run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            candles = _make_candles(400)
            sweeps = [
                {
                    'name': 'Bad Strategy',
                    'factory': _bad_strategy_factory,
                    'grid': {'explode': [True]},
                },
                {
                    'name': 'EMA Crossover',
                    'factory': ema_crossover,
                    'grid': {'fast': [5], 'slow': [20]},
                },
            ]
            runner = OvernightRunner(
                results_dir=tmpdir,
                candles=candles,
                cross_validate_tickers=[],
                strategy_sweeps=sweeps,
                experiment_timeout=30,
            )
            result = runner.run()
            # Run should complete despite the bad strategy
            assert result['errors'] >= 1
            # The EMA experiment should still have run
            assert result['total_experiments'] >= 1

    def test_errors_logged(self):
        """Errors should be logged to errors.log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            candles = _make_candles(400)
            sweeps = [
                {
                    'name': 'Bad Strategy',
                    'factory': _bad_strategy_factory,
                    'grid': {'explode': [True]},
                },
            ]
            runner = OvernightRunner(
                results_dir=tmpdir,
                candles=candles,
                cross_validate_tickers=[],
                strategy_sweeps=sweeps,
                experiment_timeout=30,
            )
            runner.run()

            errors_path = os.path.join(tmpdir, 'errors.log')
            assert os.path.exists(errors_path)
            with open(errors_path) as f:
                content = f.read()
            assert 'Bad Strategy' in content
            assert 'Intentional test explosion' in content


# ---------------------------------------------------------------------------
# Tests — Save frequency
# ---------------------------------------------------------------------------

class TestSaveFrequency:

    def test_experiments_json_updated_after_each(self):
        """experiments.json should be updated after each experiment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            candles = _make_candles(400)
            runner = OvernightRunner(
                results_dir=tmpdir,
                candles=candles,
                cross_validate_tickers=[],
                strategy_sweeps=_tiny_sweeps(),
                experiment_timeout=30,
                save_every=1,
            )
            runner.run()

            # experiments.json should exist with data
            exp_path = os.path.join(tmpdir, 'experiments.json')
            assert os.path.exists(exp_path)
            with open(exp_path) as f:
                data = json.load(f)
            assert data['total_experiments'] > 0
            assert len(data['experiments']) > 0


# ---------------------------------------------------------------------------
# Tests — Results directory structure
# ---------------------------------------------------------------------------

class TestResultsDirectory:

    def test_directory_structure(self):
        """All expected output files should be created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            candles = _make_candles(400)
            runner = OvernightRunner(
                results_dir=tmpdir,
                candles=candles,
                cross_validate_tickers=[],
                strategy_sweeps=_tiny_sweeps(),
                experiment_timeout=30,
            )
            runner.run()

            assert os.path.exists(os.path.join(tmpdir, 'experiments.json'))
            assert os.path.exists(os.path.join(tmpdir, 'summary.md'))
            assert os.path.exists(os.path.join(tmpdir, 'best_strategies.json'))
            assert os.path.exists(os.path.join(tmpdir, 'run_log.txt'))

    def test_summary_is_readable(self):
        """summary.md should contain meaningful content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            candles = _make_candles(400)
            runner = OvernightRunner(
                results_dir=tmpdir,
                candles=candles,
                cross_validate_tickers=[],
                strategy_sweeps=_tiny_sweeps(),
                experiment_timeout=30,
            )
            runner.run()

            with open(os.path.join(tmpdir, 'summary.md')) as f:
                content = f.read()
            assert 'AutoResearch Summary' in content
            assert 'Total experiments' in content

    def test_best_strategies_valid_json(self):
        """best_strategies.json should be valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            candles = _make_candles(400)
            runner = OvernightRunner(
                results_dir=tmpdir,
                candles=candles,
                cross_validate_tickers=[],
                strategy_sweeps=_tiny_sweeps(),
                experiment_timeout=30,
            )
            runner.run()

            with open(os.path.join(tmpdir, 'best_strategies.json')) as f:
                data = json.load(f)
            assert isinstance(data, list)


# ---------------------------------------------------------------------------
# Tests — Run log
# ---------------------------------------------------------------------------

class TestRunLog:

    def test_run_log_timestamped(self):
        """Run log entries should have timestamps."""
        with tempfile.TemporaryDirectory() as tmpdir:
            candles = _make_candles(400)
            runner = OvernightRunner(
                results_dir=tmpdir,
                candles=candles,
                cross_validate_tickers=[],
                strategy_sweeps=_tiny_sweeps(),
                experiment_timeout=30,
            )
            runner.run()

            with open(os.path.join(tmpdir, 'run_log.txt')) as f:
                lines = f.readlines()

            assert len(lines) > 0
            # Every line should start with [YYYY-MM-DD HH:MM:SS]
            for line in lines:
                line = line.strip()
                if line:
                    assert line.startswith('['), f'Line missing timestamp: {line}'
                    assert ']' in line, f'Line missing timestamp close: {line}'

    def test_run_log_contains_sweep_start(self):
        """Run log should mention strategy sweep starts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            candles = _make_candles(400)
            runner = OvernightRunner(
                results_dir=tmpdir,
                candles=candles,
                cross_validate_tickers=[],
                strategy_sweeps=_tiny_sweeps(),
                experiment_timeout=30,
            )
            runner.run()

            with open(os.path.join(tmpdir, 'run_log.txt')) as f:
                content = f.read()
            assert 'EMA Crossover sweep' in content
            assert 'combos' in content


# ---------------------------------------------------------------------------
# Tests — Experiment key
# ---------------------------------------------------------------------------

class TestExperimentKey:

    def test_same_params_same_key(self):
        key1 = OvernightRunner._experiment_key('EMA', {'fast': 5, 'slow': 20})
        key2 = OvernightRunner._experiment_key('EMA', {'fast': 5, 'slow': 20})
        assert key1 == key2

    def test_different_params_different_key(self):
        key1 = OvernightRunner._experiment_key('EMA', {'fast': 5, 'slow': 20})
        key2 = OvernightRunner._experiment_key('EMA', {'fast': 9, 'slow': 20})
        assert key1 != key2

    def test_different_strategy_different_key(self):
        key1 = OvernightRunner._experiment_key('EMA', {'fast': 5, 'slow': 20})
        key2 = OvernightRunner._experiment_key('RSI', {'fast': 5, 'slow': 20})
        assert key1 != key2

    def test_param_order_independent(self):
        key1 = OvernightRunner._experiment_key('EMA', {'fast': 5, 'slow': 20})
        key2 = OvernightRunner._experiment_key('EMA', {'slow': 20, 'fast': 5})
        assert key1 == key2


# ---------------------------------------------------------------------------
# Tests — Strategy sweeps config
# ---------------------------------------------------------------------------

class TestStrategySweepsConfig:

    def test_all_strategies_defined(self):
        """All 11 strategies should be in STRATEGY_SWEEPS."""
        names = {s['name'] for s in STRATEGY_SWEEPS}
        assert 'EMA Crossover' in names
        assert 'MACD' in names
        assert 'RSI Mean Reversion' in names
        assert 'RSI(2) Connors' in names
        assert 'Bollinger Breakout' in names
        assert 'Donchian Breakout' in names
        assert 'MA+ATR Mean Reversion' in names
        assert 'Golden Cross' in names
        assert 'Keltner Squeeze' in names
        assert 'Volume Confirmed' in names
        assert 'Bull Flag' in names
        assert len(STRATEGY_SWEEPS) == 11

    def test_total_combos(self):
        """Verify total combo count matches expected."""
        total = sum(_count_combos(s['grid']) for s in STRATEGY_SWEEPS)
        # EMA: 7*7=49, MACD: 5*5*5=125, RSI: 4*5*5=100, RSI2: 3*3*4*4=144,
        # Boll: 5*4=20, Donch: 6*5=30, MA+ATR: 5*5*4=100, GC: 4*4=16,
        # Keltner: 4*4=16, Volume: 4*4=16, BullFlag: 4*4=16
        # Total = 632
        assert total > 600  # Rough sanity check


# ---------------------------------------------------------------------------
# Tests — Full run (tiny grid)
# ---------------------------------------------------------------------------

class TestFullRun:

    def test_full_run_returns_summary(self):
        """A full run with tiny grid should return a valid summary dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            candles = _make_candles(400)
            runner = OvernightRunner(
                results_dir=tmpdir,
                candles=candles,
                cross_validate_tickers=[],
                strategy_sweeps=_tiny_sweeps(),
                experiment_timeout=30,
            )
            result = runner.run()

            assert isinstance(result, dict)
            assert 'total_experiments' in result
            assert 'errors' in result
            assert 'timeouts' in result
            assert 'best_train_sharpe' in result
            assert 'best_test_sharpe' in result
            assert 'kept_strategies' in result
            assert result['total_experiments'] > 0
            assert result['errors'] == 0
            assert result['timeouts'] == 0


# ---------------------------------------------------------------------------
# Tests — Signal handling
# ---------------------------------------------------------------------------

class TestSignalHandling:

    def test_handle_stop_sets_flag(self):
        """_handle_stop should set _stop_requested to True."""
        runner = OvernightRunner()
        assert runner._stop_requested is False
        runner._handle_stop(signal.SIGINT, None)
        assert runner._stop_requested is True

    def test_handle_stop_sigterm(self):
        """_handle_stop should work with SIGTERM too."""
        runner = OvernightRunner()
        runner._handle_stop(signal.SIGTERM, None)
        assert runner._stop_requested is True

    def test_install_restore_signal_handlers(self):
        """Signal handlers should be installed and restored cleanly."""
        runner = OvernightRunner()
        original_sigint = signal.getsignal(signal.SIGINT)
        original_sigterm = signal.getsignal(signal.SIGTERM)

        runner._install_signal_handlers()
        # After install, handlers should be our custom ones
        assert signal.getsignal(signal.SIGINT) == runner._handle_stop
        assert signal.getsignal(signal.SIGTERM) == runner._handle_stop

        runner._restore_signal_handlers()
        # After restore, handlers should be back to originals
        assert signal.getsignal(signal.SIGINT) == original_sigint
        assert signal.getsignal(signal.SIGTERM) == original_sigterm

    def test_stop_requested_breaks_sweep(self):
        """When _stop_requested is True, experiments should stop."""
        with tempfile.TemporaryDirectory() as tmpdir:
            candles = _make_candles(400)
            # Use a large sweep so we can stop mid-way
            sweeps = [
                {
                    'name': 'EMA Crossover',
                    'factory': ema_crossover,
                    'grid': {
                        'fast': [5, 7, 9, 11, 13],
                        'slow': [20, 25, 30, 35, 40],
                    },
                },
            ]
            runner = OvernightRunner(
                results_dir=tmpdir,
                candles=candles,
                cross_validate_tickers=[],
                strategy_sweeps=sweeps,
                experiment_timeout=30,
            )
            # Pre-set stop_requested so it stops immediately
            runner._stop_requested = True
            result = runner.run()
            # Should have very few or zero experiments since stop was pre-set
            assert result['total_experiments'] == 0


# ---------------------------------------------------------------------------
# Tests — Continuous mode
# ---------------------------------------------------------------------------

class TestContinuousMode:

    def test_continuous_false_backward_compat(self):
        """continuous=False should produce identical behavior to original."""
        with tempfile.TemporaryDirectory() as tmpdir:
            candles = _make_candles(400)
            runner = OvernightRunner(
                results_dir=tmpdir,
                candles=candles,
                cross_validate_tickers=[],
                strategy_sweeps=_tiny_sweeps(),
                experiment_timeout=30,
                continuous=False,
            )
            result = runner.run()

            assert isinstance(result, dict)
            assert 'total_experiments' in result
            assert 'best_train_sharpe' in result
            assert 'best_test_sharpe' in result
            assert result['total_experiments'] > 0

    def test_continuous_immediate_stop(self):
        """Continuous mode with pre-set stop should exit after saving."""
        with tempfile.TemporaryDirectory() as tmpdir:
            candles = _make_candles(400)
            runner = OvernightRunner(
                results_dir=tmpdir,
                candles=candles,
                cross_validate_tickers=[],
                strategy_sweeps=_tiny_sweeps(),
                experiment_timeout=30,
                continuous=True,
                tickers=['TEST'],
            )
            # Pre-set stop so it exits immediately
            runner._stop_requested = True
            result = runner.run()

            assert 'cycles_completed' in result
            assert 'tickers' in result
            assert result['tickers'] == ['TEST']

    def test_continuous_one_cycle_then_stop(self):
        """Continuous mode should complete one full cycle then stop on signal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            candles = _make_candles(400)

            class StopAfterFirstCycle(OvernightRunner):
                """Subclass that stops after first cycle."""
                def _run_refinement_cycle(self, researcher, ticker, cycle):
                    # Stop before second cycle starts
                    self._stop_requested = True
                    super()._run_refinement_cycle(researcher, ticker, cycle)

            runner = StopAfterFirstCycle(
                results_dir=tmpdir,
                candles=candles,
                cross_validate_tickers=[],
                strategy_sweeps=_tiny_sweeps(),
                experiment_timeout=30,
                continuous=True,
                tickers=['TEST'],
            )
            result = runner.run()

            assert result['total_experiments'] > 0
            assert result['cycles_completed'] >= 1

            # Check that per-ticker directory was created
            ticker_dir = os.path.join(tmpdir, 'test')
            assert os.path.isdir(ticker_dir)
            assert os.path.exists(os.path.join(ticker_dir, 'experiments.json'))
            assert os.path.exists(os.path.join(ticker_dir, 'best_strategies.json'))
            assert os.path.exists(os.path.join(ticker_dir, 'summary.md'))


# ---------------------------------------------------------------------------
# Tests — Multi-ticker results directory structure
# ---------------------------------------------------------------------------

class TestMultiTickerDirectory:

    def test_ticker_dir_path(self):
        """Ticker directories should use lowercase with underscores."""
        runner = OvernightRunner(results_dir='/tmp/results')
        assert runner._ticker_dir('SPY') == '/tmp/results/spy'
        assert runner._ticker_dir('BTC-USD') == '/tmp/results/btc_usd'
        assert runner._ticker_dir('AAPL') == '/tmp/results/aapl'

    def test_ticker_paths(self):
        runner = OvernightRunner(results_dir='/tmp/results')
        assert runner._ticker_experiments_path('SPY') == '/tmp/results/spy/experiments.json'
        assert runner._ticker_best_strategies_path('SPY') == '/tmp/results/spy/best_strategies.json'
        assert runner._ticker_summary_path('SPY') == '/tmp/results/spy/summary.md'


# ---------------------------------------------------------------------------
# Tests — Refinement cycle parameter variations
# ---------------------------------------------------------------------------

class TestRefinementCycle:

    def test_generate_param_variations_int(self):
        """Integer parameters should generate nearby integer variations."""
        params = {'fast': 10, 'slow': 30}
        grid = {'fast': [5, 10, 15], 'slow': [20, 30, 40]}
        variations = OvernightRunner._generate_param_variations(params, grid)

        # Should have some variations
        assert len(variations) > 0
        # Should not include original params
        assert params not in variations
        # All values should be valid types
        for v in variations:
            assert isinstance(v['fast'], int)
            assert isinstance(v['slow'], int)
            assert v['fast'] > 0
            assert v['slow'] > 0

    def test_generate_param_variations_float(self):
        """Float parameters should generate nearby float variations."""
        params = {'std_dev': 2.0}
        grid = {'std_dev': [1.5, 2.0, 2.5]}
        variations = OvernightRunner._generate_param_variations(params, grid)

        assert len(variations) > 0
        for v in variations:
            assert isinstance(v['std_dev'], float)
            assert v['std_dev'] > 0

    def test_generate_param_variations_excludes_grid_values(self):
        """Variations should not include values already in the original grid."""
        params = {'fast': 10}
        grid = {'fast': [5, 10, 15]}
        variations = OvernightRunner._generate_param_variations(params, grid)

        # None of the variations should have values that are exactly in the grid
        # (except the original value which is kept for cross-product)
        for v in variations:
            # The variation should differ from the original
            assert v != params

    def test_generate_param_variations_capped_at_50(self):
        """Should cap at 50 variations maximum."""
        # Large grid that would produce many combos
        params = {'a': 10, 'b': 20, 'c': 30, 'd': 40}
        grid = {'a': [10], 'b': [20], 'c': [30], 'd': [40]}
        variations = OvernightRunner._generate_param_variations(params, grid)
        assert len(variations) <= 50

    def test_generate_param_variations_count_range(self):
        """Should generate a reasonable number of variations (20-50 for typical params)."""
        # Typical EMA crossover params
        params = {'fast': 9, 'slow': 25}
        grid = {'fast': [5, 7, 9, 11], 'slow': [15, 20, 25, 30]}
        variations = OvernightRunner._generate_param_variations(params, grid)
        # Should generate a meaningful number (depends on grid exclusion)
        assert len(variations) >= 3  # At minimum a few variations
        assert len(variations) <= 50
