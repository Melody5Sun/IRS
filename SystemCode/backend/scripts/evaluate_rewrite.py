"""评测简历改写：W1 问题检测器 P/R、W3 端到端前后对比、W5 无 RAG 消融，可导出 W4 人工评分表。

用法：python -m scripts.evaluate_rewrite [-v] [--export] | --score
- W1 不读库：issue_detector_cases.json 里人工标注的要点行（标注规则见文件里的 guide，银标），按 split 分别出数：
  dev = 调检测器正则时看过的旧 10 份简历，heldout = 改完正则后新加的简历，以 heldout 为准
- W3/W5 读库（只读）：rewrite_eval_pairs.json 里的（简历上传记录, 岗位）组，各跑一遍完整改写链路；
  W5 把知识库检索换成空结果，其余不变。LLM 回答由 ReplayClient 回放（见 scripts/eval_llm_cache.py），
  有待答提示时先派子代理作答再重跑，直到没有待答
- --export 导出 W4 评分表（两组的改动混在一起、隐去分组，供人工 1–5 分盲评）和被拒改动审阅表到 eval_outputs/
- --score 读填好分的评分表 + w4_key.json，按组输出 4 个维度均分，以及被拒改动审阅表的判定统计
"""

from __future__ import annotations

import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

from app.core.config import settings
from app.matching.embedding_provider import SentenceTransformerEmbeddingProvider
from app.repositories.job_semantic_repository import JobSemanticRepository
from app.repositories.resume_history_repository import ResumeHistoryRepository
from app.resume.issue_detector import jd_alignments, line_issues
from app.resume.removed_skills import groups_text
from app.resume.resume_rewriter import (
    LIST_ATTR,
    SYSTEM_PROMPT,
    TEXT_FIELD,
    ResumeRewriteError,
    ResumeRewriter,
    change_problems,
)
from app.resume.rewrite_applier import as_text, placeholders
from app.schemas.match import ResponsibilityScoreRequest, SkillScoreRequest
from app.schemas.resume import ResumeDocument
from app.schemas.resume_rewrite import ResumeChange, ResumeChangeSet, ResumeRewriteResult
from app.services.responsibility_match_service import ResponsibilityMatchService
from app.services.skill_match_service import SkillMatchService
from scripts.eval_llm_cache import OUTPUT_ROOT, PendingResponse, ReplayClient

HERE = Path(__file__).resolve().parent
CASES_PATH = HERE / "issue_detector_cases.json"
PAIRS_PATH = HERE / "rewrite_eval_pairs.json"
LINE_ISSUES = ("weak_action_verb", "passive_voice", "buzzword", "missing_quantification", "missing_outcome")
ARMS = {"rag": "有 RAG", "no_rag": "无 RAG"}
# W4 评分表每组抽多少个改动；固定种子保证每次导出同一批
RATING_SAMPLE = {"rag": 20, "no_rag": 10}
RATING_DIMENSIONS = ("事实一致(1-5)", "比原文好(1-5)", "贴合JD(1-5)", "理由正确(1-5)")


def w1_detector(verbose: bool) -> None:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    for split in ("dev", "heldout"):
        detector_report([case for case in cases if case.get("split", "dev") == split], split, verbose)


def detector_report(cases: list[dict], split: str, verbose: bool) -> dict[str, Counter]:
    counts = {issue: Counter() for issue in LINE_ISSUES}
    mistakes: list[str] = []
    for case in cases:
        got, want = set(line_issues(case["text"], case["section"])), set(case["issues"])
        for issue in LINE_ISSUES:
            if issue in got and issue in want:
                counts[issue]["tp"] += 1
            elif issue in got:
                counts[issue]["fp"] += 1
                mistakes.append(f"  误报 {issue}: {case['text'][:110]}")
            elif issue in want:
                counts[issue]["fn"] += 1
                mistakes.append(f"  漏报 {issue}: {case['text'][:110]}")
    print(f"\nW1 问题检测器 {split}（{len(cases)} 行人工标注）")
    print(f"{'问题类型':<24}{'标注':>5}{'检出':>5}{'P':>8}{'R':>8}{'F1':>8}")
    for issue, c in counts.items():
        p, r = _safe(c["tp"], c["tp"] + c["fp"]), _safe(c["tp"], c["tp"] + c["fn"])
        f1 = _safe(2 * c["tp"], 2 * c["tp"] + c["fp"] + c["fn"])
        print(f"{issue:<24}{c['tp'] + c['fn']:>5}{c['tp'] + c['fp']:>5}{_fmt(p):>8}{_fmt(r):>8}{_fmt(f1):>8}")
    if verbose:
        print("\n".join(mistakes))
    return counts


