// Render SVG files to transparent PNGs (PowerPoint fallback images for SVG icons/graphics).
//   node render_icons.js jobs.json      jobs = [{ "svg": "path.svg", "png": "path.png", "size": 256 }]
const { chromium } = require('D:/cyclonexus-demo/recorder/node_modules/playwright-core');
const fs = require('fs');

(async () => {
  const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const b = await chromium.launch({ channel: 'chrome', headless: true });
  const p = await b.newPage({ viewport: { width: 256, height: 256 } });
  for (const j of jobs) {
    const svg = fs.readFileSync(j.svg, 'utf8');
    const w = j.w || j.size || 256; const h = j.h || j.size || 256;
    await p.setViewportSize({ width: w, height: h });
    await p.setContent(`<html><body style="margin:0;background:transparent">
      <img src="data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}" style="width:${w}px;height:${h}px;display:block"></body></html>`);
    await p.screenshot({ path: j.png, omitBackground: true });
  }
  await b.close();
  console.log(`rendered ${jobs.length}`);
})();
