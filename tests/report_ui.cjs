// Verify report behavior without external browser packages; layout is not tested.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync(process.argv[2], 'utf8');
const data = html.match(/<script type="application\/json" id="report-data">([\s\S]*?)<\/script>/)[1];
const code = html.match(/<script>\s*([\s\S]*?)<\/script>/)[1];
const elements = {};
for (const id of ['report-data','metrics','status','routes','balances','search','sort','ledger','count','chart','download']) {
  elements[id] = {textContent:'',innerHTML:'',value:'',listeners:{},
    addEventListener(name, callback){this.listeners[name]=callback;}};
}
elements['report-data'].textContent = data;
elements.sort.value = 'time';
let clicked = false, exported = null, revoked = false;
const link = {click(){clicked = true;}};
const document = {getElementById(id){assert.ok(elements[id], `Unknown element ${id}`);return elements[id];},
  createElement(tag){assert.equal(tag,'a');return link;}};
class Blob {constructor(parts, options){exported = {parts,options};}}
const URL = {createObjectURL(){return 'blob:session';},revokeObjectURL(url){assert.equal(url,'blob:session');revoked=true;}};
vm.runInNewContext(code, {document,Intl,console,Blob,URL,setTimeout(callback){callback();}}, {timeout:1000});
assert.equal(elements.count.textContent, '6 of 6 executions');
assert.match(elements.chart.innerHTML, /<polyline/);
assert.match(elements.routes.innerHTML, /\$2\.08/);
assert.match(elements.metrics.innerHTML, /\$1,220\.50/);
elements.search.value = 'Cedar';
elements.search.listeners.input();
assert.equal(elements.count.textContent, '5 of 6 executions');
elements.search.value = 'not-present';
elements.search.listeners.input();
assert.equal(elements.count.textContent, '0 of 6 executions');
elements.search.value = '';
elements.sort.value = 'value';
elements.sort.listeners.change();
assert.match(elements.ledger.innerHTML.split('</tr>')[0], /Delta/);
elements.download.listeners.click();
assert.ok(clicked && revoked);
assert.equal(link.download,'market-ledger-session.json');
assert.equal(JSON.parse(exported.parts[0]).simulation.trade_count,6);
console.log('Report JavaScript: metrics, chart, routes, filtering, sorting, and export passed.');
