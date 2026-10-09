import { useI18n } from "../../../i18n/LanguageProvider";
import { COUNTRIES, DEGREE_OPTIONS, EMPLOYMENT_OPTIONS, ENTRY_TYPE_OPTIONS, LANGUAGES, QUICK_LANGUAGES, RESEARCH_TYPE_OPTIONS } from "../constants";
import { ChoiceGroup, SelectField, TagEditor, TextField } from "../fields";
import { AddEntryButton, EntryCard, FormSection, useOptions, type SectionProps } from "./SectionParts";

// 简历各区块（教育、技能、经历、项目、科研、证书奖项、其他）。字段 id 规则：fld-<列表>-<序号>-<字段>

const splitList = (value: string, separator: string) => value.split(separator).map((part) => part.trim()).filter(Boolean);

export function EducationSection({ editor, draft }: SectionProps) {
  const { t } = useI18n();
  const entryTypes = useOptions(ENTRY_TYPE_OPTIONS);
  const degrees = useOptions(DEGREE_OPTIONS);
  const update = (index: number, field: string, value: unknown) => editor.updateListItem("educations", index, field, value);
  return <FormSection id="profile-educations" title={t("profile.section.education")} section="educations">
    {draft.resume.educations.map((item, index) => {
      const id = (field: string) => `fld-educations-${index}-${field}`;
      return <EntryCard key={index} title={item.institution || t("profile.newEducation")} section="educations" index={index} onRemove={() => editor.removeListItem("educations", index)}>
        <TextField id={id("institution")} required label={t("profile.field.institution")} value={item.institution} onChange={(value) => update(index, "institution", value)} />
        <div className="field-row">
          <ChoiceGroup compact id={id("entry_type")} label={t("profile.field.entryType")} options={entryTypes} selected={[item.entry_type]} onSelect={(value) => update(index, "entry_type", value)} />
          {item.entry_type !== "exchange" && <SelectField id={id("degree")} required label={t("profile.field.degree")} value={item.degree} onChange={(value) => update(index, "degree", value)} options={degrees} />}
        </div>
        <div className="field-row">
          <TextField label={t("profile.field.major")} value={item.major} onChange={(value) => update(index, "major", value)} />
          <TextField id={id("country")} required label={t("profile.field.country")} value={item.country} placeholder={t("profile.countryPlaceholder")} suggestions={COUNTRIES} onChange={(value) => update(index, "country", value)} />
        </div>
        <div className="field-row">
          <TextField type="month" id={id("start_date")} required label={t("profile.field.startDate")} value={item.start_date} onChange={(value) => update(index, "start_date", value)} />
          <TextField type="month" id={id("end_date")} required label={t("profile.field.graduationDate")} value={item.end_date} onChange={(value) => update(index, "end_date", value)} />
        </div>
        <div className="field-row">
          <TextField label={t("profile.field.gpa")} value={item.gpa} onChange={(value) => update(index, "gpa", value)} />
          <TextField label={t("profile.field.ranking")} value={item.ranking} onChange={(value) => update(index, "ranking", value)} />
        </div>
        <TextField label={t("profile.field.researchDirection")} value={item.research_direction} onChange={(value) => update(index, "research_direction", value)} />
        <TextField label={t("profile.field.courses")} value={item.courses.join(", ")} onChange={(value) => update(index, "courses", splitList(value, ","))} />
      </EntryCard>;
    })}
    <AddEntryButton label={t("profile.addEducation")} onClick={() => editor.addListItem("educations")} />
  </FormSection>;
}

