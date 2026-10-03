import { useCallback, useEffect, useSyncExternalStore } from 'react';

// Theme preference: 'system' | 'light' | 'dark'. The resolved theme ('light' | 'dark')
// is applied to <html data-theme>. index.html applies it once before first paint.
export const THEME_KEY = 'ma-theme';
export const THEME_PREFS = ['system', 'light', 'dark'];
const META_COLOR = { light: '#f2f4f8', dark: '#0d1014' };

const listeners = new Set();
const emit = () => listeners.forEach((l) => l());

export function readPref() {
  try {
    const v = localStorage.getItem(THEME_KEY);
    return THEME_PREFS.includes(v) ? v : 'system';
  } catch {
    return 'system';
  }
}

const mq = () => (typeof window !== 'undefined' && window.matchMedia ? window.matchMedia('(prefers-color-scheme: light)') : null);
export const resolveTheme = (pref) => (pref === 'system' ? (mq()?.matches ? 'light' : 'dark') : pref);

export function applyTheme(pref) {
  const resolved = resolveTheme(pref);
  const root = document.documentElement;
  if (root.dataset.theme !== resolved) root.dataset.theme = resolved;
  root.dataset.themePref = pref;
  root.style.colorScheme = resolved;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute('content', META_COLOR[resolved]);
  return resolved;
}

let pref = readPref();
let resolved = resolveTheme(pref);

function setPref(next) {
  pref = next;
  try { localStorage.setItem(THEME_KEY, next); } catch { /* storage unavailable */ }
  resolved = applyTheme(next);
  emit();
}

function subscribe(cb) {
  listeners.add(cb);
  const m = mq();
  const onChange = () => {
    if (pref !== 'system') return;
    resolved = applyTheme('system');
    emit();
  };
  m?.addEventListener?.('change', onChange);
  const onStorage = (e) => {
    if (e.key !== THEME_KEY) return;
    pref = readPref();
    resolved = applyTheme(pref);
    emit();
  };
  window.addEventListener('storage', onStorage);
  return () => {
    listeners.delete(cb);
    m?.removeEventListener?.('change', onChange);
    window.removeEventListener('storage', onStorage);
  };
}

/** Returns { pref, theme, setPref } - theme is the resolved 'light' | 'dark'. */
export default function useTheme() {
  const p = useSyncExternalStore(subscribe, () => pref, () => 'system');
  const theme = useSyncExternalStore(subscribe, () => resolved, () => 'dark');
  useEffect(() => { applyTheme(p); }, [p]);
  const set = useCallback((v) => setPref(v), []);
  return { pref: p, theme, setPref: set };
}