class _NoGuidelines:
    """W5 消融：知识库检索一律返回空，其余流程不变。"""

    def search(self, *args, **kwargs) -> list:
        return []


def run_arms() -> tuple[dict[str, list[dict]], list[str]]:
    pairs = json.loads(PAIRS_PATH.read_text(encoding="utf-8"))
    semantic = JobSemanticRepository()
    embedding_provider = SentenceTransformerEmbeddingProvider(settings.resume_guideline_embedding_model)
    # 只读：JD 职责缺向量时现算但不回写
    responsibility_service = ResponsibilityMatchService(persist=False)
    skill_service = SkillMatchService()
    records: dict[str, list[dict]] = {arm: [] for arm in ARMS}
    pending: list[str] = []
    for pair in pairs:
        upload = ResumeHistoryRepository().get(pair["upload_id"])
        resume = ResumeDocument.model_validate(upload.resume.model_dump(exclude={"about"}))
        job = semantic.get_analyzed_job(pair["job_id"])
        role_categories = semantic.load_role_categories(pair["job_id"])
        for arm in ARMS:
            # 回答来自 Claude Code 里的 haiku 子代理，不是线上的 Gemini，见 scripts/eval_llm_cache.py
            client = ReplayClient()
            rewriter = ResumeRewriter(
                client=client,
                guideline_repository=_NoGuidelines() if arm == "no_rag" else None,
                embedding_provider=embedding_provider,
                responsibility_service=responsibility_service,
                skill_service=skill_service,
            )
            record = {"pair": pair, "resume": resume, "job": job, "client": client, "result": None}
            try:
                record["result"] = rewriter.rewrite(resume, job, role_categories)
            except PendingResponse:
                pending.append(f"{arm}:{pair['upload_id']}x{pair['job_id']}")
                continue
            except ResumeRewriteError:
                pass
            records[arm].append(record)
    for arm_records in records.values():
        for record in arm_records:
            if record["result"] is not None:
                record["scores"] = {
                    label: _scores(document, record["job"], responsibility_service, skill_service)
                    for label, document in (("before", record["resume"]), ("after", record["result"].rewritten_resume))
                }
                record["alignment"] = {
                    label: jd_alignments(responsibility_service, document, record["job"])
                    for label, document in (("before", record["resume"]), ("after", record["result"].rewritten_resume))
                }
    return records, pending


