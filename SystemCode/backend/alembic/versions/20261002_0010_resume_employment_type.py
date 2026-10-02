"""Resume experience employment_type: keep only full_time/part_time/internship.

简历经历的工作类型只保留 full_time / part_time / internship：
not_stated -> null（解析时判断不出，等用户在画像里填写）；
contract / freelance -> null，原值记进 additional_info（"Employment type at <公司>: contract"），简历内容不丢。
只改 JSONB 里的简历数据（resume_uploads.resume_json、user_profile.resume），岗位侧的 employment_type 不动。

Revision ID: 20261002_0010
Revises: 20261002_0009
Create Date: 2026-10-02
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20261002_0010"
down_revision: Union[str, None] = "20261002_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (表, 存简历 JSON 的列)
RESUME_COLUMNS = [("resume_uploads", "resume_json"), ("user_profile", "resume")]
DROPPED_TYPES = "('contract', 'freelance')"


def _map_experiences(table: str, column: str, case_sql: str) -> None:
    # 逐条改写 experiences 数组里的元素，保持原顺序
    op.execute(
        f"""
        UPDATE {table} SET {column} = jsonb_set({column}, '{{experiences}}', (
            SELECT COALESCE(jsonb_agg({case_sql} ORDER BY ord), '[]'::jsonb)
            FROM jsonb_array_elements({column} -> 'experiences') WITH ORDINALITY AS t(e, ord)
        ))
        WHERE jsonb_typeof({column} -> 'experiences') = 'array'
        """
    )


def upgrade() -> None:
    for table, column in RESUME_COLUMNS:
        # 先把要删掉的类型原值追加进 additional_info，再清空 employment_type
        op.execute(
            f"""
            UPDATE {table} SET {column} = jsonb_set(
                {column}, '{{additional_info}}',
                COALESCE({column} -> 'additional_info', '[]'::jsonb) || (
                    SELECT jsonb_agg(
                        'Employment type at ' || COALESCE(e ->> 'company', '') || ': ' || (e ->> 'employment_type')
                        ORDER BY ord
                    )
                    FROM jsonb_array_elements({column} -> 'experiences') WITH ORDINALITY AS t(e, ord)
                    WHERE e ->> 'employment_type' IN {DROPPED_TYPES}
                )
            )
            WHERE jsonb_typeof({column} -> 'experiences') = 'array'
              AND EXISTS (
                  SELECT 1 FROM jsonb_array_elements({column} -> 'experiences') AS e
                  WHERE e ->> 'employment_type' IN {DROPPED_TYPES}
              )
            """
        )
        _map_experiences(
            table,
            column,
            f"""
            CASE WHEN e ->> 'employment_type' = 'not_stated' OR e ->> 'employment_type' IN {DROPPED_TYPES}
                THEN e || '{{"employment_type": null}}'
                ELSE e
            END
            """,
        )


def downgrade() -> None:
    # null 回到 not_stated；contract / freelance 只留在 additional_info 里，不再还原
    for table, column in RESUME_COLUMNS:
        _map_experiences(
            table,
            column,
            """
            CASE WHEN e ->> 'employment_type' IS NULL
                THEN e || '{"employment_type": "not_stated"}'
                ELSE e
            END
            """,
        )
