import { useState } from "react";
import { PageFrame } from "../../components/layout/PageFrame";
import { useI18n } from "../../i18n/LanguageProvider";
import { REWRITE_BLOCKS } from "../../mocks/data";

type Review = "accepted" | "rejected";

// 简历改写页目前仍是示例数据，尚未接入 /resumes/rewrite 接口
export function RewritePage() {
  const { t } = useI18n();
  const [active, setActive] = useState(0);
  const [reviewed, setReviewed] = useState<Record<number, Review>>({});
  const block = REWRITE_BLOCKS[active];
  const reviewLabel = (index: number) => reviewed[index] === "accepted" ? t("rewrite.accepted") : reviewed[index] === "rejected" ? t("rewrite.rejected") : t("rewrite.review");
  const acceptedCount = Object.values(reviewed).filter((value) => value === "accepted").length;

  return (
    <PageFrame eyebrow={t("rewrite.eyebrow")} title={t("rewrite.title")} description={t("rewrite.description")}>
      <div className="workspace">
        <aside>
          <div className="aside-head"><h3>{t("rewrite.blocks")}</h3><span>{t("rewrite.reviewedCount", { reviewed: Object.keys(reviewed).length, total: REWRITE_BLOCKS.length })}</span></div>
          {REWRITE_BLOCKS.map((item, index) => <button className={active === index ? "active" : ""} onClick={() => setActive(index)} key={item.title}><span>{String(index + 1).padStart(2, "0")}</span><b>{item.title}</b><small>{reviewLabel(index)}</small></button>)}
        </aside>
        <main className="editor">
          <span className="eyebrow">{t("rewrite.targetRole")}</span><h2>Backend Engineer Intern · Lumen Pay</h2>
          <div className="compare">
            <section><header>{t("rewrite.originalLabel")}</header><p>{block.original}</p></section>
            <section><header>{t("rewrite.draftLabel")}</header><textarea value={block.revised} readOnly /></section>
          </div>
          <div className="reason"><h3>{t("rewrite.why")}</h3><p>{block.reason}</p></div>
          <div className="editor-actions">
            <button className="secondary" onClick={() => setReviewed({ ...reviewed, [active]: "rejected" })}>{t("rewrite.reject")}</button>
            <button className="primary" onClick={() => setReviewed({ ...reviewed, [active]: "accepted" })}>{t("rewrite.accept")}</button>
          </div>
        </main>
      </div>
      <div className="savebar"><span>{t("rewrite.savebar", { count: acceptedCount })}</span><button className="primary">{t("rewrite.save")}</button></div>
    </PageFrame>
  );
}
