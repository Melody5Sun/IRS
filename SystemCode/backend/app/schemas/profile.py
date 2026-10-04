from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.resume import ResumeDocument

# 现场 / 混合 / 远程
WorkMode = Literal["onsite", "hybrid", "remote"]

# 正职 / 实习：用户要找的工作类型
TargetEmploymentType = Literal["full_time", "internship"]

# 目标岗位：二级索引，一级为职能大类，二级为具体岗位名称，覆盖 IT 相关职位；参考 ISCO-08/ESCO 的 ICT 职业分类、
# LinkedIn/Indeed 的岗位命名习惯，以及 2026 年 LinkedIn Jobs on the Rise / Forbes 等报道里生成式 AI 催生的新岗位
# （AI Engineer、Agent Engineer、MLOps 等）；内容用英文，和简历 schema（LLM 强制英文输出）保持一致；前端下拉框据此渲染
TARGET_ROLE_CATEGORIES: dict[str, tuple[str, ...]] = {
    "Software Development": (
        "Frontend Developer",
        "Backend Developer",
        "Full Stack Developer",
        "Mobile Developer (Android)",
        "Mobile Developer (iOS)",
        "Game Developer",
        "Embedded Software Engineer",
        "Desktop Application Developer",
        "Software Architect",
    ),
    "AI & Machine Learning": (
        "Algorithm Engineer",
        "Machine Learning Engineer",
        "Deep Learning Engineer",
        "Computer Vision Engineer",
        "NLP Engineer",
        "Speech Recognition Engineer",
        "Recommender Systems Engineer",
        "AI Research Scientist",
        # 生成式 AI / Agent 浪潮下新出现的岗位（2026 年招聘趋势）
        "AI Engineer",
        "Generative AI Engineer",
        "LLM Engineer",
        "Prompt Engineer",
        "Agent Engineer",
        "MLOps Engineer",
        "AI Solutions Architect",
    ),
    "Data": (
        "Data Analyst",
        "Data Scientist",
        "Data Engineer",
        "Data Architect",
        "Business Intelligence (BI) Engineer",
        "Database Administrator (DBA)",
        "Data Annotator / Labeling Specialist",
    ),
    "Quality Assurance & Testing": (
        "QA / Software Test Engineer",
        "Automation Test Engineer",
        "Performance Test Engineer",
        "Software Development Engineer in Test (SDET)",
    ),
    "DevOps & Cloud Infrastructure": (
        "DevOps Engineer",
        "Cloud Engineer",
        "Platform Engineer",
        "Site Reliability Engineer (SRE)",
        "Network Engineer",
        "Systems Administrator",
    ),
    "Cybersecurity": (
        "Information Security Engineer",
        "Penetration Tester",
        "Security Operations (SOC) Engineer",
        "Security Analyst",
        "AI Governance & Compliance Specialist",
    ),
    "Product & Project Management": (
        "Product Manager",
        "AI Product Manager",
        "Product Operations",
        "Project Manager",
        "Business/Requirements Analyst",
        "Scrum Master / Agile Coach",
    ),
    "UI/UX Design": (
        "UI Designer",
        "UX / Interaction Designer",
        "Visual Designer",
        "Product Designer",
    ),
    "Technical Support & Implementation": (
        "Technical Support Engineer",
        "Implementation Engineer",
        "Systems Integration Engineer",
        "IT Support Specialist",
        "Forward Deployed Engineer",
    ),
    "Hardware & Semiconductors": (
        "Hardware Engineer",
        "IC Design Engineer",
        "FPGA Engineer",
        "Electronics Engineer",
        "Semiconductor Process Engineer",
    ),
}
TARGET_ROLES: tuple[str, ...] = tuple(
    role for roles in TARGET_ROLE_CATEGORIES.values() for role in roles
)
_TARGET_ROLE_SET = frozenset(TARGET_ROLES)

# 目标行业：限定在 IT 相关行业范围内；参考 GICS Information Technology 板块和 LinkedIn 行业分类整理；
# 内容用英文，和上面的岗位清单及简历 schema 保持一致；前端下拉框据此渲染
TARGET_INDUSTRIES: tuple[str, ...] = (
    "Internet",
    "Software & IT Services",
    "Artificial Intelligence",
    "Semiconductors & Integrated Circuits",
    "Telecommunications",
    "Cloud Computing & Big Data",
    "Financial Technology (FinTech)",
    "E-commerce",
    "Gaming",
    "IoT & Smart Hardware",
    "Enterprise Software & SaaS",
    "Cybersecurity",
    "Education Technology (EdTech)",
    "Healthcare Technology (HealthTech)",
    "Automotive & Autonomous Driving",
)
_TARGET_INDUSTRY_SET = frozenset(TARGET_INDUSTRIES)


class JobSearchConstraints(BaseModel):
    target_roles: list[str] = Field(default_factory=list)
    target_industries: list[str] = Field(default_factory=list)
    work_modes: list[WorkMode] = Field(default_factory=list)
    # 用户要找的工作类型：正职/实习，可多选
    target_employment_types: list[TargetEmploymentType] = Field(default_factory=list)
    # 补充说明（选填）；上传简历时用简历里的自我介绍预填
    notes: str = ""

    @field_validator("target_roles")
    @classmethod
    def _validate_target_roles(cls, value: list[str]) -> list[str]:
        invalid = [item for item in value if item not in _TARGET_ROLE_SET]
        if invalid:
            raise ValueError(f"target_roles must be chosen from the preset list, invalid: {invalid}")
        return value

    @field_validator("target_industries")
    @classmethod
    def _validate_target_industries(cls, value: list[str]) -> list[str]:
        invalid = [item for item in value if item not in _TARGET_INDUSTRY_SET]
        if invalid:
            raise ValueError(f"target_industries must be chosen from the preset list, invalid: {invalid}")
        return value


class UserProfile(BaseModel):
    # 画像沿用简历 schema：parse-pdf 解析结果，用户可在前端修改补全
    resume: ResumeDocument
    constraints: JobSearchConstraints = Field(default_factory=JobSearchConstraints)
    # 画像来自哪条上传记录（resume_uploads.id）；保存画像时必填，补全后的简历会回写到这一条。
    # 设为可选是因为 rules-screening / matches 等接口仍直接拿 UserProfile 当请求体，不要求有上传记录
    resume_upload_id: int | None = None


class SavedProfile(UserProfile):
    """库里保存的画像，多一个最后保存时间（前端显示「画像更新于」）。"""

    updated_at: datetime


class ProfileOptions(BaseModel):
    """目标岗位/目标行业的预设范围，供前端渲染下拉框。"""

    target_role_categories: dict[str, list[str]] = Field(
        default_factory=lambda: {k: list(v) for k, v in TARGET_ROLE_CATEGORIES.items()}
    )
    target_industries: list[str] = Field(default_factory=lambda: list(TARGET_INDUSTRIES))
