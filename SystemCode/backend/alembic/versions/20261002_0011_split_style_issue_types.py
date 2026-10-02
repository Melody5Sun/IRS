"""Split passive_voice and buzzword out of weak_action_verb.

知识库问题类型新增 passive_voice / buzzword（从 weak_action_verb 拆出），放宽 CHECK 约束，
并把对应条目改标：向量模型按主题匹配，分不出"被动语态""空话"这类写法问题，只能由规则检测后用标签直接定位。
只改标签不改文本，文本块向量不受影响；content_hash 不在这里重算，下次 upsert 同样内容时只会刷新一次 updated_at。

Revision ID: 20261002_0011
Revises: 20261002_0010
Create Date: 2026-10-02
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20261002_0011"
down_revision: Union[str, None] = "20261002_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 迁移不导入应用代码，取值清单写死；必须与 app/schemas/resume_guideline.py 的 IssueType 保持一致
OLD_ISSUE_TYPES = (
    "weak_action_verb",
    "missing_quantification",
    "missing_outcome",
    "unclear_tech_stack",
    "weak_jd_alignment",
    "unsurfaced_skill",
    "irrelevant_content",
)
NEW_ISSUE_TYPES = OLD_ISSUE_TYPES + ("passive_voice", "buzzword")

# 条目 key → (旧标签, 新标签)
RETAG = {
    "action-verb-04": (["weak_action_verb"], ["passive_voice"]),
    "action-verb-03": (["weak_action_verb"], ["buzzword"]),
    "javaguide-07": (["irrelevant_content", "weak_action_verb"], ["irrelevant_content", "buzzword"]),
    "ai-26": (["unclear_tech_stack", "weak_action_verb"], ["unclear_tech_stack", "buzzword"]),
    "data-03": (["weak_action_verb", "missing_outcome"], ["buzzword", "missing_outcome"]),
    "sd-38": (["unclear_tech_stack", "weak_action_verb"], ["unclear_tech_stack", "buzzword"]),
}


def _array(values) -> str:
    return "ARRAY[" + ", ".join(f"'{value}'" for value in values) + "]::TEXT[]"


def _set_check(issue_types: tuple[str, ...]) -> None:
    op.execute(
        f"""
        ALTER TABLE resume_guidelines DROP CONSTRAINT resume_guidelines_issue_types_check;
        ALTER TABLE resume_guidelines ADD CONSTRAINT resume_guidelines_issue_types_check
            CHECK (cardinality(issue_types) > 0 AND issue_types <@ {_array(issue_types)});
        """
    )


def _retag(new: bool) -> None:
    for key, (old_tags, new_tags) in RETAG.items():
        op.execute(
            f"UPDATE resume_guidelines SET issue_types = {_array(new_tags if new else old_tags)} "
            f"WHERE guideline_key = '{key}'"
        )


def upgrade() -> None:
    _set_check(NEW_ISSUE_TYPES)
    _retag(new=True)


def downgrade() -> None:
    _retag(new=False)
    _set_check(OLD_ISSUE_TYPES)
