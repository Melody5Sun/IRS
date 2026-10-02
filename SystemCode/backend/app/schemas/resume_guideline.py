from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.knowledge.guideline_source_registry import GUIDELINE_SOURCE_NAMES
from app.schemas.profile import TARGET_ROLE_CATEGORIES


# 条目适用的简历段落，只包含改写模块会改动的块；个人信息、教育、证书、语言原样保留，不需要知识库条目
ResumeSection = Literal["experience", "project", "research", "skills"]

# 条目要解决的问题类型。先由规则/现有评分器检测出简历存在哪类问题，再按问题类型过滤知识库，最后用向量相似度排序，
# 每一类都标明检测来源，保证"为什么给这条建议"可以追溯
IssueType = Literal[
    "weak_action_verb",          # 规则：要点以 "Responsible for" / "Helped" / "Worked on" 等弱动词开头
    # 下面两类从 weak_action_verb 拆出：向量检索按主题匹配、分不出写法问题，只能靠规则检测后用标签直接定位条目
    "passive_voice",             # 规则：被动语态（be 动词 + 过去分词，或 "by me"）
    "buzzword",                  # 规则：命中空话/自夸词表（leveraged、spearheaded、cutting-edge、AI-powered、successfully 等）
    "missing_quantification",    # 规则：要点里没有任何数字、百分比或规模描述
    "missing_outcome",           # 规则：只写了做什么，没写结果/影响（STAR 缺 Result）
    "unclear_tech_stack",        # 规则：project/experience 没有提到任何技术名词
    "weak_jd_alignment",         # 评分器：ResponsibilityScorer 中该证据单元与 JD 职责的最高相似度低于阈值
    "unsurfaced_skill",          # 评分器：JD 要求的技能出现在 skills 列表，但没有任何经历/项目支撑
    "irrelevant_content",        # 评分器：证据单元与所有 JD 职责都不相关，建议精简或下移
]


class GuidelineExample(BaseModel):
    # 改写前/后示例：既用作 LLM 的 few-shot，改写前原句也单独向量化，让检索能匹配到和用户原句相似的"反面例子"
    # 约定：改写后只使用改写前已有的事实，缺失的数据用 [...] 占位
    before: str = Field(min_length=1)
    after: str = Field(min_length=1)


class ResumeGuideline(BaseModel):
    id: int | None = None
    # 稳定的人类可读标识（如 "quantify-01"），LLM 输出建议时用它引用条目，导入数据时用它去重
    key: str
    # 出处名，取值来自 GUIDELINE_SOURCES（app/knowledge/guideline_source_registry.py）
    source: str
    # 出处里具体参考的文档链接；团队自行整理的条目为空
    source_url: str | None = None
    title: str
    # 建议本身：应该怎么写
    guideline: str
    # 为什么这样写，展示给用户作为可解释的理由
    rationale: str
    examples: list[GuidelineExample] = Field(min_length=1, max_length=3)
    sections: list[ResumeSection] = Field(min_length=1)
    issue_types: list[IssueType] = Field(min_length=1)
    # 适用的岗位大类，取值来自 TARGET_ROLE_CATEGORIES 的一级分类（数据库里由 role_categories 表外键再约束一次）；
    # 空列表表示所有 IT 岗位通用
    role_categories: list[str] = Field(default_factory=list)

    @field_validator("source")
    @classmethod
    def _validate_source(cls, value: str) -> str:
        if value not in GUIDELINE_SOURCE_NAMES:
            raise ValueError(f"source must be one of GUIDELINE_SOURCES, got {value!r}")
        return value

    @field_validator("role_categories")
    @classmethod
    def _validate_role_categories(cls, value: list[str]) -> list[str]:
        invalid = [category for category in value if category not in TARGET_ROLE_CATEGORIES]
        if invalid:
            raise ValueError(f"role_categories must be chosen from TARGET_ROLE_CATEGORIES, invalid: {invalid!r}")
        return value

    def chunk_texts(self) -> list[tuple[int | None, str]]:
        """检索用的文本块：(示例下标, 文本)。下标为 None 的是说明块（标题 + 建议），其余是各示例的改写前原句。"""
        chunks: list[tuple[int | None, str]] = [(None, f"{self.title}. {self.guideline}")]
        chunks += [(index, example.before) for index, example in enumerate(self.examples)]
        return chunks
