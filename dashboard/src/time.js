// The API speaks UTC ("2026-10-08T09:00", "2026-10-08T09:00Z", "...:00Z"). People read their own clock,
// so show local time first and keep UTC one hover or one line away.
const LOCALE = (typeof navigator !== "undefined" && navigator.language) || "en-GB";

export function parse(iso) {
  if (!iso) return null;
  const core = String(iso).replace(/Z$/, "");
  const d = new Date(core.length === 16 ? `${core}:00Z` : `${core}Z`);
  return Number.isNaN(d.getTime()) ? null : d;
}

const fmtFull = new Intl.DateTimeFormat(LOCALE, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false, timeZoneName: "short" });
const fmtShort = new Intl.DateTimeFormat(LOCALE, { weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false });
const fmtClock = new Intl.DateTimeFormat(LOCALE, { hour: "2-digit", minute: "2-digit", hour12: false });

/** "Thu, 9 Oct, 14:30 GMT+5:30" */
export const when = (iso) => { const d = parse(iso); return d ? fmtFull.format(d) : "–"; };
/** "Thu 14:30" */
export const whenShort = (iso) => { const d = parse(iso); return d ? fmtShort.format(d) : "–"; };
export const clock = (iso) => { const d = parse(iso); return d ? fmtClock.format(d) : "–"; };
/** "09:00 UTC" */
export const utc = (iso) => { const d = parse(iso); return d ? `${d.toISOString().slice(11, 16)} UTC` : "–"; };
/** "in 14 h", "3 h ago", "just now" */
export function relative(iso, now = Date.now()) {
  const d = parse(iso); if (!d) return "–";
  const mins = Math.round((d.getTime() - now) / 60000), a = Math.abs(mins);
  if (a < 2) return "just now";
  const t = a < 90 ? `${a} min` : a < 48 * 60 ? `${Math.round(a / 60)} h` : `${Math.round(a / 1440)} d`;
  return mins > 0 ? `in ${t}` : `${t} ago`;
}

/** Rewrite "2026-10-08T09:00 UTC" style stamps inside a server sentence into local times. */
export function humanise(text) {
  return String(text || "").replace(/(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})(?::\d{2})?(?: UTC|Z)?/g, (m, t) => when(t));
}
