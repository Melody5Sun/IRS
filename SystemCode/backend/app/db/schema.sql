CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    company TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    location TEXT,
    description TEXT NOT NULL,
    url TEXT NOT NULL,
    employment_type TEXT,
    collected_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    raw_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(source, external_id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);

CREATE TABLE IF NOT EXISTS company_sources (
    name TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    provider TEXT NOT NULL,
    identifier TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    priority INTEGER NOT NULL DEFAULT 100,
    last_checked_at TEXT,
    last_status TEXT,
    last_message TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_company_sources_enabled_priority
ON company_sources(enabled, priority, company);

CREATE TABLE IF NOT EXISTS industries (
    name TEXT PRIMARY KEY
);

INSERT OR IGNORE INTO industries(name) VALUES
    ('Internet'),
    ('Software & IT Services'),
    ('Artificial Intelligence'),
    ('Semiconductors & Integrated Circuits'),
    ('Telecommunications'),
    ('Cloud Computing & Big Data'),
    ('Financial Technology (FinTech)'),
    ('E-commerce'),
    ('Gaming'),
    ('IoT & Smart Hardware'),
    ('Enterprise Software & SaaS'),
    ('Cybersecurity'),
    ('Education Technology (EdTech)'),
    ('Healthcare Technology (HealthTech)'),
    ('Automotive & Autonomous Driving');

CREATE TABLE IF NOT EXISTS company_industries (
    normalized_company TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    industry TEXT NOT NULL,
    FOREIGN KEY(industry) REFERENCES industries(name)
);

CREATE INDEX IF NOT EXISTS idx_company_industries_industry
ON company_industries(industry, company);

CREATE TABLE IF NOT EXISTS job_analysis (
    job_id INTEGER PRIMARY KEY,
    summary TEXT NOT NULL DEFAULT '',
    responsibilities_json TEXT NOT NULL DEFAULT '[]',
    required_skills_json TEXT NOT NULL DEFAULT '[]',
    preferred_skills_json TEXT NOT NULL DEFAULT '[]',
    employment_type TEXT NOT NULL DEFAULT 'not_stated',
    candidate_type TEXT NOT NULL DEFAULT 'not_stated',
    remote_policy TEXT NOT NULL DEFAULT 'not_stated',
    degree_required TEXT NOT NULL DEFAULT 'not_stated',
    major_required_json TEXT NOT NULL DEFAULT '[]',
    keywords_json TEXT NOT NULL DEFAULT '[]',
    source_evidence_json TEXT NOT NULL DEFAULT '[]',
    analysis_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(job_id) REFERENCES jobs(id)
);

-- 面试题库，供后续和 JD/候选人做标签匹配（技能/关键词）与语义匹配（embedding）
CREATE TABLE IF NOT EXISTS interview_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    question_text TEXT NOT NULL,
    standard_answer TEXT NOT NULL DEFAULT '',
    question_text_en TEXT,
    standard_answer_en TEXT,
    roles_json TEXT NOT NULL DEFAULT '[]',
    difficulty_level TEXT NOT NULL DEFAULT 'not_stated',
    company TEXT,
    collected_at TEXT NOT NULL,
    question_embedding_json TEXT,
    skills_json TEXT NOT NULL DEFAULT '[]',
    keywords_json TEXT NOT NULL DEFAULT '[]',
    UNIQUE(source, external_id)
);

CREATE INDEX IF NOT EXISTS idx_interview_questions_company ON interview_questions(company);
