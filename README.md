## SECTION 1 : PROJECT TITLE
## IT CareerPilot — An Explainable Hybrid Reasoning System for IT Student Internships and Graduate Employment

<img src="Miscellaneous/Beginning page.png"
     style="float: left; margin-right: 0px;" />

---

## SECTION 2 : EXECUTIVE SUMMARY / PAPER ABSTRACT

IT students looking for internships or graduate roles in Singapore face job postings scattered across many company portals, fast-changing technology requirements, and many similar-looking job descriptions (JDs). Sending one generic resume everywhere hides the link between a student's experience and the responsibilities of a specific role, while reading every JD, checking eligibility, tailoring the resume and preparing for interviews is slow and stressful. Existing tools each cover only one step: job boards aggregate postings with opaque recommendations, resume tools focus on keyword coverage, and auto-apply bots chase volume and may break platform terms. Our question was: without auto-submitting applications or inventing experience, how can a student find roles worth the effort, understand why they match and where the gaps are, turn real experience into role-specific material, and manage the whole job-search process?

IT CareerPilot answers this with a five-step workflow — resume profile, job recommendation, resume tailoring, mock interview and application tracking — built on hybrid reasoning. An Experta forward-chaining rule engine first screens out ineligible jobs (status, education, work mode, employment type, experience-only roles, industry). Remaining jobs are ranked by direct skill coverage, MIND skill-ontology (knowledge graph) coverage and Sentence-BERT responsibility similarity, and every recommendation shows its matched skills, evidence and gaps. Resume tailoring is a RAG pipeline over an expert knowledge base of 385 writing guidelines and 1,155 before/after examples; it proposes block-wise diffs with cited reasons, and a local fact checker rejects any new number or skill that is not in the original resume, asking the student to fill in missing facts instead. Mock interviews draw role-specific questions from a question bank and transcribe recorded English answers with Whisper.

In evaluation, the hybrid ranker reached a mean NDCG@10 of 0.841 on held-out resumes, and removing any component lowered it; LLM resume parsing came close to the silver labels with almost no fabricated content; and 97% of rewrite reasons trace back to a specific knowledge-base entry. The main lesson is that the trustworthiness of a cognitive system comes less from the LLM itself than from the symbolic constraints, knowledge organisation and human-in-the-loop design around it. Future work includes re-testing the rewrite flow on the production Gemini model with human raters, per-answer interview feedback, and the genetic-algorithm application scheduler from the original proposal.

---

## SECTION 3 : CREDITS / PROJECT CONTRIBUTION

| Official Full Name  | Student ID (MTech Applicable)  | Work Items (Who Did What) | Email (Optional) |
| :------------ |:---------------:| :-----| :-----|
| **Zhao Jiayi** | **A0329873M** | Built the job data pipeline: job ingestion, JD requirement parsing and MIND skill knowledge-graph integration<br/>Migrated storage to PostgreSQL + pgvector and maintained the shared team database snapshots<br/>Developed the hybrid job ranking engine: skill-graph coverage, responsibility semantic matching and career-intent matching<br/>Validated ranking weights with cross-validation and an ablation study (mean NDCG@10 0.841)<br/>Built the interview question and Whisper answer-transcription APIs, connected the recommendation and mock-interview pages, and co-wrote the project report | |
| **Sun Wenjing** | **A0326610N** | Developed the Experta forward-chaining rule engine for eligibility screening<br/>Built layout-aware resume PDF parsing and the user profile flow<br/>Developed the resume tailoring module: RAG over an expert knowledge base (385 guidelines, 1,155 examples), block-wise rewrites with cited reasons, and fact checking<br/>Built target-job and application-progress tracking, the frontend dashboard, resume-rewrite page and Chinese/English switch<br/>Evaluated and optimised resume parsing and rewriting, co-wrote the project report and produced the promotion video |e1538441@u.nus.edu|

---

## SECTION 4 : VIDEO OF SYSTEM MODELLING & USE CASE DEMO

**Promotion video**

![IT CareerPilot Promotion](<Miscellaneous/video1 封面.jpg>)

