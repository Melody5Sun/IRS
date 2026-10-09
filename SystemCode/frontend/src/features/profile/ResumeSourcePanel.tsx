import { useI18n } from "../../i18n/LanguageProvider";
import { formatDateTime } from "../../lib/format";
import type { ProfileEditor } from "./useProfileEditor";

// 当前简历来源 + 上传入口 + 上传历史列表
export function ResumeSourcePanel({ editor }: { editor: ProfileEditor }) {
  const { lang, t } = useI18n();
  const { activeUpload, updatedAt, uploading, history, historyOpen, draft } = editor;
  return <>
    <input ref={editor.fileRef} className="visually-hidden" type="file" accept="application/pdf,.pdf" onChange={(event) => editor.handleFile(event.target.files?.[0])} />
    <section className="upload">
      <h3>{activeUpload?.filename ?? (updatedAt ? t("profile.source.manual") : t("profile.source.none"))}</h3>
      <p>{activeUpload ? t("profile.source.current", { date: formatDateTime(activeUpload.uploaded_at, lang) }) : updatedAt ? t("profile.source.manualHint") : t("profile.source.noneHint")}</p>
      <button className="secondary" disabled={uploading} onClick={editor.requestUpload}>{uploading ? t("profile.source.processing") : activeUpload ? t("profile.source.uploadAgain") : t("profile.source.upload")}</button>
      {history.length > 0 && <button className="ghost" onClick={() => editor.setHistoryOpen(!historyOpen)}>{historyOpen ? t("profile.history.hide") : t("profile.history.show")}</button>}
    </section>

    {historyOpen && <section className="card history">
      <div className="section-title"><h2>{t("profile.history.title")}</h2><span>{t("profile.history.meta", { count: history.length })}</span></div>
      <p className="history-intro">{t("profile.history.intro")}</p>
      {history.map((item) => <div className="history-row" key={item.id}>
        <span><b>{item.filename || item.name || t("profile.history.untitled")}</b><small>{item.name || t("profile.nameNotDetected")} · {formatDateTime(item.uploaded_at, lang)}</small></span>
        <div className="history-actions">
          <button className="ghost" disabled={uploading} onClick={() => editor.previewHistory(item.id)}>{t("profile.history.preview")}</button>
          {item.id === draft?.resume_upload_id
            ? <em>{t("profile.history.current")}</em>
            : <button className="secondary" disabled={uploading} onClick={() => editor.setOverwriteTarget(item)}>{t("profile.useVersion")}</button>}
        </div>
      </div>)}
    </section>}
  </>;
}
