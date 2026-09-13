# bursabot

A scaffold for a **Shariah-screened, long-only** trading bot for **Bursa Malaysia**.

It is deliberately boring and deliberately strict. The interesting parts of a trading
bot are not the signals — they are the fee model, the compliance rules and the honesty
of the backtest. Those are what this repository implements properly; the strategy
included is a plain trend rule you are expected to replace.

**Not investment advice, and not a Shariah ruling.** Verify every fee, holiday and
compliance decision against primary sources before risking money. See
[Disclaimers](#disclaimers).

---

## What it does

- **Shariah screen as a hard gate.** The SAC list is applied *before* signals, so a
  non-compliant name can never reach the strategy or the broker.
- **Point-in-time compliance.** Backtests resolve the SAC list *as of* each simulated
  day. Screening ten years of history with today's list is look-ahead bias, and the
  store refuses it outright rather than quietly flattering your results.
- **Forced exits and purification.** When a holding leaves the SAC list, the engine
  exits it and books any gain above the announcement-day close to a charity ledger.
- **No margin, no shorts — enforced at the broker.** `GuardedBroker` refuses a sale
  larger than the holding and a buy larger than the cash balance. A strategy bug
  cannot produce a riba-bearing or short position.
- **A real Bursa cost model.** Tiered tick sizes, 100-share board lots, minimum
  brokerage, clearing fee and cap, stamp duty rounded up per RM1,000 and capped,
  and SST. Round-trip cost on a small ticket is ~1–2%, and the sizing layer drops
  tickets that cannot clear their own fees.
- **A calendar that fails loudly.** Two sessions a day, T+2 settlement, and a hard
  error for any year with no holiday data rather than an assumption that Bursa is open.

## Quickstart

```bash
cd bursa-bot
pip install -e .                  # stdlib only; pip install -e '.[data]' adds yfinance
python -m unittest discover -s tests -t tests    # or: pytest

bursabot demo-data                # synthetic prices so the pipeline runs end to end
bursabot screen                   # today's tradeable universe
bursabot sac-diff                 # what the latest SAC edition added and removed
bursabot costs 2.50 4000          # full fee breakdown for one trade
bursabot calendar                 # is Bursa open, and when does this trade settle
bursabot backtest                 # run the strategy
bursabot ledger                   # purification (charity) amounts owed
bursabot check                    # screen the counters you already hold
bursabot daily                    # today's recommended orders, as alerts
```

The shipped SAC editions and price data are **synthetic samples** (codes `9001`–`9020`,
which are not real Bursa listings) so everything runs before you download anything.
Every command warns while unverified data is in place.

## Using it with M+ Online (Malacca Securities)

M+ Online has no public order-placement API, so the bot runs in **alert-only** mode:
it decides, you place the order. Two things about this broker are worth knowing:

- **M+ Silver is a cash-upfront account**, so you are structurally unable to trade on
  margin — that matches the bot's no-margin rule instead of fighting it.
- **Malacca Securities is a window-based Islamic Participating Organisation on Bursa
  Malaysia-i.** Ask them to open a Shariah-compliant trading account and the brokerage,
  settlement and cash legs are Shariah-structured too, not just the stock list.

```bash
cp config.mplus.toml config.toml          # brokerage 0.05% / min RM8 - confirm yours
cp portfolio.example.json portfolio.json  # then edit in your actual counters

bursabot fetch --symbols 5285,6012,1961   # real history from Yahoo (.KL handled for you)
bursabot check                            # are my counters on the SAC list?
bursabot daily                            # what would the strategy do today?
```

`portfolio.json` is yours to keep in step with your contract notes — the bot cannot see
your account. Use your **all-in** entry price as `cost_basis` (contract value plus
brokerage, clearing fee, stamp duty and SST, divided by shares).

### `check` before `daily`

`bursabot check` is useful on day one and carries no strategy risk: it screens the
counters you already hold against the SAC edition in force and tells you which, if any,
must be disposed of and what the purification rule means for them.

`bursabot daily` is the strategy, and it needs a **candidate universe**, not just your
holdings. It ranks names against each other, so fed only the counters you own it can
tell you what to sell and never what to buy — it warns when the screened universe is
smaller than `top_n`. Fetch a real candidate list (the FBM Hijrah Shariah constituents
are a sane starting point) before its buy side means anything.

### Ticket size matters more than the strategy

At M+ Silver rates, round-trip cost is about **0.61% on an RM5,000 ticket** and **0.37%
on RM20,000**. That is the hurdle every trade must clear before it makes you anything,
which is why `min_ticket_value` defaults to RM5,000 in the preset and `top_n` to 6.
A small account holding ten positions pays the RM8 minimum brokerage ten times over.

## Getting real data in

**SAC list** — download each edition from the
[SC's ICM publications](https://www.sc.com.my/development/icm/icm-publications/list-of-shariah-compliant-securities).
Editions take effect on the last Friday of **May** and **November**. They are PDFs, so
extract the stock codes into a text file (one per line) and import:

```bash
bursabot sac-import --codes codes.txt --effective 2025-11-28 --source "SC SAC list Nov 2025"
```

Check the reported count against the SC's press release, then set `"verified": true` in
the generated file. Keep **every** edition — deleting old ones breaks point-in-time
backtesting. Delete the synthetic samples once real data is in.

**Prices** — Bursa tickers on Yahoo carry a `.KL` suffix (`1155.KL`; the index is
`^KLSE`). `bursabot.data.yahoo.fetch_daily` handles this with the optional `yfinance`
extra. Free data is fine for end-of-day backtesting and is **not** fine for intraday
work. Adjust for splits, bonus issues and dividends before storing — unadjusted
Malaysian history invents overnight gaps that any momentum rule will happily trade.

**Holidays** — `data/calendar/holidays.json` ships marked `"verified": false`. Islamic
holidays depend on moon sighting and are often gazetted late. Check each year against
Bursa's official trading calendar and flip the flag.

## Architecture

```
data/         price ingest and local CSV store
shariah/      point-in-time SAC lists, screen, forced exits, purification ledger
universe/     Shariah filter first, then liquidity and history filters
signals/      strategy: prices in -> target weights out
risk/         sizing, exposure caps, ADV participation, kill switch
costs.py      Bursa fees, tick sizes, board lots
calendar_my.py  sessions, holidays, T+2 settlement
backtest/     event-driven engine sharing the live cost and risk code paths
execution/    Broker protocol + GuardedBroker | AlertOnlyBroker | PaperBroker
monitor/      console and Telegram notifiers
```

Backtest and live call the **same** `signals`, `risk`, `costs` and guard code. If a
backtester keeps its own copy of that logic, live results diverge and you cannot tell why.

## Execution: start in alert-only mode

Most Malaysian retail brokers expose no public order-placement API, so the default
adapter is `AlertOnlyBroker` — the bot decides, sends you the order, and you place it.
It needs no broker API, it is unambiguously permitted under every broker's terms, and it
makes you watch the strategy's decisions for months before code touches real money.

Wiring a real broker means implementing the `Broker` protocol and wrapping it in
`GuardedBroker`; nothing above that layer changes. Realistic options today are
**moomoo MY's OpenAPI** (via OpenD — confirm it accepts *orders*, not only quotes, on
Bursa-listed stocks for your account type) and **Bursa Derivatives futures** through a
broker offering FIX or an ATS. Confirm with your broker that automated order entry is
permitted under your account terms first. Do not scrape or browser-automate a broker
portal: it violates their terms, breaks silently, and can get the account suspended.

For end-to-end Shariah structuring, trade through **Bursa Malaysia-i**, where the
brokerage, settlement and cash accounts are Shariah-structured — not just the stock list.

## Build order

1. Real data in: SAC editions, adjusted prices, a verified holiday calendar.
2. Confirm the fee model against an actual contract note from your broker.
3. Replace the trend rule with your own strategy.
4. Backtest honestly: walk-forward, out-of-sample holdout, a survivorship-bias-free
   universe including delisted names, and at least one tick of slippage. Compare
   against buy-and-hold **FBM Hijrah Shariah** — if it does not beat that after costs,
   stop here.
5. Paper trade for three months or more on live data. Expect the gap to be ugly.
6. Go live tiny, with the kill switch armed.

Applying machine learning to daily Bursa bars is the classic trap: ~900 names, thin
liquidity, ~1% round-trip costs and limited clean history means you will overfit long
before you find an edge. Get steps 1–5 working with a dumb rule first.

## What it does NOT model

Dividends, corporate actions beyond whatever your price adjustment already applied,
price limits and trading halts, UMA queries, partial fills, queue position, and contra
settlement. Treat any backtest result as an upper bound.

## Disclaimers

- **Not investment advice.** Trading your own money with your own bot needs no licence
  in Malaysia, but managing anyone else's money or selling signals is regulated activity
  under the CMSA 2007 and requires a CMSL from the Securities Commission.
- **Not a Shariah ruling.** This code *applies* the SAC list; it does not issue rulings.
  For futures, Islamic margin, crypto, or purification on a real portfolio, consult a
  qualified Shariah advisor or your Islamic broker's Shariah committee. If you follow a
  stricter standard than the SAC (AAOIFI requires dividend purification even for
  listed-compliant companies), tighten the screen in `shariah/`.
- **Fee, tick and holiday figures are defaults, not quotes.** Confirm them against
  Bursa's published schedules and your own contract notes.
- Check any platform against the SC's Investor Alert List and Bank Negara's Financial
  Consumer Alert List before sending it money.

## References

- [SC — Shariah-compliant securities](https://www.sc.com.my/development/icm/shariah-compliant-securities)
  and [screening methodology](https://www.sc.com.my/development/icm/shariah-compliant-securities/shariah-compliant-securities-screening-methodology)
- [SAC resolutions](https://www.sc.com.my/development/icm/shariah/resolutions-of-the-shariah-advisory-council-of-the-sc)
- [Bursa — transaction costs, fees and charges](https://www.bursamalaysia.com/trade/post_trade/transaction_costs_fees_charges)
- [Bursa — board lot](https://www.bursamalaysia.com/trade/trading_resources/equities/board_lot)
- [Bursa — FAQs on Shariah non-compliant securities](https://www.bursamalaysia.com/reference/faqs/islamic_market/faqs_on_shariah_non_compliant_securities)
- [Bursa Malaysia-i](https://www.bursamalaysia.com/trade/our_products_services/islamic_market/bursa_malaysia_i/overview)

MIT licensed.
