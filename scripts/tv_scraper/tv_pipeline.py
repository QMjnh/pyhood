#!/Users/nyra/Projects/pyhood/.venv/bin/python
"""
TV Strategy Intelligence Pipeline Orchestrator

Sequential pipeline: scrape → enrich → classify → llm-classify → backtest
Each step runs as a subprocess with streaming output to console and log file.

Usage:
    python tv_pipeline.py                              # Full pipeline
    python tv_pipeline.py --start-from enrich          # Start from step 2
    python tv_pipeline.py --skip scrape,backtest       # Skip specific steps
    python tv_pipeline.py --only classify,llm-classify # Run only these steps
    python tv_pipeline.py --dry-run                    # Show plan, don't execute
    python tv_pipeline.py --step-args enrich="--limit 50"  # Override step args
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Constants ────────────────────────────────────────────────────────────────

VENV_PYTHON = "/Users/nyra/Projects/pyhood/.venv/bin/python"
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
LOG_FILE = DATA_DIR / "pipeline.log"

STEPS = [
    {
        "name": "scrape",
        "script": "tv_scrape.py",
        "args": ["--max-pages", "50"],
        "output": "data/strategies.json",
        "description": "Scrape TradingView strategy listings",
    },
    {
        "name": "enrich",
        "script": "tv_enrich.py",
        "args": [],
        "input": "data/strategies.json",
        "output": "data/strategies_enriched.json",
        "description": "Enrich strategies with page metadata",
    },
    {
        "name": "classify",
        "script": "tv_classify.py",
        "args": [
            "--input", "data/strategies_enriched.json",
            "--output", "data/strategies_classified.json",
        ],
        "input": "data/strategies_enriched.json",
        "output": "data/strategies_classified.json",
        "description": "Regex-based text classification",
    },
    {
        "name": "llm-classify",
        "script": "tv_llm_classify.py",
        "args": ["--input", "data/strategies_classified.json"],
        "input": "data/strategies_classified.json",
        "output": "data/strategies_classified.json",
        "description": "LLM-powered deep classification",
    },
    {
        "name": "backtest",
        "script": "tv_backtest.py",
        "args": [],
        "input": "data/strategies_classified.json",
        "output": "data/backtest_results.json",
        "description": "Automated backtesting on TradingView",
        "optional": True,
    },
]

STEP_NAMES = [s["name"] for s in STEPS]

# ── Colors ───────────────────────────────────────────────────────────────────

class C:
    """ANSI color codes — disabled when not a TTY."""
    _enabled = sys.stdout.isatty()

    RESET  = "\033[0m"  if _enabled else ""
    BOLD   = "\033[1m"  if _enabled else ""
    RED    = "\033[91m" if _enabled else ""
    GREEN  = "\033[92m" if _enabled else ""
    YELLOW = "\033[93m" if _enabled else ""
    CYAN   = "\033[96m" if _enabled else ""
    DIM    = "\033[2m"  if _enabled else ""


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, s = divmod(int(seconds), 60)
    if m < 60:
        return f"{m}m {s}s"
    h, m = divmod(m, 60)
    return f"{h}h {m}m {s}s"


# ── Logging ──────────────────────────────────────────────────────────────────

class PipelineLogger:
    def __init__(self, log_path: Path):
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(log_path, "a", buffering=1)  # line-buffered
        self._log(f"\n{'='*72}")
        self._log(f"Pipeline started at {_ts()}")
        self._log(f"{'='*72}")

    def _log(self, msg: str):
        self._fh.write(f"[{_ts()}] {msg}\n")

    def info(self, msg: str):
        self._log(msg)
        print(f"{C.DIM}[{_ts()}]{C.RESET} {msg}")

    def step_start(self, name: str, desc: str):
        self._log(f"▶ STEP [{name}] — {desc}")
        print(f"\n{C.CYAN}{C.BOLD}▶ [{name}]{C.RESET} {desc}")

    def step_skip(self, name: str, reason: str):
        self._log(f"⏭ SKIP [{name}] — {reason}")
        print(f"  {C.YELLOW}⏭ [{name}]{C.RESET} skipped — {reason}")

    def step_pass(self, name: str, elapsed: float):
        dur = _fmt_duration(elapsed)
        self._log(f"✓ PASS [{name}] in {dur}")
        print(f"  {C.GREEN}✓ [{name}]{C.RESET} completed in {dur}")

    def step_fail(self, name: str, code: int, elapsed: float):
        dur = _fmt_duration(elapsed)
        self._log(f"✗ FAIL [{name}] exit={code} in {dur}")
        print(f"  {C.RED}✗ [{name}]{C.RESET} failed (exit {code}) after {dur}")

    def subprocess_line(self, line: str):
        """Write a subprocess output line to the log file (console streaming handled separately)."""
        self._fh.write(f"    {line}\n")

    def close(self):
        self._log(f"Pipeline finished at {_ts()}")
        self._fh.close()


# ── Gate Checks ──────────────────────────────────────────────────────────────

def _check_file(path: Path) -> tuple[bool, str]:
    """Return (ok, message) — checks file exists and is non-empty."""
    if not path.exists():
        return False, f"required file missing: {path}"
    if path.stat().st_size == 0:
        return False, f"required file is empty: {path}"
    # For JSON files, validate parseable and has content
    if path.suffix == ".json":
        try:
            data = json.loads(path.read_text())
            if isinstance(data, list) and len(data) == 0:
                return False, f"required file has empty list: {path}"
            if isinstance(data, dict) and len(data) == 0:
                return False, f"required file has empty dict: {path}"
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return False, f"required file is not valid JSON: {path} ({e})"
    return True, "ok"


def _gate_check(step: dict) -> tuple[bool, str]:
    """Check that a step's input file exists and has data."""
    input_file = step.get("input")
    if not input_file:
        return True, "no input required"
    return _check_file(SCRIPT_DIR / input_file)


