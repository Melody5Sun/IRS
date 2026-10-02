from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

EmploymentType = Literal[
    "internship", "full_time", "part_time", "contract", "freelance", "not_stated"
]
# not_applicable 用于没有学位产出的条目，比如短期交换/交流经历
Degree = Literal["bachelor", "master", "phd", "diploma", "not_applicable"]
EducationEntryType = Literal["degree", "exchange"]


class Experience(BaseModel):
    company: str
    title: str
    employment_type: EmploymentType = "not_stated"
    start_date: str | None = None
    end_date: str | None = None
    description: str = ""
    country: str | None = None


class Project(BaseModel):
    title: str
    summary: str = ""
    technologies: list[str] = Field(default_factory=list)
    role: str | None = None


class Research(BaseModel):
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


class Certificate(BaseModel):
    name: str
    issuer: str | None = None
    issue_date: str | None = None
    expiry_date: str | None = None


class ResumeDocument(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    experiences: list[Experience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    research: list[Research] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    educations: list[Education] = Field(default_factory=list)
    certificates: list[Certificate] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)


class ParsedResume(ResumeDocument):
    """LLM 解析 PDF 的输出：比画像多一个 about，存入画像时合并进求职约束的 notes。"""

    about: str | None = None


class ResumeHistoryEntry(BaseModel):
    """一次上传解析的历史记录（列表展示用，不含完整简历内容）。"""

    id: int
    filename: str | None = None
    name: str | None = None
    uploaded_at: datetime
