import pytest

from app.parsers.text_parser import extract_skills


@pytest.mark.parametrize(
    ("text", "skill", "expected"),
    [
        # ReAct 是 Agent 推理范式，不是 React 框架
        ("Built agents with ReAct and Plan-and-Execute", "react", False),
        ("Built the dashboard with React and TypeScript", "react", True),
        ("react", "react", True),
        # 夹在英文单词之间的小写 go 是动词
        ("Let us go to the next step", "go", False),
        ("Services written in Go and Python", "go", True),
        ("Skills: python, go, java", "go", True),
        ("go", "go", True),
        ("Golang microservices", "go", True),
    ],
)
def test_ambiguous_aliases(text: str, skill: str, expected: bool) -> None:
    assert (skill in extract_skills(text)) is expected