# ── Subprocess Runner ────────────────────────────────────────────────────────

def _run_step(step: dict, extra_args: list[str], logger: PipelineLogger) -> tuple[int, float]:
    """
    Run a pipeline step as a subprocess, streaming stdout/stderr to console and log.
    Returns (exit_code, elapsed_seconds).
    """
    script = SCRIPT_DIR / step["script"]
    cmd = [VENV_PYTHON, str(script)] + step["args"] + extra_args

    logger.info(f"  cmd: {' '.join(cmd)}")
    t0 = time.monotonic()

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(SCRIPT_DIR),
        text=True,
        bufsize=1,
    )

    try:
        for line in proc.stdout:
            line = line.rstrip("\n")
            print(f"    {line}")
            logger.subprocess_line(line)
        proc.wait()
    except KeyboardInterrupt:
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=10)
        raise

    elapsed = time.monotonic() - t0
    return proc.returncode, elapsed


# ── Summary ──────────────────────────────────────────────────────────────────

def _run_summary(logger: PipelineLogger):
    """Run summary.py if it exists."""
    summary_script = SCRIPT_DIR / "summary.py"
    if not summary_script.exists():
        logger.info("summary.py not found — skipping summary")
        return

    print(f"\n{C.CYAN}{C.BOLD}📊 Summary{C.RESET}")
    logger.info("Running summary.py")
    proc = subprocess.run(
        [VENV_PYTHON, str(summary_script)],
        cwd=str(SCRIPT_DIR),
        capture_output=False,
    )
    if proc.returncode != 0:
        logger.info(f"summary.py exited with code {proc.returncode}")


# ── Plan / Resolve Steps ────────────────────────────────────────────────────

