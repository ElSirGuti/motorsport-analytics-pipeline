import { createContext, useContext, useState } from 'react';
import es from '../i18n/es';
import en from '../i18n/en';

const STRINGS = { es, en };

const LanguageContext = createContext({ lang: 'en', t: en, setLang: () => {} });

export function LanguageProvider({ children }) {
  const stored = typeof localStorage !== 'undefined'
    ? (localStorage.getItem('lang') || 'en')
    : 'en';
  const [lang, setLangState] = useState(stored);

  function setLang(l) {
    setLangState(l);
    localStorage.setItem('lang', l);
  }

  return (
    <LanguageContext.Provider value={{ lang, t: STRINGS[lang] || es, setLang }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  return useContext(LanguageContext);
}
