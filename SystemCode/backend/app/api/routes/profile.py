from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from app.schemas.profile import ProfileOptions, UserProfile
from app.services.profile_service import find_empty_fields, merge_patch, profile_service

router = APIRouter()
UPLOAD_NOT_FOUND = "未找到该简历上传记录"


@router.get("/options", response_model=ProfileOptions)
def get_profile_options() -> ProfileOptions:
    # 目标岗位（二级分类）、目标行业的固定范围，前端下拉框据此渲染
    return ProfileOptions()


@router.get("", response_model=UserProfile)
def get_profile() -> UserProfile:
    profile = profile_service.get()
    if profile is None:
        raise HTTPException(status_code=404, detail="尚未上传简历或保存画像")
    return profile


@router.put("", response_model=UserProfile)
def save_profile(profile: UserProfile) -> UserProfile:
    # 整体覆盖：前端提交补全后的完整画像 + 求职约束，这是画像唯一的写入入口。
    # 除选填字段外都必须填写；resume_upload_id 也必填（画像必须来自一份上传的简历）
    empty_fields = find_empty_fields(profile.model_dump())
    if empty_fields:
        # 错误格式与 FastAPI 自带的 422 一致，前端用同一套逻辑定位出错字段
        raise HTTPException(
            status_code=422,
            detail=[{"loc": ["body", *loc], "msg": "不能为空", "type": "empty"} for loc in empty_fields],
        )
    if not profile_service.save(profile):
        raise HTTPException(status_code=404, detail=UPLOAD_NOT_FOUND)
    return profile


@router.patch("", response_model=UserProfile)
def patch_profile(patch: dict) -> UserProfile:
    # 局部更新：只传要改的字段，不要求先满足 PUT 的“非空”校验；仍会跑 pydantic 自身的字段校验（如枚举范围）
    current = profile_service.get()
    if current is None:
        raise HTTPException(status_code=404, detail="尚未上传简历或保存画像")
    merged = merge_patch(current.model_dump(), patch)
    try:
        updated = UserProfile.model_validate(merged)
    except ValidationError as error:
        # 手动调用 model_validate 不会像请求体参数那样自动转成 422，这里转换成和 FastAPI 一致的格式
        raise HTTPException(status_code=422, detail=error.errors()) from error
    if not profile_service.save(updated):
        raise HTTPException(status_code=404, detail=UPLOAD_NOT_FOUND)
    return updated
