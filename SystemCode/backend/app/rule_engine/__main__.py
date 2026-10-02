"""命令行入口：python -m app.rule_engine <profile.json> [--stats | --documents]（读根目录 .env 的 DATABASE_URL）"""

import argparse
import json
import logging
from pathlib import Path

from app.rule_engine.engine import screen_jobs
from app.schemas.profile import UserProfile


def main() -> None:
    parser = argparse.ArgumentParser(description="按硬规则筛选岗位，输出通过全部规则的岗位 id")
    parser.add_argument("profile", help="UserProfile JSON 文件路径")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--stats", action="store_true", help="改为输出每条规则单独剔除的岗位数")
    mode.add_argument("--documents", action="store_true", help="改为输出通过筛选的 JobRequirementDocument 列表")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    profile = UserProfile.model_validate_json(Path(args.profile).read_text(encoding="utf-8"))
    screened = screen_jobs(profile)

    if args.documents:
        result = {"jobs": [document.model_dump(mode="json") for document in screened.documents]}
    elif args.stats:
        # 单独剔除数：被该规则拒绝的岗位数，不管其他规则是否也拒绝了它（不是累计）
        result = {
            "total_jobs": screened.total_jobs,
            "rejected_by_rule": screened.rejected_by_rule,
            "kept": len(screened.documents),
        }
    else:
        result = {"job_ids": [document.job_id for document in screened.documents]}
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.stats else None))


if __name__ == "__main__":
    main()
