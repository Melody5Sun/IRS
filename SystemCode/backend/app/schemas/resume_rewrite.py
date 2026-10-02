from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.resume import ResumeDocument, SkillGroup
from app.schemas.resume_guideline import IssueType, ResumeSection


# 允许 LLM 改动的字段；公司、职位、日期、学校等身份字段不在这里，LLM 无法改动。
# 技能栏改的是 skill_groups（技能栏原文），扁平的 skills 列表只供匹配使用、不改动
RewriteField = Literal["description", "summary", "technologies", "skill_groups"]

# 本地检查器拒绝一条改动的原因
RejectionReason = Literal[
    "invalid_target",       # 段落/字段组合不在白名单、下标越界，或同一字段被改了两次
    "original_mismatch",    # LLM 复述的原文和简历实际内容对不上，说明它"记错"了原文
    "not_a_reorder",        # technologies 只允许重新排序，不能增删条目
    "new_number",           # 改写后出现了原块里没有的数字（编造量化结果）
    "new_skill",            # 改写后出现了原简历里没有的技能
    "too_long",             # 改写后篇幅膨胀过多
    "jd_company_mention",   # 把 JD 的公司名写进了简历
]


class RewriteReason(BaseModel):
    issue_type: IssueType
    # 展示给用户的改写原因
    explanation: str
    # 引用的知识库条目 key（ResumeGuideline.key）
    guideline_keys: list[str] = Field(default_factory=list)
    # 这次改写对齐的 JD 职责原文，没有对齐具体职责时为 None
    jd_responsibility: str | None = None


class ResumeChange(BaseModel):
    """LLM 输出的一条改动：只描述要改的地方，原简历由代码保留。"""

    section: ResumeSection
    # 在对应列表（experiences/projects/research）中的下标；skills 段落固定为 0
    index: int = Field(default=0, ge=0)
    field: RewriteField
    # LLM 复述的原文，用来核对它改的确实是这一块
    original: str | list[str] | list[SkillGroup]
    # skills 段落输出完整的新技能栏（skill_groups 格式），同时参考 skills 列表和原 skill_groups：
    # 只放对目标 JD 有用的技能（可补入 skills 列表里有、原技能栏没写的），分组和组内技能都按对 JD 的重要性排序；
    # 不限篇幅，可删掉无关技能，删掉的由代码找出并提醒用户
    value: str | list[str] | list[SkillGroup]
    reasons: list[RewriteReason] = Field(min_length=1)
    # 缺少数据时不编造，改写文本里用 [metric] 之类的占位符，并在这里向用户提问
    needs_user_input: list[str] = Field(default_factory=list)


class ResumeChangeSet(BaseModel):
    """LLM 的完整输出。"""

    changes: list[ResumeChange] = Field(default_factory=list)


class RejectedChange(BaseModel):
    change: ResumeChange
    reason: RejectionReason
    detail: str


class RewriteBlock(BaseModel):
    """按块展示的改写结果：一个块就是简历里的一条经历/项目/研究，或整个技能栏。"""

    section: ResumeSection
    index: int
    # 块标题由代码从原简历生成（如 "Backend Intern · Shopee"），不经过 LLM
    heading: str
    # 通过检查并已应用的改动；为空表示这一块保持原样
    changes: list[ResumeChange] = Field(default_factory=list)
    # 仅技能栏块：改写后技能栏里删掉的技能（原文写法），提醒用户确认
    removed_skills: list[str] = Field(default_factory=list)


class ResumeRewriteResult(BaseModel):
    blocks: list[RewriteBlock]
    rewritten_resume: ResumeDocument
    # 被拒绝的改动连同原因一起返回给用户，不静默丢弃
    rejected_changes: list[RejectedChange] = Field(default_factory=list)
