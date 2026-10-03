"""简历改写的问题检测：先找出每块/每行有哪些问题，再按问题类型去知识库检索条目。

行级问题用规则检测（不调用模型）；块级问题来自现有评分器的结果：
JD 职责相似度（weak_jd_alignment / irrelevant_content）和技能匹配（unsurfaced_skill）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.matching.responsibility_scorer import ResponsibilityScorer
from app.parsers.text_parser import extract_skills
from app.schemas.job import JobRequirementDocument
from app.schemas.match import SkillScoreResponse
from app.schemas.resume import ResumeDocument
from app.schemas.resume_guideline import IssueType, ResumeSection
from app.services.responsibility_match_service import ResponsibilityMatchService

_BULLET = re.compile(r"^\s*(?:[-*•·▪●]|\d+[.)])\s*")
# 「小标题: 内容」写法的小标题（不超过 MAX_LABEL_WORDS 个词才算），检测前去掉，否则行首规则命中不了 "Participated in"
_LABEL = re.compile(r"^([^:：]{1,60})[:：]\s+")
MAX_LABEL_WORDS = 6
# 这些小标题的行只是项目名/技术栈/链接，不是成果要点，不做行级检测
_HEADER_LABELS = {"project", "tech stack", "technology stack", "core technologies", "technologies", "github", "link", "demo"}
_WEAK_VERB = re.compile(
    r"^(?:responsible for|in charge of|helped|helping|assisted|assisting|worked on|working on|"
    r"participated in|involved in|tasked with|duties included|took part in|contributed to)\b",
    re.IGNORECASE,
)
# ponytail: be 动词 + 规则过去分词/常见不规则过去分词的正则，会漏判少见的不规则动词，也可能把 "was keen" 这类形容词误判
_PASSIVE = re.compile(
    r"\b(?:am|is|are|was|were|be|been|being)\s+(?:\w+ly\s+)?"
    r"(?:\w+ed|built|made|done|given|taken|written|sent|run|led|held|kept|set|put|chosen|shown|seen|known|brought)\b"
    r"|\bby me\b",
    re.IGNORECASE,
)
_BUZZWORD = re.compile(
    r"\b(?:leverag(?:e|ed|ing)|spearhead(?:ed|ing)?|synerg(?:y|ies)|cutting[- ]edge|state[- ]of[- ]the[- ]art|"
    r"best[- ]in[- ]class|world[- ]class|ai[- ]powered|successfully|seamless(?:ly)?|passionate|results[- ]driven|"
    r"innovative|utiliz(?:e|ed|ing)|various)\b",
    re.IGNORECASE,
)
_QUANTITY = re.compile(
    r"\d|\b(?:two|three|four|five|six|seven|eight|nine|ten|dozens?|hundreds?|thousands?|millions?|billions?)\b",
    re.IGNORECASE,
)
# ponytail: 只按结果类词语判断是否写了结果，"Built X for Y team" 这类隐含结果的句子也会被报 missing_outcome；
# 要更准需要 LLM 或句法分析
_OUTCOME = re.compile(
    r"%|\b(?:result(?:ed|ing)? in|lead(?:ing)? to|led to|so that|enabl(?:e|ed|ing)|allow(?:ed|ing)|"
    r"reduc\w*|improv\w*|increas\w*|decreas\w*|cut(?:ting)?|sav(?:e|ed|ing)|boost\w*|achiev\w*|"
    r"accelerat\w*|lower\w*|rais(?:e|ed|ing)|gr[eo]w\w*|speed\w* up|faster|shorten\w*|eliminat\w*|"
    r"prevent\w*|adopted|praised|award\w*|won)\b",
    re.IGNORECASE,
)
# 少于这么多词的行（小标题、"Tech: ..." 之类）不做行级检测
MIN_LINE_WORDS = 4


@dataclass(frozen=True)
class LineIssues:
    # 块原文按 "\n" 拆开后的行号（空行也占行号），前端按同样方式拆分即可定位
    line: int
    text: str
    issue_types: list[IssueType]


@dataclass
class BlockIssues:
    section: ResumeSection
    index: int
    heading: str
    # 被改写的文本：experience.description / project.summary / research.summary，技能栏为分组原文
    text: str
    lines: list[LineIssues] = field(default_factory=list)
    # 块级问题：unclear_tech_stack / weak_jd_alignment / irrelevant_content / unsurfaced_skill
    block_issues: list[IssueType] = field(default_factory=list)
    # 与该块最相近的 JD 职责原文和相似度，作为改写的对齐目标
    jd_responsibility: str | None = None
    jd_similarity: float | None = None
    # 仅技能栏：JD 要求、技能栏里有、但没有任何经历/项目/研究支撑的技能
    unsurfaced_skills: list[str] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        return bool(self.lines or self.block_issues)


def line_issues(text: str) -> list[IssueType]:
    """一行要点的规则检测，一行可同时报多个问题类型。"""
    line = _BULLET.sub("", text).strip()
    if (label := _LABEL.match(line)) and len(label.group(1).split()) <= MAX_LABEL_WORDS:
        if label.group(1).strip().casefold() in _HEADER_LABELS:
            return []
        line = line[label.end():]
    if len(line.split()) < MIN_LINE_WORDS:
        return []
    issues: list[IssueType] = []
    if _WEAK_VERB.match(line):
        issues.append("weak_action_verb")
    if _PASSIVE.search(line):
        issues.append("passive_voice")
    if _BUZZWORD.search(line):
        issues.append("buzzword")
    if not _QUANTITY.search(line):
        issues.append("missing_quantification")
    if not _OUTCOME.search(line):
        issues.append("missing_outcome")
    return issues


def jd_alignments(
    service: ResponsibilityMatchService,
    resume: ResumeDocument,
    job: JobRequirementDocument,
) -> dict[tuple[str, int], tuple[float, str]]:
    """每个证据块（经历/项目/研究）与各条 JD 职责的最高相似度及对应职责；JD 没有职责时为空。"""
    responsibilities = service.scorer.responsibility_texts(job)
    job_embeddings = service.ensure_job_embeddings(job)
    prepared = service.prepare_candidate(resume)
    if not responsibilities or not job_embeddings or not prepared.evidence:
        return {}
    alignments: dict[tuple[str, int], tuple[float, str]] = {}
    for unit, vector in zip(prepared.evidence, prepared.embeddings, strict=True):
        similarities = [ResponsibilityScorer._cosine_similarity(vector, job_vector) for job_vector in job_embeddings]
        best = max(range(len(similarities)), key=similarities.__getitem__)
        alignments[(unit.evidence_type, unit.evidence_index)] = (similarities[best], responsibilities[best])
    return alignments


def detect_issues(
    resume: ResumeDocument,
    alignments: dict[tuple[str, int], tuple[float, str]],
    skill_score: SkillScoreResponse,
    similarity_floor: float,
    similarity_full: float,
) -> list[BlockIssues]:
    """按块输出检测结果（经历 → 项目 → 研究 → 技能栏），没有问题的块也返回，由调用方筛选。"""
    blocks: list[BlockIssues] = []
    entries = [
        *(("experience", i, f"{e.title} · {e.company}", e.description, None) for i, e in enumerate(resume.experiences)),
        *(("project", i, p.title, p.summary, p.technologies) for i, p in enumerate(resume.projects)),
        *(("research", i, r.title, r.summary, None) for i, r in enumerate(resume.research)),
    ]
    for section, index, heading, text, technologies in entries:
        block = BlockIssues(section=section, index=index, heading=heading, text=text)
        for number, line in enumerate(text.split("\n")):
            if issues := line_issues(line):
                block.lines.append(LineIssues(number, line.strip(), issues))
        if text.strip() and not extract_skills(text) and not technologies:
            block.block_issues.append("unclear_tech_stack")
        if (section, index) in alignments:
            similarity, responsibility = alignments[(section, index)]
            block.jd_similarity, block.jd_responsibility = similarity, responsibility
            if similarity < similarity_floor:
                block.block_issues.append("irrelevant_content")
            elif similarity < similarity_full:
                block.block_issues.append("weak_jd_alignment")
        blocks.append(block)

    skills_block = BlockIssues(
        section="skills", index=0, heading="Skills",
        text="\n".join(f"{g.category or ''}: {g.description}" for g in resume.skill_groups),
    )
    skills_block.unsurfaced_skills = _unsurfaced_skills(resume, skill_score)
    # 技能栏总要按 JD 精简和排序，固定带 irrelevant_content，保证 LLM 写理由时有合法的问题类型
    skills_block.block_issues.append("irrelevant_content")
    if skills_block.unsurfaced_skills:
        skills_block.block_issues.append("unsurfaced_skill")
    blocks.append(skills_block)
    return blocks


def _unsurfaced_skills(resume: ResumeDocument, skill_score: SkillScoreResponse) -> list[str]:
    # 经历/项目/研究里提到过的技能（归一化后的名字，和技能评分用同一套词表）
    evidence = [e.description for e in resume.experiences]
    evidence += [f"{p.summary}\n{', '.join(p.technologies)}" for p in resume.projects]
    evidence += [r.summary for r in resume.research]
    surfaced = {skill.casefold() for skill in extract_skills("\n".join(evidence))}
    matches = [*skill_score.direct_required_matches, *skill_score.direct_preferred_matches]
    return list(dict.fromkeys(
        match.jd_skill for match in matches
        if match.jd_skill.casefold() not in surfaced and match.candidate_skill.casefold() not in surfaced
    ))
