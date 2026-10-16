"""评测脚本共用的 LLM 回放客户端：按提示的哈希读已存好的回答，没有回答的提示写成待答文件。

为什么不直接调 LLM：线上用的 Gemini 免费额度（约 20 次/天）不够评测用，评测里的回答目前由
Claude Code 会话里的 haiku 子代理产生，而脚本本身调不到那个模型，所以分三步：
1. 跑评测脚本：每次 complete() 先找 responses/<hash>.txt；找不到就把提示写进 pending/<hash>.txt，
   抛 PendingResponse，脚本跳过这条用例并在最后列出待答数
2. 在 Claude Code 会话里给每个 pending 文件派一个 haiku 子代理作答：一个提示一个子代理（和线上一次请求一次调用一致，
   上一份简历也不会留在上下文里）；子代理只读这一个提示文件，把原始输出原样写进 responses/<hash>.txt，不读其他任何文件
   （仓库里有金标 JSON，读到就等于看了答案）
3. 重跑脚本：命中的提示继续走真实代码（校验 → 重试 → 后续调用），重试提示和第二段调用会成为新的待答，
   重复到没有待答为止；命中时会顺手删掉对应的 pending 文件
responses/ 随仓库保存，之后任何人重跑评测脚本都得到同一组数字，不需要调用任何 LLM。
"""

from __future__ import annotations

import hashlib
from pathlib import Path

# shortcut: 回答来自 Claude Code 里的 haiku 子代理，不是线上用的 Gemini，也没有 JSON mode、不能设温度；
# 以后换成 Gemini 或 API 时，把脚本里的 ReplayClient 换成 OpenAICompatibleClient（或包一层把回答写进 responses/）
# 并改这个常量，旧模型的结果按目录保留
EVAL_MODEL = "haiku"
OUTPUT_ROOT = Path(__file__).resolve().parents[1] / "eval_outputs" / EVAL_MODEL


class PendingResponse(RuntimeError):
    """这条提示还没有回答，已写进 pending/，等子代理作答后重跑。"""


def prompt_key(system_prompt: str, user_prompt: str) -> str:
    return hashlib.sha256(f"{system_prompt}\0{user_prompt}".encode()).hexdigest()[:16]


class ReplayClient:
    """实现 ChatClient 协议，可直接注入 LLMResumeParser(client=...)、ResumeRewriter(client=...)。"""

    def __init__(self, root: Path = OUTPUT_ROOT) -> None:
        self.responses = root / "responses"
        self.pending = root / "pending"
        # 本实例收到的每次调用：(system_prompt, 哈希)，脚本据此区分调用类型、统计重试
        self.history: list[tuple[str, str]] = []

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        key = prompt_key(system_prompt, user_prompt)
        self.history.append((system_prompt, key))
        response = self.responses / f"{key}.txt"
        if response.exists():
            (self.pending / f"{key}.txt").unlink(missing_ok=True)
            return response.read_text(encoding="utf-8")
        self.pending.mkdir(parents=True, exist_ok=True)
        (self.pending / f"{key}.txt").write_text(
            f"=== SYSTEM PROMPT ===\n{system_prompt}\n=== USER PROMPT ===\n{user_prompt}\n", encoding="utf-8"
        )
        raise PendingResponse(key)

    def response(self, key: str) -> str:
        return (self.responses / f"{key}.txt").read_text(encoding="utf-8")
