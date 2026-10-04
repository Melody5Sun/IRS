import type { ReactNode } from "react";

export function DashboardCard({ title, meta, text, onExplore, children }: { title: string; meta: string; text: string; onExplore: () => void; children: ReactNode }) {
  return (
    <section className="card dash-card">
      <div className="card-head"><h2>{title}</h2><span>{meta}</span></div>
      <p>{text}</p>
      <div className="card-body">{children}</div>
      <button className="primary explore" onClick={onExplore}>Explore More →</button>
    </section>
  );
}
