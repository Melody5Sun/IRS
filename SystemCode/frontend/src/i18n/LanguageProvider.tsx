import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { en, type MessageKey } from "./en";
import { zh } from "./zh";

export type Lang = "en" | "zh";
export type Translate = (key: MessageKey, vars?: Record<string, string | number>) => string;

const DICTIONARIES: Record<Lang, Record<MessageKey, string>> = { en, zh };
const STORAGE_KEY = "careerpilot:lang";

// 把 {name} 占位符替换成实际值；缺失的变量保留原样，便于发现漏传
export function format(template: string, vars?: Record<string, string | number>) {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (match, name: string) => (name in vars ? String(vars[name]) : match));
}

export function translate(lang: Lang, key: MessageKey, vars?: Record<string, string | number>) {
  return format(DICTIONARIES[lang][key] ?? en[key], vars);
}

// localStorage 在隐私模式等情况下可能抛异常，读写都要兜底
function readStoredLang(): Lang {
  try {
    return localStorage.getItem(STORAGE_KEY) === "zh" ? "zh" : "en";
  } catch {
    return "en";
  }
}

type LanguageContextValue = { lang: Lang; setLang: (lang: Lang) => void; t: Translate };

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(readStoredLang);

  useEffect(() => {
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
  }, [lang]);

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // 存不了就只在本次会话生效
    }
  }, []);

  const value = useMemo<LanguageContextValue>(() => ({
    lang,
    setLang,
    t: (key, vars) => translate(lang, key, vars),
  }), [lang, setLang]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useI18n() {
  const value = useContext(LanguageContext);
  if (!value) throw new Error("useI18n must be used inside LanguageProvider");
  return value;
}
