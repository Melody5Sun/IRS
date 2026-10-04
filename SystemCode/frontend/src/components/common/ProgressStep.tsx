export function ProgressStep({ done, title, detail, action, onClick }: { done?: boolean; title: string; detail: string; action: string; onClick?: () => void }) {
  return (
    <div className="step">
      <i className={done ? "done" : ""} />
      <span><b>{title}</b><small>{detail}</small></span>
      <button className="secondary" onClick={onClick}>{action}</button>
    </div>
  );
}
