import { Dialog } from "../../components/common/Dialog";
import { useI18n } from "../../i18n/LanguageProvider";
import type { TargetJob } from "../../types/api";

type Props = {
  target: TargetJob;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

// 删除目标岗位会连带删除改写稿和准备记录，需勾选确认后才能提交
export function RemoveTargetDialog({ target, checked, onCheckedChange, busy, onCancel, onConfirm }: Props) {
  const { t } = useI18n();
  return (
    <Dialog titleId="remove-target-title" className="remove-target-dialog">
      <h2 id="remove-target-title">{t("jobs.remove.title")}</h2>
      <h3>{target.title}</h3>
      <small>{target.company}</small>
      <p>{t("jobs.remove.text")}</p>
      <label className="remove-confirm">
        <input type="checkbox" checked={checked} onChange={(event) => onCheckedChange(event.target.checked)} />
        <span>{t("jobs.remove.confirmLabel")}</span>
      </label>
      <div className="dialog-actions">
        <button className="secondary" onClick={onCancel}>{t("common.cancel")}</button>
        <button className="primary" disabled={!checked || busy} onClick={onConfirm}>{busy ? t("jobs.remove.removing") : t("jobs.remove.confirm")}</button>
      </div>
    </Dialog>
  );
}
