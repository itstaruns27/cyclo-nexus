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
  const [savedAt, setSavedAt] = useState(null); // set when the data shown came from the offline store
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
    const saved = s.status === 'fulfilled' ? api.savedAt('/cyclones') : null;
    setSavedAt(saved);
    setOffline(s.status === 'rejected' || Boolean(saved));
    setLoaded(true);
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  // Warm the offline store (public/sw.js) with the advisory and forecast of every active system, so
  // safety advice is readable later without network even if those pages were never opened.
  const warmKey = savedAt ? '' : `${lang}|${systems.map(s => `${s.cyclone_id}@${s.observation_time}`).join(',')}`;
  useEffect(() => {
    if (!warmKey || !navigator.serviceWorker?.controller) return;
    for (const s of systems) {
      api.getAdvisory(s.cyclone_id, lang).catch(() => {});
      api.getCycloneForecast(s.cyclone_id).catch(() => {});
    }
  }, [warmKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // Keep a valid selection: previous choice if still active, else the strongest official system
  const selected = useMemo(() => {
    if (!systems.length) return null;
    return systems.find(s => s.cyclone_id === selectedId)
      || systems.find(isOfficial)
      || systems[0];
  }, [systems, selectedId]);

  const value = useMemo(() => ({
    lang, setLang, systems, health, offline, savedAt, loaded, selected, select: setSelectedId, refresh,
  }), [lang, setLang, systems, health, offline, savedAt, loaded, selected, refresh]);

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>;
}

export function useData() {
  const ctx = useContext(DataContext);
  if (!ctx) throw new Error('useData must be used inside <DataProvider>');
  return ctx;
}
