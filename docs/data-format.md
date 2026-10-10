# Input and output reference

Input is plain UTF-8 CSV with an exact header, no quoting or embedded commas,
and no whitespace around fields. Both LF and CRLF line endings are accepted.
Blank lines and lines beginning with `#` are ignored. A header with no data is a
valid empty session. Timestamps must be nondecreasing; ties preserve line order.

Identifiers contain 1–64 ASCII letters, digits, underscores, hyphens, or dots.
Symbols are case sensitive. Each file allows up to 10,000 events and 4,096 bytes
per line. Basket notation is described in [architecture.md](architecture.md).

## Orders

```csv
timestamp,id,broker,instrument,side,price,quantity,ttl
0,S1,Atlas,ALPHA,SELL,10000,8,-1
1,B1,Cedar,ALPHA,BUY,10050,5,-1
```

| Field | Meaning | Limits |
| --- | --- | --- |
| timestamp | Event time in your chosen consistent time unit | 0–10^12 |
| id | Unique order ID, including filled and expired orders | Identifier |
| broker | Owner used for cash accounting and self-trade prevention | Identifier |
| instrument | Symbol or normalized basket | Up to 16 input legs |
| side | Limit-order side | `BUY` or `SELL` |
| price | Positive integer cents per instrument/package | 1–10^8 |
| quantity | Positive whole instrument/package units | 1–10^6 |
| ttl | Inclusive lifetime in the timestamp unit | -1 (forever), or 0–10^12 |

Basket coefficients and their combined value per symbol must be between -10^6
and 10^6; all-zero baskets are rejected. An instrument string is at most 2,048
bytes. A price of `10000` means $100.00, not $10,000.

## Quotes

```csv
timestamp,venue,instrument,bid,ask,bid_size,ask_size
0,North,ALPHA,9980,10000,25,20
0,South,ALPHA,10025,10040,10,15
```

Timestamp and identifier rules match orders. Bid/ask use positive integer cents
in the range 1–10^8, with `bid <= ask` at each venue. Bid/ask sizes range from
0–10^6. A zero size withdraws liquidity on that side. The newest row replaces
the whole quote. Crossed venue quotes are rejected; spreads across distinct
venues are the opportunities the scanner evaluates.

## CLI and output

| Command/option | Behavior |
| --- | --- |
| `simulate --input PATH` | Execute the complete order stream |
| `arbitrage --input PATH` | Analyze the final quote snapshot |
| `--fee N` | Scanner fee per unit per leg, in cents; default 0, range 0–10^8 |
| `--max-age N` | Scanner quote age limit; default 5, range 0–10^12 |
| `--max-quantity N` | Scanner route cap; default 1000, range 1–10^6 |
| `--output PATH` | Write JSON to a new file; refuses an existing readable file |
| `--help` / `--version` | Show usage / version |

Only scanner commands accept scanner options. Duplicate and unknown options
are rejected. An invalid input produces exit code 1, an `error:` on stderr, and
no report on stdout. Input is fully validated before an output file is opened.
Successful commands exit with code 0 and produce one JSON object followed by a
newline. Existing reports must be removed or a new path chosen before writing.
Output paths should be local files under your control; output creation is not an
atomic exclusive-create operation for concurrent processes.

Simulation JSON contains submitted, expired, resting, and self-prevention counts;
traded units; gross turnover; the complete execution ledger; and per-broker
bought/sold units and signed net cash in cents. Cash received from selling is
positive. Cash paid to buy is negative. These cash movements do not measure P&L.

Arbitrage JSON contains independent opportunities, with instrument, buy/sell
venues, prices, capped quantity, net edge, and potential profit. It deliberately
has no realized-profit field. All monetary JSON keys end in `_cents`.

The HTML generator uses an assumed fee of **2 cents per unit per leg** by default;
the native scanner defaults to 0. Pass `--fee` explicitly to compare reports.
The report generator overwrites its generated HTML destination; native JSON
report output uses the no-overwrite behavior above.
