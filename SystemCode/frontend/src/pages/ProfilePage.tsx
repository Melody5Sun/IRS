import { useEffect, useRef, useState, type ReactNode } from "react";
import { ApiError } from "../api";
import { profileApi } from "../api/profile";
import { resumesApi } from "../api/resumes";
import type {
  JobSearchConstraints, ProfileOptions, ResumeDocument, ResumeHistoryEntry,
  ResumeUpload, SavedProfile, UserProfile,
} from "../types/api";
import type { Page } from "../types/domain";

type ListKey = "experiences" | "projects" | "research" | "educations" | "certificates" | "skill_groups" | "awards";
type ActiveUpload = Pick<ResumeHistoryEntry, "id" | "filename" | "name" | "uploaded_at">;
type ValidationIssue = { id: string; section: string; message: string };

const TODO_AMBER = "#8a6a3b";
const ERROR_RED = "#9d3a2c";
const MONTH_PATTERN = /^\d{4}-\d{2}$/;

const EMPTY_CONSTRAINTS: JobSearchConstraints = {
  target_roles: [], target_industries: [], work_modes: [],
  target_employment_types: [], notes: "",
};

const EMPTY_RESUME: ResumeDocument = {
  name: "", email: "", phone: "", experiences: [], projects: [], research: [],
  skills: [], skill_groups: [],
  educations: [{ institution: "", entry_type: "degree", degree: "not_applicable", major: "", start_date: "", end_date: "", country: "", school_tier: "", research_direction: "", gpa: "", ranking: "", courses: [] }],
  certificates: [], languages: [], awards: [], additional_info: [],
};

const NEW_ITEMS: Record<ListKey, Record<string, unknown>> = {
  experiences: { company: "", title: "", employment_type: null, start_date: "", end_date: "", description: "", country: "" },
  projects: { title: "", summary: "", technologies: [], role: "", start_date: "", end_date: "" },
  research: { type: "research_project", title: "", institution: "", summary: "", start_date: "", end_date: "" },
  educations: { institution: "", entry_type: "degree", degree: "not_applicable", major: "", start_date: "", end_date: "", country: "", school_tier: "", research_direction: "", gpa: "", ranking: "", courses: [] },
  certificates: { name: "", issuer: "", issue_date: "", expiry_date: "", score: "" },
  skill_groups: { category: "", description: "" },
  awards: { name: "", date: "" },
};

function FormSection({ title, meta, metaColor, id, children }: { title: string; meta?: string; metaColor?: string; id?: string; children: ReactNode }) {
  return <section className="form-section" id={id}><div className="section-title"><h2>{title}</h2><span style={{ color: metaColor }}>{meta ?? "Editable"}</span></div>{children}</section>;
}

function TextField({ id, label, value, onChange, area, type = "text", required, placeholder, error, errorColor }: { id?: string; label: string; value: string | null | undefined; onChange: (value: string) => void; area?: boolean; type?: string; required?: boolean; placeholder?: string; error?: string; errorColor?: string }) {
  const borderStyle = error ? { borderColor: errorColor } : undefined;
  return <label className="field" id={id}><span>{label}{required && " *"}</span>{area ? <textarea style={borderStyle} value={value ?? ""} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} /> : <input type={type} style={borderStyle} value={value ?? ""} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} />}{error && <small className="field-error">{error}</small>}</label>;
}

function SelectField({ id, label, value, onChange, options, required, error, errorColor }: { id?: string; label: string; value: string | null | undefined; onChange: (value: string) => void; options: Array<[string, string]>; required?: boolean; error?: string; errorColor?: string }) {
  return <label className="field" id={id}><span>{label}{required && " *"}</span><select style={error ? { borderColor: errorColor } : undefined} value={value ?? ""} onChange={(event) => onChange(event.target.value)}><option value="">Select</option>{options.map(([optionValue, labelText]) => <option key={optionValue} value={optionValue}>{labelText}</option>)}</select>{error && <small className="field-error">{error}</small>}</label>;
}

function EntryCard({ title, todoCount, onRemove, children }: { title: string; todoCount?: number; onRemove: () => void; children: ReactNode }) {
  const [open, setOpen] = useState(true);
  const [confirming, setConfirming] = useState(false);
  return <div className="entry-card"><div className="entry-head"><button className="entry-toggle" onClick={() => setOpen(!open)}><small>{open ? "COLLAPSE" : "EXPAND"}</small><h3>{title}</h3>{Boolean(todoCount) && <span className="entry-todo">TO DO {todoCount}</span>}</button>{confirming ? <span className="delete-confirm">Delete this entry?<button className="secondary" onClick={onRemove}>Delete</button><button className="ghost" onClick={() => setConfirming(false)}>Cancel</button></span> : <button className="ghost" onClick={() => setConfirming(true)}>Remove</button>}</div>{open && children}</div>;
}

