import type { Theme } from "@/types/settings";

export const THEME_STORAGE_KEY = "signal.theme";

/**
 * Runs as an inline <script> in <head>, before the first paint, so a reload never flashes
 * the wrong theme (Next's "preventing flash before hydration" pattern). "system" means no
 * attribute: theme.css then follows prefers-color-scheme.
 */
export const THEME_BOOT_SCRIPT = `try{var t=localStorage.getItem("${THEME_STORAGE_KEY}");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;

export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  if (theme === "system") delete root.dataset.theme;
  else root.dataset.theme = theme;
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // Storage unavailable: the theme still applies for this page view.
  }
}