def summarize(records: list[dict]) -> dict[str, str]:
    done = [r for r in records if r["result"] is not None]
    tally: Counter = Counter()
    rejected_reasons: Counter = Counter()
    issues_before: Counter = Counter()
    issues_after: Counter = Counter()
    for record in done:
        result: ResumeRewriteResult = record["result"]
        calls = [key for system, key in record["client"].history if system == SYSTEM_PROMPT]
        tally["retried"] += len(calls) > 1
        changes = [change for block in result.blocks for change in block.changes]
        tally["applied"] += len(changes)
        tally["rejected"] += len(result.rejected_changes)
        rejected_reasons.update(item.reason for item in result.rejected_changes)
        tally["rewritten_blocks"] += sum(block.status == "rewritten" for block in result.blocks)
        tally["needs_input_blocks"] += sum(block.status == "needs_input" for block in result.blocks)
        tally["questions"] += sum(len(block.pending_inputs) for block in result.blocks)
        tally["deletions"] += len(result.deletion_suggestions)
        tally["rejected_deletions"] += len(result.rejected_deletions)

        kept_reasons = [
            reason
            for item in [*changes, *(r.change for r in result.rejected_changes),
                         *result.deletion_suggestions, *(r.deletion for r in result.rejected_deletions)]
            for reason in item.reasons
        ]
        raw = ResumeChangeSet.model_validate_json(record["client"].response(calls[-1]))
        raw_keys = sum(len(reason.guideline_keys) for item in [*raw.changes, *raw.deletions] for reason in item.reasons)
        tally["reasons"] += len(kept_reasons)
        tally["reasons_without_key"] += sum(not reason.guideline_keys for reason in kept_reasons)
        tally["dropped_keys"] += raw_keys - sum(len(reason.guideline_keys) for reason in kept_reasons)
        tally["raw_keys"] += raw_keys

        # 问题解决率只看直接写进改写稿的文本改动（待补充的草稿还没定稿）
        for change in changes:
            if change.field in TEXT_FIELD.values() and not change.needs_user_input:
                before = getattr(getattr(record["resume"], LIST_ATTR[change.section])[change.index], change.field)
                issues_before.update(_issues(before, change.section))
                issues_after.update(_issues(change.value, change.section))
        for name in ("responsibility", "skill"):
            tally[f"{name}_delta"] += record["scores"]["after"][name] - record["scores"]["before"][name]

        for change in changes:
            new = len(placeholders(as_text(change.value)) - placeholders(as_text(change.original)))
            tally["placeholders"] += new
            tally["max_placeholders"] = max(tally["max_placeholders"], new)
            kinds = Counter(kind for kind, _ in change_problems(change, record["resume"], record["job"]))
            tally["over_placeholder_limit"] += bool(kinds["too_many_placeholders"])
            tally["unsupported_reasons"] += kinds["unsupported_reason"]
            tally["reasons_with_jd"] += sum(bool(reason.jd_responsibility) for reason in change.reasons)
        # 只看改写稿里文本确实变了的块：与它最相近的 JD 职责的相似度变化
        before, after = record["alignment"]["before"], record["alignment"]["after"]
        for key in before.keys() & after.keys():
            if before[key][0] != after[key][0]:
                tally["aligned_blocks"] += 1
                tally["alignment_delta"] += after[key][0] - before[key][0]

    n = len(done)
    proposed = tally["applied"] + tally["rejected"]
    summary = {
        "完成组数（失败 = 两次输出都不合法）": f"{sum(r['result'] is not None for r in records)}/{len(records)}",
        "重试组数": str(tally["retried"]),
        "改动：通过 / 被拒": f"{tally['applied']} / {tally['rejected']}（拒绝率 {_fmt(_safe(tally['rejected'], proposed))}）",
        "被拒原因": ", ".join(f"{reason} {count}" for reason, count in rejected_reasons.most_common()) or "-",
        "直接改写块 / 待补充块 / 问询数": f"{tally['rewritten_blocks']} / {tally['needs_input_blocks']} / {tally['questions']}",
        "删除建议：通过 / 被拒": f"{tally['deletions']} / {tally['rejected_deletions']}",
        "理由数 / 无引用的理由": f"{tally['reasons']} / {tally['reasons_without_key']}（{_fmt(_safe(tally['reasons_without_key'], tally['reasons']))}）",
        "错配引用被丢弃 / 原始引用": f"{tally['dropped_keys']} / {tally['raw_keys']}",
        "行级问题 改前 → 改后": f"{sum(issues_before.values())} → {sum(issues_after.values())}",
    }
    for issue in LINE_ISSUES:
        summary[f"  {issue}"] = f"{issues_before[issue]} → {issues_after[issue]}"
    applied = tally["applied"]
    summary["新增占位 / 改动（最多）"] = f"{_fmt(_safe(tally['placeholders'], applied))}（{tally['max_placeholders']}）"
    summary["占位超上限的改动"] = str(tally["over_placeholder_limit"])
    summary["理由提到原文/改写/JD 都没有的技能"] = str(tally["unsupported_reasons"])
    summary["理由标了对齐的 JD 职责"] = f"{tally['reasons_with_jd']}/{tally['reasons']}"
    summary["改写块与对齐职责相似度 Δ 均值"] = (
        f"{tally['alignment_delta'] / tally['aligned_blocks']:+.3f}（{tally['aligned_blocks']} 块）" if tally["aligned_blocks"] else "-"
    )
    summary["职责契合分 Δ 均值（满分 30）"] = f"{tally['responsibility_delta'] / n:+.2f}" if n else "-"
    summary["技能分 Δ 均值（满分 65）"] = f"{tally['skill_delta'] / n:+.2f}" if n else "-"
    return summary


