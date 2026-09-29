from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.engine import Connection


def normalized_name(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def ensure_company(connection: Connection, company_name: str) -> int:
    name = company_name.strip() or "Unknown"
    return int(
        connection.execute(
            text(
                """
                INSERT INTO companies (name, normalized_name)
                VALUES (:name, :normalized_name)
                ON CONFLICT (normalized_name) DO UPDATE SET
                    name = EXCLUDED.name,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
                """
            ),
            {"name": name, "normalized_name": normalized_name(name)},
        ).scalar_one()
    )


def ensure_skill(connection: Connection, skill_name: str) -> int:
    name = skill_name.strip()
    return int(
        connection.execute(
            text(
                """
                INSERT INTO skills (canonical_name, normalized_name)
                VALUES (:name, :normalized_name)
                ON CONFLICT (normalized_name) DO UPDATE SET
                    canonical_name = EXCLUDED.canonical_name
                RETURNING id
                """
            ),
            {"name": name, "normalized_name": normalized_name(name)},
        ).scalar_one()
    )


def ensure_role(connection: Connection, role_name: str) -> int:
    name = role_name.strip()
    return int(
        connection.execute(
            text(
                """
                INSERT INTO roles (canonical_name)
                VALUES (:name)
                ON CONFLICT (canonical_name) DO UPDATE SET
                    canonical_name = EXCLUDED.canonical_name
                RETURNING id
                """
            ),
            {"name": name},
        ).scalar_one()
    )


def ensure_single_user(connection: Connection) -> int:
    connection.execute(
        text(
            """
            INSERT INTO users (id)
            VALUES (1)
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    return 1
