"""硬约束筛选规则引擎：岗位匹配前按规则剔除不满足条件的岗位，独立于 FastAPI。"""

from app.rule_engine.engine import ScreeningResult, filter_jobs, screen_jobs, screen_jobs_postgres

__all__ = ["ScreeningResult", "filter_jobs", "screen_jobs", "screen_jobs_postgres"]