export function SkillsSection({ editor, draft }: SectionProps) {
  const { t } = useI18n();
  return <FormSection id="profile-skills" title={t("profile.section.skills")} section="skills">
    <TagEditor id="fld-skills-0-skills" required label={t("profile.field.skills")} values={draft.resume.skills} onChange={(values) => editor.updateResume("skills", values)} placeholder={t("profile.skillsPlaceholder")} />
    <TagEditor id="fld-skills-0-languages" required label={t("profile.field.languages")} values={draft.resume.languages} onChange={(values) => editor.updateResume("languages", values)} placeholder={t("profile.languagesPlaceholder")} quickOptions={QUICK_LANGUAGES} suggestions={LANGUAGES} />
    {draft.resume.skill_groups.map((item, index) => <EntryCard key={index} title={item.category || t("profile.skillGroup")} section="skill_groups" index={index} onRemove={() => editor.removeListItem("skill_groups", index)}>
      <TextField label={t("profile.field.category")} value={item.category} onChange={(value) => editor.updateListItem("skill_groups", index, "category", value)} />
      <TextField id={`fld-skill_groups-${index}-description`} required label={t("profile.field.description")} value={item.description} onChange={(value) => editor.updateListItem("skill_groups", index, "description", value)} />
    </EntryCard>)}
    <AddEntryButton label={t("profile.addSkillGroup")} onClick={() => editor.addListItem("skill_groups")} />
  </FormSection>;
}

export function ExperienceSection({ editor, draft }: SectionProps) {
  const { t } = useI18n();
  const employmentTypes = useOptions(EMPLOYMENT_OPTIONS);
  const update = (index: number, field: string, value: unknown) => editor.updateListItem("experiences", index, field, value);
  return <FormSection id="profile-experiences" title={t("profile.section.experience")} section="experiences">
    {draft.resume.experiences.map((item, index) => {
      const id = (field: string) => `fld-experiences-${index}-${field}`;
      return <EntryCard key={index} title={item.title || item.company || t("profile.newExperience")} section="experiences" index={index} onRemove={() => editor.removeListItem("experiences", index)}>
        <div className="field-row">
          <TextField id={id("company")} required label={t("profile.field.company")} value={item.company} onChange={(value) => update(index, "company", value)} />
          <TextField id={id("title")} required label={t("profile.field.title")} value={item.title} onChange={(value) => update(index, "title", value)} />
        </div>
        <div className="field-row">
          <SelectField id={id("employment_type")} required label={t("profile.field.employmentType")} value={item.employment_type} onChange={(value) => update(index, "employment_type", value)} options={employmentTypes} />
          <TextField id={id("country")} required label={t("profile.field.country")} value={item.country} placeholder={t("profile.countryPlaceholder")} suggestions={COUNTRIES} onChange={(value) => update(index, "country", value)} />
        </div>
        <div className="field-row date-with-check">
          <TextField type="month" id={id("start_date")} required label={t("profile.field.startDate")} value={item.start_date} onChange={(value) => update(index, "start_date", value)} />
          <div className="date-end">
            <TextField type="month" id={id("end_date")} required label={t("profile.field.endDate")} value={item.end_date === "present" ? "" : item.end_date} onChange={(value) => update(index, "end_date", value)} />
            <label className="check-inline"><input type="checkbox" checked={item.end_date === "present"} onChange={(event) => update(index, "end_date", event.target.checked ? "present" : "")} />{t("profile.present")}</label>
          </div>
        </div>
        <TextField id={id("description")} required area label={t("profile.field.description")} value={item.description} onChange={(value) => update(index, "description", value)} />
      </EntryCard>;
    })}
    <AddEntryButton label={t("profile.addExperience")} onClick={() => editor.addListItem("experiences")} />
  </FormSection>;
}

export function ProjectsSection({ editor, draft }: SectionProps) {
  const { t } = useI18n();
  const update = (index: number, field: string, value: unknown) => editor.updateListItem("projects", index, field, value);
  return <FormSection id="profile-projects" title={t("profile.section.projects")} section="projects">
    {draft.resume.projects.map((item, index) => <EntryCard key={index} title={item.title || t("profile.newProject")} section="projects" index={index} onRemove={() => editor.removeListItem("projects", index)}>
      <div className="field-row">
        <TextField id={`fld-projects-${index}-title`} required label={t("profile.field.projectTitle")} value={item.title} onChange={(value) => update(index, "title", value)} />
        <TextField label={t("profile.field.role")} value={item.role} onChange={(value) => update(index, "role", value)} />
      </div>
      <TextField id={`fld-projects-${index}-summary`} required area label={t("profile.field.summary")} value={item.summary} onChange={(value) => update(index, "summary", value)} />
      <TagEditor id={`fld-projects-${index}-technologies`} required label={t("profile.field.technologies")} values={item.technologies} onChange={(values) => update(index, "technologies", values)} placeholder={t("profile.technologiesPlaceholder")} />
    </EntryCard>)}
    <AddEntryButton label={t("profile.addProject")} onClick={() => editor.addListItem("projects")} />
  </FormSection>;
}

