"""bursabot - a Shariah-screened, long-only trading bot scaffold for Bursa Malaysia.

Design rules baked into this package:

1. The Shariah universe filter runs *before* signals, so a non-compliant name can
   never reach the strategy.
2. Backtests use point-in-time SAC lists. Screening history with today's list is
   look-ahead bias and is refused by `shariah.list_store`.
3. No margin and no short selling, asserted at the broker adapter (`execution.base`)
   rather than only in the strategy.
4. Backtest and live share the same cost, sizing and signal code paths.
"""

__version__ = "0.1.0"
