// Plain .js (no JSX) so the provider, context and hook can live together
// without tripping react-refresh/only-export-components.
import { createContext, createElement, useContext, useState } from 'react';
import es from '../i18n/es';
import en from '../i18n/en';

const STRINGS = { es, en };

function readStoredLang() {
  try {
    return localStorage.getItem('lang') || 'en';
  } catch {
    return 'en';
  }
}

const LanguageContext = createContext({ lang: 'en', t: en, setLang: () => {} });

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(readStoredLang);

  function setLang(l) {
    setLangState(l);
    try {
      localStorage.setItem('lang', l);
    } catch {
      // storage unavailable - language still changes for this session
    }
  }

  return createElement(
    LanguageContext.Provider,
    { value: { lang, t: STRINGS[lang] || es, setLang } },
    children,
  );
}

export function useLanguage() {
  return useContext(LanguageContext);
}
