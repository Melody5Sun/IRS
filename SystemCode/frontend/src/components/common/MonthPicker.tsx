import { useState, type CSSProperties, type FocusEvent } from "react";
import { useI18n } from "../../i18n/LanguageProvider";

type MonthPickerProps = {
  // "YYYY-MM"，空串表示未填
  value: string;
  onChange: (value: string) => void;
  style?: CSSProperties;
  // 读屏用的字段名（按钮在 <label> 里时浏览器不会从 label 取名）
  "aria-label"?: string;
};

const MONTH_VALUE = /^(\d{4})-(\d{2})$/;
const locale = (lang: string) => (lang === "zh" ? "zh-CN" : "en");

// 年月选择器：原生 <input type="month"> 的弹出日历由浏览器绘制、无法和页面统一，所以自己渲染一个「年份 + 12 个月」面板
export function MonthPicker({ value, onChange, style, "aria-label": ariaLabel }: MonthPickerProps) {
  const { lang, t } = useI18n();
  const match = MONTH_VALUE.exec(value);
  const [open, setOpen] = useState(false);
  const [year, setYear] = useState(() => (match ? Number(match[1]) : new Date().getFullYear()));
  const label = match ? new Intl.DateTimeFormat(locale(lang), { year: "numeric", month: "short" }).format(new Date(Number(match[1]), Number(match[2]) - 1)) : "";
  const monthName = (month: number) => new Intl.DateTimeFormat(locale(lang), { month: "short" }).format(new Date(2000, month, 1));
  const today = new Date();

  const show = () => { setYear(match ? Number(match[1]) : today.getFullYear()); setOpen(true); };
  const pick = (next: string) => { onChange(next); setOpen(false); };
  // 焦点移到面板外才关闭；在面板里按 Tab 切换按钮时保持打开
  const blur = (event: FocusEvent<HTMLDivElement>) => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false); };

  return <div className="select month-picker" onBlur={blur} onKeyDown={(event) => { if (event.key === "Escape" && open) { event.preventDefault(); setOpen(false); } }}>
    <button type="button" className="select-trigger" aria-haspopup="dialog" aria-expanded={open} style={style}
      aria-label={ariaLabel && ariaLabel + "：" + (match ? label : t("common.selectMonth"))} onClick={() => (open ? setOpen(false) : show())}>
      <span className={match ? undefined : "select-placeholder"}>{match ? label : t("common.selectMonth")}</span>
    </button>
    {/* 选择器常放在 <label> 里：阻止面板空白处的 click 触发 label 的默认行为（会把面板重新打开） */}
    {open && <div className="popover month-panel" role="dialog" aria-label={t("common.selectMonth")} onClick={(event) => event.preventDefault()}
      // 点面板空白处不让焦点离开，否则会被当成点到外面而关闭
      onMouseDown={(event) => { if (!(event.target instanceof HTMLButtonElement)) event.preventDefault(); }}>
      <header>
        <button type="button" aria-label={t("common.prevYear")} onClick={() => setYear(year - 1)}>‹</button>
        <b>{year}</b>
        <button type="button" aria-label={t("common.nextYear")} onClick={() => setYear(year + 1)}>›</button>
      </header>
      <div className="month-grid">
        {Array.from({ length: 12 }, (_, month) => {
          const next = `${year}-${String(month + 1).padStart(2, "0")}`;
          const thisMonth = year === today.getFullYear() && month === today.getMonth();
          return <button type="button" key={month} aria-pressed={next === value} className={thisMonth ? "this-month" : undefined} onClick={() => pick(next)}>{monthName(month)}</button>;
        })}
      </div>
      {match && <footer><button type="button" onClick={() => pick("")}>{t("common.clear")}</button></footer>}
    </div>}
  </div>;
}