[▶ Watch the promotion video on YouTube](https://youtu.be/MtBKkAwVGTU)

**System design & use case demo video**

[![IT CareerPilot System Demo](http://img.youtube.com/vi/<YOUTUBE_ID>/0.jpg)](https://youtu.be/<YOUTUBE_ID> "IT CareerPilot System Demo")

Video files are not stored in this repository (they exceed GitHub's 100 MB file limit). See [Video/README.md](Video/README.md).

---

## SECTION 5 : USER GUIDE

`Refer to appendix <Installation & User Guide> in project report at Github Folder: ProjectReport`

### [ 1 ] Requirements

> Windows 10 / 11 (the start script is PowerShell), Docker Desktop, Conda (Python 3.11), Node.js and npm

> A Gemini API key (resume parsing, JD extraction and resume rewriting); optionally a Cloudflare account ID and API token (interview answer transcription)

### [ 2 ] Install and start

> $ git clone https://github.com/Melody5Sun/IRS.git

> $ cd IRS

> $ conda create -n careerpilot-backend python=3.11

> $ conda activate careerpilot-backend

> (careerpilot-backend) $ python -m pip install -r SystemCode/backend/requirements.txt

> Copy `SystemCode/backend/.env.example` to `SystemCode/backend/.env` and fill in `DATABASE_URL` (local Docker: `postgresql+psycopg://careerpilot:careerpilot@127.0.0.1:5433/careerpilot`), `GEMINI_API_KEY` (or all three of `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`), and optionally `CLOUDFLARE_ACCOUNT_ID` / `CLOUDFLARE_API_TOKEN`

> (careerpilot-backend) PS> .\SystemCode\start-backend.ps1

> The script starts Docker Desktop and the PostgreSQL container (pgvector/pgvector:pg16, port 5433), offers to import the team data snapshot on first run, runs `alembic upgrade head` if needed, then starts the backend on port 8000 and opens http://localhost:8000/docs

> $ cd SystemCode/frontend

> $ npm install

> $ npm run dev

> **Go to URL using web browser** http://localhost:5173

> (Optional) Tests: `python -m pytest tests/ -q` in `SystemCode/backend`; `npm test` in `SystemCode/frontend`

### [ 3 ] Using the system

Follow the five steps in the flow menu at the bottom right:

1. **Resume profile & career intent** — upload a PDF resume, review and complete the parsed experience, projects and skills, choose target roles, industries, work mode and employment type, then save the profile.
2. **Job recommendation** — browse the rule-screened, ranked jobs; open match details to see matched skills, evidence and gaps; add suitable jobs to "My Target Jobs".
3. **Resume tailoring** — pick a target job and click "Generate" (about one minute); accept or reject each block's change and reason; answer the system's questions for "to be completed" blocks; save the final version and export it as PDF via print.
4. **Mock interview** — draw interview questions for a target job, record answers with camera and microphone, view the English transcript and reference answer, then mark the mock interview as done.
5. **My Target Jobs** — update each job's application stage and notes, and track preparation progress (resume rewrite, mock interview, application).

The interface can be switched between Chinese and English at the top right. If the system reports that the LLM is busy or out of quota, try again later.

---
## SECTION 6 : PROJECT REPORT / PAPER

`Refer to project report at Github Folder: ProjectReport`

**Sections of the Project Report:**
- Introduction: Background, Problem Statement, Objectives & Success Criteria
- Business Case & Market Research
- Project Scope & Constraints
- Data Collection & Preparation
- System Design
- System Development & Implementation
- Evaluation & Optimisation
- Findings & Discussion
- Conclusion & Future Work
- References
- Appendix: Project Proposal
- Appendix: Mapped System Functionalities against knowledge, techniques and skills of modular courses: MR, RS, CGS
- Appendix: Installation and User Guide

---
## SECTION 7 : MISCELLANEOUS

`Refer to Github Folder: Miscellaneous`

### Project proposal
* `IRS-Project-Proposal-IT-CareerPilot-Group28.pdf` — submitted proposal
* `IRS-Project-Proposal-V1-EN.docx` / `IRS-Project-Proposal-V1-CN.docx` — proposal source (English / Chinese)
* `IT-CareerPilot-Project-Proposal-Final-EN-10min.pptx` — proposal presentation slides
* `IT-CareerPilot-Proposal-Architecture.html`, `IT-CareerPilot-Use-Case-Diagram.html` — proposal diagrams

### proposal-assets/
* Student persona, pain-point word cloud and their research sources (`CareerPilot-Persona-Research-Sources.md`)
* Architecture, functional module, typical user flow and use case diagrams (HTML + PNG previews)

### video-production/
* Promotion video script, voice-over drafts and subtitles, style guide, style frames, sources and review notes
* Background music track used in the promotion video

### FinalReport-zjy.docx
* An earlier full draft of the project report, kept for reference

### Evaluation write-ups (in SystemCode)
* [`SystemCode/evaluation/README.md`](SystemCode/evaluation/README.md) — resume parsing and rewrite evaluation
* [`SystemCode/backend/evaluation/job_ranking/`](SystemCode/backend/evaluation/job_ranking/) — job ranking evaluation


