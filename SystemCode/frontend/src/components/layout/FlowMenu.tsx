import { useEffect, useRef, useState, type PointerEvent } from "react";
import { useGo } from "../../app/routes";
import { useI18n } from "../../i18n/LanguageProvider";
import type { MessageKey } from "../../i18n/en";
import type { Page } from "../../types/domain";

// 参考原型的「流程快捷菜单」：五步流程，仪表盘不算一步
const STEPS: Array<{ page: Page; name: MessageKey; desc: MessageKey }> = [
  { page: "profile", name: "nav.profile", desc: "flow.desc.profile" },
  { page: "jobs", name: "nav.jobs", desc: "flow.desc.jobs" },
  { page: "rewrite", name: "nav.rewrite", desc: "flow.desc.rewrite" },
  { page: "interview", name: "nav.interview", desc: "flow.desc.interview" },
  { page: "targets", name: "nav.targets", desc: "flow.desc.targets" },
];

type Position = { left: number; top: number };

const STORAGE_KEY = "careerpilot.flowMenuPosition";
const MARGIN = 12;
// 移动超过这个距离才算拖动，否则当作点击
const DRAG_THRESHOLD = 4;

const pad = (value: number) => String(value).padStart(2, "0");

function clamp(position: Position, size: number): Position {
  return {
    left: Math.min(Math.max(MARGIN, position.left), window.innerWidth - size - MARGIN),
    top: Math.min(Math.max(MARGIN, position.top), window.innerHeight - size - MARGIN),
  };
}

// 位置只是本机偏好：读不到（隐私模式、被清理）就回到默认的右下角
function loadPosition(): Position | null {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null") as Position | null;
    return value && typeof value.left === "number" && typeof value.top === "number" ? value : null;
  } catch { return null; }
}

function savePosition(position: Position) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(position)); } catch { /* 存不下就只在本次会话生效 */ }
}

export function FlowMenu({ page }: { page: Page }) {
  const { t } = useI18n();
  const go = useGo();
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<Position | null>(loadPosition);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const drag = useRef<{ dx: number; dy: number; x: number; y: number; moved: boolean } | null>(null);
  // 拖动结束后浏览器还会派发一次 click，用它吞掉，避免拖完就打开菜单
  const justDragged = useRef(false);
  const latest = useRef(position);
  latest.current = position;

  const index = STEPS.findIndex((step) => step.page === page);
  const last = STEPS.length - 1;

  useEffect(() => setOpen(false), [page]);

  // 窗口变小后把按钮拉回可见区域
  useEffect(() => {
    const onResize = () => {
      if (latest.current && buttonRef.current) setPosition(clamp(latest.current, buttonRef.current.offsetWidth));
    };
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const navigate = (target: Page) => { setOpen(false); go(target); };

  const onPointerDown = (event: PointerEvent<HTMLButtonElement>) => {
    if (event.button !== 0) return;
    const rect = event.currentTarget.getBoundingClientRect();
    drag.current = { dx: event.clientX - rect.left, dy: event.clientY - rect.top, x: event.clientX, y: event.clientY, moved: false };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const onPointerMove = (event: PointerEvent<HTMLButtonElement>) => {
    const state = drag.current;
    if (!state) return;
    if (!state.moved && Math.hypot(event.clientX - state.x, event.clientY - state.y) < DRAG_THRESHOLD) return;
    state.moved = true;
    setPosition(clamp({ left: event.clientX - state.dx, top: event.clientY - state.dy }, event.currentTarget.offsetWidth));
  };

  const onPointerUp = () => {
    const state = drag.current;
    drag.current = null;
    if (!state?.moved) return;
    justDragged.current = true;
    if (latest.current) savePosition(latest.current);
  };

  const onClick = () => {
    if (justDragged.current) { justDragged.current = false; return; }
    setOpen((value) => !value);
  };

  // 面板朝屏幕中心展开，按钮拖到哪个角都不会超出视口
  const alignLeft = position ? position.left < window.innerWidth / 2 : false;
  const below = position ? position.top < window.innerHeight / 2 : false;

  const hint = index < 0 ? t("flow.hint.start")
    : index === last ? t("flow.hint.end")
    : t("flow.hint.next", { name: t(STEPS[index + 1].name), desc: t(STEPS[index + 1].desc) });

  return (
    <div className="flow-fab" style={position ? { left: position.left, top: position.top, right: "auto", bottom: "auto" } : undefined}>
      {open && <div className={"flow-menu" + (alignLeft ? " left" : "") + (below ? " below" : "")} aria-label={t("flow.title")}>
        <div className="flow-menu-head">
          <span className="eyebrow">{t("flow.title")}</span>
          <span>{index < 0 ? t("flow.dashboard") : t("flow.position", { step: pad(index + 1), total: pad(STEPS.length) })}</span>
        </div>
        {STEPS.map((step, stepIndex) => (
          <button key={step.page} className="flow-step" onClick={() => navigate(step.page)} aria-current={stepIndex === index ? "step" : undefined}>
            <span className="flow-step-number">{pad(stepIndex + 1)}</span>
            <span>
              <span className="flow-step-name">
                {t(step.name)}
                {stepIndex === index && <em>{t("flow.current")}</em>}
                {index > -1 && stepIndex < index && <i aria-label={t("flow.done")}>✓</i>}
              </span>
              <small>{t(step.desc)}</small>
            </span>
          </button>
        ))}
        <div className="flow-menu-actions">
          <button className="secondary" disabled={index <= 0} onClick={() => navigate(STEPS[index - 1].page)}>{t("flow.prev")}</button>
          <button className="primary" disabled={index === last} onClick={() => navigate(STEPS[index + 1].page)}>{t("flow.next")}</button>
          <button className="flow-dashboard" onClick={() => navigate("dashboard")}>{t("flow.dashboardButton")}</button>
        </div>
        <p className="flow-hint">{hint}</p>
      </div>}
      <button
        ref={buttonRef}
        className="float"
        title={t("app.floatTitle")}
        aria-expanded={open}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={() => { drag.current = null; }}
        onClick={onClick}
      >
        {open ? "✕" : <>↗<small>{index < 0 ? "00" : pad(index + 1)}</small></>}
      </button>
    </div>
  );
}
