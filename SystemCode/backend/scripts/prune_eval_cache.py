"""清理回放缓存：重跑解析和改写评测，删掉 responses/ 里这次没被用到的回答。

用法：python -m scripts.prune_eval_cache [--apply]
- 不加 --apply 只列出会删的文件；加了才删
- 提示一改（prompt、检测器、检索、JD 数据），旧回答就再也不会命中（见 scripts/eval_llm_cache.py），
  留着只会让人分不清哪些是当前结果；删掉的回答仍可从 git 历史恢复
- 任何一个评测还有待答时不删：待答作答后可能用到的回答此时还看不出来
"""

from __future__ import annotations

import sys

from scripts import evaluate_resume_parsing, evaluate_rewrite
from scripts.eval_llm_cache import OUTPUT_ROOT, ReplayClient

used: set[str] = set()
_complete = ReplayClient.complete


def _recording_complete(self: ReplayClient, *, system_prompt: str, user_prompt: str) -> str:
    try:
        return _complete(self, system_prompt=system_prompt, user_prompt=user_prompt)
    finally:
        used.add(self.history[-1][1])


def main(apply: bool) -> None:
    ReplayClient.complete = _recording_complete
    evaluate_resume_parsing.main(verbose=False)
    evaluate_rewrite.main(verbose=False, export_sheets=False)
    pending = sorted((OUTPUT_ROOT / "pending").glob("*.txt"))
    if pending:
        print(f"\n还有 {len(pending)} 个待答，先作答再清理，本次不删")
        return
    stale = sorted(path for path in (OUTPUT_ROOT / "responses").glob("*.txt") if path.stem not in used)
    print(f"\n用到 {len(used)} 个回答，未用到 {len(stale)} 个" + ("，已删除" if apply else "（加 --apply 删除）"))
    for path in stale:
        print(f"  {path.name}")
        if apply:
            path.unlink()


if __name__ == "__main__":
    main(apply="--apply" in sys.argv[1:])