function TagEditor({ id, label, values, onChange, required, placeholder, error, errorColor, quickOptions = [] }: { id?: string; label: string; values: string[]; onChange: (values: string[]) => void; required?: boolean; placeholder: string; error?: string; errorColor?: string; quickOptions?: string[] }) {
  const [draftValue, setDraftValue] = useState("");
  const add = (raw = draftValue) => {
    const additions = raw.split(",").map((item) => item.trim()).filter(Boolean);
    if (!additions.length) return;
    onChange([...values, ...additions.filter((item) => !values.some((value) => value.toLowerCase() === item.toLowerCase()))]);
    setDraftValue("");
  };
  return <div className="field tag-editor" id={id}>
    <span>{label}{required && " *"}</span>
    {values.length > 0 && <div className="tag-list">{values.map((value) => <span className="profile-tag" key={value}>{value}<button type="button" title={`Remove ${value}`} onClick={() => onChange(values.filter((item) => item !== value))}>x</button></span>)}</div>}
    <div className="tag-entry"><input style={error ? { borderColor: errorColor } : undefined} value={draftValue} placeholder={placeholder} onChange={(event) => setDraftValue(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === ",") { event.preventDefault(); add(); } }} /><button type="button" className="secondary" onClick={() => add()}>Add</button></div>
    {quickOptions.length > 0 && <div className="quick-options"><small>Common</small>{quickOptions.filter((item) => !values.includes(item)).map((item) => <button type="button" key={item} onClick={() => add(item)}>{item}</button>)}</div>}
    {error && <small className="field-error">{error}</small>}
  </div>;
}

function validateProfile(profile: UserProfile): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const blank = (value: unknown) => value == null || (typeof value === "string" && !value.trim()) || (Array.isArray(value) && value.length === 0);
  const requireValue = (value: unknown, id: string, section: string, label: string, verb = "Enter") => {
    if (blank(value)) issues.push({ id, section, message: `${verb} ${label}` });
  };
  const requireMonth = (value: string | null, id: string, section: string, label: string, after?: string | null) => {
    const text = String(value ?? "");
    if (/^\d{4}$/.test(text)) issues.push({ id, section, message: "Add a month" });
    else if (!MONTH_PATTERN.test(text)) issues.push({ id, section, message: `Enter ${label}` });
    else if (after && MONTH_PATTERN.test(after) && text < after) issues.push({ id, section, message: "Cannot be earlier than the start date" });
  };

  requireValue(profile.resume.name, "fld-basic-0-name", "basic", "full name");
  requireValue(profile.resume.email, "fld-basic-0-email", "basic", "email");
  requireValue(profile.resume.phone, "fld-basic-0-phone", "basic", "phone number");
  requireValue(profile.constraints.target_roles, "fld-intent-0-target_roles", "intent", "at least one target role", "Select");
  requireValue(profile.constraints.target_industries, "fld-intent-0-target_industries", "intent", "at least one target industry", "Select");
  requireValue(profile.constraints.work_modes, "fld-intent-0-work_modes", "intent", "at least one work mode", "Select");
  requireValue(profile.constraints.target_employment_types, "fld-intent-0-target_employment_types", "intent", "at least one employment type", "Select");

  if (!profile.resume.educations.length) issues.push({ id: "profile-educations", section: "educations", message: "Add at least one education entry" });
  profile.resume.educations.forEach((item, index) => {
    const prefix = `fld-educations-${index}`;
    requireValue(item.institution, `${prefix}-institution`, "educations", "institution");
    requireValue(item.entry_type, `${prefix}-entry_type`, "educations", "entry type", "Select");
    if (item.entry_type !== "exchange") requireValue(item.degree === "not_applicable" ? "" : item.degree, `${prefix}-degree`, "educations", "degree", "Select");
    requireMonth(item.start_date, `${prefix}-start_date`, "educations", "start date");
    requireMonth(item.end_date, `${prefix}-end_date`, "educations", "graduation date", item.start_date);
    requireValue(item.country, `${prefix}-country`, "educations", "country");
  });

  requireValue(profile.resume.skills, "fld-skills-0-skills", "skills", "at least one skill", "Add");
  requireValue(profile.resume.languages, "fld-skills-0-languages", "skills", "at least one language", "Add");
  profile.resume.skill_groups.forEach((item, index) => requireValue(item.description, `fld-skill_groups-${index}-description`, "skills", "description"));

  profile.resume.experiences.forEach((item, index) => {
    const prefix = `fld-experiences-${index}`;
    requireValue(item.company, `${prefix}-company`, "experiences", "company");
    requireValue(item.title, `${prefix}-title`, "experiences", "title");
    requireValue(item.employment_type, `${prefix}-employment_type`, "experiences", "employment type", "Select");
    requireMonth(item.start_date, `${prefix}-start_date`, "experiences", "start date");
    if (item.end_date !== "present") requireMonth(item.end_date, `${prefix}-end_date`, "experiences", "end date", item.start_date);
    requireValue(item.country, `${prefix}-country`, "experiences", "country");
    requireValue(item.description, `${prefix}-description`, "experiences", "description");
  });
  profile.resume.projects.forEach((item, index) => {
    const prefix = `fld-projects-${index}`;
    requireValue(item.title, `${prefix}-title`, "projects", "project title");
    requireValue(item.summary, `${prefix}-summary`, "projects", "summary");
    requireValue(item.technologies, `${prefix}-technologies`, "projects", "at least one technology", "Add");
  });
  profile.resume.research.forEach((item, index) => {
    const prefix = `fld-research-${index}`;
    requireValue(item.type, `${prefix}-type`, "research", "research type", "Select");
    requireValue(item.title, `${prefix}-title`, "research", "title");
    requireValue(item.summary, `${prefix}-summary`, "research", "summary");
  });
  profile.resume.certificates.forEach((item, index) => requireValue(item.name, `fld-certificates-${index}-name`, "certificates", "certificate name"));
  profile.resume.awards.forEach((item, index) => requireValue(item.name, `fld-awards-${index}-name`, "certificates", "award name"));
  return issues;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-SG", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function messageForError(error: unknown, action: "load" | "upload" | "save") {
  if (!(error instanceof ApiError)) return "Unable to connect to the backend. Check that the API server is running.";
  if (action === "upload" && error.status === 400) return "Only PDF files can be uploaded.";
  if (action === "upload" && error.status === 422) return "No text could be extracted. Please use a text-based PDF.";
  if (action === "upload" && error.status === 503) return "Resume parsing requires the backend LLM configuration. You can still complete and save the profile manually.";
  if (error.status === 502) return action === "upload" ? "Resume parsing is temporarily unavailable. Please try again later." : "The AI service is temporarily unavailable.";
  if (error.status === 422) return "Some required fields are incomplete. Review the highlighted section and try again.";
  if (error.status === 404 && action === "save") return "The selected resume upload no longer exists. Upload the PDF again.";
  return action === "load" ? "Profile data could not be loaded." : "The request could not be completed.";
}

