"""评测简历解析：P1 金标对比、P2 无金标自检、P3 过程指标。

用法：python -m scripts.evaluate_resume_parsing [-v]
对 "resume test/" 下的测试 PDF 跑和 POST /resumes/parse-pdf 一样的流程（pdfminer 提取文本 → LLMResumeParser），
和 "resume test/parsed/" 下同名的金标 JSON 比较。金标由 Claude 按解析规则手工整理（银标），报告里要写明。
LLM 的回答由 ReplayClient 回放（见 scripts/eval_llm_cache.py）：有待答提示时先派子代理作答，再重跑本脚本。
-v 逐份打印漏掉/多出的条目、不一致的字段和疑似编造的数字，用来决定优化哪里。
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from pydantic import ValidationError

from app.core.config import settings
from app.matching.embedding_provider import SentenceTransformerEmbeddingProvider
from app.parsers.text_parser import EMAIL_PATTERN, extract_skills
from app.resume.llm_resume_parser import LLMResumeParser, ResumeParsingError, _cjk_string_paths
from app.resume.resume_parser import pdf_text
from app.resume.rewrite_applier import _numbers
from app.schemas.resume import ParsedResume
from scripts.eval_llm_cache import OUTPUT_ROOT, PendingResponse, ReplayClient

RESUME_DIR = Path(__file__).resolve().parents[1] / "resume test"
GOLD_DIR = RESUME_DIR / "parsed"
# 段落 → (对齐条目用的标识字段, 逐字段精确比较的字段, 长文本字段)
SECTIONS: dict[str, tuple[tuple[str, ...], tuple[str, ...], str | None]] = {
    "experiences": (("company", "title"), ("employment_type", "start_date", "end_date"), "description"),
    "projects": (("title",), ("start_date", "end_date"), "summary"),
    "research": (("title",), ("type", "start_date", "end_date"), "summary"),
    "educations": (("institution", "degree"), ("entry_type", "degree", "start_date", "end_date", "gpa", "ranking"), None),
    "certificates": (("name",), ("issue_date", "score"), None),
    "awards": (("name",), ("date",), None),
    "skill_groups": (("category", "description"), (), "description"),
    "additional_info": (("text",), (), None),
}
# 标识文本相似度达到阈值才算同一条目；开始日期相同另加分（中文简历两边各自翻译，标题措辞常不一样）
MATCH_THRESHOLD = 0.5
DATE_BONUS = 0.3
_URL = re.compile(r"(?:https?://|www\.|github\.com/)[^\s,;)]+", re.IGNORECASE)
_DIGITS = re.compile(r"\d+")


@dataclass
class Comparison:
    # 各项计数，跨简历直接相加即为微平均
    tally: Counter = field(default_factory=Counter)
    # （金标, 解析）长文本对，用来算语义相似度
    texts: list[tuple[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def compare(parsed: dict, gold: dict) -> Comparison:
    result = Comparison()
    tally = result.tally
    for key in ("name", "email", "phone"):
        tally[f"{key}.total"] += 1
        if _same(parsed.get(key), gold.get(key), digits_only=key == "phone"):
            tally[f"{key}.correct"] += 1
        else:
            result.errors.append(f"{key}: 金标 {gold.get(key)!r} / 解析 {parsed.get(key)!r}")
    for key, canon in (("skills", _skill_key), ("languages", _norm)):
        got, want = {canon(s) for s in parsed[key]}, {canon(s) for s in gold[key]}
        tally[f"{key}.tp"] += len(got & want)
        tally[f"{key}.parsed"] += len(got)
        tally[f"{key}.gold"] += len(want)
        if missing := want - got:
            result.errors.append(f"{key} 漏掉: {sorted(missing)}")

    for section, (identity, fields, long_field) in SECTIONS.items():
        gold_entries, parsed_entries = _entries(gold, section), _entries(parsed, section)
        pairs = _align(gold_entries, parsed_entries, identity)
        tally[f"{section}.gold"] += len(gold_entries)
        tally[f"{section}.parsed"] += len(parsed_entries)
        tally[f"{section}.tp"] += len(pairs)
        matched_gold = [id(g) for g, _ in pairs]
        matched_parsed = [id(p) for _, p in pairs]
        result.errors += [f"{section} 漏掉: {_label(g, identity)}" for g in gold_entries if id(g) not in matched_gold]
        result.errors += [f"{section} 多出: {_label(p, identity)}" for p in parsed_entries if id(p) not in matched_parsed]
        for g, p in pairs:
            for name in fields:
                tally[f"{section}.{name}.total"] += 1
                if _same(p.get(name), g.get(name)):
                    tally[f"{section}.{name}.correct"] += 1
                else:
                    result.errors.append(f"{section}.{name} [{_label(g, identity)}]: 金标 {g.get(name)!r} / 解析 {p.get(name)!r}")
            if long_field and g.get(long_field):
                want_facts, got_facts = _facts(g[long_field]), _facts(p.get(long_field) or "")
                tally["facts.total"] += len(want_facts)
                tally["facts.hit"] += len(want_facts & got_facts)
                if lost := want_facts - got_facts:
                    result.errors.append(f"{section}.{long_field} [{_label(g, identity)}] 丢失事实: {sorted(lost)}")
                result.texts.append((g[long_field], p.get(long_field) or ""))
    return result


def self_check(text: str, parsed: dict) -> tuple[Counter, list[str]]:
    """P2：不需要金标，拿 PDF 原文核对解析结果——原文的数字/邮箱/链接是否保留，结果里有没有原文没有的数字。"""
    tally: Counter = Counter()
    leaves = list(_leaves(parsed))
    source = set(_DIGITS.findall(text))
    output_all = {d for _, value in leaves for d in _DIGITS.findall(value)}
    # 日期字段不查编造：英文简历原文的月份是单词（Aug 2022），规范成 2022-08 后会多出 "08"
    output_content = {d for key, value in leaves if not key.endswith("date") for d in _DIGITS.findall(value)}
    invented = sorted(output_content - source, key=int)
    tally["numbers.source"] += len(source)
    tally["numbers.kept"] += len(source & output_all)
    tally["numbers.output"] += len(output_content)
    tally["numbers.invented"] += len(invented)
    dump = _norm(" ".join(value for _, value in leaves))
    for kind, pattern in (("emails", EMAIL_PATTERN), ("urls", _URL)):
        found = {_norm(match).rstrip(".") for match in pattern.findall(text)}
        tally[f"{kind}.source"] += len(found)
        tally[f"{kind}.kept"] += sum(match in dump for match in found)
    return tally, invented


def main(verbose: bool) -> None:
    groups = {"全部": Comparison(), "CN": Comparison(), "EN": Comparison()}
    checks: Counter = Counter()
    process: Counter = Counter()
    pending: list[str] = []
    for gold_path in sorted(GOLD_DIR.glob("*.json")):
        name = gold_path.stem
        text = pdf_text(RESUME_DIR / f"{name}.pdf")
        # 回答来自 Claude Code 里的 haiku 子代理，不是线上的 Gemini，见 scripts/eval_llm_cache.py
        client = ReplayClient()
        try:
            parsed = LLMResumeParser(client=client).parse(text).model_dump()
        except PendingResponse:
            pending.append(name)
            continue
        except ResumeParsingError:
            process["failed"] += 1
            process[f"首次失败:{_first_failure(client)}"] += 1
            print(f"[{name}] 重试后仍解析失败")
            continue
        if len(client.history) == 1:
            process["first_pass"] += 1
        else:
            process["retried"] += 1
            process[f"首次失败:{_first_failure(client)}"] += 1

        gold = ParsedResume.model_validate_json(gold_path.read_text(encoding="utf-8")).model_dump()
        comparison = compare(parsed, gold)
        for group in ("全部", name.rsplit("_", 1)[-1]):
            groups[group].tally += comparison.tally
            groups[group].texts += comparison.texts
        check, invented = self_check(text, parsed)
        checks += check
        if verbose:
            print(f"\n[{name}] 调用 {len(client.history)} 次")
            for error in comparison.errors:
                print(f"  {error}")
            if invented:
                print(f"  原文没有的数字: {invented}")

    if pending:
        print(f"\n{len(pending)} 份有待答提示（{', '.join(pending)}）：派子代理作答 {OUTPUT_ROOT / 'pending'} 后重跑")
    done = process["first_pass"] + process["retried"]
    if not done:
        return
    print(f"\nP3 过程：完成 {done} 份，首次通过 {process['first_pass']}，重试后通过 {process['retried']}，失败 {process['failed']}；"
          f"首次失败原因 {dict((k.split(':', 1)[1], v) for k, v in process.items() if k.startswith('首次失败:'))}")

    similarities = _similarities({group: comparison.texts for group, comparison in groups.items()})
    print("\nP1 金标对比（微平均）" + "".join(f"{group:>10}" for group in groups))
    rows = [("条目 F1（全部段落）", lambda t: _f1(t, [s for s in SECTIONS]))]
    rows += [(f"  {section} F1", lambda t, s=section: _f1(t, [s])) for section in SECTIONS]
    rows += [(f"字段准确率（{len(_field_keys())} 个字段）", lambda t: _ratio(t, _field_keys()))]
    rows += [("长文本事实保留率", lambda t: _safe(t["facts.hit"], t["facts.total"]))]
    rows += [("长文本语义相似度", None)]
    rows += [(f"{key} 准确率", lambda t, k=key: _safe(t[f"{k}.correct"], t[f"{k}.total"])) for key in ("name", "email", "phone")]
    rows += [(f"{key} F1", lambda t, k=key: _f1(t, [k])) for key in ("skills", "languages")]
    for label, metric in rows:
        values = [similarities[group] if metric is None else metric(groups[group].tally) for group in groups]
        print(f"{label:<28}" + "".join(f"{_fmt(value):>10}" for value in values))

    print("\n字段准确率明细（全部）")
    tally = groups["全部"].tally
    for key in _field_keys():
        print(f"  {key:<32} {tally[f'{key}.correct']:>3}/{tally[f'{key}.total']:<3} {_fmt(_safe(tally[f'{key}.correct'], tally[f'{key}.total']))}")

    print("\nP2 无金标自检（全部）")
    print(f"  原文数字保留率   {checks['numbers.kept']}/{checks['numbers.source']} = {_fmt(_safe(checks['numbers.kept'], checks['numbers.source']))}")
    print(f"  疑似编造数字占比 {checks['numbers.invented']}/{checks['numbers.output']} = {_fmt(_safe(checks['numbers.invented'], checks['numbers.output']))}（-v 查看具体数字）")
    for kind in ("emails", "urls"):
        print(f"  {kind} 保留      {checks[f'{kind}.kept']}/{checks[f'{kind}.source']}")


def _first_failure(client: ReplayClient) -> str:
    """第一次回答为什么没通过：JSON/字段校验失败，还是残留中文。"""
    raw = client.response(client.history[0][1])
    try:
        parsed = ParsedResume.model_validate_json(raw)
    except ValidationError:
        return "JSON 或字段不合法"
    return "残留中文" if _cjk_string_paths(parsed.model_dump()) else "其他"


def _align(gold: list[dict], parsed: list[dict], identity: tuple[str, ...]) -> list[tuple[dict, dict]]:
    """按相似度从高到低贪心配对，一条金标最多配一条解析结果。"""
    scored = sorted(
        ((_similarity(g, p, identity), i, j) for i, g in enumerate(gold) for j, p in enumerate(parsed)),
        reverse=True,
    )
    used_gold, used_parsed, pairs = set(), set(), []
    for score, i, j in scored:
        if score < MATCH_THRESHOLD:
            break
        if i not in used_gold and j not in used_parsed:
            used_gold.add(i)
            used_parsed.add(j)
            pairs.append((gold[i], parsed[j]))
    return pairs


def _similarity(a: dict, b: dict, identity: tuple[str, ...]) -> float:
    # 没写名称的专利、软著标识为空，两个空串相似度是 1，会随便配对把类型算错；这时退回按类型配对
    label_a, label_b = (_label(entry, identity) or str(entry.get("type") or "") for entry in (a, b))
    score = SequenceMatcher(None, label_a.casefold(), label_b.casefold()).ratio()
    if identity == ("text",):
        # additional_info 的「标签」是自由文本，同一事实标签可能写法不同，也只比冒号后的值，取较高的
        value_a, value_b = (text.split(":", 1)[-1].strip().casefold() for text in (label_a, label_b))
        score = max(score, SequenceMatcher(None, value_a, value_b).ratio())
    if a.get("start_date") and a.get("start_date") == b.get("start_date"):
        score += DATE_BONUS
    return score


def _entries(resume: dict, section: str) -> list[dict]:
    return [{"text": item} for item in resume[section]] if section == "additional_info" else resume[section]


def _label(entry: dict, identity: tuple[str, ...]) -> str:
    return " ".join(str(entry.get(key) or "") for key in identity).strip()[:80]


def _facts(text: str) -> set[str]:
    # 数字和技能不受翻译措辞影响，中英文简历都能比
    return {f"#{number}" for number in _numbers(text)} | {f"@{skill}" for skill in extract_skills(text)}


def _skill_key(skill: str) -> str:
    # 词表认得的技能按标准名比（K8s = Kubernetes），认不得的按原文比
    return "|".join(extract_skills(skill)) or _norm(skill)


def _same(a: object, b: object, digits_only: bool = False) -> bool:
    a, b = _norm(a or ""), _norm(b or "")
    if digits_only:
        a, b = "".join(_DIGITS.findall(a)), "".join(_DIGITS.findall(b))
    return a == b


def _leaves(value: object, key: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(value, dict):
        for child_key, child in value.items():
            yield from _leaves(child, child_key)
    elif isinstance(value, list):
        for item in value:
            yield from _leaves(item, key)
    elif value is not None:
        yield key, str(value)


def _similarities(texts: dict[str, list[tuple[str, str]]]) -> dict[str, float | None]:
    provider = SentenceTransformerEmbeddingProvider(settings.resume_guideline_embedding_model)
    result: dict[str, float | None] = {}
    for group, pairs in texts.items():
        vectors = provider.encode([text for pair in pairs for text in pair])
        # 向量已归一化，点积即余弦相似度
        scores = [sum(x * y for x, y in zip(vectors[i], vectors[i + 1])) for i in range(0, len(vectors), 2)]
        result[group] = sum(scores) / len(scores) if scores else None
    return result


def _field_keys() -> list[str]:
    return [f"{section}.{name}" for section, (_, fields, _) in SECTIONS.items() for name in fields]


def _f1(tally: Counter, keys: list[str]) -> float | None:
    tp = sum(tally[f"{key}.tp"] for key in keys)
    parsed = sum(tally[f"{key}.parsed"] for key in keys)
    gold = sum(tally[f"{key}.gold"] for key in keys)
    return _safe(2 * tp, parsed + gold)


def _ratio(tally: Counter, keys: list[str]) -> float | None:
    return _safe(sum(tally[f"{key}.correct"] for key in keys), sum(tally[f"{key}.total"] for key in keys))


def _safe(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.3f}"


def _norm(text: object) -> str:
    return " ".join(str(text).split()).casefold()


if __name__ == "__main__":
    main(verbose="-v" in sys.argv[1:])
