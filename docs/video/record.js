// Records the Tidewise demo video against the REAL deployed API.
// Usage: API=https://<api> APP=http://localhost:4173 OUT=/path node record.js   (needs playwright + the dashboard built with VITE_API_URL=$API and served by `vite preview`)
// Writes OUT/demo.webm and OUT/demo.srt. Captions are burned into the page, so no editor is needed.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const API = process.env.API, APP = process.env.APP || "http://localhost:4173", OUT = process.env.OUT || "/tmp/demo";
const CHROME = process.env.CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const FIX = path.join(__dirname, "fixtures");
const HERO_JOB = process.env.HERO_JOB || "3780bcd0def3";       // a finished job placed through the assistant
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const get = async (p) => (await fetch(API + p)).json();

const CSS = `
:root{color-scheme:dark} *{box-sizing:border-box} body{margin:0;background:#0e0e0e;color:#ededed;font-family:"IBM Plex Sans",system-ui,sans-serif;min-height:100vh;display:grid;place-items:center}
.card{width:min(1040px,92vw);display:grid;gap:28px}
.eyebrow{font:500 14px "IBM Plex Mono",monospace;letter-spacing:.12em;text-transform:uppercase;color:#8c8c8c}
h1{font-size:60px;margin:0;letter-spacing:-.02em;line-height:1.08} h2{font-size:38px;margin:0;letter-spacing:-.01em}
p{font-size:24px;color:#b6b6b6;margin:0;line-height:1.45}
.two{display:grid;grid-template-columns:1fr 1fr;gap:24px}
.stat{border:1px solid #3b3b3b;background:#151515;padding:26px 28px;display:grid;gap:10px;border-radius:4px}
.stat b{font:500 56px "IBM Plex Mono",monospace;letter-spacing:-.02em} .stat small{font:400 20px "IBM Plex Mono",monospace;color:#8c8c8c}
.hot b{color:#e5694f} .cool b{color:#3fa3cc}
.note{font:400 16px "IBM Plex Mono",monospace;color:#8c8c8c}
svg text{font-family:"IBM Plex Mono",monospace}
`;
const FONTS = fs.readdirSync(path.join(__dirname, "../../dashboard/dist/assets")).filter((f) => /plex-(sans|mono)-latin-(400|500|600)-normal.*woff2$/.test(f));
const fontFace = FONTS.map((f) => { const m = /plex-(sans|mono)-latin-(\d+)/.exec(f); return `@font-face{font-family:"IBM Plex ${m[1] === "sans" ? "Sans" : "Mono"}";font-weight:${m[2]};src:url(${APP}/assets/${f}) format("woff2")}`; }).join("");
const page_ = (body) => `<!doctype html><meta charset=utf-8><style>${fontFace}${CSS}</style><body>${body}`;

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  // ---- real numbers, fetched now ----------------------------------------------------------------------------
  const price = async (r) => (await get(`/price?region=${r}`));
  const [mum, sto, surf] = await Promise.all([price("ap-south-1"), price("eu-north-1"), get("/surface?gpu_hours=4")]);
  const L = (p) => p.per_kwh_it.litres, K = (p) => p.per_kwh_it.kg_co2;
  const base = surf.regions.find((r) => r.id === "ap-south-1").cells[0];
  const best = surf.best, bestCell = surf.regions.find((r) => r.id === best.region).cells.find((c) => c.hour === best.hour);
  const pct = (a, b) => Math.round(100 * (1 - a / b));
  console.log("numbers", { mumbai: [L(mum), K(mum)], stockholm: [L(sto), K(sto)], best, baseLitres: base.litres, bestLitres: bestCell.litres });

  const cards = {
    title: page_(`<div class=card><div class=eyebrow>Environmental Hacks · Heat and Water</div><h1>Tidewise</h1><p>Run AI where and when it uses the least cooling water and carbon.</p></div>`),
    problem: page_(`<div class=card><div class=eyebrow>One kWh of AI compute, right now (modelled)</div><div class=two>
      <div class="stat hot"><span>Mumbai · wet-bulb ${mum.inputs.t_wb.toFixed(0)} °C</span><b>${L(mum).toFixed(1)} L</b><small>water · ${K(mum).toFixed(2)} kg CO₂</small><small>${mum.per_kwh_it.litres_site.toFixed(1)} L cooling + ${mum.per_kwh_it.litres_grid.toFixed(1)} L power plant</small></div>
      <div class="stat cool"><span>Stockholm · wet-bulb ${sto.inputs.t_wb.toFixed(0)} °C</span><b>${L(sto).toFixed(1)} L</b><small>water · ${K(sto).toFixed(2)} kg CO₂</small><small>${sto.per_kwh_it.litres_site.toFixed(1)} L cooling + ${sto.per_kwh_it.litres_grid.toFixed(1)} L power plant</small></div></div>
      <p class=note>Live from the Tidewise API. Modelled from published cooling curves, weather forecasts and grid carbon forecasts.</p></div>`),
    arch: page_(`<div class=card><div class=eyebrow>How it runs on AWS</div><svg viewBox="0 0 1040 380" width="100%" fill="none" stroke="#8c8c8c" stroke-width="1.5">
      <g font-size="17" fill="#ededed" stroke="none"><text x="20" y="26" fill="#8c8c8c">EVERY HOUR</text><text x="20" y="226" fill="#8c8c8c">PER JOB</text></g>
      ${[["EventBridge",20,50],["Step Functions\nforecast",230,50],["Open-Meteo\nElectricity Maps",440,50],["Forecast model\n(only if it beats\npersistence)",650,50],["DynamoDB + S3",860,50]].map(([t,x,y]) => `<g><rect x="${x}" y="${y}" width="160" height="96" rx="4" fill="#151515" stroke="#3b3b3b"/>${t.split("\n").map((l,i,a)=>`<text x="${x+80}" y="${y+48+(i-(a.length-1)/2)*22}" text-anchor="middle" font-size="16" fill="#ededed" stroke="none">${l}</text>`).join("")}</g>`).join("")}
      ${[[180,98],[390,98],[600,98],[810,98]].map(([x,y]) => `<path d="M${x} ${y} h40" stroke="#8c8c8c" marker-end="url(#a)"/>`).join("")}
      ${[["POST /jobs\nscheduler picks\nregion + hour",20,250],["Step Functions\nwaits for\nthe chosen hour",230,250],["Lambda worker\nin the\nchosen region",440,250],["Receipt\nwater + carbon",650,250],["Email (SNS)\nnudges + results",860,250]].map(([t,x,y]) => `<g><rect x="${x}" y="${y}" width="160" height="96" rx="4" fill="#151515" stroke="#3b3b3b"/>${t.split("\n").map((l,i,a)=>`<text x="${x+80}" y="${y+48+(i-(a.length-1)/2)*22}" text-anchor="middle" font-size="16" fill="#ededed" stroke="none">${l}</text>`).join("")}</g>`).join("")}
      ${[[180,298],[390,298],[600,298],[810,298]].map(([x,y]) => `<path d="M${x} ${y} h40" stroke="#8c8c8c" marker-end="url(#a)"/>`).join("")}
      <path d="M940 146 V198 H100 V250" stroke="#3fa3cc" stroke-dasharray="5 5" marker-end="url(#a)"/><text x="520" y="190" text-anchor="middle" font-size="14" fill="#3fa3cc" stroke="none">the scheduler reads the stored forecast</text>
      <defs><marker id="a" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8z" fill="#8c8c8c" stroke="none"/></marker></defs></svg>
      </div>`),
    close: page_(`<div class=card><div class=eyebrow>Tidewise</div><h2>We used AI to decide when AI should run.</h2><p>Deployed on AWS · built for the Heat and Water track.</p><p class=note>Water and carbon are modelled from published cooling curves, weather and grid forecasts. Absolute litres are uncertain; the ranking of slots holds up.</p></div>`),
  };

  const browser = await chromium.launch({ executablePath: CHROME });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 }, colorScheme: "dark", recordVideo: { dir: OUT, size: { width: 1280, height: 720 } } });
  await ctx.addInitScript(() => {
    const mk = () => {
      if (document.getElementById("__cur")) return;
      const s = document.createElement("style");
      s.textContent = `#__cur{position:fixed;z-index:99999;width:18px;height:18px;border-radius:50%;border:2px solid #fff;background:rgba(255,255,255,.25);box-shadow:0 0 0 1px #000;pointer-events:none;transform:translate(-50%,-50%);left:-50px;top:-50px;transition:transform .12s}
      #__cur.d{transform:translate(-50%,-50%) scale(.7);background:rgba(255,255,255,.7)}
      #__cap{position:fixed;z-index:99998;left:50%;bottom:34px;transform:translateX(-50%);max-width:1000px;width:max-content;padding:14px 22px;background:rgba(14,14,14,.92);color:#ededed;border:1px solid #3b3b3b;border-radius:6px;font:500 24px/1.35 "IBM Plex Sans",system-ui,sans-serif;text-align:center;opacity:0;transition:opacity .25s}
      #__cap.on{opacity:1}`;
      document.head.append(s);
      const c = document.createElement("div"); c.id = "__cur"; document.body.append(c);
      const p = document.createElement("div"); p.id = "__cap"; document.body.append(p);
      addEventListener("mousemove", (e) => { c.style.left = e.clientX + "px"; c.style.top = e.clientY + "px"; }, true);
      addEventListener("mousedown", () => c.classList.add("d"), true); addEventListener("mouseup", () => c.classList.remove("d"), true);
    };
    document.addEventListener("DOMContentLoaded", mk); if (document.body) mk();
  });
  const page = await ctx.newPage();
  await page.route("http://cards.test/**", (r) => { const k = new URL(r.request().url()).pathname.slice(1); r.fulfill({ status: 200, contentType: "text/html", body: cards[k] }); });
  page.on("pageerror", (e) => console.log("PAGEERROR", e.message));

  const t0 = Date.now(); const srt = []; let n = 0;
  const stamp = (ms) => { const d = new Date(ms); return d.toISOString().slice(11, 23).replace(".", ","); };
  let pending = null;
  const closeCue = () => { if (pending) { srt.push(`${++n}\n${stamp(pending.at)} --> ${stamp(Date.now() - t0)}\n${pending.text}\n`); pending = null; } };
  const cap = async (text) => { closeCue(); if (!text) { await page.evaluate(() => document.getElementById("__cap")?.classList.remove("on")); return; }
    await page.evaluate((t) => { const e = document.getElementById("__cap"); if (e) { e.textContent = t; e.classList.add("on"); } }, text); pending = { at: Date.now() - t0, text }; };
  const show = async (hash, wait = 1200) => { await page.goto(`${APP}/#/${hash}`); await page.reload(); await sleep(wait); };
  const card = async (name) => { await page.goto(`http://cards.test/${name}`); await sleep(500); };
  const moveTo = async (sel) => { await page.locator(sel).first().scrollIntoViewIfNeeded(); await sleep(350); const b = await page.locator(sel).first().boundingBox(); await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2, { steps: 28 }); await sleep(250); return b; };
  const click = async (sel) => { await moveTo(sel); await page.mouse.down(); await sleep(90); await page.mouse.up(); await sleep(300); };
  const say = async (text, ms) => { await cap(text); await sleep(ms); };

  // 1. title
  await card("title"); await say("AI jobs need electricity, and the data centres behind them need cooling water.", 6500);
  // 2. the problem
  await card("problem");
  await say(`Right now, one kWh of AI compute in Mumbai takes about ${L(mum).toFixed(1)} litres of water and ${K(mum).toFixed(1)} kg of CO₂.`, 7500);
  await say(`In Stockholm: about ${L(sto).toFixed(0)} litre, and ${K(sto).toFixed(2)} kg. That is ${(L(mum) / L(sto)).toFixed(0)}× the water and ${(K(mum) / K(sto)).toFixed(0)}× the carbon.`, 8000);
  await cap("");
  // 3. submit
  await show("submit", 1500);
  await say("Most AI work is not urgent. You tell Tidewise how much compute you need, and by when.", 3000);
  await click("#name"); await page.keyboard.type("nightly fine-tune", { delay: 70 });
  await click("#gpu_hours"); await page.keyboard.press("Control+A"); await page.keyboard.type("4", { delay: 120 });
  await click(".chips .chip >> nth=2"); await sleep(1200);
  await say("You choose how much water and carbon each matter.", 2500);
  await moveTo("#water"); await page.focus("#water"); for (let i = 0; i < 3; i++) { await page.keyboard.press("ArrowRight"); await sleep(260); } await sleep(900);
  await say(`The estimate updates live: run now in Mumbai, or wait for a better slot and region.`, 4800);
  // 4. surface
  await show("surface", 1800);
  await say("Every hour Tidewise forecasts weather and grid carbon for eight AWS regions, 48 hours ahead.", 4200);
  await moveTo("#hr"); await page.focus("#hr");
  await say("It prices every region and every hour. Blue is cheaper than running now in Mumbai.", 1500);
  for (let i = 0; i < 26; i++) { await page.keyboard.press("ArrowRight"); await sleep(170); }
  await sleep(1400);
  await say(`The cheapest slot: ${best.region}, ${new Date(best.hour + "Z").toUTCString().slice(5, 22)} UTC, ${pct(best.cost, 1)}% lower cost than now.`, 4200);
  await click(".heat-cell.best"); await sleep(1500);
  await page.mouse.wheel(0, 520); await sleep(900);
  await say("The table and map show litres of water and kilograms of CO₂ for every region at that hour.", 4800);
  // 5. place + job
  await show("submit", 1500);
  await click("#name"); await page.keyboard.type("nightly fine-tune (demo)", { delay: 40 });
  await click("#gpu_hours"); await page.keyboard.press("Control+A"); await page.keyboard.type("4", { delay: 80 });
  await click(".chips .chip >> nth=2"); await sleep(600);
  await say("Place the job. Tidewise searches every region and hour that still meets the deadline.", 2800);
  await click("button.primary"); await sleep(3000);
  await say("It explains the choice in plain language, with the water and carbon it saves, and a range for the uncertainty.", 6500);
  await page.mouse.wheel(0, 380); await sleep(1500);
  await say("Every option it considered is listed, so the choice can be audited.", 4000);
  // 6. architecture
  await card("arch");
  await say("An hourly Step Functions pipeline refreshes forecasts. Each job gets its own state machine that waits for the chosen hour…", 6500);
  await say("…then launches in the chosen region, writes a receipt, and emails you. Forecast models are only used where they beat a naive baseline.", 7000);
  await cap("");
  // 7. receipt of a finished job
  await show(`jobs/${HERO_JOB}`, 1800);
  await say("A finished job placed through the built-in assistant: it ran in Ireland instead of Mumbai.", 4500);
  await show(`receipt/${HERO_JOB}`, 1800);
  await say("Each job gets a receipt to share or print. Water and carbon are modelled; the stand-in workload's energy is measured. We say which is which.", 7500);
  // 8. savings
  await show("savings", 2200);
  const sv = (await get("/savings?days=30")).totals;
  await say(`Across ${sv.jobs} jobs placed so far: ${sv.litres_saved.toFixed(0)} litres of water and ${sv.kg_co2_saved.toFixed(1)} kg of CO₂ saved, by team and over time.`, 6000);
  // 9. operations
  await page.route(`${API}/facilities`, (r) => r.fulfill({ status: 200, contentType: "application/json", headers: { "access-control-allow-origin": "*" }, body: fs.readFileSync(path.join(FIX, "facs.json")) }));
  await page.route(`${API}/facilities/**`, (r) => r.fulfill({ status: 200, contentType: "application/json", headers: { "access-control-allow-origin": "*" }, body: fs.readFileSync(path.join(FIX, "fac.json")) }));
  await show("operations", 2000);
  await say("And when the grid fails, DG-Shift protects critical services and defers flexible work while the site runs on a generator.", 6000);
  await page.mouse.wheel(0, 460); await sleep(800);
  await say("Simulated demo: 47 kW of IT demand drops to 19 kW. 42 kWh of work moves to later. Every deadline still holds.", 6500);
  // 10. docs + close
  await show("docs/how-placement-works", 1800);
  await say("Everything is documented in the app: concepts, user guide, API reference, FAQ.", 4000);
  await card("close"); await say("Water and carbon are modelled, so absolute litres are uncertain. The ranking of slots holds up.", 5500);
  await cap(""); await sleep(1500);
  closeCue();
  fs.writeFileSync(path.join(OUT, "demo.srt"), srt.join("\n"));
  const v = page.video(); await ctx.close(); await v.saveAs(path.join(OUT, "demo.webm")); await browser.close();
  console.log("done", ((Date.now() - t0) / 1000).toFixed(0) + "s");
})();
