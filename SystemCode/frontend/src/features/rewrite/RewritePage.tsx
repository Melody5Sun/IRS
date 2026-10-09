import { useGo } from "../../app/routes";
import { PageFrame } from "../../components/layout/PageFrame";
import { useI18n } from "../../i18n/LanguageProvider";
import type { MessageKey } from "../../i18n/en";
import { formatDateTime } from "../../lib/format";
import type { RewriteBlock, RewriteField, RewriteValue } from "../../types/api";
import { blockKey, draftKey } from "./assemble";
import { rewriteErrorMessage } from "./messages";
import { inputChangeIndex, useRewriteSession, type RewriteSession } from "./useRewriteSession";

const FIELD_KEYS: Record<RewriteField, MessageKey> = {
  description: "rewrite.field.description",
  summary: "rewrite.field.summary",
  technologies: "rewrite.field.technologies",
  skill_groups: "rewrite.field.skillGroups",
};

// 技术栈和技能栏是列表，只读展示成文本
function formatValue(value: RewriteValue) {
  if (typeof value === "string") return value;
  return value.map((item) => typeof item === "string" ? item : item.category ? `${item.category}: ${item.description}` : item.description).join("\n");
}

export function RewritePage() {
  const { lang, t } = useI18n();
  const go = useGo();
  const session = useRewriteSession();
  const { selectedTarget, saved, result, block } = session;

  const statusLabel = (item: RewriteBlock) => {
    if (item.status === "unchanged") return t("rewrite.status.unchanged");
    const decision = session.reviews[blockKey(item)];
    if (decision) return decision === "accepted" ? t("rewrite.accepted") : t("rewrite.rejected");
    return session.pending[blockKey(item)]?.length ? t("rewrite.status.needsInput") : t("rewrite.review");
  };

  return (
    <PageFrame eyebrow={t("rewrite.eyebrow")} title={t("rewrite.title")} description={t("rewrite.description")}>
      {session.error && <div className="form-message error" role="alert">{rewriteErrorMessage(session.error.reason, t)}</div>}
      {session.loading ? <div className="interview-state"><h2>{t("rewrite.loading")}</h2></div>
        : !selectedTarget ? <div className="interview-state">
          <h2>{t("rewrite.emptyTitle")}</h2>
          <p>{t("rewrite.emptyText")}</p>
          <button className="primary" onClick={() => go("jobs")}>{t("targets.emptyAction")}</button>
        </div>
        : <>
          <div className="rewrite-toolbar">
            <label>{t("rewrite.targetRole")}
              <select value={selectedTarget.job_id} disabled={session.generating} onChange={(event) => session.selectJob(Number(event.target.value))}>
                {session.targets.map((target) => <option key={target.job_id} value={target.job_id}>{target.title} · {target.company}</option>)}
              </select>
            </label>
            <button className="primary" disabled={session.generating} onClick={session.generate}>
              {session.generating ? t("rewrite.generating") : result || saved ? t("rewrite.regenerate") : t("rewrite.generate")}
            </button>
            <small>{t("rewrite.generateHint")}</small>
          </div>

          {saved && <div className={"form-message" + (saved.stale ? " error" : " success")}>
            {session.justSaved ? t("rewrite.justSaved") : t("rewrite.savedAt", { date: formatDateTime(saved.updated_at, lang) })}
            {saved.stale && <> {t("rewrite.stale")}</>}
          </div>}

          {session.generating && <div className="interview-state"><h2>{t("rewrite.generating")}</h2><p>{t("rewrite.generatingText")}</p></div>}

          {result && !session.generating && <>
            <div className="workspace">
              <aside>
                <div className="aside-head"><h3>{t("rewrite.blocks")}</h3><span>{t("rewrite.reviewedCount", { reviewed: session.reviewedCount, total: session.reviewable.length })}</span></div>
                {session.blocks.map((item, index) => <button className={session.active === index ? "active" : ""} onClick={() => session.setActive(index)} key={blockKey(item)}>
                  <span>{String(index + 1).padStart(2, "0")}</span><b>{item.heading}</b><small>{statusLabel(item)}</small>
                </button>)}
              </aside>
              {block && <BlockEditor session={session} block={block} />}
            </div>

            {result.deletion_suggestions.length > 0 && <section className="rewrite-deletions">
              <h3>{t("rewrite.deletionsTitle")}</h3>
              <p>{t("rewrite.deletionsHint")}</p>
              {result.deletion_suggestions.map((deletion, index) => {
                const heading = session.blocks.find((item) => item.section === deletion.section && item.index === deletion.index)?.heading;
                return <label key={index}>
                  <input type="checkbox" checked={Boolean(session.confirmedDeletions[index])} onChange={() => session.toggleDeletion(index)} />
                  <span>
                    <b>{heading}{deletion.line === null ? ` · ${t("rewrite.deleteWhole")}` : ""}</b>
                    <del>{deletion.original}</del>
                    {deletion.reasons.map((reason, reasonIndex) => <small key={reasonIndex}>{reason.explanation[lang]}</small>)}
                  </span>
                </label>;
              })}
            </section>}

            <div className="savebar">
              <span>{t("rewrite.savebar", { reviewed: session.reviewedCount, total: session.reviewable.length, count: session.acceptedCount })}</span>
              <button className="primary" disabled={!session.canSave || session.saving} onClick={session.save}>{session.saving ? t("rewrite.saving") : t("rewrite.save")}</button>
            </div>
          </>}
        </>}
    </PageFrame>
  );
}

