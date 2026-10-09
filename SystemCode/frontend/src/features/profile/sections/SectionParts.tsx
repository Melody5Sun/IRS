import { useState, type ReactNode } from "react";
import { useI18n } from "../../../i18n/LanguageProvider";
import type { UserProfile } from "../../../types/api";
import type { Option } from "../constants";
import type { ProfileEditor } from "../useProfileEditor";
import { useValidation } from "../ValidationContext";

export type SectionProps = { editor: ProfileEditor; draft: UserProfile };

// 把 [value, 文案 key] 选项翻译成下拉框/按钮组使用的 [value, 文案]
export function useOptions(options: Option[]): Array<[string, string]> {
  const { t } = useI18n();
  return options.map(([value, key]) => [value, t(key)]);
}

// 表单区块：标题右侧显示该区块剩余必填项；不传 section 时视为已完成
export function FormSection({ id, title, section, children }: { id?: string; title: string; section?: string; children: ReactNode }) {
  const { t } = useI18n();
  const { sectionStatus } = useValidation();
  const status = section ? sectionStatus(section) : { meta: t("profile.complete"), color: undefined };
  return <section className="form-section" id={id}>
    <div className="section-title"><h2>{title}</h2><span style={{ color: status.color }}>{status.meta}</span></div>
    {children}
  </section>;
}

// 可折叠的条目卡片（某段经历、某个项目…），删除需二次确认
export function EntryCard({ title, section, index, onRemove, children }: { title: string; section: string; index: number; onRemove: () => void; children: ReactNode }) {
  const { t } = useI18n();
  const { entryTodo } = useValidation();
  const todoCount = entryTodo(section, index);
  const [open, setOpen] = useState(true);
  const [confirming, setConfirming] = useState(false);
  return <div className="entry-card">
    <div className="entry-head">
      <button className="entry-toggle" onClick={() => setOpen(!open)}>
        <small>{open ? t("profile.collapse") : t("profile.expand")}</small>
        <h3>{title}</h3>
        {Boolean(todoCount) && <span className="entry-todo">{t("profile.todo", { count: todoCount })}</span>}
      </button>
      {confirming
        ? <span className="delete-confirm">{t("profile.deleteEntry")}<button className="secondary" onClick={onRemove}>{t("profile.delete")}</button><button className="ghost" onClick={() => setConfirming(false)}>{t("common.cancel")}</button></span>
        : <button className="ghost" onClick={() => setConfirming(true)}>{t("profile.remove")}</button>}
    </div>
    {open && children}
  </div>;
}

export function AddEntryButton({ label, onClick }: { label: string; onClick: () => void }) {
  return <button className="secondary add-entry" onClick={onClick}>{label}</button>;
}
