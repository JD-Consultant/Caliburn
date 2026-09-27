'use client';
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

export type ColorMode = 'light' | 'dark';
const STORAGE_KEY = 'caliburn-color-mode';
const ColorModeContext = createContext<{ mode: ColorMode; toggle: () => void }>({ mode: 'light', toggle: () => {} });

export function useColorMode() {
  return useContext(ColorModeContext);
}

export function ColorModeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<ColorMode>('light');
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === 'light' || stored === 'dark') { setMode(stored); return; }
    } catch { /* Storage may be blocked (private window); fall back to the system preference below. */ }
    if (window.matchMedia?.('(prefers-color-scheme: dark)').matches) setMode('dark');
  }, []);
  const toggle = () => setMode(current => {
    const next: ColorMode = current === 'light' ? 'dark' : 'light';
    try { localStorage.setItem(STORAGE_KEY, next); } catch { /* Per-viewer convenience only; safe to lose. */ }
    return next;
  });
  const value = useMemo(() => ({ mode, toggle }), [mode]);
  return <ColorModeContext.Provider value={value}>{children}</ColorModeContext.Provider>;
}