function BlockEditor({ session, block }: { session: RewriteSession; block: RewriteBlock }) {
  const { lang, t } = useI18n();
  const target = session.selectedTarget;
  const questions = session.pending[blockKey(block)] ?? [];
  const inputIndex = inputChangeIndex(block);

  return (
    <main className="editor">
      <span className="eyebrow">{t("rewrite.targetRole")} · {target?.title} · {target?.company}</span>
      <h2>{block.heading}</h2>
      {block.status === "unchanged" ? <p className="rewrite-note">{t("rewrite.unchangedText")}</p> : <>
        {block.changes.map((change, index) => {
          const draft = session.drafts[draftKey(block, index)];
          return <div key={index}>
            <div className="compare">
              <section><header>{t("rewrite.originalLabel")} · {t(FIELD_KEYS[change.field])}</header><p>{formatValue(change.original)}</p></section>
              <section><header>{t("rewrite.draftLabel")}</header>
                {draft === undefined ? <p className="draft">{formatValue(change.value)}</p>
                  : <textarea value={draft} disabled={session.filling} onChange={(event) => session.editDraft(block, index, event.target.value)} />}
              </section>
            </div>
            <div className="reason">
              <h3>{t("rewrite.why")}</h3>
              {change.reasons.map((reason, reasonIndex) => <p key={reasonIndex}>{reason.explanation[lang]}</p>)}
            </div>
          </div>;
        })}

        {block.removed_skills.length > 0 && <div className="form-message error">{t("rewrite.removedSkills", { skills: block.removed_skills.join(", ") })}</div>}

        {questions.length > 0 && inputIndex >= 0 && <div className="rewrite-questions">
          <h3>{t("rewrite.questionsTitle")}</h3>
          <p>{t("rewrite.questionsHint")}</p>
          {questions.map((question) => <label key={question.placeholder}>
            <span>{question.question[lang]}</span>
            <small>{question.reason[lang]}</small>
            <input value={session.answerOf(block, question.placeholder)} disabled={session.filling} placeholder={question.placeholder} onChange={(event) => session.setAnswer(block, question.placeholder, event.target.value)} />
          </label>)}
          <button className="primary" disabled={session.filling} onClick={() => session.submitAnswers(block)}>{session.filling ? t("rewrite.filling") : t("rewrite.submitAnswers")}</button>
        </div>}

        <div className="editor-actions">
          <button className="secondary" onClick={() => session.review(block, "rejected")}>{t("rewrite.reject")}</button>
          <button className="primary" disabled={questions.length > 0} title={questions.length ? t("rewrite.answerFirst") : undefined} onClick={() => session.review(block, "accepted")}>{t("rewrite.accept")}</button>
        </div>
      </>}
    </main>
  );
}
