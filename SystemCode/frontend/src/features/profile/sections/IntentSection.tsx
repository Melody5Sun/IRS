import { useState } from "react";
import { useI18n } from "../../../i18n/LanguageProvider";
import type { TargetEmploymentType, WorkMode } from "../../../types/api";
import { TARGET_EMPLOYMENT_OPTIONS, WORK_MODE_OPTIONS } from "../constants";
import { Select } from "../../../components/common/Select";
import { ChoiceGroup, TagPickerField, TextField } from "../fields";
import { errorBorder, useValidation } from "../ValidationContext";
import { FormSection, useOptions, type SectionProps } from "./SectionParts";

// 在数组里切换某个值（多选按钮组）
function toggle<T>(values: T[], value: T) {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

// 求职意向只用于匹配排序，不写入简历；岗位/行业取值来自 GET /profile/options
export function IntentSection({ editor, draft }: SectionProps) {
  const { t } = useI18n();
  const { errorFor, color } = useValidation();
  const [roleCategory, setRoleCategory] = useState("");
  const workModes = useOptions(WORK_MODE_OPTIONS);
  const employmentTypes = useOptions(TARGET_EMPLOYMENT_OPTIONS);
  const { constraints } = draft;
  const { options } = editor;
  const roleBorder = errorBorder(errorFor("fld-intent-0-target_roles"), color);

  return <FormSection id="profile-constraints" title={t("profile.section.intent")} section="intent">
    <p className="section-note">{t("profile.intentNote")}</p>
    <TagPickerField id="fld-intent-0-target_roles" label={t("profile.field.targetRoles")} values={constraints.target_roles} onRemove={(role) => editor.updateConstraint("target_roles", constraints.target_roles.filter((item) => item !== role))}>
      <div className="select-pair">
        <Select style={roleBorder} value={roleCategory} placeholder={t("profile.roleCategory")} aria-label={t("profile.roleCategory")} onChange={setRoleCategory}
          options={Object.keys(options?.target_role_categories ?? {}).map((category) => ({ value: category, label: category }))} />
        {/* 选中即加成标签，下拉本身不保留值 */}
        <Select style={roleBorder} value="" disabled={!roleCategory} placeholder={roleCategory ? t("profile.selectRole") : t("profile.chooseCategory")} aria-label={t("profile.field.targetRoles")}
          onChange={(role) => { if (!constraints.target_roles.includes(role)) editor.updateConstraint("target_roles", [...constraints.target_roles, role]); }}
          options={(options?.target_role_categories[roleCategory] ?? []).filter((role) => !constraints.target_roles.includes(role)).map((role) => ({ value: role, label: role }))} />
      </div>
    </TagPickerField>
    <TagPickerField id="fld-intent-0-target_industries" label={t("profile.field.targetIndustries")} values={constraints.target_industries} onRemove={(industry) => editor.updateConstraint("target_industries", constraints.target_industries.filter((item) => item !== industry))}>
      <Select style={errorBorder(errorFor("fld-intent-0-target_industries"), color)} value="" placeholder={t("profile.selectIndustry")} aria-label={t("profile.field.targetIndustries")}
        onChange={(industry) => { if (!constraints.target_industries.includes(industry)) editor.updateConstraint("target_industries", [...constraints.target_industries, industry]); }}
        options={(options?.target_industries ?? []).filter((industry) => !constraints.target_industries.includes(industry)).map((industry) => ({ value: industry, label: industry }))} />
    </TagPickerField>
    <ChoiceGroup id="fld-intent-0-work_modes" label={t("profile.field.workModes")} options={workModes} selected={constraints.work_modes} onSelect={(mode) => editor.updateConstraint("work_modes", toggle(constraints.work_modes, mode as WorkMode))} />
    <ChoiceGroup id="fld-intent-0-target_employment_types" label={t("profile.field.employmentTypes")} options={employmentTypes} selected={constraints.target_employment_types} onSelect={(type) => editor.updateConstraint("target_employment_types", toggle(constraints.target_employment_types, type as TargetEmploymentType))} />
    <TextField area label={t("profile.field.notes")} value={constraints.notes} onChange={(value) => editor.updateConstraint("notes", value)} />
  </FormSection>;
}
