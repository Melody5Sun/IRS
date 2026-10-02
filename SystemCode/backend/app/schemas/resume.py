from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# 简历经历的工作类型（和 schemas/common.py 里岗位用的 EmploymentType 是两套）
EmploymentType = Literal["full_time", "part_time", "internship"]
# not_applicable 用于没有学位产出的条目，比如短期交换/交流经历
Degree = Literal["bachelor", "master", "phd", "diploma", "not_applicable"]
EducationEntryType = Literal["degree", "exchange"]
# 研究类成果的类型：论文、专利、软件著作权、学位论文、科研项目（实验室/导师课题、科研助理），其余归 other
ResearchType = Literal["paper", "patent", "software_copyright", "thesis", "research_project", "other"]


class Experience(BaseModel):
    company: str
    title: str
    # None = 解析时没判断出来，保存画像前必须由用户选择
    employment_type: EmploymentType | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str = ""
    country: str | None = None


class Project(BaseModel):
    title: str
    summary: str = ""
    technologies: list[str] = Field(default_factory=list)
    role: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class Research(BaseModel):
    type: ResearchType = "research_project"
    title: str
    institution: str | None = None
    summary: str = ""
    start_date: str | None = None
    end_date: str | None = None


class Education(BaseModel):
    institution: str
    entry_type: EducationEntryType = "degree"
    degree: Degree = "not_applicable"
    major: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    country: str | None = None
    # 学校层次标签，如 "985"、"211, Double First-Class"、"QS 52"
    school_tier: str | None = None
    # 研究方向，研究型硕士/博士常写
    research_direction: str | None = None
    # 保留原文的分制，如 "3.92/4.00"
    gpa: str | None = None
    # 如 "4/64"、"Top 5%"
    ranking: str | None = None
    courses: list[str] = Field(default_factory=list)


class Certificate(BaseModel):
    name: str
    issuer: str | None = None
    issue_date: str | None = None
    expiry_date: str | None = None
    # 考试类证书的成绩，如 CET-6 的 "527"
    score: str | None = None


class SkillGroup(BaseModel):
    """技能栏原文的一行：保留分类标题、熟练程度和知识点描述，供简历改写使用（匹配仍用扁平的 skills 列表）。"""

    # 如 "Backend Development Fundamentals"；原文这一行没有分类标题时为 None
    category: str | None = None
    description: str


class Award(BaseModel):
    """奖项、奖学金、竞赛获奖、荣誉称号。"""

    name: str
    date: str | None = None


class ResumeDocument(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    experiences: list[Experience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    research: list[Research] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    skill_groups: list[SkillGroup] = Field(default_factory=list)
    educations: list[Education] = Field(default_factory=list)
    certificates: list[Certificate] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    awards: list[Award] = Field(default_factory=list)
    # 兜底：简历里没有专门字段的内容（年龄、政治面貌、可实习时长、兴趣爱好等），"Label: value" 形式，保证简历内容不丢
    additional_info: list[str] = Field(default_factory=list)


class ParsedResume(ResumeDocument):
    """LLM 解析 PDF 的输出：比画像多一个 about，存入画像时合并进求职约束的 notes。"""

    about: str | None = None


class ResumeHistoryEntry(BaseModel):
    """一次上传解析的历史记录（列表展示用，不含完整简历内容）。"""

    id: int
    filename: str | None = None
    name: str | None = None
    uploaded_at: datetime


class ResumeUpload(ResumeHistoryEntry):
    """resume_uploads 的一整条记录：上传/查看历史简历时返回，保存画像时把 id 填进 resume_upload_id。"""

    resume: ParsedResume