def _resolve_steps(args) -> list[tuple[dict, str]]:
    """
    Return list of (step_dict, status) where status is 'run' | 'skip:<reason>'.
    """
    result = []

    # Determine which steps to include
    if args.only:
        only_set = set(args.only.split(","))
        invalid = only_set - set(STEP_NAMES)
        if invalid:
            print(f"{C.RED}Error: unknown step(s): {', '.join(invalid)}{C.RESET}")
            print(f"Valid steps: {', '.join(STEP_NAMES)}")
            sys.exit(1)
        for step in STEPS:
            if step["name"] in only_set:
                result.append((step, "run"))
            else:
                result.append((step, "skip:not in --only list"))
        return result

    skip_set = set(args.skip.split(",")) if args.skip else set()
    invalid = skip_set - set(STEP_NAMES)
    if invalid:
        print(f"{C.RED}Error: unknown step(s) to skip: {', '.join(invalid)}{C.RESET}")
        print(f"Valid steps: {', '.join(STEP_NAMES)}")
        sys.exit(1)

    started = False if args.start_from else True

    for step in STEPS:
        if not started:
            if step["name"] == args.start_from:
                started = True
            else:
                result.append((step, "skip:before --start-from"))
                continue

        if step["name"] in skip_set:
            result.append((step, "skip:--skip flag"))
        else:
            result.append((step, "run"))

    if args.start_from and not started:
        print(f"{C.RED}Error: --start-from '{args.start_from}' not found{C.RESET}")
        print(f"Valid steps: {', '.join(STEP_NAMES)}")
        sys.exit(1)

    return result


