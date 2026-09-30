import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api } from '../services/api';
import { isOfficial } from '../types/cyclone';

const DataContext = createContext(null);
const POLL_MS = 60000;

function readLang() {
  try {
    return localStorage.getItem('cyclonexus.lang') || 'en';
  } catch {
    return 'en';
  }
}

/**
 * Polls active systems and API health every minute. On a failed poll the last good
 * data is kept and `offline` is set, so the UI can warn instead of going blank.
 */
export function DataProvider({ children }) {
  const [lang, setLangState] = useState(readLang);
  const [systems, setSystems] = useState([]);
  const [health, setHealth] = useState(null);
  const [offline, setOffline] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [selectedId, setSelectedId] = useState(null);

  const setLang = useCallback(l => {
    setLangState(l);
    try { localStorage.setItem('cyclonexus.lang', l); } catch { /* storage unavailable */ }
    document.documentElement.lang = l;
  }, []);

  const refresh = useCallback(async () => {
    const [s, h] = await Promise.allSettled([api.getActiveCyclones(), api.getHealth()]);
    if (s.status === 'fulfilled') setSystems(s.value);
    if (h.status === 'fulfilled') setHealth(h.value);
    setOffline(s.status === 'rejected');
    setLoaded(true);
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  // Keep a valid selection: previous choice if still active, else the strongest official system
  const selected = useMemo(() => {
    if (!systems.length) return null;
    return systems.find(s => s.cyclone_id === selectedId)
      || systems.find(isOfficial)
      || systems[0];
  }, [systems, selectedId]);

  const value = useMemo(() => ({
    lang, setLang, systems, health, offline, loaded, selected, select: setSelectedId, refresh,
  }), [lang, setLang, systems, health, offline, loaded, selected, refresh]);

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>;
}

export function useData() {
  const ctx = useContext(DataContext);
  if (!ctx) throw new Error('useData must be used inside <DataProvider>');
  return ctx;
}
