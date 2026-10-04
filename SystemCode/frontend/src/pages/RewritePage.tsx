import { useState } from "react";
import { PageFrame } from "../components/layout/PageFrame";
import { REWRITE_BLOCKS } from "../mocks/data";

export function RewritePage() {
  const [active, setActive] = useState(0);
  const [reviewed, setReviewed] = useState<Record<number, string>>({});
  const block = REWRITE_BLOCKS[active];
  return (
    <PageFrame eyebrow="STEP 03 · JD-GROUNDED RESUME TAILORING" title="Resume tailoring" description="Review every proposed change against the original. CareerPilot never adds an achievement that you have not confirmed.">
      <div className="workspace">
        <aside>
          <div className="aside-head"><h3>Suggestion blocks</h3><span>{Object.keys(reviewed).length}/{REWRITE_BLOCKS.length} reviewed</span></div>
          {REWRITE_BLOCKS.map((item, index) => <button className={active === index ? "active" : ""} onClick={() => setActive(index)} key={item.title}><span>{String(index + 1).padStart(2, "0")}</span><b>{item.title}</b><small>{reviewed[index] || "Review"}</small></button>)}
        </aside>
        <main className="editor">
          <span className="eyebrow">TARGET ROLE</span><h2>Backend Engineer Intern · Lumen Pay</h2>
          <div className="compare"><section><header>ORIGINAL</header><p>{block.original}</p></section><section><header>TAILORED DRAFT</header><textarea value={block.revised} readOnly /></section></div>
          <div className="reason"><h3>Why this change</h3><p>{block.reason}</p></div>
          <div className="editor-actions"><button className="secondary" onClick={() => setReviewed({ ...reviewed, [active]: "Rejected" })}>Reject</button><button className="primary" onClick={() => setReviewed({ ...reviewed, [active]: "Accepted" })}>Accept change</button></div>
        </main>
      </div>
      <div className="savebar"><span>{Object.values(reviewed).filter((value) => value === "Accepted").length} accepted changes · Draft not saved</span><button className="primary">Save final resume</button></div>
    </PageFrame>
  );
}