def _parse_step_args(raw: list[str] | None) -> dict[str, list[str]]:
    """Parse --step-args values like enrich='--limit 50' into {name: [args]}."""
    if not raw:
        return {}
    result = {}
    for item in raw:
        if "=" not in item:
            print(f"{C.RED}Error: --step-args must be key=value, got: {item}{C.RESET}")
            sys.exit(1)
        name, val = item.split("=", 1)
        if name not in STEP_NAMES:
            print(f"{C.RED}Error: unknown step in --step-args: {name}{C.RESET}")
            sys.exit(1)
        result[name] = val.split()
    return result


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="TV Strategy Intelligence Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Steps: {', '.join(STEP_NAMES)}",
    )
    parser.add_argument("--start-from", metavar="STEP",
                        help="Start from this step (skip earlier ones)")
    parser.add_argument("--skip", metavar="STEPS",
                        help="Comma-separated steps to skip")
    parser.add_argument("--only", metavar="STEPS",
                        help="Comma-separated steps to run (exclusive)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show execution plan without running")
    parser.add_argument("--step-args", nargs="*", metavar='STEP="ARGS"',
                        help='Override args for a step: enrich="--limit 50"')

    args = parser.parse_args()

    # Validate mutual exclusivity
    if args.only and (args.start_from or args.skip):
        print(f"{C.RED}Error: --only cannot be combined with --start-from or --skip{C.RESET}")
        sys.exit(1)

    plan = _resolve_steps(args)
    step_extra_args = _parse_step_args(args.step_args)

    # ── Dry run ──────────────────────────────────────────────────────────
    if args.dry_run:
        print(f"\n{C.BOLD}📋 Pipeline Plan (dry run){C.RESET}\n")
        for i, (step, status) in enumerate(plan, 1):
            extra = step_extra_args.get(step["name"], [])
            all_args = step["args"] + extra
            arg_str = f" {' '.join(all_args)}" if all_args else ""
            opt = f" {C.DIM}(optional){C.RESET}" if step.get("optional") else ""

            if status == "run":
                print(f"  {C.GREEN}{i}. [{step['name']}]{C.RESET} {step['description']}{opt}")
                print(f"     {C.DIM}→ {step['script']}{arg_str}{C.RESET}")
                if step.get("input"):
                    print(f"     {C.DIM}  input:  {step['input']}{C.RESET}")
                print(f"     {C.DIM}  output: {step['output']}{C.RESET}")
            else:
                reason = status.split(":", 1)[1] if ":" in status else status
                print(f"  {C.YELLOW}{i}. [{step['name']}]{C.RESET} {C.DIM}{step['description']} — {reason}{C.RESET}")

        run_count = sum(1 for _, s in plan if s == "run")
        skip_count = len(plan) - run_count
        print(f"\n  {C.BOLD}→ {run_count} step(s) to run, {skip_count} skipped{C.RESET}\n")
        return

    # ── Execute pipeline ─────────────────────────────────────────────────
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logger = PipelineLogger(LOG_FILE)
    pipeline_t0 = time.monotonic()
    results: list[dict] = []
    interrupted_step = None

    run_count = sum(1 for _, s in plan if s == "run")
    skip_count = len(plan) - run_count
    logger.info(f"Pipeline: {run_count} step(s) to run, {skip_count} to skip")

    print(f"\n{C.BOLD}🚀 TV Strategy Pipeline{C.RESET}")
    print(f"   {C.DIM}Log: {LOG_FILE}{C.RESET}")

    try:
        for step, status in plan:
            name = step["name"]

            if status != "run":
                reason = status.split(":", 1)[1] if ":" in status else status
                logger.step_skip(name, reason)
                results.append({"name": name, "status": "skipped", "reason": reason})
                continue

            # Gate check — verify input exists
            ok, msg = _gate_check(step)
            if not ok:
                if step.get("optional"):
                    logger.step_skip(name, f"gate failed: {msg}")
                    results.append({"name": name, "status": "skipped", "reason": f"gate: {msg}"})
                    continue
                else:
                    logger.step_fail(name, -1, 0)
                    logger.info(f"Gate check failed: {msg}")
                    print(f"\n  {C.RED}✗ Gate check failed for [{name}]: {msg}{C.RESET}")
                    results.append({"name": name, "status": "gate_fail", "error": msg})
                    break

            logger.step_start(name, step["description"])
            extra = step_extra_args.get(name, [])

            exit_code, elapsed = _run_step(step, extra, logger)

            if exit_code == 0:
                logger.step_pass(name, elapsed)
                results.append({"name": name, "status": "pass", "elapsed": elapsed})
            else:
                logger.step_fail(name, exit_code, elapsed)
                results.append({"name": name, "status": "fail", "exit_code": exit_code, "elapsed": elapsed})
                print(f"\n{C.RED}{C.BOLD}Pipeline halted — [{name}] failed with exit code {exit_code}{C.RESET}")
                break

    except KeyboardInterrupt:
        interrupted_step = name
        print(f"\n\n{C.YELLOW}{C.BOLD}⚠ Pipeline interrupted during [{name}]{C.RESET}")
        logger.info(f"Pipeline interrupted by user during [{name}]")
        results.append({"name": name, "status": "interrupted"})

    # ── Results summary ──────────────────────────────────────────────────
    pipeline_elapsed = time.monotonic() - pipeline_t0

    print(f"\n{C.BOLD}{'─'*50}{C.RESET}")
    print(f"{C.BOLD}Pipeline Results{C.RESET}  ({_fmt_duration(pipeline_elapsed)} total)\n")

    for r in results:
        name = r["name"]
        st = r["status"]
        if st == "pass":
            print(f"  {C.GREEN}✓{C.RESET} {name:15s} {C.DIM}{_fmt_duration(r['elapsed'])}{C.RESET}")
        elif st == "fail":
            print(f"  {C.RED}✗{C.RESET} {name:15s} exit {r['exit_code']} ({_fmt_duration(r['elapsed'])})")
        elif st == "skipped":
            print(f"  {C.YELLOW}⏭{C.RESET} {name:15s} {C.DIM}{r.get('reason', '')}{C.RESET}")
        elif st == "gate_fail":
            print(f"  {C.RED}⊘{C.RESET} {name:15s} {C.DIM}gate: {r.get('error', '')}{C.RESET}")
        elif st == "interrupted":
            print(f"  {C.YELLOW}⚠{C.RESET} {name:15s} interrupted")

    # Run summary.py if all executed steps passed
    all_passed = all(r["status"] in ("pass", "skipped") for r in results)
    if all_passed and any(r["status"] == "pass" for r in results):
        print()
        _run_summary(logger)

    logger.close()

    # Exit code: 0 if all good, 1 if anything failed/interrupted
    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
