'use client';

import { createContext, useCallback, useContext, useEffect, useState } from 'react';

const Ctx = createContext({ t: k => k, lang: 'ca', setLang: () => {} });

export function TranslationProvider({ children }) {
  const [lang, setLangState] = useState('ca');
  const [messages, setMessages] = useState({});

  async function load(l) {
    try {
      const r = await fetch(`/api/i18n/${l}`);
      if (r.ok) setMessages(await r.json());
    } catch {}
  }

  function setLang(l) {
    setLangState(l);
    if (typeof localStorage !== 'undefined') localStorage.setItem('ulr_lang', l);
    load(l);
  }

  useEffect(() => {
    const saved = (typeof localStorage !== 'undefined' && localStorage.getItem('ulr_lang')) || 'ca';
    setLangState(saved);
    load(saved);
  }, []);

  const t = useCallback((key, fallback) => messages[key] ?? fallback ?? key, [messages]);

  return <Ctx.Provider value={{ t, lang, setLang }}>{children}</Ctx.Provider>;
}

export function useT() {
  return useContext(Ctx).t;
}

export function useLang() {
  const { lang, setLang } = useContext(Ctx);
  return { lang, setLang };
}
