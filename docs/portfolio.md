# Portfolio presentation

Suggested repository name: `market-ledger`.

Suggested GitHub description:

> Portable C++17 trading simulator with price-time order matching, basket instruments,
> fee-aware cross-market spread analysis, and an interactive offline report.

Suggested topics: `cpp`, `cpp17`, `algorithmic-trading`, `order-book`,
`market-microstructure`, `simulation`, `arbitrage`, `cmake`.

Suggested portfolio text:

> Market Ledger is a local market simulation and analysis project. It uses ordered
> price levels, FIFO queues, and an expiry heap to model deterministic order
> execution. The project includes integer-cent cash accounting, basket instrument
> normalization, cross-market quote analysis, randomized reference testing, and
> a browser-viewable session report with no runtime dependencies.

Suggested demonstration:

1. Build and run tests using the README instructions.
2. Generate the HTML report with `python tools/report.py` and open `build/report.html`.
3. Explain why the best price executes first and equal-price orders use arrival order.
4. Show the expired BETA order and the prevented GAMMA self-trade in the demo input.
5. Filter the execution ledger by `Cedar`, then sort by largest traded value.
6. Show the ALPHA quote route and explain the distinction between a spread and realized profit.
7. Show the randomized reference test and the cash/quantity conservation assertions.

The native CLI, engine, tests, and offline report are the deliverable. Live trading,
profitability, exchange-grade performance, and production broker deployment are
not claims made by this version. Keep `LICENSE` and `THIRD_PARTY_NOTICES.md` when
publishing.

## Manual GitHub upload

Open the standalone `MarketLedger` project folder and upload its source files to a
new repository in the `thejas-droid` account. Exclude generated `build` and
`release` directories. Include hidden
files `.github`, `.gitignore`, and `.gitattributes` in the upload; the `.github`
workflow may need to be added through Git locally if your browser omits it.

If you use Git, run these commands **inside the standalone MarketLedger folder**:

```sh
git init
git add .
git commit -m "Release Market Ledger 1.0.0"
git branch -M main
git remote add origin https://github.com/thejas-droid/market-ledger.git
git push -u origin main
```

Create the empty GitHub repository first, without an automatically added README
or license, since those files are already included. After upload, inspect the
Actions run for the Windows, Linux, macOS, and sanitizer checks. CI is configured
here; hosted runs are not verified until the repository has been pushed.

For a clean ZIP, run `python tools/export.py`. The ZIP includes a deterministic
source layout. `release/SHA256SUMS.txt` verifies
the archive; `release/MANIFEST.sha256` lists the SHA-256 of each exported file.
Regenerate the export after changing any published source or documentation.
