from datetime import datetime
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
    "placeholder_mismatch", # 改写稿里的占位和 needs_user_input 对不上（有占位没提问，或提了问却没占位）
]
# unchanged = 不用改；rewritten = 已改好，用户只需接受/拒绝；
# needs_input = 信息不足，草稿带占位，要用户通过 /resumes/rewrite/fill 补充后才回填进简历
BlockStatus = Literal["unchanged", "rewritten", "needs_input"]


class LocalizedText(BaseModel):
    """给用户看的文字中英各一份，前端切换语言时不用重新调 LLM。"""

    en: str
    zh: str


class RewriteReason(BaseModel):
    issue_type: IssueType
    # LLM 结合知识库条目写成的易读理由（哪里有问题 → 建议怎么写 → 为什么）
    explanation: LocalizedText
    # 引用的知识库条目 key（ResumeGuideline.key），只保留本次检索结果里确实有的
    guideline_keys: list[str] = Field(default_factory=list)
    # 这次改写对齐的 JD 职责原文，没有对齐具体职责时为 None
    jd_responsibility: str | None = None


class UserInputRequest(BaseModel):
    """改写稿里缺数据的占位：前端向用户提问，拿到回答后把 placeholder 原样替换掉。"""

    # 改写稿里原样出现的占位，如 "[number of users]"
    placeholder: str
    question: LocalizedText
    # 为什么需要补这项（如：量化结果让招聘方看到影响）
    reason: LocalizedText


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
    needs_user_input: list[UserInputRequest] = Field(default_factory=list)


class DeletionSuggestion(BaseModel):
    """和 JD 无关、建议删除的内容；不直接应用，由用户在前端确认后再删。"""

    section: Literal["experience", "project", "research"]
    index: int = Field(ge=0)
    # None = 删整条经历/项目/研究；否则删该条 description/summary 按换行拆开后的第 line 行（从 0 开始）
    line: int | None = Field(default=None, ge=0)
    # 要删的原文：整条删除时是 description/summary 全文，按行删除时是那一行
    original: str
    reasons: list[RewriteReason] = Field(min_length=1)


class ResumeChangeSet(BaseModel):
    """LLM 的完整输出。"""

    changes: list[ResumeChange] = Field(default_factory=list)
    deletions: list[DeletionSuggestion] = Field(default_factory=list)


class RejectedChange(BaseModel):
    change: ResumeChange
    reason: RejectionReason
    detail: str


class RejectedDeletion(BaseModel):
    deletion: DeletionSuggestion
    detail: str


class RewriteBlock(BaseModel):
    """按块展示的改写结果：一个块就是简历里的一条经历/项目/研究，或整个技能栏。"""

    section: ResumeSection
    index: int
    # 块标题由代码从原简历生成（如 "Backend Intern · Shopee"），不经过 LLM
    heading: str
    status: BlockStatus = "unchanged"
    # 通过检查的改动；为空表示这一块保持原样。带 needs_user_input 的改动是草稿，没有写进 rewritten_resume
    changes: list[ResumeChange] = Field(default_factory=list)
    # 该块所有改动待用户回答的问询汇总，status=needs_input 时非空
    pending_inputs: list[UserInputRequest] = Field(default_factory=list)
    # 仅技能栏块：改写后技能栏里删掉的技能（原文写法），提醒用户确认
    removed_skills: list[str] = Field(default_factory=list)


class CitedGuideline(BaseModel):
    """被引用的知识库条目，只作出处；理由正文已由 LLM 写进 RewriteReason.explanation。"""

    key: str
    title: str
    source: str
    source_url: str | None = None


class ResumeRewriteResult(BaseModel):
    job_id: int | None = None
    blocks: list[RewriteBlock]
    # 只应用了直接改写的改动；待补充块的字段保持原文，补全后由前端回填
    rewritten_resume: ResumeDocument
    # 被拒绝的改动连同原因一起返回给用户，不静默丢弃
    rejected_changes: list[RejectedChange] = Field(default_factory=list)
    # 删除建议不应用到 rewritten_resume，用户确认后由前端删除
    deletion_suggestions: list[DeletionSuggestion] = Field(default_factory=list)
    rejected_deletions: list[RejectedDeletion] = Field(default_factory=list)
    # 本次改动和删除建议引用到的知识库条目
    guidelines: list[CitedGuideline] = Field(default_factory=list)


class ResumeRewriteRequest(BaseModel):
    # 用户从库里选的岗位；简历由服务端从画像读取
    job_id: int


class PlaceholderAnswer(BaseModel):
    # 改写稿里原样出现的占位，如 "[number of users]"
    placeholder: str
    # None 或空串 = 用户跳过，改成不含该信息的中性表述
    answer: str | None = None


class BlockFillRequest(BaseModel):
    """待补充块的一轮问答：用户回答（或跳过）若干问询，LLM 把回答写进该块。"""

    job_id: int
    section: Literal["experience", "project", "research"]
    index: int = Field(ge=0)
    # 该块当前草稿：第一轮是改写结果里该改动的 value，之后是上一轮 fill 返回的 value
    text: str
    answers: list[PlaceholderAnswer] = Field(min_length=1)


class BlockFill(BaseModel):
    """LLM 的输出。"""

    value: str
    # 回答太含糊无法写成事实时的追问，value 里保留对应占位
    needs_user_input: list[UserInputRequest] = Field(default_factory=list)


class BlockFillResult(BlockFill):
    section: ResumeSection
    index: int
    field: RewriteField
    # needs_user_input 为空 = 补全完成，前端把 value 写进改写后简历的该字段


class RewriteSession(BaseModel):
    """改写对比和用户的审阅进度，前端原样存取；块的 key 为 "section:index"，草稿的 key 为 "section:index:改动序号"。"""

    result: ResumeRewriteResult
    reviews: dict[str, Literal["accepted", "rejected"]] = Field(default_factory=dict)
    # 用户编辑或补全后的文本草稿
    drafts: dict[str, str] = Field(default_factory=dict)
    # 待补充块还没回答的问询
    pending: dict[str, list[UserInputRequest]] = Field(default_factory=dict)
    # 删除建议下标 → 是否已勾选
    confirmed_deletions: dict[int, bool] = Field(default_factory=dict)


class SavedResumeRewrite(BaseModel):
    """按（简历, 岗位）保存的改写稿。"""

    # 终稿；None = 只生成了草稿、还没保存终稿
    resume: ResumeDocument | None
    # 改写对比和审阅进度；旧数据没有时为 None
    session: RewriteSession | None = None
    # 画像里的简历在这份改写稿保存之后又被修改过
    stale: bool
    updated_at: datetime
