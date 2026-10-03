"""评测简历改写的检索覆盖率：检测出的每个（块, 问题类型），检索结果里有没有带该标签的知识库条目。

用法：python -m scripts.evaluate_rewrite_retrieval <upload_id> <job_id> [<upload_id> <job_id> ...]
跑真实的问题检测和检索（读库，不调 LLM、不写库）；upload_id 是 resume_uploads 的记录，job_id 是已分析的岗位。
"""

from __future__ import annotations

import sys
from collections import Counter

from app.repositories.job_semantic_repository import JobSemanticRepository
from app.repositories.resume_history_repository import ResumeHistoryRepository
from app.resume.issue_detector import detect_issues, jd_alignments
from app.resume.resume_rewriter import ResumeRewriter
from app.schemas.match import SkillScoreRequest
from app.schemas.resume import ResumeDocument


def main(pairs: list[tuple[int, int]]) -> None:
    rewriter = ResumeRewriter()
    # 只读：JD 职责缺向量时现算但不回写
    rewriter.responsibility_service.repository = None
    semantic = JobSemanticRepository()
    detected, covered = Counter(), Counter()
    distinct: dict[str, set[str]] = {}
    similarities: list[float] = []
    for upload_id, job_id in pairs:
        upload = ResumeHistoryRepository().get(upload_id)
        job = semantic.get_analyzed_job(job_id)
        if upload is None or job is None:
            print(f"[{upload_id} x {job_id}] 简历或岗位不存在，跳过")
            continue
        resume = ResumeDocument.model_validate(upload.resume.model_dump(exclude={"about"}))
        scorer = rewriter.responsibility_service.scorer
        blocks = detect_issues(
            resume,
            jd_alignments(rewriter.responsibility_service, resume, job),
            rewriter.skill_service.score(SkillScoreRequest(candidate=resume, job=job)),
            scorer.similarity_floor,
            scorer.similarity_full,
        )
        blocks = [b for b in blocks if (b.has_issues if b.section != "skills" else bool(resume.skill_groups))]
        retrieved = rewriter._retrieve(blocks, semantic.load_role_categories(job_id))
        for block in blocks:
            by_issue = retrieved[(block.section, block.index)]
            issues = {i for line in block.lines for i in line.issue_types} | set(block.block_issues)
            for issue in issues:
                matches = by_issue.get(issue, [])
                detected[issue] += 1
                covered[issue] += any(issue in m.guideline.issue_types for m in matches)
                distinct.setdefault(issue, set()).update(m.guideline.key for m in matches)
                similarities += [m.similarity for m in matches[:1]]
        print(f"[{upload_id} x {job_id}] {job.title[:60]}：{len(blocks)} 块")

    total = sum(detected.values())
    if not total:
        return
    print(f"\n覆盖率 {sum(covered.values())}/{total} = {sum(covered.values()) / total:.2f}"
          f"  平均最高相似度 {sum(similarities) / len(similarities):.3f}")
    for issue, count in detected.most_common():
        print(f"  {issue:24s} {covered[issue]:3d}/{count:<3d} 用到 {len(distinct[issue])} 条不同条目")


if __name__ == "__main__":
    args = [int(value) for value in sys.argv[1:]]
    if not args or len(args) % 2:
        sys.exit(__doc__)
    main(list(zip(args[::2], args[1::2])))
