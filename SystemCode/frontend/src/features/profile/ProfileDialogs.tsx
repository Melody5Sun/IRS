import { Dialog } from "../../components/common/Dialog";
import { useI18n } from "../../i18n/LanguageProvider";
import { formatDateTime } from "../../lib/format";
import type { ProfileEditor } from "./useProfileEditor";

// 画像页的三个确认/预览对话框：重新上传、使用历史版本、预览历史版本
export function ProfileDialogs({ editor }: { editor: ProfileEditor }) {
  const { lang, t } = useI18n();
  const { reuploadOpen, overwriteTarget, previewUpload, activeUpload, draft } = editor;
  return <>
    {reuploadOpen && <Dialog titleId="reupload-title">
      <h2 id="reupload-title">{t("profile.reupload.title")}</h2>
      <p>{t("profile.reupload.text")}</p>
      <small>{t("profile.reupload.note")}</small>
      <div className="dialog-actions">
        <button className="secondary" onClick={() => editor.setReuploadOpen(false)}>{t("common.cancel")}</button>
        <button className="primary" onClick={editor.confirmReupload}>{t("profile.reupload.continue")}</button>
      </div>
    </Dialog>}

    {overwriteTarget && <Dialog titleId="overwrite-title">
      <h2 id="overwrite-title">{t("profile.overwrite.title")}</h2>
      <p><b>{activeUpload?.filename || t("profile.history.current")}</b> → <b>{overwriteTarget.filename}</b></p>
      <p>{t("profile.overwrite.text")}</p>
      <div className="dialog-actions">
        <button className="secondary" onClick={() => editor.setOverwriteTarget(null)}>{t("common.cancel")}</button>
        <button className="primary" onClick={() => editor.applyHistoryVersion(overwriteTarget.id)}>{t("profile.useVersion")}</button>
      </div>
    </Dialog>}

    {previewUpload && <Dialog titleId="preview-title" className="profile-preview">
      <h2 id="preview-title">{previewUpload.filename}</h2>
      <p>{t("profile.preview.meta", { name: previewUpload.resume.name || t("profile.nameNotDetected"), date: formatDateTime(previewUpload.uploaded_at, lang) })}</p>
      <dl>
        <div><dt>{t("profile.section.education")}</dt><dd>{previewUpload.resume.educations.length}</dd></div>
        <div><dt>{t("profile.section.experience")}</dt><dd>{previewUpload.resume.experiences.length}</dd></div>
        <div><dt>{t("profile.section.projects")}</dt><dd>{previewUpload.resume.projects.length}</dd></div>
        <div><dt>{t("profile.field.skills")}</dt><dd>{previewUpload.resume.skills.length}</dd></div>
      </dl>
      <div className="dialog-actions">
        <button className="secondary" onClick={() => editor.setPreviewUpload(null)}>{t("profile.preview.close")}</button>
        {previewUpload.id !== draft?.resume_upload_id && <button className="primary" onClick={() => {
          editor.setPreviewUpload(null);
          editor.setOverwriteTarget({ id: previewUpload.id, filename: previewUpload.filename, name: previewUpload.name, uploaded_at: previewUpload.uploaded_at });
        }}>{t("profile.useVersion")}</button>}
      </div>
    </Dialog>}
  </>;
}
