# Pyhood Development Log

## 2026-02-28 — Initial Setup

### Robinhood Trading Setup
- robin_stocks forked to github.com/jamestford/robin_stocks
- Cloned to ~/Projects/robin_stocks with venv
- 3 security fixes applied: updated deps (PR #1645), pickle→JSON (PR #1646), GET timeouts (fork-only)
- Authenticated to Robinhood successfully — device approval flow
- Creds stored in ~/.openclaw/secrets.json and ~/Projects/robin_stocks/.env
- Account: $16,102.84 cash, $16,175.83 buying power, 0.01 TSLA shares
- James plans to withdraw $5,000, recover via options trading
- Monday morning cron job set for 9:00 AM pre-market scan
- Plays: MRVL earnings (March 5, $4,500 in calls), XYZ momentum ($2,500 if dips), $4,100 cash reserve

### Trading Scanner Launch
- Built nightly options scanner: `~/.openclaw/workspace/trading/scripts/nightly_scanner.py`
- Scans 51 symbols, narrows to top 21 movers, pulls options chains
- Scoring: unusual volume (vol/OI ratio), delta, leverage efficiency, liquidity, IV penalty
- First successful run: 122 plays found in ~3 min
- Bug fixes: use default find_options_by_expiration() (market data embedded), use actual expiration dates from chains
- Suppressed robin_stocks spinner output (was burning tokens)
- Cron: `nightly-options-scan` runs midnight Mon-Fri, delivers briefing via Telegram
- Cron: `monday-premarket-scan` one-shot for March 2 at 9:00 AM (delete after run)

### Top Scan Results (Feb 28 close data)
1. MRVL $80 put — Score 74.33 ⚡EARNINGS (Mar 5) — smart money hedging with puts
2. AVGO $315 put — Score 67.88 ⚡EARNINGS (Mar 4) — same bearish hedging
3. XYZ $65 call — Score 63.14 — post-earnings momentum, 4.6x vol/OI
4. NVDA $180 call — Score 62.93 — 9.58x vol/OI, bounce bet
5. NFLX $100 call — Score 59.06 — 26.25x vol/OI insane unusual activity

## 2026-03-08 — Scanner Bug Fixes

### Cron Delivery Bug Fixed
- Root cause: cron agent was calling message tool with `@james` — not a valid Telegram ID
- Fix applied: `--to telegram:8211537861` on nightly-options-scan
- Agent prompt still tells it to "deliver to James via Telegram" — needs prompt update

## 2026-03-16 — Hood Project Launch

### New Modern Robinhood Client
- **Repo:** github.com/jamestford/hood (private)
- **Location:** ~/Projects/hood
- **Venv:** ~/Projects/hood/.venv (Python 3.14)
- **Goal:** Modern replacement for robin_stocks (abandoned, 300+ open issues, no releases since 2023)
- **Named "hood"** — `import hood` — simple, memorable
- **Credits:** README acknowledges Josh Fernandes / robin_stocks as foundation

### Architecture Built
- `hood/auth.py` — Login with timeouts, device approval handling, token refresh
- `hood/client.py` — HoodClient: quotes, options chains, earnings, positions, buying power
- `hood/http.py` — Rate-limited HTTP session with retries, pagination, accept_codes for login
- `hood/models.py` — Typed dataclasses: Quote, OptionContract, OptionsChain, Position, Order, Earnings
- `hood/exceptions.py` — Full hierarchy: LoginTimeoutError, DeviceApprovalRequiredError, MFARequiredError, TokenExpiredError, RateLimitError, etc.
- `hood/urls.py` — All Robinhood API endpoints
- `RATE_LIMITS.md` — Documented observed rate limit behavior

### Key Discovery: Token Refresh Works!
- **Refresh token flow is functional** — `hood.refresh()` exchanges refresh_token for new access+refresh tokens
- **NO device approval needed** for refresh — this is the killer feature robin_stocks never implemented
- **Token lifetime observed:** ~5-8 days (not 24h as commonly assumed). Robinhood ignores the `expiresIn` parameter.
- **Tokens rotate on refresh** — old tokens invalidated, new pair saved to `~/.hood/session.json`
- **login() auto-tries refresh** before falling back to full re-login
- This means the nightly scanner can self-heal by calling `hood.refresh()` — no human needed

### Testing & Quality
- 58 tests passing, ~79% coverage
- Tests use `responses` library for HTTP mocking
- CI pipeline: GitHub Actions on Python 3.10-3.13, ruff linting, coverage
- All 4 Python versions passing
- Live tested: login, refresh, quotes, buying power all confirmed working

### Auth Lessons (Hard-Won)
- Robinhood rate-limits auth AGGRESSIVELY: 2-3 failed attempts → account-wide 429 for 5+ minutes
- Device approval has short TTL — new login = new workflow, old approvals don't carry over
- NEVER retry auth without explicit human confirmation of approval
- robin_stocks headers: `Accept: */*`, `User-Agent: *` — Robinhood rejects other User-Agents
- Login endpoint returns 400/403 with valid JSON (verification data) — must accept these status codes
- Verification polling needs generous delays (8-10s) to avoid rate limits

### Scanner Issues Identified
- **Root cause:** Robinhood token expired March 6, scanner tried re-login → hung on device approval
- **March 9-10:** Scanner ran but produced 0 plays (silent failure — no options data)
- **March 11-15:** Scanner hung entirely on login, no output files
- **Fix needed:** Migrate scanner from robin_stocks to hood, use `hood.refresh()` for auth

