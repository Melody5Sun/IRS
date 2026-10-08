import hashlib

from app.repositories.resume_history_repository import ProfileRepository, ResumeHistoryRepository
from app.schemas.profile import SavedProfile, UserProfile
from app.schemas.resume import ResumeDocument

# 用户提交画像时允许留空的字段，按所在段落区分（同名字段如 start_date 在不同段落规则不同）。
# 标量字段：可以为 None/空串；列表字段：可以一条都不填，但填了的条目里字段仍要完整
OPTIONAL_FIELDS: dict[str, set[str]] = {
    # 手动填写画像时没有上传记录；首次保存会自动建立 Manual profile 来源记录
    "": {"resume_upload_id"},
    # 学生可能没有经历/项目/研究/证书/奖项，也可能没有零散补充信息
    "resume": {"experiences", "projects", "research", "certificates", "awards", "additional_info", "skill_groups"},
    # 技能栏原文的某一行可以没有分类标题
    "skill_groups": {"category"},
    "constraints": {"notes"},
    # 个人项目没有角色；很多简历不写项目时间
    "projects": {"role", "start_date", "end_date"},
    # 专利、软著、论文常常没有起止时间和所属机构
    "research": {"institution", "start_date", "end_date"},
    # 交换项目没有专业；学校层次、研究方向、GPA、排名、课程是简历里有才填的补充信息
    "educations": {"major", "school_tier", "research_direction", "gpa", "ranking", "courses"},
    # 证书可以永久有效；CET 这类考试常不写颁发机构和日期；成绩只有考试类证书才有
    "certificates": {"issuer", "issue_date", "expiry_date", "score"},
    "awards": {"date"},
}

Loc = list[str | int]


def _is_blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def resume_hash(resume: ResumeDocument) -> str:
    """改写稿据此判断画像简历是否在保存后改过；同一个模型的序列化结果是稳定的，不用额外规范化。"""
    return hashlib.sha256(resume.model_dump_json().encode()).hexdigest()


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
    # 所在段落 = loc 里最后一个字段名，如 ["resume", "projects", 0] -> "projects"
    section = next((part for part in reversed(loc) if isinstance(part, str)), "")
    optional = OPTIONAL_FIELDS.get(section, set())
    empty: list[Loc] = []
    for key, value in data.items():
        field_loc = [*loc, key]
        if isinstance(value, dict):
            empty += find_empty_fields(value, field_loc)
        elif isinstance(value, list):
            if not value and key not in optional:
                empty.append(field_loc)
            for index, item in enumerate(value):
                if isinstance(item, dict):
                    empty += find_empty_fields(item, [*field_loc, index])
                elif _is_blank(item):
                    empty.append([*field_loc, index])
        elif _is_blank(value) and key not in optional:
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

    def get(self) -> SavedProfile | None:
        return self.profile_repository.get()

    def save(self, profile: UserProfile) -> SavedProfile | None:
        """上传画像回写来源记录；纯手动画像首次保存时建立 Manual profile 来源记录。"""
        if profile.resume_upload_id is None:
            profile = profile.model_copy(
                update={"resume_upload_id": self.resume_history.add_manual(profile.resume)}
            )
        elif not self.resume_history.update(profile.resume_upload_id, profile.resume):
            return None
        return self.profile_repository.save(profile)


# resumes / profile / ranking / targets 路由共用同一份画像
profile_service = ProfileService()
