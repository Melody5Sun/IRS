import { createContext, useContext, useMemo, type ReactNode } from "react";
import { useI18n } from "../../i18n/LanguageProvider";
import type { ValidationIssue } from "./validation";

type ValidationValue = {
  color: string;
  // 字段按自己的 DOM id 取错误文案，无需逐个传 error/errorColor
  errorFor: (id?: string) => string | undefined;
  sectionStatus: (section: string) => { meta: string; color?: string };
  entryTodo: (section: string, index: number) => number;
};

const ValidationContext = createContext<ValidationValue>({
  color: "",
  errorFor: () => undefined,
  sectionStatus: () => ({ meta: "" }),
  entryTodo: () => 0,
});

export function ValidationProvider({ issues, color, children }: { issues: ValidationIssue[]; color: string; children: ReactNode }) {
  const { t } = useI18n();
  const value = useMemo<ValidationValue>(() => {
    const byId = new Map(issues.map((issue) => [issue.id, issue]));
    return {
      color,
      errorFor: (id) => {
        const issue = id ? byId.get(id) : undefined;
        return issue && t(issue.message);
      },
      sectionStatus: (section) => {
        const count = issues.filter((issue) => issue.section === section).length;
        return count ? { meta: t("profile.fieldsRemaining", { count }), color } : { meta: t("profile.complete") };
      },
      entryTodo: (section, index) => issues.filter((issue) => issue.id.startsWith(`fld-${section}-${index}-`)).length,
    };
  }, [color, issues, t]);
  return <ValidationContext.Provider value={value}>{children}</ValidationContext.Provider>;
}

export function useValidation() {
  return useContext(ValidationContext);
}

// 有错误时给输入框描边
export function errorBorder(error: string | undefined, color: string) {
  return error ? { borderColor: color } : undefined;
}
