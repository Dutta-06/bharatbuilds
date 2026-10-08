// Diverging cost scale: cheaper than running now (low), the same (mid), costlier (high).
// The poles and midpoint are CSS tokens, so the scale follows the theme. It is the one place the
// interface uses hue, because here colour carries data.
export const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

function hexToRgb(h) {
  const n = parseInt(h.replace("#", ""), 16);
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
  const p = { low: cssVar("--scale-low"), mid: cssVar("--scale-mid"), high: cssVar("--scale-high") };
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
