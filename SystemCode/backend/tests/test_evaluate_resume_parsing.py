from app.schemas.resume import ParsedResume
from scripts.evaluate_resume_parsing import GOLD_DIR, _f1, _ratio, _field_keys, compare


def _gold() -> dict:
    path = GOLD_DIR / "resume_test_AgentDeveloper_EN.json"
    return ParsedResume.model_validate_json(path.read_text(encoding="utf-8")).model_dump()


def test_gold_against_itself_is_perfect() -> None:
    result = compare(_gold(), _gold())
    assert result.errors == []
    assert _f1(result.tally, ["experiences", "projects", "skills"]) == 1.0
    assert _ratio(result.tally, _field_keys()) == 1.0
    assert result.tally["facts.hit"] == result.tally["facts.total"] > 0


def test_untitled_research_entries_pair_by_type() -> None:
    gold = _gold()
    untitled = {"title": "", "institution": None, "summary": "", "start_date": None, "end_date": None}
    gold["research"] = [{**untitled, "type": "patent"}, {**untitled, "type": "software_copyright"}]
    parsed = {**gold, "research": list(reversed(gold["research"]))}
    tally = compare(parsed, gold).tally
    assert tally["research.type.correct"] == tally["research.type.total"] == 2


def test_missing_entry_and_wrong_date_are_counted() -> None:
    parsed = _gold()
    parsed["experiences"] = parsed["experiences"][:1]
    parsed["projects"][0]["start_date"] = "1999-01"
    tally = compare(parsed, _gold()).tally
    assert (tally["experiences.tp"], tally["experiences.gold"]) == (1, 2)
    assert tally["projects.start_date.correct"] == 0