export function ProfilePage({ navigate }: { navigate: (page: Page) => void }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState<UserProfile | null>(null);
  const [options, setOptions] = useState<ProfileOptions | null>(null);
  const [history, setHistory] = useState<ResumeHistoryEntry[]>([]);
  const [activeUpload, setActiveUpload] = useState<ActiveUpload | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [attempted, setAttempted] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [roleCategory, setRoleCategory] = useState("");
  const [reuploadOpen, setReuploadOpen] = useState(false);
  const [overwriteTarget, setOverwriteTarget] = useState<ResumeHistoryEntry | null>(null);
  const [previewUpload, setPreviewUpload] = useState<ResumeUpload | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([profileApi.getOptions(), resumesApi.getHistory(), profileApi.get().catch((reason) => {
      if (reason instanceof ApiError && reason.status === 404) return null;
      throw reason;
    })]).then(([profileOptions, resumeHistory, saved]) => {
      if (!active) return;
      setOptions(profileOptions);
      setHistory(resumeHistory);
      if (saved) {
        setDraft({ resume: saved.resume, constraints: saved.constraints, resume_upload_id: saved.resume_upload_id });
        setUpdatedAt(saved.updated_at);
        setActiveUpload(resumeHistory.find((item) => item.id === saved.resume_upload_id) ?? null);
      } else {
        setDraft({ resume: { ...EMPTY_RESUME, educations: EMPTY_RESUME.educations.map((item) => ({ ...item })) }, constraints: { ...EMPTY_CONSTRAINTS }, resume_upload_id: null });
      }
    }).catch((reason) => active && setError(messageForError(reason, "load")))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, []);

  useEffect(() => () => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
  }, []);

  const showToast = (message: string) => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast(message);
    toastTimer.current = setTimeout(() => setToast(null), 2400);
  };

  const updateDraft = (recipe: (current: UserProfile) => UserProfile) => {
    setDraft((current) => current ? recipe(current) : current);
    setDirty(true);
  };

  const updateResume = <K extends keyof ResumeDocument>(key: K, value: ResumeDocument[K]) =>
    updateDraft((current) => ({ ...current, resume: { ...current.resume, [key]: value } }));

  const updateConstraint = <K extends keyof JobSearchConstraints>(key: K, value: JobSearchConstraints[K]) =>
    updateDraft((current) => ({ ...current, constraints: { ...current.constraints, [key]: value } }));

  const updateListItem = (section: ListKey, index: number, field: string, value: unknown) => {
    updateDraft((current) => {
      const list = [...current.resume[section]] as unknown as Array<Record<string, unknown>>;
      list[index] = { ...list[index], [field]: value };
      return { ...current, resume: { ...current.resume, [section]: list } as ResumeDocument };
    });
  };

  const addListItem = (section: ListKey) => {
    updateDraft((current) => ({ ...current, resume: { ...current.resume, [section]: [...current.resume[section], { ...NEW_ITEMS[section] }] } as ResumeDocument }));
  };

  const removeListItem = (section: ListKey, index: number) => {
    updateDraft((current) => ({ ...current, resume: { ...current.resume, [section]: current.resume[section].filter((_, itemIndex) => itemIndex !== index) } as ResumeDocument }));
  };

  const adoptUpload = (upload: ResumeUpload) => {
    const { about, ...resume } = upload.resume;
    const constraints = draft?.constraints ?? EMPTY_CONSTRAINTS;
    setDraft({
      resume,
      constraints: { ...constraints, notes: constraints.notes || about || "" },
      resume_upload_id: upload.id,
    });
    setActiveUpload({ id: upload.id, filename: upload.filename, name: upload.name, uploaded_at: upload.uploaded_at });
    setUpdatedAt(null);
    setDirty(true);
    setAttempted(false);
    showToast("Resume parsed. Review and complete the required fields.");
    setError(null);
  };

  const handleFile = async (file?: File) => {
    if (!file) return;
    setUploading(true); setError(null);
    try {
      const upload = await resumesApi.parsePdf(file);
      adoptUpload(upload);
      setHistory((current) => [{ id: upload.id, filename: upload.filename, name: upload.name, uploaded_at: upload.uploaded_at }, ...current.filter((item) => item.id !== upload.id)]);
    } catch (reason) {
      setError(messageForError(reason, "upload"));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const useHistory = async (id: number) => {
    setUploading(true); setError(null);
    try { adoptUpload(await resumesApi.getHistoryItem(id)); }
    catch (reason) { setError(messageForError(reason, "load")); }
    finally { setUploading(false); setOverwriteTarget(null); }
  };

  const previewHistory = async (id: number) => {
    setUploading(true); setError(null);
    try { setPreviewUpload(await resumesApi.getHistoryItem(id)); }
    catch (reason) { setError(messageForError(reason, "load")); }
    finally { setUploading(false); }
  };

  const save = async () => {
    if (!draft) return;
    const missing = validateProfile(draft);
    if (missing.length) {
      setAttempted(true);
      showToast(`${missing.length} required fields still need to be completed`);
      requestAnimationFrame(() => {
        const element = document.getElementById(missing[0].id);
        if (element) window.scrollTo({ top: Math.max(0, element.getBoundingClientRect().top + window.scrollY - 110), behavior: "smooth" });
      });
      return;
    }
    setSaving(true); setError(null);
    try {
      const saved: SavedProfile = await profileApi.save(draft);
      setDraft({ resume: saved.resume, constraints: saved.constraints, resume_upload_id: saved.resume_upload_id });
      if (!activeUpload && saved.resume_upload_id) {
        const refreshedHistory = await resumesApi.getHistory();
        setHistory(refreshedHistory);
        setActiveUpload(refreshedHistory.find((item) => item.id === saved.resume_upload_id) ?? null);
      }
      setUpdatedAt(saved.updated_at);
      setDirty(false);
      setAttempted(false);
      showToast("Saved");
    } catch (reason) {
      setError(messageForError(reason, "save"));
      if (reason instanceof ApiError && Array.isArray(reason.body.detail)) {
        const location = reason.body.detail[0]?.loc;
        const section = location?.[1] === "resume" ? location?.[2] : location?.[1];
        document.getElementById("profile-" + String(section))?.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    } finally { setSaving(false); }
  };

  if (loading) return <div className="page profile-page"><header className="profile-page-header"><div className="eyebrow">STEP 01 · UPLOAD RESUME · BUILD PROFILE</div><h1>My resume profile & career intent</h1><p>Loading your saved profile and resume history.</p></header><div className="profile-state">Loading profile...</div></div>;

  const validationIssues = draft ? validateProfile(draft) : [];
  const validationColor = attempted ? ERROR_RED : TODO_AMBER;
  const issueById = new Map(validationIssues.map((issue) => [issue.id, issue]));
  const fieldError = (id: string) => issueById.get(id)?.message;
  const sectionTodo = (section: string) => validationIssues.filter((issue) => issue.section === section).length;
  const entryTodo = (section: string, index: number) => validationIssues.filter((issue) => issue.id.startsWith(`fld-${section}-${index}-`)).length;
  const sectionStatus = (section: string) => {
    const count = sectionTodo(section);
    return { meta: count ? `${count} fields remaining` : "✓ Complete", color: count ? validationColor : undefined };
  };

  return (
    <div className="page profile-page">
      <header className="profile-page-header">
        <div className="eyebrow">STEP 01 · UPLOAD RESUME · BUILD PROFILE</div>
        <h1>My resume profile & career intent</h1>
        <p>Upload a resume PDF to prefill your profile, or enter the details manually. Review every field before saving; incomplete required fields will not be submitted.</p>
      </header>
      <div className="profile-content">
      <input ref={fileRef} className="visually-hidden" type="file" accept="application/pdf,.pdf" onChange={(event) => handleFile(event.target.files?.[0])} />
      <section className="upload">
        <h3>{activeUpload?.filename ?? (updatedAt ? "Manual profile" : "No resume uploaded")}</h3>
        <p>{activeUpload ? "Current source · uploaded " + formatDate(activeUpload.uploaded_at) : updatedAt ? "This profile was entered manually and can be edited below." : "Fill in the profile manually, or upload a text-based PDF to prefill it."}</p>
        <button className="secondary" disabled={uploading} onClick={() => (activeUpload || dirty) ? setReuploadOpen(true) : fileRef.current?.click()}>{uploading ? "Processing resume..." : activeUpload ? "Upload again" : "Upload resume PDF"}</button>
        {history.length > 0 && <button className="ghost" onClick={() => setHistoryOpen(!historyOpen)}>{historyOpen ? "Hide upload history" : "View upload history"}</button>}
      </section>

      {historyOpen && <section className="card history"><div className="section-title"><h2>Resume upload history</h2><span>{history.length} files · retained for 12 months</span></div><p className="history-intro">Preview a previous upload or use its parsed content to replace the current profile. The original upload remains in history.</p>{history.map((item) => <div className="history-row" key={item.id}><span><b>{item.filename || item.name || "Untitled resume"}</b><small>{item.name || "Name not detected"} · {formatDate(item.uploaded_at)}</small></span><div className="history-actions"><button className="ghost" disabled={uploading} onClick={() => previewHistory(item.id)}>Preview</button>{item.id === draft?.resume_upload_id ? <em>Current profile</em> : <button className="secondary" disabled={uploading} onClick={() => setOverwriteTarget(item)}>Use this version</button>}</div></div>)}</section>}

      {error && <div className="form-message error" role="alert">{error}</div>}

      {draft && <>
          {validationIssues.length > 0 && <div className="profile-todo-summary" style={{ color: validationColor }}><span>Your resume has been prefilled. Review and complete <b>{validationIssues.length}</b> required fields.</span><button onClick={() => { const element = document.getElementById(validationIssues[0].id); if (element) window.scrollTo({ top: Math.max(0, element.getBoundingClientRect().top + window.scrollY - 110), behavior: "smooth" }); }}>Jump to first item</button></div>}
          <div className="forms">
            <div>
              <FormSection id="profile-name" title="Personal information" meta={sectionStatus("basic").meta} metaColor={sectionStatus("basic").color}>
                <div className="field-row basic-fields"><TextField id="fld-basic-0-name" error={fieldError("fld-basic-0-name")} errorColor={validationColor} required label="Full name" value={draft.resume.name} onChange={(value) => updateResume("name", value)} /><TextField id="fld-basic-0-email" error={fieldError("fld-basic-0-email")} errorColor={validationColor} required label="Email" value={draft.resume.email} onChange={(value) => updateResume("email", value)} /><TextField id="fld-basic-0-phone" error={fieldError("fld-basic-0-phone")} errorColor={validationColor} required label="Phone" value={draft.resume.phone} onChange={(value) => updateResume("phone", value)} /></div>
              </FormSection>

              <FormSection id="profile-constraints" title="Career intent" meta={sectionStatus("intent").meta} metaColor={sectionStatus("intent").color}>
                <p className="section-note">Used for job matching and ranking. This information will not be added to your resume.</p>
                <div className="field" id="fld-intent-0-target_roles"><span>Target roles *</span>{draft.constraints.target_roles.length > 0 && <div className="tag-list">{draft.constraints.target_roles.map((role) => <span className="profile-tag" key={role}>{role}<button title={"Remove " + role} onClick={() => updateConstraint("target_roles", draft.constraints.target_roles.filter((item) => item !== role))}>x</button></span>)}</div>}<div className="select-pair"><select style={fieldError("fld-intent-0-target_roles") ? { borderColor: validationColor } : undefined} value={roleCategory} onChange={(event) => setRoleCategory(event.target.value)}><option value="">Role category</option>{options && Object.keys(options.target_role_categories).map((category) => <option key={category}>{category}</option>)}</select><select style={fieldError("fld-intent-0-target_roles") ? { borderColor: validationColor } : undefined} value="" disabled={!roleCategory} onChange={(event) => { const role = event.target.value; if (role && !draft.constraints.target_roles.includes(role)) updateConstraint("target_roles", [...draft.constraints.target_roles, role]); }}><option value="">{roleCategory ? "Select a role to add" : "Choose a category first"}</option>{roleCategory && options?.target_role_categories[roleCategory]?.filter((role) => !draft.constraints.target_roles.includes(role)).map((role) => <option key={role}>{role}</option>)}</select></div>{fieldError("fld-intent-0-target_roles") && <small className="field-error">{fieldError("fld-intent-0-target_roles")}</small>}</div>
                <div className="field" id="fld-intent-0-target_industries"><span>Target industries *</span>{draft.constraints.target_industries.length > 0 && <div className="tag-list">{draft.constraints.target_industries.map((industry) => <span className="profile-tag" key={industry}>{industry}<button title={"Remove " + industry} onClick={() => updateConstraint("target_industries", draft.constraints.target_industries.filter((item) => item !== industry))}>x</button></span>)}</div>}<select style={fieldError("fld-intent-0-target_industries") ? { borderColor: validationColor } : undefined} value="" onChange={(event) => { const industry = event.target.value; if (industry && !draft.constraints.target_industries.includes(industry)) updateConstraint("target_industries", [...draft.constraints.target_industries, industry]); }}><option value="">Select an industry to add</option>{options?.target_industries.filter((industry) => !draft.constraints.target_industries.includes(industry)).map((industry) => <option key={industry}>{industry}</option>)}</select>{fieldError("fld-intent-0-target_industries") && <small className="field-error">{fieldError("fld-intent-0-target_industries")}</small>}</div>
                <div className="field" id="fld-intent-0-work_modes"><span>Work modes *</span><div className="choices">{(["onsite", "hybrid", "remote"] as const).map((mode) => <button style={fieldError("fld-intent-0-work_modes") ? { borderColor: validationColor } : undefined} key={mode} className={draft.constraints.work_modes.includes(mode) ? "active" : ""} onClick={() => updateConstraint("work_modes", draft.constraints.work_modes.includes(mode) ? draft.constraints.work_modes.filter((item) => item !== mode) : [...draft.constraints.work_modes, mode])}>{mode === "onsite" ? "On-site" : mode[0].toUpperCase() + mode.slice(1)}</button>)}</div>{fieldError("fld-intent-0-work_modes") && <small className="field-error">{fieldError("fld-intent-0-work_modes")}</small>}</div>
                <div className="field" id="fld-intent-0-target_employment_types"><span>Employment types *</span><div className="choices">{([["full_time", "Full-time"], ["internship", "Internship"]] as const).map(([value, label]) => <button style={fieldError("fld-intent-0-target_employment_types") ? { borderColor: validationColor } : undefined} key={value} className={draft.constraints.target_employment_types.includes(value) ? "active" : ""} onClick={() => updateConstraint("target_employment_types", draft.constraints.target_employment_types.includes(value) ? draft.constraints.target_employment_types.filter((item) => item !== value) : [...draft.constraints.target_employment_types, value])}>{label}</button>)}</div>{fieldError("fld-intent-0-target_employment_types") && <small className="field-error">{fieldError("fld-intent-0-target_employment_types")}</small>}</div>
                <TextField area label="Additional notes" value={draft.constraints.notes} onChange={(value) => updateConstraint("notes", value)} />
              </FormSection>

              <FormSection id="profile-educations" title="Education" meta={sectionStatus("educations").meta} metaColor={sectionStatus("educations").color}>
                {draft.resume.educations.map((item, index) => <EntryCard key={index} title={item.institution || "New education"} todoCount={entryTodo("educations", index)} onRemove={() => removeListItem("educations", index)}>
                  <TextField id={`fld-educations-${index}-institution`} error={fieldError(`fld-educations-${index}-institution`)} errorColor={validationColor} required label="Institution" value={item.institution} onChange={(value) => updateListItem("educations", index, "institution", value)} />
                  <div className="field-row"><div className="field" id={`fld-educations-${index}-entry_type`}><span>Entry type *</span><div className="choices compact-choices">{([["degree", "Degree"], ["exchange", "Exchange"]] as const).map(([value, label]) => <button type="button" style={fieldError(`fld-educations-${index}-entry_type`) ? { borderColor: validationColor } : undefined} key={value} className={item.entry_type === value ? "active" : ""} onClick={() => updateListItem("educations", index, "entry_type", value)}>{label}</button>)}</div>{fieldError(`fld-educations-${index}-entry_type`) && <small className="field-error">{fieldError(`fld-educations-${index}-entry_type`)}</small>}</div>{item.entry_type !== "exchange" && <SelectField id={`fld-educations-${index}-degree`} error={fieldError(`fld-educations-${index}-degree`)} errorColor={validationColor} required label="Degree" value={item.degree} onChange={(value) => updateListItem("educations", index, "degree", value)} options={[["bachelor", "Bachelor"], ["master", "Master"], ["phd", "PhD"], ["diploma", "Diploma"], ["not_applicable", "Not applicable"]]} />}</div>
                  <div className="field-row"><TextField label="Major (optional)" value={item.major} onChange={(value) => updateListItem("educations", index, "major", value)} /><TextField id={`fld-educations-${index}-country`} error={fieldError(`fld-educations-${index}-country`)} errorColor={validationColor} required label="Country" value={item.country} onChange={(value) => updateListItem("educations", index, "country", value)} /></div>
                  <div className="field-row"><TextField type="month" id={`fld-educations-${index}-start_date`} error={fieldError(`fld-educations-${index}-start_date`)} errorColor={validationColor} required label="Start date" value={item.start_date} onChange={(value) => updateListItem("educations", index, "start_date", value)} /><TextField type="month" id={`fld-educations-${index}-end_date`} error={fieldError(`fld-educations-${index}-end_date`)} errorColor={validationColor} required label="Graduation date (or expected)" value={item.end_date} onChange={(value) => updateListItem("educations", index, "end_date", value)} /></div>
                  <div className="field-row"><TextField label="GPA" value={item.gpa} onChange={(value) => updateListItem("educations", index, "gpa", value)} /><TextField label="Ranking" value={item.ranking} onChange={(value) => updateListItem("educations", index, "ranking", value)} /></div>
                  <TextField label="Research direction" value={item.research_direction} onChange={(value) => updateListItem("educations", index, "research_direction", value)} />
                  <TextField label="Courses" value={item.courses.join(", ")} onChange={(value) => updateListItem("educations", index, "courses", value.split(",").map((part) => part.trim()).filter(Boolean))} />
                </EntryCard>)}
                <button className="secondary add-entry" onClick={() => addListItem("educations")}>+ Add education</button>
              </FormSection>

              <FormSection id="profile-skills" title="Skills & languages" meta={sectionStatus("skills").meta} metaColor={sectionStatus("skills").color}>
                <TagEditor id="fld-skills-0-skills" error={fieldError("fld-skills-0-skills")} errorColor={validationColor} required label="Skills" values={draft.resume.skills} onChange={(values) => updateResume("skills", values)} placeholder="Enter a language, framework or tool" />
                <TagEditor id="fld-skills-0-languages" error={fieldError("fld-skills-0-languages")} errorColor={validationColor} required label="Languages" values={draft.resume.languages} onChange={(values) => updateResume("languages", values)} placeholder="English, Mandarin..." quickOptions={["English", "Mandarin", "Malay", "Tamil", "Cantonese"]} />
                {draft.resume.skill_groups.map((item, index) => <EntryCard key={index} title={item.category || "Skill group"} todoCount={entryTodo("skill_groups", index)} onRemove={() => removeListItem("skill_groups", index)}><TextField label="Category" value={item.category} onChange={(value) => updateListItem("skill_groups", index, "category", value)} /><TextField id={`fld-skill_groups-${index}-description`} error={fieldError(`fld-skill_groups-${index}-description`)} errorColor={validationColor} required label="Description" value={item.description} onChange={(value) => updateListItem("skill_groups", index, "description", value)} /></EntryCard>)}
                <button className="secondary add-entry" onClick={() => addListItem("skill_groups")}>+ Add skill group</button>
              </FormSection>
            </div>

            <div>

              <FormSection id="profile-experiences" title="Experience" meta={sectionStatus("experiences").meta} metaColor={sectionStatus("experiences").color}>
                {draft.resume.experiences.map((item, index) => <EntryCard key={index} title={item.title || item.company || "New experience"} todoCount={entryTodo("experiences", index)} onRemove={() => removeListItem("experiences", index)}>
                  <div className="field-row"><TextField id={`fld-experiences-${index}-company`} error={fieldError(`fld-experiences-${index}-company`)} errorColor={validationColor} required label="Company" value={item.company} onChange={(value) => updateListItem("experiences", index, "company", value)} /><TextField id={`fld-experiences-${index}-title`} error={fieldError(`fld-experiences-${index}-title`)} errorColor={validationColor} required label="Title" value={item.title} onChange={(value) => updateListItem("experiences", index, "title", value)} /></div>
                  <div className="field-row"><SelectField id={`fld-experiences-${index}-employment_type`} error={fieldError(`fld-experiences-${index}-employment_type`)} errorColor={validationColor} required label="Employment type" value={item.employment_type} onChange={(value) => updateListItem("experiences", index, "employment_type", value)} options={[["full_time", "Full-time"], ["part_time", "Part-time"], ["internship", "Internship"]]} /><TextField id={`fld-experiences-${index}-country`} error={fieldError(`fld-experiences-${index}-country`)} errorColor={validationColor} required label="Country" value={item.country} onChange={(value) => updateListItem("experiences", index, "country", value)} /></div>
                  <div className="field-row date-with-check"><TextField type="month" id={`fld-experiences-${index}-start_date`} error={fieldError(`fld-experiences-${index}-start_date`)} errorColor={validationColor} required label="Start date" value={item.start_date} onChange={(value) => updateListItem("experiences", index, "start_date", value)} /><div className="date-end"><TextField type="month" id={`fld-experiences-${index}-end_date`} error={fieldError(`fld-experiences-${index}-end_date`)} errorColor={validationColor} required label="End date" value={item.end_date === "present" ? "" : item.end_date} onChange={(value) => updateListItem("experiences", index, "end_date", value)} /><label className="check-inline"><input type="checkbox" checked={item.end_date === "present"} onChange={(event) => updateListItem("experiences", index, "end_date", event.target.checked ? "present" : "")} />Present</label></div></div>
                  <TextField id={`fld-experiences-${index}-description`} error={fieldError(`fld-experiences-${index}-description`)} errorColor={validationColor} required area label="Description" value={item.description} onChange={(value) => updateListItem("experiences", index, "description", value)} />
                </EntryCard>)}
                <button className="secondary add-entry" onClick={() => addListItem("experiences")}>+ Add experience</button>
              </FormSection>

              <FormSection id="profile-projects" title="Projects" meta={sectionStatus("projects").meta} metaColor={sectionStatus("projects").color}>
                {draft.resume.projects.map((item, index) => <EntryCard key={index} title={item.title || "New project"} todoCount={entryTodo("projects", index)} onRemove={() => removeListItem("projects", index)}>
                  <div className="field-row"><TextField id={`fld-projects-${index}-title`} error={fieldError(`fld-projects-${index}-title`)} errorColor={validationColor} required label="Project title" value={item.title} onChange={(value) => updateListItem("projects", index, "title", value)} /><TextField label="Role (optional)" value={item.role} onChange={(value) => updateListItem("projects", index, "role", value)} /></div>
                  <TextField id={`fld-projects-${index}-summary`} error={fieldError(`fld-projects-${index}-summary`)} errorColor={validationColor} required area label="Summary" value={item.summary} onChange={(value) => updateListItem("projects", index, "summary", value)} />
                  <TagEditor id={`fld-projects-${index}-technologies`} error={fieldError(`fld-projects-${index}-technologies`)} errorColor={validationColor} required label="Technologies" values={item.technologies} onChange={(values) => updateListItem("projects", index, "technologies", values)} placeholder="e.g. Python, press Enter to add" />
                </EntryCard>)}
                <button className="secondary add-entry" onClick={() => addListItem("projects")}>+ Add project</button>
              </FormSection>
              <FormSection id="profile-research" title="Research" meta={sectionStatus("research").meta} metaColor={sectionStatus("research").color}>
                {draft.resume.research.map((item, index) => <EntryCard key={index} title={item.title || "New research"} todoCount={entryTodo("research", index)} onRemove={() => removeListItem("research", index)}>
                  <SelectField id={`fld-research-${index}-type`} error={fieldError(`fld-research-${index}-type`)} errorColor={validationColor} required label="Type" value={item.type} onChange={(value) => updateListItem("research", index, "type", value)} options={[["paper", "Paper"], ["patent", "Patent"], ["software_copyright", "Software copyright"], ["thesis", "Thesis"], ["research_project", "Research project"], ["other", "Other"]]} />
                  <TextField id={`fld-research-${index}-title`} error={fieldError(`fld-research-${index}-title`)} errorColor={validationColor} required label="Title" value={item.title} onChange={(value) => updateListItem("research", index, "title", value)} />
                  <TextField label="Institution" value={item.institution} onChange={(value) => updateListItem("research", index, "institution", value)} />
                  <div className="field-row"><TextField type="month" label="Start date" value={item.start_date} onChange={(value) => updateListItem("research", index, "start_date", value)} /><TextField type="month" label="End date" value={item.end_date} onChange={(value) => updateListItem("research", index, "end_date", value)} /></div>
                  <TextField id={`fld-research-${index}-summary`} error={fieldError(`fld-research-${index}-summary`)} errorColor={validationColor} required area label="Summary" value={item.summary} onChange={(value) => updateListItem("research", index, "summary", value)} />
                </EntryCard>)}
                <button className="secondary add-entry" onClick={() => addListItem("research")}>+ Add research</button>
              </FormSection>

              <FormSection id="profile-certificates" title="Certificates & awards" meta={sectionStatus("certificates").meta} metaColor={sectionStatus("certificates").color}>
                {draft.resume.certificates.map((item, index) => <EntryCard key={"certificate-" + index} title={item.name || "New certificate"} todoCount={entryTodo("certificates", index)} onRemove={() => removeListItem("certificates", index)}>
                  <TextField id={`fld-certificates-${index}-name`} error={fieldError(`fld-certificates-${index}-name`)} errorColor={validationColor} required label="Certificate" value={item.name} onChange={(value) => updateListItem("certificates", index, "name", value)} />
                  <div className="field-row"><TextField label="Issuer" value={item.issuer} onChange={(value) => updateListItem("certificates", index, "issuer", value)} /><TextField type="month" label="Issue date" value={item.issue_date} onChange={(value) => updateListItem("certificates", index, "issue_date", value)} /></div>
                  <TextField type="month" label="Expiry date (optional)" value={item.expiry_date} onChange={(value) => updateListItem("certificates", index, "expiry_date", value)} />
                </EntryCard>)}
                <button className="secondary add-entry" onClick={() => addListItem("certificates")}>+ Add certificate</button>
                {draft.resume.awards.map((item, index) => <EntryCard key={"award-" + index} title={item.name || "New award"} todoCount={entryTodo("awards", index)} onRemove={() => removeListItem("awards", index)}><TextField id={`fld-awards-${index}-name`} error={fieldError(`fld-awards-${index}-name`)} errorColor={validationColor} required label="Award" value={item.name} onChange={(value) => updateListItem("awards", index, "name", value)} /><TextField label="Date" value={item.date} onChange={(value) => updateListItem("awards", index, "date", value)} /></EntryCard>)}
                <button className="secondary add-entry" onClick={() => addListItem("awards")}>+ Add award</button>
              </FormSection>

              <FormSection title="Additional information" meta="✓ Complete">
                <TextField area label="Other resume information" value={draft.resume.additional_info.join("\n")} onChange={(value) => updateResume("additional_info", value.split("\n").map((part) => part.trim()).filter(Boolean))} placeholder="Label: value" />
              </FormSection>
            </div>
          </div>
          <div className={"profile-savebar " + (dirty ? "dirty" : "")}><div><button className="primary" disabled={saving} onClick={save}>{saving ? "Saving..." : "Save"}</button><button className="secondary" onClick={() => navigate("jobs")}>Go to job recommendations →</button><button className="ghost" onClick={() => navigate("dashboard")}>Back to dashboard</button></div><span style={{ color: validationIssues.length ? validationColor : undefined }}>{saving ? "Saving profile..." : validationIssues.length ? (dirty ? `You have unsaved changes · ${validationIssues.length} required fields remaining` : `${validationIssues.length} required fields remaining`) : dirty ? "You have unsaved changes" : updatedAt ? "Saved · last updated " + formatDate(updatedAt) : "Ready to save"}</span></div>
        </>}
      </div>
      {toast && <div className="profile-toast" role="status">{toast}</div>}
      {reuploadOpen && <div className="dialog-backdrop"><div className="profile-dialog" role="dialog" aria-modal="true" aria-labelledby="reupload-title"><h2 id="reupload-title">Upload a new resume?</h2><p>The new parsed resume will replace the resume fields in this draft. Your career intent will be preserved, but unsaved resume edits will be lost.</p><small>Only text-based PDF files are supported.</small><div className="dialog-actions"><button className="secondary" onClick={() => setReuploadOpen(false)}>Cancel</button><button className="primary" onClick={() => { setReuploadOpen(false); fileRef.current?.click(); }}>Continue</button></div></div></div>}
      {overwriteTarget && <div className="dialog-backdrop"><div className="profile-dialog" role="dialog" aria-modal="true" aria-labelledby="overwrite-title"><h2 id="overwrite-title">Use this resume version?</h2><p><b>{activeUpload?.filename || "Current profile"}</b> → <b>{overwriteTarget.filename}</b></p><p>The selected parsed resume will replace the current resume fields. Career intent will remain unchanged.</p><div className="dialog-actions"><button className="secondary" onClick={() => setOverwriteTarget(null)}>Cancel</button><button className="primary" onClick={() => useHistory(overwriteTarget.id)}>Use this version</button></div></div></div>}
      {previewUpload && <div className="dialog-backdrop"><div className="profile-dialog profile-preview" role="dialog" aria-modal="true" aria-labelledby="preview-title"><h2 id="preview-title">{previewUpload.filename}</h2><p>{previewUpload.resume.name || "Name not detected"} · uploaded {formatDate(previewUpload.uploaded_at)}</p><dl><div><dt>Education</dt><dd>{previewUpload.resume.educations.length}</dd></div><div><dt>Experience</dt><dd>{previewUpload.resume.experiences.length}</dd></div><div><dt>Projects</dt><dd>{previewUpload.resume.projects.length}</dd></div><div><dt>Skills</dt><dd>{previewUpload.resume.skills.length}</dd></div></dl><div className="dialog-actions"><button className="secondary" onClick={() => setPreviewUpload(null)}>Close</button>{previewUpload.id !== draft?.resume_upload_id && <button className="primary" onClick={() => { setPreviewUpload(null); setOverwriteTarget({ id: previewUpload.id, filename: previewUpload.filename, name: previewUpload.name, uploaded_at: previewUpload.uploaded_at }); }}>Use this version</button>}</div></div></div>}
    </div>
  );
}
