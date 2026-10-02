from app.repositories.resume_history_repository import ProfileRepository, ResumeHistoryRepository
from app.schemas.profile import JobSearchConstraints, UserProfile
from app.schemas.resume import ParsedResume, ResumeDocument

# 用户提交画像时允许留空的字段（补充说明选填、证书永久有效、交换项目没有专业、个人项目没有角色）
OPTIONAL_FIELDS = {"notes", "expiry_date", "major", "role"}
# 可以一条都不填的列表（学生可能没有）；但只要填了条目，条目里的字段仍要完整
OPTIONAL_LISTS = {"experiences", "projects", "research", "certificates"}

Loc = list[str | int]


def _is_blank(value: object) -> bool:
    # not_stated 是 LLM 解析不出来时的占位，用户手动提交时视同没填
    return value is None or value == "not_stated" or (isinstance(value, str) and not value.strip())


def merge_patch(base: dict[str, object], patch: dict[str, object]) -> dict[str, object]:
    """类似 JSON Merge Patch：patch 里的 key 覆盖 base，双方都是 dict 才递归合并，否则整体替换（含列表）。"""
    merged = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_patch(merged[key], value)  # type: ignore[arg-type]
        else:
            merged[key] = value
    return merged


def find_empty_fields(data: dict[str, object], loc: Loc | None = None) -> list[Loc]:
    """返回不允许为空却为空的字段位置，比如 ["resume", "experiences", 0, "country"]。"""
    loc = loc or []
    empty: list[Loc] = []
    for key, value in data.items():
        if key in OPTIONAL_FIELDS:
            continue
        field_loc = [*loc, key]
        if isinstance(value, dict):
            empty += find_empty_fields(value, field_loc)
        elif isinstance(value, list):
            if not value and key not in OPTIONAL_LISTS:
                empty.append(field_loc)
            for index, item in enumerate(value):
                if isinstance(item, dict):
                    empty += find_empty_fields(item, [*field_loc, index])
                elif _is_blank(item):
                    empty.append([*field_loc, index])
        elif _is_blank(value):
            empty.append(field_loc)
    return empty


class ProfileService:
    """画像相关的业务规则；持久化交给仓库（默认 PostgreSQL，测试注入 Fake 仓库）。"""

    def __init__(
        self,
        profile_repository: ProfileRepository | None = None,
        resume_history: ResumeHistoryRepository | None = None,
    ) -> None:
        self.profile_repository = profile_repository or ProfileRepository()
        self.resume_history = resume_history or ResumeHistoryRepository()

    def get(self) -> UserProfile | None:
        return self.profile_repository.get()

    def save(self, profile: UserProfile) -> None:
        self.profile_repository.save(profile)

    def save_resume(self, parsed: ParsedResume) -> UserProfile:
        # 重新上传简历时只替换画像，已经填写的求职约束保留
        current = self.get()
        constraints = current.constraints if current else JobSearchConstraints()
        # 简历里的自我介绍合并进补充说明；用户已经写过 notes 就不覆盖
        if parsed.about and not constraints.notes.strip():
            constraints = constraints.model_copy(update={"notes": parsed.about})
        resume = ResumeDocument.model_validate(parsed.model_dump(exclude={"about"}))
        profile = UserProfile(resume=resume, constraints=constraints)
        self.save(profile)
        return profile


# resumes 和 profile 两个路由共用同一份画像
profile_service = ProfileService()
