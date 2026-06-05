from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.chat import _resolve_session_id, _save_message
from app.core.auth import get_current_user_id
from app.core.config import settings
from app.database.session import get_db
from app.services.media_analysis import (
    analyze_food_image,
    analyze_movement_video,
    classify_media_intent,
    confirm_food_portions,
    infer_media_kind,
)
from app.services.quota import QuotaService

router = APIRouter()


def _max_upload_bytes(media_kind: str) -> int:
    if media_kind == "video":
        return settings.MAX_VIDEO_UPLOAD_MB * 1024 * 1024
    return settings.MAX_IMAGE_UPLOAD_MB * 1024 * 1024


class PortionConfirmRequest(BaseModel):
    session_id: str | None = None
    prompt: str
    meal_type: str
    portion_note: str | None = None
    items: list[dict]


@router.post("/analyze")
async def analyze_media(
    file: UploadFile = File(...),
    user_input: str = Form(...),
    mode: str = Form("detailed"),
    session_id: str | None = Form(None),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    if mode != "detailed":
        raise HTTPException(status_code=403, detail="上传解析功能仅在专家模式下可用。")

    await QuotaService.assert_can_chat(user_id, db, "detailed")
    await QuotaService.increment_message(user_id, db)

    media_kind = infer_media_kind(file.content_type or "", file.filename or "")
    if not media_kind:
        raise HTTPException(status_code=400, detail="仅支持图片或视频文件上传。")

    resolved_session_id = await _resolve_session_id(user_id, session_id, db, allow_create=True)
    gate = await classify_media_intent(user_input, media_kind, user_id=user_id, db=db, session_id=resolved_session_id)
    if not gate.get("should_invoke"):
        raise HTTPException(status_code=400, detail=gate.get("message") or "请先明确告诉我要分析这份媒体。")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="上传文件为空。")
    if len(file_bytes) > _max_upload_bytes(media_kind):
        max_mb = settings.MAX_VIDEO_UPLOAD_MB if media_kind == "video" else settings.MAX_IMAGE_UPLOAD_MB
        raise HTTPException(status_code=413, detail=f"上传文件过大，当前{media_kind}最大支持 {max_mb}MB。")

    await _save_message(
        user_id,
        resolved_session_id,
        "user",
        user_input,
        db,
        custom_card={
            "type": "media_attachment",
            "mediaKind": media_kind,
            "fileName": file.filename or "media",
            "mimeType": file.content_type or "",
        },
        title_hint=user_input,
    )

    if gate["capability"] == "nutrition_photo":
        result = await analyze_food_image(
            image_bytes=file_bytes,
            mime_type=file.content_type or "image/jpeg",
            user_input=user_input,
            user_id=user_id,
            db=db,
            session_id=resolved_session_id,
        )
    elif gate["capability"] == "movement_video":
        result = await analyze_movement_video(
            video_bytes=file_bytes,
            user_input=user_input,
            user_id=user_id,
            db=db,
            session_id=resolved_session_id,
        )
    else:
        raise HTTPException(status_code=400, detail="当前媒体与请求意图不匹配。")

    await _save_message(
        user_id,
        resolved_session_id,
        "assistant",
        result["final_response"],
        db,
        custom_card=result.get("card"),
    )
    return {
        "session_id": resolved_session_id,
        **result,
    }


@router.post("/portion-confirm")
async def confirm_media_portion(
    request: PortionConfirmRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    resolved_session_id = await _resolve_session_id(user_id, request.session_id, db, allow_create=True)
    summary = "，".join(
        f"{(item.get('display_name') or item.get('name') or '食物')} {int(float(item.get('selected_weight_g') or 0))}g"
        for item in request.items[:5]
        if float(item.get("selected_weight_g") or 0) > 0
    )
    await _save_message(
        user_id,
        resolved_session_id,
        "user",
        f"[分量确认] {summary or '已确认本次饮食分量'}",
        db,
    )

    result = await confirm_food_portions(
        user_input=request.prompt,
        meal_type=request.meal_type,
        portion_note=request.portion_note or "",
        items=request.items,
        user_id=user_id,
        db=db,
        session_id=resolved_session_id,
    )
    await _save_message(
        user_id,
        resolved_session_id,
        "assistant",
        result["final_response"],
        db,
        custom_card=result.get("card"),
    )
    return {
        "session_id": resolved_session_id,
        **result,
    }
