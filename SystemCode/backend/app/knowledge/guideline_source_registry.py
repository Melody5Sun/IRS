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
    GuidelineSource(
        name="javaguide",
        provider="github",
        identifier="Snailclimb/JavaGuide",
        url="https://github.com/Snailclimb/JavaGuide",
        license="Apache-2.0",
        retrieved_at=_RETRIEVED,
    ),
    # 以下网页/PDF 资料没有开源许可，只提炼写作原则，示例全部由团队自写，不摘录原文
    GuidelineSource(
        name="uf-technical-resume-guide",
        provider="university",
        identifier="University of Florida Career Connections Center",
        url="https://cdn.uconnectlabs.com/wp-content/uploads/sites/244/2025/09/Technical-Resume-Guide.pdf.pdf",
        retrieved_at=_RETRIEVED,
    ),
    GuidelineSource(
        name="google-xyz-formula",
        provider="web",
        identifier="Laszlo Bock (Google) X-Y-Z formula",
        url="https://www.businessinsider.in/google-hr-boss-says-this-is-the-key-to-a-perfect-resume/amp_articleshow/43924179.cms",
        retrieved_at=_RETRIEVED,
    ),
    GuidelineSource(
        name="datadriven-io",
        provider="web",
        identifier="DataDriven Data Engineer Resume Guide",
        url="https://datadriven.io/data-engineer-resume",
        retrieved_at=_RETRIEVED,
    ),
    GuidelineSource(
        name="weekday-works",
        provider="web",
        identifier="Weekday Machine Learning Engineer Resume Guide",
        url="https://www.weekday.works/post/machine-learning-engineer-resume-examples-guide",
        retrieved_at=_RETRIEVED,
    ),
    GuidelineSource(
        name="cyberdefenders",
        provider="web",
        identifier="CyberDefenders SOC Analyst Resume Guide",
        url="https://cyberdefenders.org/blog/how-to-build-a-resume-for-soc-analyst/",
        retrieved_at=_RETRIEVED,
    ),
    GuidelineSource(
        name="wiz-academy",
        provider="web",
        identifier="Wiz Academy Site Reliability Engineer Resume Example",
        url="https://www.wiz.io/academy/cloud-careers/site-reliability-engineer-resume-example",
        retrieved_at=_RETRIEVED,
    ),
    GuidelineSource(
        name="resumegeni",
        provider="web",
        identifier="ResumeGeni role-specific resume guides",
        url="https://resumegeni.com/resume-guides",
        retrieved_at=_RETRIEVED,
    ),
    GuidelineSource(
        name="resumementor",
        provider="web",
        identifier="ResumeMentor IT help desk resume examples",
        url="https://resumementor.com/blog/it-help-desk-resume-examples/",
        retrieved_at=_RETRIEVED,
    ),
    GuidelineSource(
        name="csusb-career-center",
        provider="university",
        identifier="CSUSB Career Center research project experience template",
        url="https://www.csusb.edu/sites/default/files/Incorporating Research Project Experience_CC Template.docx.pdf",
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
