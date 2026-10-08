import { useEffect, useState } from "react";

const KEY = "pravaah-theme";
export const THEMES = ["system", "light", "dark"];

export function getTheme() {
  try { return localStorage.getItem(KEY) || "system"; } catch { return "system"; }
}
export function applyTheme(theme) {
  const root = document.documentElement;
  if (theme === "system") root.removeAttribute("data-theme"); else root.dataset.theme = theme;
  try { localStorage.setItem(KEY, theme); } catch { /* private window: the choice just won't persist */ }
}
/** Re-render when the theme changes (explicit toggle or OS setting), for code that reads CSS tokens. */
export function useThemeTick() {
  const [n, setN] = useState(0);
  useEffect(() => {
    const bump = () => setN((x) => x + 1);
    const mo = new MutationObserver(bump);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    mq?.addEventListener?.("change", bump);
    return () => { mo.disconnect(); mq?.removeEventListener?.("change", bump); };
  }, []);
  return n;
}
