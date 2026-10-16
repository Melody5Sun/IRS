import pytest

from app.resume.issue_detector import detect_issues, line_issues
from app.schemas.match import DirectSkillMatch, SkillScoreResponse
from app.schemas.resume import Experience, Project, ResumeDocument, SkillGroup


@pytest.mark.parametrize(
    ("line", "issue", "expected"),
    [
        ("Responsible for building REST APIs for 3 teams, reducing latency", "weak_action_verb", True),
        ("Built REST APIs for 3 teams, reducing latency", "weak_action_verb", False),
        ("The dashboard was built with React for 3 teams, reducing toil", "passive_voice", True),
        ("Built the dashboard with React for 3 teams, reducing toil", "passive_voice", False),
        ("Leveraged cutting-edge AI to cut costs by 20%", "buzzword", True),
        ("Used PyTorch to cut costs by 20%", "buzzword", False),
        ("Built REST APIs with FastAPI, reducing latency", "missing_quantification", True),
        ("Built 12 REST APIs with FastAPI, reducing latency", "missing_quantification", False),
        ("Built 12 REST APIs with FastAPI for the team", "missing_outcome", True),
        ("Built 12 REST APIs with FastAPI, reducing latency", "missing_outcome", False),
        # 「小标题: 内容」写法：去掉小标题后再看行首
        ("Intent Recognition: Participated in designing a routing chain for 3 teams, reducing toil", "weak_action_verb", True),
        ("Implemented dynamic batching for 3 services, reducing latency", "buzzword", False),
        ("Responsibilities: as project owner, responsible for delivering 3 modules, reducing toil", "weak_action_verb", True),
        ("Combined ReAct and CoT for 3 agents, significantly improving accuracy", "buzzword", True),
        # 型号版本和结构描述里的数字不算量化
        ("Used Qwen3-8b and a three-layer cache to cut latency", "missing_quantification", True),
        ("Served 1000 users with a three-layer cache, cutting latency", "missing_quantification", False),
        ("Used Redis Lua scripts for 3 services, ensuring no overselling", "missing_outcome", False),
    ],
)
def test_line_rules(line: str, issue: str, expected: bool) -> None:
    assert (issue in line_issues(line)) is expected


def test_one_line_can_report_several_issues_and_short_lines_are_skipped() -> None:
    issues = line_issues("- The login page was designed by me")
    assert {"passive_voice", "missing_quantification", "missing_outcome"} <= set(issues)
    assert line_issues("Tech: Python") == []
    # 项目名/技术栈这类标题行不是成果要点，不报缺量化/缺结果
    assert line_issues("Tech stack: Python, FastAPI, Redis, MySQL and Docker") == []
    assert line_issues("Project: Smart Asset Disposal Agent Platform built for law firms") == []
    assert line_issues("Technical Department. Tech stack: TypeScript, NestJS, PostgreSQL, Redis and SSE") == []
    # 关键词/论文署名/主题标签行也不是成果要点
    assert line_issues("Keywords: MLLM, Qwen3-VL, dynamic resolution, M-RoPE, DeepStack, SFT") == []
    assert line_issues("First Author, CCF-A, ICCV-25") == []
    assert line_issues("Video sentiment analysis, temporal modeling, explainability", "research") == []
    # 主题标签行只在研究块里跳过：经历/项目里逗号分隔的短要点照常检测
    for bullet in ("Built REST APIs, wrote unit tests, deployed services", "Led backend team, cut costs, shipped features"):
        assert "missing_quantification" in line_issues(bullet, "experience")
        assert line_issues(bullet, "research") == []
    # 长的研究摘要顺带提到 first author 仍要检测
    summary = "A cache method was proposed for diffusion transformers to reduce repeated computation; I am the first author of the paper"
    assert "passive_voice" in line_issues(summary)


def test_block_issues_from_scores() -> None:
    resume = ResumeDocument(
        experiences=[Experience(company="Acme", title="Intern", description="Built APIs with Python for 3 teams, reducing toil")],
        projects=[Project(title="Blog", summary="A personal blog about travel and food photos")],
        skills=["Python", "Docker"],
        skill_groups=[SkillGroup(category="Tools", description="Python, Docker")],
    )
    skill_score = SkillScoreResponse(
        required_skills_calculable=True, preferred_skills_available=False,
        required_direct_coverage=100, required_direct_points=20, required_graph_coverage=0, required_graph_points=0,
        preferred_direct_coverage=0, preferred_graph_coverage=0, preferred_skill_coverage=0, preferred_bonus=0,
        partial_score=20,
        direct_required_matches=[
            DirectSkillMatch(jd_skill="python", candidate_skill="python"),
            DirectSkillMatch(jd_skill="docker", candidate_skill="docker"),
        ],
    )
    alignments = {("experience", 0): (0.5, "Build APIs"), ("project", 0): (0.1, "Build APIs")}

    experience, project, skills = detect_issues(resume, alignments, skill_score, 0.35, 0.75)

    assert experience.block_issues == ["weak_jd_alignment"]
    assert experience.jd_responsibility == "Build APIs"
    assert project.block_issues == ["unclear_tech_stack", "irrelevant_content"]
    # python 在经历里出现过，docker 只在技能栏里
    assert skills.unsurfaced_skills == ["docker"]
    # 技能栏固定带 irrelevant_content（按 JD 精简排序），检测到未支撑技能时再加 unsurfaced_skill
    assert skills.block_issues == ["irrelevant_content", "unsurfaced_skill"]
