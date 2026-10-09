import { useEffect, useId, useState, type CSSProperties, type KeyboardEvent } from "react";

export type SelectOption = { value: string; label: string };

type SelectProps = {
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  // 当前值不在选项里时显示（如「请选择」）
  placeholder?: string;
  disabled?: boolean;
  style?: CSSProperties;
  // 读屏用的字段名：按钮在 <label> 里时浏览器不会从 label 取名，选中的值由按钮内容读出
  "aria-label"?: string;
};

// 自绘下拉框：原生 <select> 展开后的选项列表由系统绘制、无法和页面统一，所以自己渲染（样式见 base.css 的 .select / .dropdown-list）。
// 键盘：↑↓ / Home / End 移动，回车或空格选中，Esc 关闭，按字母跳到以它开头的选项
export function Select({ value, options, onChange, placeholder, disabled, style, "aria-label": ariaLabel }: SelectProps) {
  const listId = useId();
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(-1);
  const selected = options.findIndex((option) => option.value === value);
  const optionId = (index: number) => listId + "-" + index;

  // 键盘移动时让高亮项保持在可视区域
  useEffect(() => { if (open && highlight >= 0) document.getElementById(optionId(highlight))?.scrollIntoView({ block: "nearest" }); }, [open, highlight]);

  const show = (index = selected) => { setOpen(true); setHighlight(Math.max(0, index)); };
  const pick = (index: number) => {
    setOpen(false);
    if (options[index] && options[index].value !== value) onChange(options[index].value);
  };

  const keyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    const move = (index: number) => {
      event.preventDefault();
      if (!open) show();
      else setHighlight(Math.max(0, Math.min(options.length - 1, index)));
    };
    if (event.key === "ArrowDown") move(highlight + 1);
    else if (event.key === "ArrowUp") move(highlight - 1);
    else if (event.key === "Home") move(0);
    else if (event.key === "End") move(options.length - 1);
    else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (open) pick(highlight); else show();
    } else if (event.key === "Escape" && open) {
      event.preventDefault();
      setOpen(false);
    } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
      // 从当前项之后开始找，连按同一个字母可以在同字母开头的选项间轮换
      const start = (open ? highlight : selected) + 1;
      const order = [...options.slice(start), ...options.slice(0, start)];
      const hit = order.find((option) => option.label.toLowerCase().startsWith(event.key.toLowerCase()));
      if (hit) show(options.indexOf(hit));
    }
  };

  return <div className="select">
    <button type="button" className="select-trigger" role="combobox" aria-haspopup="listbox" aria-expanded={open} aria-controls={listId}
      aria-label={ariaLabel} aria-activedescendant={open && highlight >= 0 ? optionId(highlight) : undefined}
      disabled={disabled} style={style} onClick={() => (open ? setOpen(false) : show())} onBlur={() => setOpen(false)} onKeyDown={keyDown}>
      <span className={selected < 0 ? "select-placeholder" : undefined}>{selected >= 0 ? options[selected].label : placeholder}</span>
    </button>
    {/* 下拉框常放在 <label> 里：阻止选项的 click 冒泡触发 label 的默认行为，否则会把列表重新打开 */}
    {open && options.length > 0 && <ul className="popover dropdown-list" id={listId} role="listbox" onClick={(event) => event.preventDefault()}>
      {/* mousedown 里选中并阻止默认行为，避免按钮先失焦把列表关掉 */}
      {options.map((option, index) => <li key={option.value} id={optionId(index)} role="option" aria-selected={index === selected}
        className={index === highlight ? "active" : undefined}
        onMouseDown={(event) => { event.preventDefault(); pick(index); }} onMouseEnter={() => setHighlight(index)}>{option.label}</li>)}
    </ul>}
  </div>;
}
