import { useEffect, useId, useState, type CSSProperties, type KeyboardEvent, type ReactNode } from "react";
import { MonthPicker } from "../../components/common/MonthPicker";
import { Select } from "../../components/common/Select";
import { useI18n } from "../../i18n/LanguageProvider";
import { errorBorder, useValidation } from "./ValidationContext";

// 画像表单的基础字段组件：传入 id 的字段会自动显示该 id 对应的校验错误

function FieldError({ error }: { error?: string }) {
  return error ? <small className="field-error">{error}</small> : null;
}

type TextFieldProps = {
  id?: string; label: string; value: string | null | undefined; onChange: (value: string) => void;
  area?: boolean; type?: string; required?: boolean; placeholder?: string;
  // 可搜索的下拉选项：边输入边筛选，也允许填列表外的值
  suggestions?: string[];
};

// 按输入筛选下拉选项（忽略大小写，开头匹配的排前面）；输入正好是某个选项或为空时列出全部，方便重新选择
export function filterSuggestions(suggestions: string[], input: string) {
  const query = input.trim().toLowerCase();
  if (!query || suggestions.some((item) => item.toLowerCase() === query)) return suggestions;
  const matches = suggestions.filter((item) => item.toLowerCase().includes(query));
  return [...matches.filter((item) => item.toLowerCase().startsWith(query)), ...matches.filter((item) => !item.toLowerCase().startsWith(query))];
}

type SuggestionInputProps = {
  value: string; onChange: (value: string) => void; onPick: (value: string) => void; suggestions: string[];
  style?: CSSProperties; placeholder?: string; onKeyDown?: (event: KeyboardEvent<HTMLInputElement>) => void;
};

// 可搜索下拉输入框：原生 datalist 的弹层样式由浏览器决定、无法和页面统一，所以自己渲染列表。
// 上下键移动、回车选中、Esc 关闭；没有高亮选项时按键交给 onKeyDown
function SuggestionInput({ value, onChange, onPick, suggestions, style, placeholder, onKeyDown }: SuggestionInputProps) {
  const listId = useId();
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(-1);
  const matches = filterSuggestions(suggestions, value);
  const expanded = open && matches.length > 0;
  const optionId = (index: number) => listId + "-" + index;

  // 键盘移动时让高亮项保持在可视区域
  useEffect(() => { if (highlight >= 0) document.getElementById(optionId(highlight))?.scrollIntoView({ block: "nearest" }); }, [highlight]);

  const pick = (item: string) => { onPick(item); setOpen(false); setHighlight(-1); };
  const keyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
      const step = event.key === "ArrowDown" ? 1 : -1;
      setHighlight((current) => Math.max(0, Math.min(matches.length - 1, current + step)));
    } else if (event.key === "Enter" && expanded && matches[highlight]) {
      event.preventDefault();
      pick(matches[highlight]);
    } else if (event.key === "Escape" && expanded) {
      event.preventDefault();
      setOpen(false);
    } else onKeyDown?.(event);
  };

  return <div className="suggest">
    <input role="combobox" aria-expanded={expanded} aria-controls={listId} aria-autocomplete="list" aria-activedescendant={expanded && highlight >= 0 ? optionId(highlight) : undefined}
      style={style} value={value} placeholder={placeholder}
      onChange={(event) => { onChange(event.target.value); setOpen(true); setHighlight(-1); }}
      onFocus={() => setOpen(true)} onBlur={() => setOpen(false)} onKeyDown={keyDown} />
    {/* 字段放在 <label> 里：阻止选项的 click 冒泡触发 label 聚焦输入框，否则列表会重新打开 */}
    {expanded && <ul className="popover dropdown-list" id={listId} role="listbox" onClick={(event) => event.preventDefault()}>
      {/* mousedown 里选中并阻止默认行为，避免输入框先失焦把列表关掉 */}
      {matches.map((item, index) => <li key={item} id={optionId(index)} role="option" aria-selected={index === highlight} className={index === highlight ? "active" : undefined}
        onMouseDown={(event) => { event.preventDefault(); pick(item); }} onMouseEnter={() => setHighlight(index)}>{item}</li>)}
    </ul>}
  </div>;
}

export function TextField({ id, label, value, onChange, area, type = "text", required, placeholder, suggestions }: TextFieldProps) {
  const { errorFor, color } = useValidation();
  const error = errorFor(id);
  const style = errorBorder(error, color);
  return <label className="field" id={id}>
    <span>{label}{required && " *"}</span>
    {area
      ? <textarea style={style} value={value ?? ""} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} />
      : type === "month"
        ? <MonthPicker style={style} value={value ?? ""} onChange={onChange} aria-label={label} />
        : suggestions
        ? <SuggestionInput style={style} value={value ?? ""} placeholder={placeholder} suggestions={suggestions} onChange={onChange} onPick={onChange} />
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
    <Select style={errorBorder(error, color)} value={value ?? ""} placeholder={t("profile.select")} onChange={onChange} aria-label={label}
      options={options.map(([optionValue, labelText]) => ({ value: optionValue, label: labelText }))} />
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
export function TagEditor({ id, label, values, onChange, required, placeholder, quickOptions = [], suggestions }: { id?: string; label: string; values: string[]; onChange: (values: string[]) => void; required?: boolean; placeholder: string; quickOptions?: string[]; suggestions?: string[] }) {
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
  const addOnKey = (event: KeyboardEvent<HTMLInputElement>) => { if (event.key === "Enter" || event.key === ",") { event.preventDefault(); add(); } };
  return <div className="field tag-editor" id={id}>
    <span>{label}{required && " *"}</span>
    <TagList values={values} onRemove={(value) => onChange(values.filter((item) => item !== value))} />
    <div className="tag-entry">
      {/* 从下拉列表选中直接加成标签，手动输入仍按回车、逗号或「添加」 */}
      {suggestions
        ? <SuggestionInput style={errorBorder(error, color)} value={draftValue} placeholder={placeholder} onChange={setDraftValue} onPick={add} onKeyDown={addOnKey}
          suggestions={suggestions.filter((item) => !values.some((value) => value.toLowerCase() === item.toLowerCase()))} />
        : <input style={errorBorder(error, color)} value={draftValue} placeholder={placeholder} onChange={(event) => setDraftValue(event.target.value)} onKeyDown={addOnKey} />}
      <button type="button" className="secondary" onClick={() => add()}>{t("profile.add")}</button>
    </div>
    {quickOptions.length > 0 && <div className="quick-options">
      <small>{t("profile.common")}</small>
      {quickOptions.filter((item) => !values.includes(item)).map((item) => <button type="button" key={item} onClick={() => add(item)}>{item}</button>)}
    </div>}
    <FieldError error={error} />
  </div>;
}
