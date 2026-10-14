import json
from pathlib import Path

from app.knowledge.mind_ontology import MindKnowledgeGraph, get_mind_knowledge_graph
from app.main import app


def test_packaged_mind_knowledge_graph_loads() -> None:
    graph = get_mind_knowledge_graph()

    assert graph.stats.skill_count == 3342
    assert graph.stats.concept_count == 974
    assert graph.stats.relation_count > 10000
    assert app.state.mind_knowledge_graph is graph


def test_skill_and_concept_aliases_resolve() -> None:
    graph = get_mind_knowledge_graph()

    react = graph.get_skill("react.js")
    logging = graph.get_concept("system logging")

    assert react is not None
    assert react.name == "React"
    assert logging is not None
    assert logging.name == "Logging"


def test_agent_skill_aliases_resolve() -> None:
    graph = get_mind_knowledge_graph()

    expected = {
        "AI Agents": "Agentic AI",
        "Retrieval-Augmented Generation": "RAG",
        "Model Context Protocol": "MCP",
        "Function Calling": "Tool Calling",
        "Guardrails": "AI Guardrails",
        "LLM": "Large Language Models",
    }

    assert {
        alias: graph.get_skill(alias).name if graph.get_skill(alias) else None
        for alias in expected
    } == expected


def test_skill_relationships_are_available_without_running_matching() -> None:
    graph = get_mind_knowledge_graph()

    implied_skills = graph.related_skills("Next.js", "impliesKnowingSkills")

    assert "React" in implied_skills
    assert "JavaScript" in implied_skills


def test_ambiguous_concept_alias_keeps_all_candidates() -> None:
    graph = get_mind_knowledge_graph()

    candidates = graph.get_concepts("data caching")

    assert {concept.name for concept in candidates} == {
        "Caching",
        "Data Fetching and Caching",
    }
    assert graph.get_concept("data caching") is None
    assert graph.get_concept("Caching") is not None


def test_loader_reports_missing_files(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.json"

    try:
        MindKnowledgeGraph.from_files(missing_path, missing_path)
    except FileNotFoundError as error:
        assert "找不到 MIND 数据文件" in str(error)
    else:
        raise AssertionError("缺少数据文件时应抛出 FileNotFoundError")


def test_loader_rejects_non_array_payload(tmp_path: Path) -> None:
    skills_path = tmp_path / "skills.json"
    concepts_path = tmp_path / "concepts.json"
    skills_path.write_text(json.dumps({"name": "Python"}), encoding="utf-8")
    concepts_path.write_text("[]", encoding="utf-8")

    try:
        MindKnowledgeGraph.from_files(skills_path, concepts_path)
    except ValueError as error:
        assert "顶层必须是数组" in str(error)
    else:
        raise AssertionError("顶层不是数组时应抛出 ValueError")
