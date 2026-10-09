import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { translate } from "../../i18n/LanguageProvider";
import type { ResumeDocument } from "../../types/api";
import { DEGREE_OPTIONS } from "../profile/constants";

// 打印用的简历排版：挂在 body 下，屏幕上隐藏，打印时只显示它（样式见 rewrite.css）。
// 简历内容是英文、投的也是英文 JD，所以小标题固定用英文，不跟界面语言切换

const lines = (text: string) => text.split("\n").map((line) => line.replace(/^\s*[-•*]\s*/, "").trim()).filter(Boolean);
const dates = (start: string | null, end: string | null) => [start, end === "present" ? "Present" : end].filter(Boolean).join(" – ");
const join = (...parts: Array<string | null | undefined>) => parts.filter(Boolean).join(" · ");

function Section({ title, show, children }: { title: string; show: boolean; children: ReactNode }) {
  return show ? <section><h2>{title}</h2>{children}</section> : null;
}

function Entry({ title, meta, when, children }: { title: string; meta?: string; when: string; children?: ReactNode }) {
  return <div className="print-entry">
    <div className="print-entry-head"><b>{title}</b><span>{when}</span></div>
    {meta && <div className="print-meta">{meta}</div>}
    {children}
  </div>;
}

function Bullets({ text }: { text: string }) {
  const items = lines(text);
  return items.length ? <ul>{items.map((item, index) => <li key={index}>{item}</li>)}</ul> : null;
}

function degreeLabel(degree: string) {
  const option = DEGREE_OPTIONS.find(([value]) => value === degree && value !== "not_applicable");
  return option ? translate("en", option[1]) : null;
}

export function ResumePrint({ resume }: { resume: ResumeDocument }) {
  const skills = resume.skill_groups.length
    ? resume.skill_groups.map((group, index) => <p key={index}>{group.category && <b>{group.category}: </b>}{group.description}</p>)
    : <p>{resume.skills.join(", ")}</p>;

  return createPortal(<article className="resume-print">
    <header><h1>{resume.name}</h1><p>{join(resume.email, resume.phone)}</p></header>
    <Section title="Education" show={resume.educations.length > 0}>
      {resume.educations.map((item, index) => <Entry key={index} title={item.institution} when={dates(item.start_date, item.end_date)}
        meta={join(item.entry_type === "exchange" ? "Exchange" : degreeLabel(item.degree), item.major, item.country, item.gpa && `GPA ${item.gpa}`, item.ranking)}>
        {item.courses.length > 0 && <p>Courses: {item.courses.join(", ")}</p>}
      </Entry>)}
    </Section>
    <Section title="Experience" show={resume.experiences.length > 0}>
      {resume.experiences.map((item, index) => <Entry key={index} title={join(item.title, item.company)} meta={item.country ?? undefined} when={dates(item.start_date, item.end_date)}>
        <Bullets text={item.description} />
      </Entry>)}
    </Section>
    <Section title="Projects" show={resume.projects.length > 0}>
      {resume.projects.map((item, index) => <Entry key={index} title={join(item.title, item.role)} meta={item.technologies.join(", ")} when={dates(item.start_date, item.end_date)}>
        <Bullets text={item.summary} />
      </Entry>)}
    </Section>
    <Section title="Research" show={resume.research.length > 0}>
      {resume.research.map((item, index) => <Entry key={index} title={item.title} meta={item.institution ?? undefined} when={dates(item.start_date, item.end_date)}>
        <Bullets text={item.summary} />
      </Entry>)}
    </Section>
    <Section title="Skills" show={resume.skill_groups.length > 0 || resume.skills.length > 0}>{skills}</Section>
    <Section title="Certificates" show={resume.certificates.length > 0}>
      {resume.certificates.map((item, index) => <p key={index}>{join(item.name, item.issuer, item.score, item.issue_date)}</p>)}
    </Section>
    <Section title="Awards" show={resume.awards.length > 0}>
      {resume.awards.map((item, index) => <p key={index}>{join(item.name, item.date)}</p>)}
    </Section>
    <Section title="Languages" show={resume.languages.length > 0}><p>{resume.languages.join(", ")}</p></Section>
    <Section title="Additional Information" show={resume.additional_info.length > 0}>
      <ul>{resume.additional_info.map((item, index) => <li key={index}>{item}</li>)}</ul>
    </Section>
  </article>, document.body);
}