def export(records: dict[str, list[dict]]) -> None:
    rows = {arm: [] for arm in ARMS}
    for arm, arm_records in records.items():
        for record in arm_records:
            if record["result"] is None:
                continue
            for block in record["result"].blocks:
                for change in block.changes:
                    rows[arm].append(_rating_row(record, block.heading, change))
    rng = random.Random(0)
    sample = [(arm, row) for arm, size in RATING_SAMPLE.items() for row in rng.sample(rows[arm], min(size, len(rows[arm])))]
    rng.shuffle(sample)
    sheet = OUTPUT_ROOT / "w4_rating_sheet.csv"
    with sheet.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["编号", "岗位", "JD职责", "块", "原文", "改写", "改写理由", "含待补充占位",
                         "事实一致(1-5)", "比原文好(1-5)", "贴合JD(1-5)", "理由正确(1-5)", "备注"])
        for number, (_, row) in enumerate(sample, start=1):
            writer.writerow([f"R{number:02d}", *row, "", "", "", "", ""])
    key = {f"R{number:02d}": arm for number, (arm, _) in enumerate(sample, start=1)}
    (OUTPUT_ROOT / "w4_key.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")

    review = OUTPUT_ROOT / "rejected_changes_review.csv"
    with review.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["组", "岗位", "拒绝原因", "说明", "原文", "改写", "判定(真编造/误拒)", "备注"])
        for arm, arm_records in records.items():
            for record in arm_records:
                for item in record["result"].rejected_changes if record["result"] else []:
                    writer.writerow([ARMS[arm], record["job"].title, item.reason, item.detail,
                                     _text(item.change.original), _text(item.change.value), "", ""])
    print(f"\n已导出：{sheet}（{len(sample)} 行，分组见 w4_key.json）、{review}")


def score() -> None:
    key = json.loads((OUTPUT_ROOT / "w4_key.json").read_text(encoding="utf-8"))
    with (OUTPUT_ROOT / "w4_rating_sheet.csv").open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    print(f"W4 盲评均分（{len(rows)} 行）" + "".join(f"{name:>16}" for name in RATING_DIMENSIONS))
    for arm, label in ARMS.items():
        arm_rows = [row for row in rows if key[row["编号"]] == arm]
        means = [_safe(sum(float(row[name]) for row in arm_rows if row[name]), sum(bool(row[name]) for row in arm_rows))
                 for name in RATING_DIMENSIONS]
        print(f"{label}（{len(arm_rows)} 行）".ljust(16) + "".join(f"{_fmt(mean):>16}" for mean in means))
    with (OUTPUT_ROOT / "rejected_changes_review.csv").open(encoding="utf-8-sig", newline="") as file:
        verdicts = Counter((row["组"], row["判定(真编造/误拒)"] or "未判定") for row in csv.DictReader(file))
    print("被拒改动判定：" + "，".join(f"{arm} {verdict} {count}" for (arm, verdict), count in sorted(verdicts.items())))


def _rating_row(record: dict, heading: str, change: ResumeChange) -> list[str]:
    reasons = "\n".join(reason.explanation.zh for reason in change.reasons)
    # 带上 JD 职责原文，盲评才能判断「贴合JD」
    return [record["job"].title, "\n".join(record["job"].responsibilities), heading, _text(change.original), _text(change.value), reasons,
            "是" if change.needs_user_input else "否"]


def _text(value: object) -> str:
    if isinstance(value, list) and value and not isinstance(value[0], str):
        return groups_text(value)
    return "\n".join(value) if isinstance(value, list) else str(value)


def _issues(text: str, section: str) -> Counter:
    return Counter(issue for line in text.split("\n") for issue in line_issues(line, section))


def _scores(resume: ResumeDocument, job, responsibility_service, skill_service) -> dict[str, float]:
    return {
        "responsibility": responsibility_service.score(ResponsibilityScoreRequest(candidate=resume, job=job)).responsibility_points,
        "skill": skill_service.score(SkillScoreRequest(candidate=resume, job=job)).partial_score,
    }


def _safe(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.3f}"


def main(verbose: bool, export_sheets: bool) -> None:
    w1_detector(verbose)
    records, pending = run_arms()
    if pending:
        print(f"\n{len(pending)} 组有待答提示（{', '.join(pending)}）：派子代理作答 {OUTPUT_ROOT / 'pending'} 后重跑")
        return
    summaries = {arm: summarize(arm_records) for arm, arm_records in records.items()}
    print(f"\nW3 端到端 / W5 消融（{len(records['rag'])} 组简历 × 岗位）" + "".join(f"{label:>16}" for label in ARMS.values()))
    for metric in summaries["rag"]:
        print(f"{metric:<36}" + "".join(f"{summaries[arm][metric]:>16}" for arm in ARMS))
    if export_sheets:
        export(records)


if __name__ == "__main__":
    if "--score" in sys.argv[1:]:
        score()
    else:
        main(verbose="-v" in sys.argv[1:], export_sheets="--export" in sys.argv[1:])
