import { useState, type ReactNode } from "react";
import { useI18n } from "../../i18n/LanguageProvider";
import { errorBorder, useValidation } from "./ValidationContext";

// 画像表单的基础字段组件：传入 id 的字段会自动显示该 id 对应的校验错误

function FieldError({ error }: { error?: string }) {
  return error ? <small className="field-error">{error}</small> : null;
}

type TextFieldProps = {
  id?: string; label: string; value: string | null | undefined; onChange: (value: string) => void;
  area?: boolean; type?: string; required?: boolean; placeholder?: string;
};

export function TextField({ id, label, value, onChange, area, type = "text", required, placeholder }: TextFieldProps) {
  const { errorFor, color } = useValidation();
  const error = errorFor(id);
  const style = errorBorder(error, color);
  return <label className="field" id={id}>
    <span>{label}{required && " *"}</span>
    {area
      ? <textarea style={style} value={value ?? ""} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} />
      : <input type={type} style={style} value={value ?? ""} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} />}
    <FieldError error={error} />
  </label>;
}

export function SelectField({ id, label, value, onChange, options, required }: { id?: string; label: string; value: string | null | undefined; onChange: (value: string) => void; options: Array<[string, string]>; required?: boolean }) {
  const { t } = useI18n();
  const { errorFor, color } = useValidation();
  const error = errorFor(id);
  return <label className="field" id={id}>
    <span>{label}{required && " *"}</span>
    <select style={errorBorder(error, color)} value={value ?? ""} onChange={(event) => onChange(event.target.value)}>
      <option value="">{t("profile.select")}</option>
      {options.map(([optionValue, labelText]) => <option key={optionValue} value={optionValue}>{labelText}</option>)}
    </select>
    <FieldError error={error} />
  </label>;
}

// 按钮组：多选（工作模式、雇佣类型）和单选（学历类型）共用
export function ChoiceGroup({ id, label, options, selected, onSelect, compact }: { id: string; label: string; options: Array<[string, string]>; selected: string[]; onSelect: (value: string) => void; compact?: boolean }) {
  const { errorFor, color } = useValidation();
  const error = errorFor(id);
  return <div className="field" id={id}>
    <span>{label} *</span>
    <div className={compact ? "choices compact-choices" : "choices"}>
      {options.map(([value, text]) => <button type="button" style={errorBorder(error, color)} key={value} className={selected.includes(value) ? "active" : ""} onClick={() => onSelect(value)}>{text}</button>)}
    </div>
    <FieldError error={error} />
  </div>;
}

export function TagList({ values, onRemove }: { values: string[]; onRemove: (value: string) => void }) {
  const { t } = useI18n();
  if (!values.length) return null;
  return <div className="tag-list">
    {values.map((value) => <span className="profile-tag" key={value}>{value}<button type="button" title={t("profile.removeTag", { value })} onClick={() => onRemove(value)}>x</button></span>)}
  </div>;
}

// 从下拉框添加标签的字段（目标行业、目标岗位），children 为下拉框
export function TagPickerField({ id, label, values, onRemove, children }: { id: string; label: string; values: string[]; onRemove: (value: string) => void; children: ReactNode }) {
  const { errorFor } = useValidation();
  return <div className="field" id={id}>
    <span>{label} *</span>
    <TagList values={values} onRemove={onRemove} />
    {children}
    <FieldError error={errorFor(id)} />
  </div>;
}

// 自由输入的标签字段：回车或逗号添加，忽略大小写去重
export function TagEditor({ id, label, values, onChange, required, placeholder, quickOptions = [] }: { id?: string; label: string; values: string[]; onChange: (values: string[]) => void; required?: boolean; placeholder: string; quickOptions?: string[] }) {
  const { t } = useI18n();
  const { errorFor, color } = useValidation();
  const error = errorFor(id);
  const [draftValue, setDraftValue] = useState("");
  const add = (raw = draftValue) => {
    const additions = raw.split(",").map((item) => item.trim()).filter(Boolean);
    if (!additions.length) return;
    onChange([...values, ...additions.filter((item) => !values.some((value) => value.toLowerCase() === item.toLowerCase()))]);
    setDraftValue("");
  };
  return <div className="field tag-editor" id={id}>
    <span>{label}{required && " *"}</span>
    <TagList values={values} onRemove={(value) => onChange(values.filter((item) => item !== value))} />
    <div className="tag-entry">
      <input style={errorBorder(error, color)} value={draftValue} placeholder={placeholder} onChange={(event) => setDraftValue(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === ",") { event.preventDefault(); add(); } }} />
      <button type="button" className="secondary" onClick={() => add()}>{t("profile.add")}</button>
    </div>
    {quickOptions.length > 0 && <div className="quick-options">
      <small>{t("profile.common")}</small>
      {quickOptions.filter((item) => !values.includes(item)).map((item) => <button type="button" key={item} onClick={() => add(item)}>{item}</button>)}
    </div>}
    <FieldError error={error} />
  </div>;
}
