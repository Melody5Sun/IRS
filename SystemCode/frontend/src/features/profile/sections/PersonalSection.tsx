import { useI18n } from "../../../i18n/LanguageProvider";
import { TextField } from "../fields";
import { FormSection, type SectionProps } from "./SectionParts";

export function PersonalSection({ editor, draft }: SectionProps) {
  const { t } = useI18n();
  return <FormSection id="profile-name" title={t("profile.section.personal")} section="basic">
    <div className="field-row basic-fields">
      <TextField id="fld-basic-0-name" required label={t("profile.field.fullName")} value={draft.resume.name} onChange={(value) => editor.updateResume("name", value)} />
      <TextField id="fld-basic-0-email" required label={t("profile.field.email")} value={draft.resume.email} onChange={(value) => editor.updateResume("email", value)} />
      <TextField id="fld-basic-0-phone" required label={t("profile.field.phone")} value={draft.resume.phone} onChange={(value) => editor.updateResume("phone", value)} />
    </div>
  </FormSection>;
}
