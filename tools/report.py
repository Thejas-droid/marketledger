"""Generate an interactive, self-contained HTML report. No server or network needed."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def execute(binary, command, path, *options):
    result = subprocess.run([str(binary), command, "--input", str(path), *options],
                            capture_output=True, text=True, timeout=30, check=True)
    return json.loads(result.stdout)


def render(simulation, analysis):
    def check_numbers(value):
        if isinstance(value, int) and abs(value) > 9007199254740991:
            raise ValueError("report exceeds browser integer precision; use the native JSON report")
        if isinstance(value, dict):
            for child in value.values():
                check_numbers(child)
        elif isinstance(value, list):
            for child in value:
                check_numbers(child)
    check_numbers(simulation)
    check_numbers(analysis)
    # JSON is text inside an HTML script element; escape HTML-significant characters.
    data = json.dumps({"simulation": simulation, "analysis": analysis}, separators=(",", ":"))
    data = data.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    return TEMPLATE.replace("__REPORT_DATA__", data)


TEMPLATE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark"><title>Market Ledger | Session report</title>
<style>
:root{--bg:#101316;--panel:#191e23;--edge:#30383e;--text:#ecf0ed;--muted:#a0ada8;--green:#bded85;--red:#f2988b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.6 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1240px;margin:auto;padding:32px}nav{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--edge);padding-bottom:22px;gap:16px}
.brand{font-weight:800;letter-spacing:-1px;font-size:23px}.mark{color:var(--green);margin-right:10px}.tag{font:11px/1.5 ui-monospace,monospace;text-transform:uppercase;letter-spacing:1.5px;color:var(--green);border:1px solid #526445;border-radius:30px;padding:5px 12px}
header{padding:55px 0 30px}.eyebrow{font:12px ui-monospace,monospace;letter-spacing:2px;color:var(--green);text-transform:uppercase}
h1{font-size:clamp(34px,5vw,60px);letter-spacing:-2.5px;line-height:1.1;margin:18px 0}p{color:var(--muted);max-width:700px}h2{font-size:18px;letter-spacing:-.3px;margin:0}.sub{font-size:12px;color:var(--muted);margin:5px 0 20px}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:10px 0 24px}.card,.panel{background:var(--panel);border:1px solid var(--edge);border-radius:12px}.card{padding:23px}.label{color:var(--muted);font-size:12px}.value{font:500 32px/1.4 ui-monospace,monospace;letter-spacing:-1px;margin:8px 0}.foot{font-size:11px;color:var(--muted)}
.grid{display:grid;grid-template-columns:1.5fr 1fr;gap:20px}.panel{padding:24px;margin-bottom:20px;overflow:hidden}.panelhead{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:15px}.chart{height:220px;width:100%;display:block}.axis{display:flex;justify-content:space-between;font-size:11px;color:var(--muted)}
input,select,button{background:var(--bg);color:var(--text);border:1px solid var(--edge);padding:9px 12px;border-radius:6px;font:inherit}input{max-width:230px}button{cursor:pointer}button:hover{border-color:var(--green)}button:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid var(--green);outline-offset:2px}
.scroll{overflow:auto}table{border-collapse:collapse;width:100%;text-align:left;white-space:nowrap;font-size:12px}th{color:var(--muted);font-weight:500;text-transform:uppercase;font-size:10px;letter-spacing:1px}td,th{padding:13px 12px;border-bottom:1px solid var(--edge)}td:first-child,th:first-child{padding-left:0}.num{font-family:ui-monospace,monospace}.positive{color:var(--green)}.negative{color:var(--red)}.empty{color:var(--muted);padding:25px 0}.route{border-top:1px solid var(--edge);padding:18px 0}.routehead{display:flex;justify-content:space-between;gap:12px;font-weight:600}.route p{font-size:12px;margin:6px 0}.route .profit{font:22px ui-monospace,monospace;color:var(--green)}
footer{display:flex;justify-content:space-between;gap:20px;margin:24px 0;font-size:11px;color:var(--muted)}.note{color:var(--muted);font-size:12px}.toolbar{display:flex;gap:10px;flex-wrap:wrap}.status{display:flex;gap:20px;flex-wrap:wrap;font-size:12px;color:var(--muted);margin-bottom:25px}
@media(max-width:850px){.metrics{grid-template-columns:repeat(2,1fr)}.grid{grid-template-columns:1fr}main{padding:20px}.panelhead{align-items:flex-start;flex-direction:column}header{padding-top:35px}footer{flex-direction:column}}
@media(prefers-reduced-motion:no-preference){.card{animation:enter .5s ease both}@keyframes enter{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:translateY(0)}}}
@media print{body{background:white;color:black}.panel,.card{background:white;border-color:#aaa}button,input,select{display:none}p,.label,.foot,.note,footer,th{color:#555}.positive{color:#376100}.negative{color:#a00}main{padding:0}.chart{height:160px}}
</style></head><body><main>
<nav><div class="brand"><span class="mark" aria-hidden="true">▥</span>Market Ledger<span style="color:var(--muted);font-weight:400"> / lab</span></div><span class="tag">Offline simulation · v1.0</span></nav>
<header><div class="eyebrow">Market microstructure / session report</div><h1>Every order.<br>Every execution.</h1><p>A deterministic view of price-time matching, liquidity, and cross-market spreads. Built with C++17. Runs entirely on your machine.</p></header>
<section class="metrics" aria-label="Session metrics" id="metrics"></section>
<div class="status" id="status"></div>
<div class="grid"><section class="panel"><h2>Cumulative traded value</h2><p class="sub">Executed notional over the session. Values shown in dollars.</p><svg id="chart" class="chart" viewBox="0 0 700 220" role="img" aria-label="Cumulative traded value by execution"><title>Cumulative traded value by execution</title></svg><div class="axis"><span>First execution</span><span>Last execution</span></div></section>
<section class="panel"><h2>Cross-market opportunities</h2><p class="sub">Best route per instrument at the final quote timestamp.</p><div id="routes"></div><div class="note">Potential spread after the configured per-leg fee. Independent snapshot routes; execution, slippage, and realized returns are not simulated.</div></section></div>
<section class="panel"><div class="panelhead"><div><h2>Execution ledger</h2><div class="sub" style="margin-bottom:0">Resting order sets the execution price.</div></div><div class="toolbar"><input id="search" type="search" aria-label="Filter executions" placeholder="Search instrument or broker"><select id="sort" aria-label="Sort executions"><option value="time">Arrival order</option><option value="value">Largest value first</option></select><button id="download" type="button">Export JSON</button></div></div>
<div class="scroll"><table><thead><tr><th>Time</th><th>Instrument</th><th>Buyer / seller</th><th>Price</th><th>Quantity</th><th>Value</th></tr></thead><tbody id="ledger"></tbody></table></div><div id="count" class="sub" style="margin-top:12px;margin-bottom:0" aria-live="polite"></div></section>
<section class="panel"><h2>Broker cash movements</h2><p class="sub">Cash transfers from simulated executions; these balances are not profit or portfolio valuations.</p><div class="scroll"><table><thead><tr><th>Broker</th><th>Bought</th><th>Sold</th><th>Net cash</th></tr></thead><tbody id="balances"></tbody></table></div></section>
<footer><span>Market Ledger · Portfolio project by thejas-droid</span><span>No broker connection · No API keys · No external assets</span></footer>
</main><script type="application/json" id="report-data">__REPORT_DATA__</script><script>
'use strict';
const report=JSON.parse(document.getElementById('report-data').textContent),s=report.simulation;
const money=v=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(v/100);
const safe=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
document.getElementById('metrics').innerHTML=[['Orders submitted',s.submitted_orders,'Validated event stream'],['Executions',s.trade_count,`${s.units_traded} instrument units traded`],['Traded value',money(s.turnover_cents),'Gross executed notional'],['Resting orders',s.resting_orders,'At final event timestamp']].map(([label,value,foot])=>`<div class="card"><div class="label">${label}</div><div class="value">${value}</div><div class="foot">${foot}</div></div>`).join('');
document.getElementById('status').textContent=`${s.expired_orders} expired orders  /  ${s.self_trade_preventions} self-trade preventions  /  Integer-cent accounting`;
document.getElementById('routes').innerHTML=report.analysis.opportunities.map(o=>`<div class="route"><div class="routehead"><span>${safe(o.instrument)}</span><span class="profit">${money(o.potential_profit_cents)}</span></div><p>${safe(o.buy_venue)} → ${safe(o.sell_venue)} · ${o.quantity} units</p><p>Buy ${money(o.buy_price_cents)} / sell ${money(o.sell_price_cents)} · net ${money(o.net_per_unit_cents)} per unit</p></div>`).join('')||'<div class="empty">No profitable routes within the configured limits.</div>';
document.getElementById('balances').innerHTML=s.brokers.map(b=>`<tr><td>${safe(b.broker)}</td><td class="num">${b.bought}</td><td class="num">${b.sold}</td><td class="num ${b.net_cash_cents>=0?'positive':'negative'}">${money(b.net_cash_cents)}</td></tr>`).join('');
function ledger(){const term=document.getElementById('search').value.toLowerCase();let rows=s.trades.filter(t=>[t.instrument,t.buyer,t.seller,t.buy_order,t.sell_order].some(v=>v.toLowerCase().includes(term)));if(document.getElementById('sort').value==='value')rows.sort((a,b)=>b.price_cents*b.quantity-a.price_cents*a.quantity);document.getElementById('ledger').innerHTML=rows.map(t=>`<tr><td class="num">${t.timestamp}</td><td>${safe(t.instrument)}</td><td>${safe(t.buyer)} / ${safe(t.seller)}</td><td class="num">${money(t.price_cents)}</td><td class="num">${t.quantity}</td><td class="num">${money(t.price_cents*t.quantity)}</td></tr>`).join('');document.getElementById('count').textContent=`${rows.length} of ${s.trades.length} executions`;}
document.getElementById('search').addEventListener('input',ledger);document.getElementById('sort').addEventListener('change',ledger);ledger();
let total=0;const cumulative=[0,...s.trades.map(t=>(total+=t.price_cents*t.quantity))],maximum=Math.max(total,1),points=cumulative.map((v,i)=>`${20+i*660/Math.max(cumulative.length-1,1)},${190-v*165/maximum}`).join(' ');
document.getElementById('chart').innerHTML=`<title>Cumulative traded value by execution</title><defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#bded85" stop-opacity=".2"/><stop offset="1" stop-color="#bded85" stop-opacity="0"/></linearGradient></defs>${[25,80,135,190].map(y=>`<line x1="20" y1="${y}" x2="680" y2="${y}" stroke="#30383e" stroke-dasharray="4 5"/>`).join('')}<polygon points="20,190 ${points} ${cumulative.length>1?'680':'20'},190" fill="url(#area)"/><polyline points="${points}" fill="none" stroke="#bded85" stroke-width="2.5" stroke-linejoin="round"/><text x="20" y="16" fill="#a0ada8" font-size="11">${money(total)}</text>`;
document.getElementById('download').addEventListener('click',()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download='market-ledger-session.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
</script></body></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=ROOT / "build" / ("market-ledger.exe" if os.name == "nt" else "market-ledger"))
    parser.add_argument("--orders", type=Path, default=ROOT / "examples/orders.csv")
    parser.add_argument("--quotes", type=Path, default=ROOT / "examples/quotes.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "build/report.html")
    parser.add_argument("--fee", type=int, default=2)
    parser.add_argument("--max-age", type=int, default=5)
    parser.add_argument("--max-quantity", type=int, default=1000)
    args = parser.parse_args()
    if args.output.resolve() in {args.binary.resolve(), args.orders.resolve(), args.quotes.resolve()}:
        parser.error("output must differ from the executable and input files")
    simulation = execute(args.binary, "simulate", args.orders)
    analysis = execute(args.binary, "arbitrage", args.quotes, "--fee", str(args.fee),
                       "--max-age", str(args.max_age), "--max-quantity", str(args.max_quantity))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(simulation, analysis), encoding="utf-8")
    print(f"Open in your browser: {args.output.resolve()}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        detail = error.stderr.strip() if isinstance(error, subprocess.CalledProcessError) else str(error)
        print(f"error: {detail}", file=sys.stderr)
        sys.exit(1)
