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
    price: page_(`<div class=card><div class=eyebrow>Public API · no key · cached 5 minutes</div><h2>GET /price?region=ap-south-1&amp;gpu=a100</h2>
      <pre style="margin:0;padding:26px 30px;background:#151515;border:1px solid #3b3b3b;border-radius:4px;font:500 24px/1.5 'IBM Plex Mono',monospace;color:#ededed">{
  "region": "ap-south-1",
  "per_kwh_it": {
    "litres": ${mum.per_kwh_it.litres.toFixed(2)},        <span style="color:#8c8c8c">// ${mum.per_kwh_it.litres_site.toFixed(2)} cooling + ${mum.per_kwh_it.litres_grid.toFixed(2)} power plant</span>
    "kg_co2": ${mum.per_kwh_it.kg_co2.toFixed(3)}
  },
  "inputs": { "t_wb": ${mum.inputs.t_wb.toFixed(1)}, "ci_g_per_kwh": ${mum.inputs.ci_g_per_kwh} }
}</pre><p class=note>Live response, with low and high ranges. For any region and any hour in the next 48.</p></div>`),
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
      const m = document.createElement("div"); m.id = "__mark"; m.style.cssText = "position:fixed;left:0;top:0;width:6px;height:6px;z-index:100000;display:none"; document.body.append(m);
      window.__fast = (k) => { m.style.display = k ? "block" : "none"; m.style.background = k === 2 ? "#00ffff" : "#ff00ff"; };
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

  // fast(0|1|2): marks the recording so finish.py plays typing/page loads at 3x (1) and waits at 6x (2). Captions stay at normal speed.
  const fast = async (k) => { await page.evaluate((k) => window.__fast && window.__fast(k), k); };
  const nav = async (hash, wait = 700) => { await fast(1); await page.evaluate((h) => { location.hash = "#/" + h; }, hash); await sleep(wait); await fast(0); };
  const app = async (hash, wait = 1200) => { await page.goto(`${APP}/#/${hash}`); await fast(1); await sleep(wait); await fast(0); };
  const read = (text) => Math.max(2000, text.split(/\s+/).length * 250 + 600);   // ~3 words a second plus a beat
  const line = async (text) => say(text, read(text));
  // 1. title + problem
  await card("title"); await line("Tidewise decides where and when to run AI jobs, so they use the least water and carbon.");
  await card("problem");
  await line(`One kWh of AI compute right now: in Mumbai, ${L(mum).toFixed(1)} litres of water and ${K(mum).toFixed(1)} kg of CO₂.`);
  await line(`In Stockholm: ${L(sto).toFixed(0)} litre and ${K(sto).toFixed(2)} kg. ${(L(mum) / L(sto)).toFixed(0)}× the water, ${(K(mum) / K(sto)).toFixed(0)}× the carbon.`);
  // 2. submit
  await app("submit", 1500);
  await line("Say how much compute you need, and by when.");
  await cap(""); await fast(1);
  await click("#name"); await page.keyboard.type("nightly fine-tune", { delay: 45 });
  await click("#gpu_hours"); await page.keyboard.press("Control+A"); await page.keyboard.type("4", { delay: 90 });
  await click(".chips .chip >> nth=2"); await fast(0);
  await line("Choose how much water and carbon each matter.");
  await cap(""); await fast(1);
  await moveTo("#water"); await page.focus("#water"); for (let i = 0; i < 3; i++) { await page.keyboard.press("ArrowRight"); await sleep(200); }
  await click(".check input[type=checkbox] >> nth=0"); await click("summary"); await sleep(300); await page.mouse.wheel(0, 300); await sleep(300); await fast(0);
  await line("Add constraints: keep data in one jurisdiction, limit regions, or let the job split across hours.");
  await cap(""); await fast(1); await page.mouse.wheel(0, -600); await sleep(500); await fast(0);
  await line("The estimate updates live, against running now in Mumbai.");
  // 3. surface
  await nav("surface", 1300);
  await line("Hourly forecasts of weather and grid carbon for eight AWS regions, 48 hours ahead.");
  await cap(""); await fast(1); await moveTo("#hr"); await page.focus("#hr");
  for (let i = 0; i < 22; i++) { await page.keyboard.press("ArrowRight"); await sleep(120); } await fast(0);
  await line(`Every region and hour is priced. Cheapest slot: ${best.region}, ${pct(best.cost, 1)}% lower cost than now.`);
  await cap(""); await fast(1); await click(".heat-cell.best"); await sleep(400); await page.mouse.wheel(0, 520); await sleep(400); await fast(0);
  await line("Litres of water and kg of CO₂ for every region, on a table and map.");
  // 4. place + job
  await nav("submit", 1000);
  await fast(1);
  await click("#name"); await page.keyboard.type("nightly fine-tune (demo)", { delay: 30 });
  await click("#gpu_hours"); await page.keyboard.press("Control+A"); await page.keyboard.type("4", { delay: 60 });
  await click(".chips .chip >> nth=2"); await fast(0);
  await line("Place the job: every region and hour that meets the deadline is searched.");
  await cap(""); await fast(1); await click("button.primary"); await sleep(1800); await fast(0);
  await line("A plain-language explanation, with litres and kg saved and their uncertainty ranges.");
  await line("Waiting jobs are re-checked as forecasts change: an email nudge, and a one-click move.");
  await cap(""); await fast(1); await page.mouse.wheel(0, 420); await sleep(400); await fast(0);
  await line("Every option considered is listed, so the choice can be audited.");
  await nav("queue", 1000);
  await line("The queue tracks every job, from placed and waiting to running and done.");
  // 5. architecture
  await card("arch");
  await line("An hourly Step Functions pipeline refreshes forecasts. Each job gets its own state machine…");
  await line("…that waits for the chosen hour, launches in that region, writes a receipt and emails you.");
  // 6. receipt, savings, forecasts, price API
  await app(`receipt/${HERO_JOB}`, 1200);
  await line("Every job gets a receipt: modelled water and carbon saved, with a measured stand-in run.");
  await cap(""); await fast(1); await click("button.primary"); await sleep(300); await fast(0);
  await line("Copy a link, download JSON or CSV, or print it.");
  await nav("savings", 1000);
  const sv = (await get("/savings?days=30")).totals;
  await line(`Across ${sv.jobs} jobs so far: ${sv.litres_saved.toFixed(0)} litres of water and ${sv.kg_co2_saved.toFixed(1)} kg of CO₂ saved, by team and over time.`);
  await nav("quality", 1200);
  await line("Forecast quality is public. A learned model is used only where it beats a naive baseline.");
  await card("price");
  await line("A public price API returns the water and carbon cost of compute for any region and hour.");
  // 7. assistant
  await app("assistant", 1000);
  await line("Or just ask. The assistant reads the live cost surface, and can place jobs.");
  await cap(""); await fast(1); await click("#msg"); await page.keyboard.type("Which region is cheapest for 2 GPU-hours right now?", { delay: 30 });
  await page.keyboard.press("Enter"); await fast(2);
  await page.waitForFunction(() => { const b = [...document.querySelectorAll(".msg.bot .body")]; const l = b[b.length - 1]; return l && !l.classList.contains("muted"); }, null, { timeout: 40000 });
  await fast(0); await sleep(3500);
  // 8. policies, DG-Shift, docs, close
  await nav("policies", 1000);
  await line("Platform leads set team rules (weights, regions, residency, delay) behind Cognito sign-in.");
  await page.route(`${API}/facilities`, (r) => r.fulfill({ status: 200, contentType: "application/json", headers: { "access-control-allow-origin": "*" }, body: fs.readFileSync(path.join(FIX, "facs.json")) }));
  await page.route(`${API}/facilities/**`, (r) => r.fulfill({ status: 200, contentType: "application/json", headers: { "access-control-allow-origin": "*" }, body: fs.readFileSync(path.join(FIX, "fac.json")) }));
  await nav("operations", 1200);
  await line("DG-Shift: when the grid fails, critical services stay up and flexible work is deferred.");
  await cap(""); await fast(1); await page.mouse.wheel(0, 460); await sleep(300); await fast(0);
  await line("Simulated demo: 47 kW of IT demand falls to 19 kW, and every deadline still holds.");
  await nav("docs/how-placement-works", 1000);
  await line("Full documentation in the app: concepts, user guide, API reference, FAQ.");
  await card("close"); await line("Water and carbon are modelled, so absolute litres are uncertain. The ranking of slots holds up.");
  await cap(""); await sleep(600);
  closeCue();
  fs.writeFileSync(path.join(OUT, "demo.srt"), srt.join("\n"));
  const v = page.video(); await ctx.close(); await v.saveAs(path.join(OUT, "demo.webm")); await browser.close();
  console.log("done", ((Date.now() - t0) / 1000).toFixed(0) + "s");
})();
