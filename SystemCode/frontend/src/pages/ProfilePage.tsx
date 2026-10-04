import { useState, type ReactNode } from "react";
import { FormField } from "../components/common/FormField";
import { PageFrame } from "../components/layout/PageFrame";

function FormSection({ title, children }: { title: string; children: ReactNode }) {
  return <section className="form-section"><div className="section-title"><h2>{title}</h2><span>Complete</span></div>{children}</section>;
}

export function ProfilePage() {
  const [saved, setSaved] = useState(true);
  const [historyOpen, setHistoryOpen] = useState(false);
  const markEdited = () => setSaved(false);
  return (
    <PageFrame eyebrow="STEP 01 · UPLOAD RESUME · BUILD PROFILE" title="My resume profile & career intent" description="Upload a resume PDF, review the extracted information, and complete the fields used by job matching.">
      <section className="upload"><h3>resume_v3.pdf</h3><p>Current source · 2 pages · uploaded 3 September 2026 at 14:22</p><button className="secondary">Upload again</button><button className="ghost" onClick={() => setHistoryOpen(!historyOpen)}>{historyOpen ? "Hide upload history" : "View upload history"}</button></section>
      {historyOpen && <section className="card history"><div className="section-title"><h2>Resume upload history</h2><span>3 files</span></div>{["resume_v3.pdf", "resume_fintech.pdf", "resume_general.pdf"].map((file) => <div className="history-row" key={file}><span><b>{file}</b><small>2 pages · September 2026</small></span><button className="secondary">Use this version</button></div>)}</section>}
      <p className="notice">Review the 2 highlighted fields before saving.</p>
      <div className="forms">
        <div>
          <FormSection title="Personal information"><FormField label="Full name" value="Alex Chen" onEdit={markEdited} /><FormField label="Email" value="alex.chen@u.nus.edu" onEdit={markEdited} /><FormField label="Phone" value="+65 8123 4567" onEdit={markEdited} /></FormSection>
          <FormSection title="Education"><FormField label="Institution" value="National University of Singapore" onEdit={markEdited} /><div className="field-row"><FormField label="Degree" value="Master" onEdit={markEdited} /><FormField label="Major" value="Computer Science" onEdit={markEdited} /></div></FormSection>
          <FormSection title="Experience"><FormField label="Company" value="Lattice Commerce" onEdit={markEdited} /><FormField label="Title" value="Backend Engineering Intern" onEdit={markEdited} /><FormField label="Description" area value="Built Spring Boot APIs for payment callbacks and reduced P99 latency from 820ms to 210ms." onEdit={markEdited} /></FormSection>
        </div>
        <div>
          <FormSection title="Skills"><FormField label="Skills" area value="Java, Python, Spring Boot, FastAPI, PostgreSQL, AWS, Docker, Git" onEdit={markEdited} /></FormSection>
          <FormSection title="Projects"><FormField label="Project title" value="Campus Payment Platform" onEdit={markEdited} /><FormField label="Summary" area value="Designed transaction APIs and asynchronous workflows for a student payment platform." onEdit={markEdited} /></FormSection>
          <FormSection title="Career intent"><FormField label="Target roles" value="Backend Developer, Platform Engineer" onEdit={markEdited} /><FormField label="Target industries" value="Financial Technology (FinTech)" onEdit={markEdited} /><div className="field"><span>Work modes</span><div className="choices"><button className="active">Hybrid</button><button className="active">On-site</button><button>Remote</button></div></div><FormField label="Additional notes" area value="Interested in payment infrastructure and trading systems." onEdit={markEdited} /></FormSection>
        </div>
      </div>
      <div className={"savebar " + (saved ? "" : "dirty")}><span>{saved ? "All changes saved" : "You have unsaved changes"}</span><button className="primary" onClick={() => setSaved(true)}>Save profile</button></div>
    </PageFrame>
  );
}
