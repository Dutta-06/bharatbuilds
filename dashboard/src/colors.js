// Diverging scale for relative cost (1.0 = running now in the submit region):
// blue = cheaper, gray midpoint = same, red = costlier. Poles from the reference palette.
const LIGHT = { low: "#184f95", mid: "#f0efec", high: "#e34948" };
const DARK = { low: "#3987e5", mid: "#383835", high: "#e66767" };

function hexToRgb(h) {
  const n = parseInt(h.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
function mix(a, b, t) {
  const [x, y] = [hexToRgb(a), hexToRgb(b)];
  return "#" + x.map((v, i) => Math.round(v + (y[i] - v) * t).toString(16).padStart(2, "0")).join("");
}

export function isDark() {
  const forced = document.documentElement.dataset.theme;
  if (forced) return forced === "dark";
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches;
}

// lo: best (lowest) cost on screen, hi: worst. 1.0 sits at the neutral midpoint.
export function costColor(cost, lo, hi) {
  const p = isDark() ? DARK : LIGHT;
  if (cost <= 1) {
    const span = Math.max(1e-9, 1 - Math.min(lo, 0.999));
    return mix(p.mid, p.low, Math.min(1, (1 - cost) / span));
  }
  const span = Math.max(1e-9, Math.max(hi, 1.001) - 1);
  return mix(p.mid, p.high, Math.min(1, (cost - 1) / span));
}

export const fmt = {
  litres: (v) => (v == null ? "–" : v < 10 ? v.toFixed(2) : v.toFixed(1)),
  kg: (v) => (v == null ? "–" : v < 1 ? v.toFixed(3) : v.toFixed(2)),
  pct: (v) => (v == null ? "–" : `${v > 0 ? "" : "+"}${Math.abs(v).toFixed(0)}%`),
  hour: (h) => (h ? h.replace("T", " ") + " UTC" : "–"),
};
