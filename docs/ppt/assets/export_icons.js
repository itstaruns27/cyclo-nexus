// Export selected lucide icons (ISC licence) as standalone SVG files for the slide deck.
const fs = require('fs'); const path = require('path');
const dir = process.argv[2]; const out = process.argv[3];
const names = process.argv.slice(4);
for (const n of names) {
  const f = path.join(dir, n + '.js');
  if (!fs.existsSync(f)) { console.log('missing', n); continue; }
  let src = fs.readFileSync(f, 'utf8');
  const alias = src.match(/from '\.\/([a-z0-9-]+)\.js'/);
  if (!/createLucideIcon\("/.test(src) && alias) src = fs.readFileSync(path.join(dir, alias[1] + '.js'), 'utf8');
  const m = src.match(/createLucideIcon\("[^"]+",\s*(\[[\s\S]*?\])\);/);
  if (!m) { console.log('unparsed', n); continue; }
  const nodes = Function('return ' + m[1])();
  const body = nodes.map(([tag, attrs]) => '<' + tag + ' ' + Object.entries(attrs).filter(([k]) => k !== 'key')
    .map(([k, v]) => `${k}="${v}"`).join(' ') + '/>').join('');
  fs.writeFileSync(path.join(out, n + '.svg'),
    `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="COLOR" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`);
}
console.log('ok');
