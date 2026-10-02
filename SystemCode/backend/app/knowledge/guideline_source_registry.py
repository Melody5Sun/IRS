from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class GuidelineSource:
    """简历改写知识库条目的出处（写法同 app/ingestion/source_registry.py 的 JobSource）。"""

    name: str
    provider: str
    identifier: str
    url: str | None = None
    license: str | None = None
    retrieved_at: date | None = None


_RETRIEVED = date(2026, 10, 2)

GUIDELINE_SOURCES = [
    GuidelineSource(
        name="tech-interview-handbook",
        provider="github",
        identifier="yangshun/tech-interview-handbook",
        url="https://github.com/yangshun/tech-interview-handbook",
        license="MIT",
        retrieved_at=_RETRIEVED,
    ),
    GuidelineSource(
        name="resume-skills",
        provider="github",
        identifier="Paramchoudhary/ResumeSkills",
        url="https://github.com/Paramchoudhary/ResumeSkills",
        license="MIT",
        retrieved_at=_RETRIEVED,
    ),
    GuidelineSource(
        name="resume-jd-optimizer-cn",
        provider="github",
        identifier="coinluu/resume-jd-optimizer-cn",
        url="https://github.com/coinluu/resume-jd-optimizer-cn",
        license="MIT",
        retrieved_at=_RETRIEVED,
    ),
    GuidelineSource(
        name="resume-matcher",
        provider="github",
        identifier="srbhr/Resume-Matcher",
        url="https://github.com/srbhr/Resume-Matcher",
        license="Apache-2.0",
        retrieved_at=_RETRIEVED,
    ),
    GuidelineSource(
        name="resume-tailoring-skill",
        provider="github",
        identifier="varunr89/resume-tailoring-skill",
        url="https://github.com/varunr89/resume-tailoring-skill",
        license="MIT",
        retrieved_at=_RETRIEVED,
    ),
    # 团队依据以上资料自行整理的条目（主要是各岗位大类的专属建议）
    GuidelineSource(
        name="it-careerpilot-team",
        provider="team",
        identifier="IT CareerPilot",
    ),
]

GUIDELINE_SOURCE_NAMES = frozenset(source.name for source in GUIDELINE_SOURCES)
