#!/Users/nyra/Projects/pyhood/.venv/bin/python
"""
TradingView Pine Script Source Code Scraper
Extracts Pine Script source code from TradingView strategy pages.

Usage:
    ./tv_source_scrape.py
    ./tv_source_scrape.py --input data/candidates_71.json --limit 10 --delay 5
    ./tv_source_scrape.py --start-from 20 --limit 10
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
DATA_DIR = SCRIPT_DIR / "data"
DEFAULT_INPUT = DATA_DIR / "candidates_71.json"
PINE_DIR = DATA_DIR / "pine_scripts"
INDEX_FILE = PINE_DIR / "index.json"
LOG_FILE = DATA_DIR / "pine_scrape.log"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging() -> logging.Logger:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PINE_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("tv_source_scrape")
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
# Helpers
# ---------------------------------------------------------------------------

def sanitize_filename(title: str) -> str:
    """Convert title to a safe filename slug."""
    s = title.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "_", s)
    return s[:120]  # cap length


def load_index() -> dict:
    """Load existing index.json or return empty dict."""
    if INDEX_FILE.exists():
        try:
            return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_index(index: dict) -> None:
    """Persist index.json."""
    INDEX_FILE.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")


PROTECTED_PATTERNS = [
    "source code is not available",
    "source code is protected",
    "invite-only",
    "this script is published closed-source",
    "this publication is closed-source",
]


async def extract_source_code(page: Page) -> str | None:
    """
    After navigating to source code tab, extract Pine Script text.
    Returns the source string or None if protected/empty.
    """
    # Strategy 1: Monaco editor view-lines (most common)
    view_lines = await page.query_selector_all(".view-line")
    if view_lines:
        lines = []
        for vl in view_lines:
            text = await vl.inner_text()
            lines.append(text)
        code = "\n".join(lines)
        if code.strip():
            return code.strip()

    # Strategy 2: look for pre/code elements in the tab content
    for selector in ["pre", "code", ".pine-editor", "[class*='source'] pre",
                     "[class*='code'] pre", "textarea"]:
        els = await page.query_selector_all(selector)
        for el in els:
            text = await el.inner_text() if selector != "textarea" else await el.input_value()
            if text and "//@version=" in text:
                return text.strip()

    # Strategy 3: look for anything containing //@version= in the page body
    body_text = await page.inner_text("body")
    match = re.search(r"(//@version=\d[\s\S]*)", body_text)
    if match:
        return match.group(1).strip()

    return None


async def is_protected(page: Page) -> bool:
    """Check if the source code is protected/invite-only."""
    try:
        body = (await page.inner_text("body")).lower()
        return any(p in body for p in PROTECTED_PATTERNS)
    except Exception:
        return False


async def scrape_one(page: Page, strategy: dict, delay: float) -> str | None:
    """
    Scrape Pine Script source for a single strategy.
    Returns the source code string or None.
    """
    url = strategy["script_url"]
    title = strategy["title"]

    log.info(f"Navigating to: {title}")
    log.debug(f"URL: {url}")

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await asyncio.sleep(2)  # let page settle
    except PlaywrightTimeout:
        log.warning(f"Timeout loading page: {title}")
        return None
    except Exception as e:
        log.warning(f"Error loading page for {title}: {e}")
        return None

    # Click "Source code" tab
    tab_clicked = False
    for tab_selector in [
        'button:has-text("Source code")',
        '[role="tab"]:has-text("Source code")',
        'a:has-text("Source code")',
        'div[class*="tab"]:has-text("Source code")',
        'span:has-text("Source code")',
    ]:
        try:
            tab = page.locator(tab_selector).first
            if await tab.count() > 0:
                await tab.click(timeout=5_000)
                tab_clicked = True
                log.debug(f"Clicked tab with selector: {tab_selector}")
                break
        except Exception:
            continue

    if not tab_clicked:
        log.warning(f"Could not find Source code tab for: {title}")
        return None

    # Wait for content to render
    await asyncio.sleep(2)

    # Check if protected
    if await is_protected(page):
        log.info(f"PROTECTED/invite-only, skipping: {title}")
        return None

    # Extract source
    code = await extract_source_code(page)

    if not code:
        log.warning(f"No source code found for: {title}")
        return None

    # Validate it looks like Pine Script
    if "//@version=" not in code and "strategy(" not in code and "indicator(" not in code:
        log.warning(f"Extracted text doesn't look like Pine Script for: {title}")
        return None

    log.info(f"Extracted {len(code)} chars of Pine Script for: {title}")
    return code


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    parser = argparse.ArgumentParser(description="Scrape Pine Script source from TradingView")
    parser.add_argument("--input", type=str, default=str(DEFAULT_INPUT),
                        help="Input JSON file with script_url and title")
    parser.add_argument("--delay", type=float, default=3.0,
                        help="Delay between requests in seconds (default: 3)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max strategies to process (0 = all)")
    parser.add_argument("--start-from", type=int, default=0,
                        help="Index to start from (for chunking)")
    args = parser.parse_args()

    # Load input
    input_path = Path(args.input)
    if not input_path.exists():
        log.error(f"Input file not found: {input_path}")
        sys.exit(1)

    strategies = json.loads(input_path.read_text(encoding="utf-8"))
    total = len(strategies)
    log.info(f"Loaded {total} strategies from {input_path.name}")

    # Slice based on start-from / limit
    end = total
    if args.limit > 0:
        end = min(args.start_from + args.limit, total)
    batch = strategies[args.start_from:end]
    log.info(f"Processing indices {args.start_from}..{end - 1} ({len(batch)} strategies)")

    # Load existing index
    index = load_index()

    PINE_DIR.mkdir(parents=True, exist_ok=True)

    stats = {"scraped": 0, "skipped_exists": 0, "protected": 0, "failed": 0}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        for i, strat in enumerate(batch):
            title = strat["title"]
            url = strat["script_url"]
            fname = sanitize_filename(title) + ".pine"
            fpath = PINE_DIR / fname

            # Resume support: skip if file already exists
            if fpath.exists() and fpath.stat().st_size > 0:
                log.info(f"[{i+1}/{len(batch)}] Already exists, skipping: {fname}")
                stats["skipped_exists"] += 1
                # Ensure index entry
                if title not in index:
                    index[title] = {"filename": fname, "script_url": url}
                    save_index(index)
                continue

            log.info(f"[{i+1}/{len(batch)}] Scraping: {title}")

            code = await scrape_one(page, strat, args.delay)

            if code is None:
                # Check if it was protected
                if await is_protected(page):
                    stats["protected"] += 1
                else:
                    stats["failed"] += 1
            else:
                # Save .pine file
                fpath.write_text(code, encoding="utf-8")
                log.info(f"Saved: {fname}")

                # Update index
                index[title] = {"filename": fname, "script_url": url}
                save_index(index)
                stats["scraped"] += 1

            # Rate limit
            if i < len(batch) - 1:
                await asyncio.sleep(args.delay)

        await browser.close()

    log.info(
        f"Done. scraped={stats['scraped']} skipped={stats['skipped_exists']} "
        f"protected={stats['protected']} failed={stats['failed']}"
    )


if __name__ == "__main__":
    asyncio.run(main())
