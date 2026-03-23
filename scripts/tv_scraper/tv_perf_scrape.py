#!/Users/nyra/Projects/pyhood/.venv/bin/python
"""
TradingView Strategy Performance Scraper
Scrapes backtest/performance data from TradingView strategy pages using Playwright.

Usage:
    ./tv_perf_scrape.py
    ./tv_perf_scrape.py --input data/strategies_classified.json --limit 50 --delay 5
    ./tv_perf_scrape.py --start-from 20 --limit 10
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR  # ~/Projects/pyhood/scripts/tv_scraper
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_INPUT = DATA_DIR / "strategies_classified.json"
DEFAULT_OUTPUT = DATA_DIR / "strategies_classified.json"
LOG_FILE = DATA_DIR / "perf_scrape.log"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging() -> logging.Logger:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("tv_perf_scrape")
    logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(asctime)s %(message)s"))

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger

log = setup_logging()

# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

# Matches the em-dash / en-dash / long dash TradingView uses for "no data"
_NO_DATA_RE = re.compile(r"^[\s—–\-]*$")


def _normalize(text: str) -> str:
    """Replace unicode minus (U+2212) with regular hyphen and strip."""
    return text.replace("\u2212", "-").replace("\u2013", "-").strip()


def parse_usd_value(text: str) -> float | None:
    """Extract a USD float from strings like '+402.90 USD', '−75,799.21 USD', '175.00'.
    Returns None if text is percentage-only (e.g. '0.04%')."""
    if text is None or _NO_DATA_RE.match(text):
        return None
    text = _normalize(text)
    # Bug 5 fix: skip if the text is purely a percentage (no USD indicator)
    stripped = text.strip()
    if stripped.endswith("%") and "USD" not in text.upper():
        # Check there's no other number before the pct — pure pct value
        non_pct = re.sub(r"[+-]?[\d,]+\.?\d*\s*%", "", stripped).strip()
        if not re.search(r"\d", non_pct):
            return None
    # Look for a number (with optional sign and commas) before optional 'USD'
    m = re.search(r"([+-]?[\d,]+\.?\d*)\s*(?:USD)?", text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def parse_pct_value(text: str) -> float | None:
    """Extract a percentage float from strings like '+0.04%', '−7.58%', '100.00%'.
    Bug 2 fix: Only matches numbers immediately followed by '%' to avoid grabbing USD values."""
    if text is None or _NO_DATA_RE.match(text):
        return None
    text = _normalize(text)
    # Strictly match number immediately followed by % (no space between number and %)
    m = re.search(r"([+-]?[\d,]+\.?\d*)%", text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def parse_int_value(text: str) -> int | None:
    """Extract an integer from strings like '3', '1 214'. Spaces are thousand separators."""
    if text is None or _NO_DATA_RE.match(text):
        return None
    text = _normalize(text)
    # Remove spaces used as thousand separators, keep digits and sign
    cleaned = re.sub(r"\s+", "", text)
    m = re.search(r"([+-]?\d+)", cleaned)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def split_usd_pct(cell_text: str) -> tuple[float | None, float | None]:
    """
    Split a cell like '+402.90 USD +0.04%' into (usd_value, pct_value).
    Also handles cells with just USD or just %.
    """
    if cell_text is None or _NO_DATA_RE.match(_normalize(cell_text)):
        return None, None
    usd = parse_usd_value(cell_text)
    pct = parse_pct_value(cell_text)
    return usd, pct

# ---------------------------------------------------------------------------
# Page extraction
# ---------------------------------------------------------------------------

async def extract_summary_bar(page: Page) -> dict:
    """
    Extract the 5 summary metrics from the Strategy Report equity chart summary bar.
    Returns a perf_summary dict.
    """
    summary = {
        "total_pnl_usd": None,
        "total_pnl_pct": None,
        "max_drawdown_usd": None,
        "max_drawdown_pct": None,
        "total_trades": None,
        "profitable_pct": None,
        "profitable_ratio": None,
        "profit_factor": None,
    }

    async def _get_card_text(label: str) -> str | None:
        """Find a summary card by its label text, go up 2 levels to card container,
        and return all inner_text. Bug 1 fix: xpath=../.. gets to card container
        so we capture both label row and value row text."""
        el = page.locator(f"text='{label}'").first
        if not await el.count():
            log.debug(f"Summary card label '{label}' not found")
            return None
        # Go up 2 levels: label element -> label row -> card container
        card = el.locator("xpath=../..").first
        if not await card.count():
            log.debug(f"Summary card container not found for '{label}', trying parent")
            card = el.locator("xpath=..").first
        if not await card.count():
            return None
        raw = await card.inner_text()
        log.debug(f"Summary card '{label}' raw text: {raw!r}")
        return raw

    try:
        # Bug 1 fix: For each summary label, go up 2 levels to card container,
        # then get all inner_text which includes both label and value rows.

        # Total P&L
        raw = await _get_card_text("Total P&L")
        if raw:
            summary["total_pnl_usd"] = parse_usd_value(raw)
            summary["total_pnl_pct"] = parse_pct_value(raw)

        # Max equity drawdown
        raw = await _get_card_text("Max equity drawdown")
        if raw:
            summary["max_drawdown_usd"] = parse_usd_value(raw)
            summary["max_drawdown_pct"] = parse_pct_value(raw)

        # Total trades
        raw = await _get_card_text("Total trades")
        if raw:
            raw_clean = raw.replace("Total trades", "").strip()
            summary["total_trades"] = parse_int_value(raw_clean)

        # Profitable trades
        raw = await _get_card_text("Profitable trades")
        if raw:
            summary["profitable_pct"] = parse_pct_value(raw)
            # Extract ratio like "3/3"
            m = re.search(r"(\d+/\d+)", raw)
            if m:
                summary["profitable_ratio"] = m.group(1)

        # Profit factor
        raw = await _get_card_text("Profit factor")
        if raw:
            raw_clean = raw.replace("Profit factor", "").strip()
            if not _NO_DATA_RE.match(_normalize(raw_clean)):
                try:
                    summary["profit_factor"] = float(_normalize(raw_clean).replace(",", ""))
                except ValueError:
                    pass

    except Exception as e:
        log.warning(f"Summary bar extraction error: {e}")

    return summary


async def extract_performance_table(page: Page) -> dict:
    """
    Click the Performance sub-tab and extract metrics from the table.
    Returns a perf_detail dict.
    """
    detail = {
        "net_profit_usd": None,
        "net_profit_pct": None,
        "gross_profit_usd": None,
        "gross_loss_usd": None,
        "buy_hold_return_usd": None,
        "buy_hold_return_pct": None,
        "strategy_outperformance_usd": None,
        "cagr_pct": None,
        "return_on_initial_capital_pct": None,
        "max_drawdown_intrabar_usd": None,
        "max_drawdown_intrabar_pct": None,
        "max_drawdown_c2c_usd": None,
        "max_drawdown_c2c_pct": None,
        "max_runup_intrabar_usd": None,
        "max_runup_intrabar_pct": None,
        "max_runup_c2c_usd": None,
        "max_runup_c2c_pct": None,
        "expected_payoff_usd": None,
    }

    # Map: lowercase label prefix -> (detail_key_usd, detail_key_pct) or just (detail_key,)
    # Bug 3 fix: Use specific prefixes for intrabar vs close-to-close drawdown/runup.
    # More specific entries MUST come before less specific ones so they match first.
    # Using a list of tuples to guarantee ordering.
    METRIC_MAP_LIST = [
        ("max equity drawdown (intrabar)", ("max_drawdown_intrabar_usd", "max_drawdown_intrabar_pct")),
        ("max equity drawdown (close-to-close)", ("max_drawdown_c2c_usd", "max_drawdown_c2c_pct")),
        ("max equity run-up (intrabar)", ("max_runup_intrabar_usd", "max_runup_intrabar_pct")),
        ("max equity run-up (close-to-close)", ("max_runup_c2c_usd", "max_runup_c2c_pct")),
        ("max equity run up (intrabar)", ("max_runup_intrabar_usd", "max_runup_intrabar_pct")),
        ("max equity run up (close-to-close)", ("max_runup_c2c_usd", "max_runup_c2c_pct")),
        ("net profit", ("net_profit_usd", "net_profit_pct")),
        ("gross profit", ("gross_profit_usd", None)),
        ("gross loss", ("gross_loss_usd", None)),
        ("buy & hold return", ("buy_hold_return_usd", "buy_hold_return_pct")),
        ("buy and hold return", ("buy_hold_return_usd", "buy_hold_return_pct")),
        ("strategy outperformance", ("strategy_outperformance_usd", None)),
        ("annualized return", (None, "cagr_pct")),
        ("return on initial capital", (None, "return_on_initial_capital_pct")),
        ("expected payoff", ("expected_payoff_usd", None)),
    ]

    try:
        # Click Performance sub-tab
        perf_tab = page.locator("button:has-text('Performance'), [role='tab']:has-text('Performance')").first
        if await perf_tab.count():
            await perf_tab.click()
            await asyncio.sleep(1.5)
        else:
            log.debug("Performance sub-tab not found")
            return detail

        # Get all table rows
        rows = page.locator("table tr, [role='row']")
        row_count = await rows.count()
        log.debug(f"Found {row_count} table rows")

        matched_count = 0
        for i in range(row_count):
            row = rows.nth(i)
            cells = row.locator("td, [role='cell']")
            cell_count = await cells.count()
            if cell_count < 2:
                continue

            label_text = await cells.nth(0).inner_text()
            label_lower = label_text.lower().strip()
            # Remove "show description" suffix
            label_lower = re.sub(r"\s*show\s+description\s*", "", label_lower).strip()

            # "All" column is typically the second cell (index 1)
            all_cell_text = await cells.nth(1).inner_text()
            log.debug(f"Perf table row: label={label_lower!r} value={all_cell_text!r}")

            for prefix, keys in METRIC_MAP_LIST:
                if label_lower.startswith(prefix):
                    usd_val, pct_val = split_usd_pct(all_cell_text)
                    usd_key = keys[0] if len(keys) > 0 else None
                    pct_key = keys[1] if len(keys) > 1 else None
                    if usd_key and usd_val is not None:
                        detail[usd_key] = usd_val
                    if pct_key and pct_val is not None:
                        detail[pct_key] = pct_val
                    # For fields that are pct-only (like CAGR), try pct from cell
                    if usd_key is None and pct_key and pct_val is None:
                        detail[pct_key] = parse_pct_value(all_cell_text)
                    # For fields that are usd-only (like gross profit), ensure we got it
                    if pct_key is None and usd_key and usd_val is None:
                        detail[usd_key] = parse_usd_value(all_cell_text)
                    matched_count += 1
                    log.debug(f"  -> matched prefix={prefix!r} usd={usd_val} pct={pct_val}")
                    break

        log.info(f"Performance table: {row_count} rows found, {matched_count} matched")

    except Exception as e:
        log.warning(f"Performance table extraction error: {e}")

    return detail


async def extract_engagement(page: Page) -> dict:
    """Extract views, boosts, and script type from the page."""
    engagement = {
        "views": None,
        "boosts": None,
        "script_type": None,
    }

    try:
        # Views: look for text containing "Views" nearby a number
        # Could be in various elements. Try common patterns.
        page_text = await page.inner_text("body")

        # Script type
        text_upper = page_text.upper()
        if "OPEN-SOURCE SCRIPT" in text_upper or "OPEN SOURCE SCRIPT" in text_upper:
            engagement["script_type"] = "open-source"
        elif "INVITE-ONLY SCRIPT" in text_upper or "INVITE ONLY SCRIPT" in text_upper:
            engagement["script_type"] = "invite-only"
        elif "PROTECTED SCRIPT" in text_upper:
            engagement["script_type"] = "protected"

        # Bug 4 fix: Views — the element with accessible name "Views" contains
        # the count as inner text (alongside an img). Get inner_text of the element itself.
        views_el = page.locator(":text('Views')").first
        if await views_el.count():
            raw = await views_el.inner_text()
            log.debug(f"Views element raw text: {raw!r}")
            # Remove the word "Views" and parse what's left
            raw_num = raw.replace("Views", "").strip()
            if raw_num:
                engagement["views"] = parse_int_value(raw_num)
            # If inner_text didn't have the number, try the parent
            if engagement["views"] is None:
                parent = views_el.locator("xpath=..").first
                if await parent.count():
                    raw = await parent.inner_text()
                    log.debug(f"Views parent raw text: {raw!r}")
                    raw_num = raw.replace("Views", "").strip()
                    engagement["views"] = parse_int_value(raw_num)

        # Bug 4 fix: Boosts — button text is like "117 boosts 1 1 7"
        # Extract just the first number before the word "boost"
        boost_el = page.locator("button:has-text('boost')").first
        if await boost_el.count():
            raw = await boost_el.inner_text()
            log.debug(f"Boost button raw text: {raw!r}")
            # Match digits (with optional spaces as thousands) before "boost"
            m = re.search(r"(\d[\d\s]*?)\s*boost", raw.lower())
            if m:
                engagement["boosts"] = parse_int_value(m.group(1))

    except Exception as e:
        log.warning(f"Engagement extraction error: {e}")

    return engagement


async def scrape_strategy(page: Page, url: str) -> dict | None:
    """
    Scrape a single strategy page. Returns dict with perf_summary, perf_detail,
    engagement — or None if this isn't a strategy page.
    """
    log.info(f"Navigating to {url}")

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)
    except PlaywrightTimeout:
        log.warning(f"Timeout loading {url}")
        return None
    except Exception as e:
        log.warning(f"Navigation error for {url}: {e}")
        return None

    # Click "Strategy report" tab
    strategy_tab = page.locator(
        "button:has-text('Strategy report'), "
        "[role='tab']:has-text('Strategy report'), "
        "a:has-text('Strategy report')"
    ).first

    if not await strategy_tab.count():
        log.info(f"No 'Strategy report' tab found — skipping {url}")
        return None

    try:
        await strategy_tab.click()
        await asyncio.sleep(2.5)
    except Exception as e:
        log.warning(f"Error clicking Strategy report tab: {e}")
        return None

    # Extract summary bar (equity chart view is default)
    perf_summary = await extract_summary_bar(page)

    # Extract performance table
    perf_detail = await extract_performance_table(page)

    # Extract engagement (can be grabbed from any view of the page)
    engagement = await extract_engagement(page)

    return {
        "perf_summary": perf_summary,
        "perf_detail": perf_detail,
        "engagement": engagement,
    }

# ---------------------------------------------------------------------------
# Save helper
# ---------------------------------------------------------------------------

def save_data(strategies: list, output_path: Path):
    """Atomic-ish save: write to tmp then rename."""
    tmp_path = output_path.with_suffix(".tmp.json")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(strategies, f, indent=2, ensure_ascii=False)
    tmp_path.rename(output_path)
    log.info(f"Saved {len(strategies)} strategies to {output_path}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    parser = argparse.ArgumentParser(description="TradingView Strategy Performance Scraper")
    parser.add_argument("--input", type=str, default=str(DEFAULT_INPUT),
                        help="Path to input JSON file")
    parser.add_argument("--output", type=str, default=None,
                        help="Path to output JSON file (defaults to same as input)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max number of strategies to scrape")
    parser.add_argument("--delay", type=float, default=3.0,
                        help="Delay between pages in seconds (default: 3)")
    parser.add_argument("--start-from", type=int, default=0,
                        help="Index to start from (0-based)")
    parser.add_argument("--headless", action="store_true", default=True,
                        help="Run browser headless (default: True)")
    parser.add_argument("--no-headless", action="store_true",
                        help="Run browser with visible window")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else input_path
    headless = not args.no_headless

    # Load strategies
    if not input_path.exists():
        log.error(f"Input file not found: {input_path}")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        strategies = json.load(f)

    log.info(f"Loaded {len(strategies)} strategies from {input_path}")

    # Determine which to process
    to_process = []
    for idx, strat in enumerate(strategies):
        if idx < args.start_from:
            continue
        if strat.get("perf_scraped"):
            log.debug(f"Skipping #{idx} (already scraped)")
            continue
        if not strat.get("script_url"):
            log.debug(f"Skipping #{idx} (no script_url)")
            continue
        to_process.append((idx, strat))
        if args.limit and len(to_process) >= args.limit:
            break

    log.info(f"Will scrape {len(to_process)} strategies (start_from={args.start_from}, limit={args.limit})")

    if not to_process:
        log.info("Nothing to scrape. Done.")
        return

    # Launch browser
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        scraped_count = 0
        failed_count = 0

        for batch_idx, (idx, strat) in enumerate(to_process):
            url = strat["script_url"]
            log.info(f"[{batch_idx + 1}/{len(to_process)}] Strategy #{idx}: {url}")

            try:
                result = await scrape_strategy(page, url)

                if result is None:
                    log.info(f"Strategy #{idx}: no data (not a strategy or error)")
                    strat["perf_scraped"] = True
                    strat["perf_scraped_at"] = datetime.now(timezone.utc).isoformat()
                    strat["perf_summary"] = None
                    strat["perf_detail"] = None
                    strat["engagement"] = strat.get("engagement", {})
                    failed_count += 1
                else:
                    strat["perf_scraped"] = True
                    strat["perf_scraped_at"] = datetime.now(timezone.utc).isoformat()
                    strat["perf_summary"] = result["perf_summary"]
                    strat["perf_detail"] = result["perf_detail"]
                    eng = result["engagement"]
                    # Bug 4 fix: fallback boosts from original scrape data
                    if eng.get("boosts") is None and strat.get("boost_count") is not None:
                        eng["boosts"] = strat["boost_count"]
                    strat["engagement"] = eng
                    scraped_count += 1
                    log.info(
                        f"Strategy #{idx}: "
                        f"PnL={result['perf_summary'].get('total_pnl_usd')}, "
                        f"Trades={result['perf_summary'].get('total_trades')}, "
                        f"Views={result['engagement'].get('views')}"
                    )

            except Exception as e:
                log.error(f"Strategy #{idx} unexpected error: {e}", exc_info=True)
                failed_count += 1

            # Progress save every 10
            if (batch_idx + 1) % 10 == 0:
                save_data(strategies, output_path)

            # Rate limit delay (skip after last item)
            if batch_idx < len(to_process) - 1:
                await asyncio.sleep(args.delay)

        # Final save
        save_data(strategies, output_path)

        await browser.close()

    log.info(f"Done. Scraped: {scraped_count}, Failed/Skipped: {failed_count}")


if __name__ == "__main__":
    asyncio.run(main())
