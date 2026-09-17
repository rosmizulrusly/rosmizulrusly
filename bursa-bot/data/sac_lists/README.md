# SAC list editions (point-in-time)

One JSON file per published edition of the **List of Shariah-Compliant Securities**
issued by the Shariah Advisory Council (SAC) of the Securities Commission Malaysia.
Editions take effect on the **last Friday of May and of November**.

Download the real lists from
<https://www.sc.com.my/development/icm/icm-publications/list-of-shariah-compliant-securities>.
They are published as PDFs, so the import step is semi-manual:

1. Extract the stock codes from the PDF into a plain text file, one code per line.
2. `bursabot sac-import --codes codes.txt --effective 2025-11-28 --source "SC SAC list, Nov 2025"`
3. Check the reported count against the figure quoted in the SC's press release.
4. Edit the generated file and set `"verified": true`.

**The two files shipped here are synthetic samples** (codes `9001`-`9020`, which are
not real Bursa listings) so the tests and the demo backtest run without a download.
They are marked `"verified": false`, and the store warns about any unverified edition.
Delete them once you have imported real data.

Keeping every edition matters: the backtester resolves the list *as of* each
simulated day. Screening history against the current list is look-ahead bias.