export function ResearchSection({ editor, draft }: SectionProps) {
  const { t } = useI18n();
  const researchTypes = useOptions(RESEARCH_TYPE_OPTIONS);
  const update = (index: number, field: string, value: unknown) => editor.updateListItem("research", index, field, value);
  return <FormSection id="profile-research" title={t("profile.section.research")} section="research">
    {draft.resume.research.map((item, index) => <EntryCard key={index} title={item.title || t("profile.newResearch")} section="research" index={index} onRemove={() => editor.removeListItem("research", index)}>
      <SelectField id={`fld-research-${index}-type`} required label={t("profile.field.type")} value={item.type} onChange={(value) => update(index, "type", value)} options={researchTypes} />
      <TextField id={`fld-research-${index}-title`} required label={t("profile.field.title")} value={item.title} onChange={(value) => update(index, "title", value)} />
      <TextField label={t("profile.field.institution")} value={item.institution} onChange={(value) => update(index, "institution", value)} />
      <div className="field-row">
        <TextField type="month" label={t("profile.field.startDate")} value={item.start_date} onChange={(value) => update(index, "start_date", value)} />
        <TextField type="month" label={t("profile.field.endDate")} value={item.end_date} onChange={(value) => update(index, "end_date", value)} />
      </div>
      <TextField id={`fld-research-${index}-summary`} required area label={t("profile.field.summary")} value={item.summary} onChange={(value) => update(index, "summary", value)} />
    </EntryCard>)}
    <AddEntryButton label={t("profile.addResearch")} onClick={() => editor.addListItem("research")} />
  </FormSection>;
}

export function CertificatesSection({ editor, draft }: SectionProps) {
  const { t } = useI18n();
  return <FormSection id="profile-certificates" title={t("profile.section.certificates")} section="certificates">
    {draft.resume.certificates.map((item, index) => <EntryCard key={"certificate-" + index} title={item.name || t("profile.newCertificate")} section="certificates" index={index} onRemove={() => editor.removeListItem("certificates", index)}>
      <TextField id={`fld-certificates-${index}-name`} required label={t("profile.field.certificate")} value={item.name} onChange={(value) => editor.updateListItem("certificates", index, "name", value)} />
      <div className="field-row">
        <TextField label={t("profile.field.issuer")} value={item.issuer} onChange={(value) => editor.updateListItem("certificates", index, "issuer", value)} />
        <TextField type="month" label={t("profile.field.issueDate")} value={item.issue_date} onChange={(value) => editor.updateListItem("certificates", index, "issue_date", value)} />
      </div>
      <TextField type="month" label={t("profile.field.expiryDate")} value={item.expiry_date} onChange={(value) => editor.updateListItem("certificates", index, "expiry_date", value)} />
    </EntryCard>)}
    <AddEntryButton label={t("profile.addCertificate")} onClick={() => editor.addListItem("certificates")} />
    {draft.resume.awards.map((item, index) => <EntryCard key={"award-" + index} title={item.name || t("profile.newAward")} section="awards" index={index} onRemove={() => editor.removeListItem("awards", index)}>
      <TextField id={`fld-awards-${index}-name`} required label={t("profile.field.award")} value={item.name} onChange={(value) => editor.updateListItem("awards", index, "name", value)} />
      <TextField label={t("profile.field.date")} value={item.date} onChange={(value) => editor.updateListItem("awards", index, "date", value)} />
    </EntryCard>)}
    <AddEntryButton label={t("profile.addAward")} onClick={() => editor.addListItem("awards")} />
  </FormSection>;
}

export function AdditionalSection({ editor, draft }: SectionProps) {
  const { t } = useI18n();
  return <FormSection title={t("profile.section.additional")}>
    <TextField area label={t("profile.field.otherInfo")} value={draft.resume.additional_info.join("\n")} onChange={(value) => editor.updateResume("additional_info", splitList(value, "\n"))} placeholder={t("profile.otherInfoPlaceholder")} />
  </FormSection>;
}
