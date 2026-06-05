import base64
import datetime
import json
import math
import os
import re
import tempfile
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.models import DietRecord, Events
from app.services.fatsecret import FatSecretService
from app.services.llm_client import llm_call, llm_call_messages_structured, llm_call_structured


MEDIA_INTENT_SYSTEM = """
你是 VolShape 的媒体意图门控器。只有当用户上传了对应媒体，并且在文字里明确表达了分析诉求时，才允许触发对应能力。

能力定义：
- nutrition_photo: 用户上传的是食物照片，并明确想知道热量、蛋白质、碳水、脂肪、营养结构或饮食建议
- movement_video: 用户上传的是训练视频，并明确想分析姿势、动作质量、是否标准或纠正建议

如果用户只是上传了媒体，但没有说明分析诉求，必须拒绝触发。

输出 JSON：
{
  "should_invoke": true,
  "capability": "nutrition_photo" | "movement_video" | "none",
  "message": "给用户的简短提示"
}
"""

FOOD_IMAGE_ANALYSIS_SYSTEM = """
你是专业营养识别助手。请结合用户上传的食物照片和文字说明，识别食物并估计份量。

严格输出 JSON：
{
  "meal_type": "breakfast" | "lunch" | "dinner" | "snack",
  "portion_note": "对份量估计的简短说明",
  "items": [
    {
      "name": "用于营养库检索的通用食物名",
      "display_name": "给用户展示的中文名称",
      "estimated_weight_g": 180,
      "estimated_calories": 220,
      "estimated_protein": 20,
      "estimated_carbs": 8,
      "estimated_fat": 12,
      "confidence": 0.82,
      "portion_basis": "standard_unit" | "visual_estimate" | "explicit_prompt",
      "requires_confirmation": true,
      "portion_options_g": [120, 180, 240]
    }
  ]
}

要求：
- 食物名称尽量返回便于营养数据库检索的通用名称
- 如果看不清，请降低 confidence，不要编造过多项目
- 最多返回 5 个主要食物
- 如果用户已经明确说了分量，可将 portion_basis 设为 explicit_prompt，requires_confirmation 设为 false
- 如果食物通常以固定单位出现，例如整颗鸡蛋、独立包装酸奶，可使用 standard_unit
- portion_options_g 必须给出 2 到 4 个候选克重，便于用户确认
"""
FOOD_RESPONSE_SYSTEM = """
你是 VolShape 的专业营养教练。请根据识别结果和营养汇总，给用户一段专业、自然、略详细的反馈。

只输出自然语言，不要输出 JSON。

要求：
- 先说明你是基于图片做的估算，存在少量误差
- 明确提到总热量、蛋白质、碳水、脂肪
- 结合用户这次的问题给出 2 到 3 条具体建议
- 语气专业，不要口语化
"""

MOVEMENT_RESPONSE_SYSTEM = """
你是 VolShape 的动作技术教练。请根据姿态检测得到的结构化问题，给用户一段专业、自然、略详细的反馈。

只输出自然语言，不要输出 JSON。

要求：
- 先总结整体动作质量
- 再列出最重要的 2 到 4 个问题
- 给出可执行的纠正建议
- 如果检测质量一般，要坦诚说明视频角度或清晰度可能影响判断
"""

PORTION_EXPLICIT_PATTERN = re.compile(
    r"(\d+\s?(g|kg|克|千克|公斤|ml|毫升|个|份|碗|盘|杯|勺|块|片|串|盒))",
    re.IGNORECASE,
)


@dataclass
class MacroBasis:
    basis_g: float
    calories: float
    protein: float
    carbs: float
    fat: float


def infer_media_kind(content_type: str, filename: str = "") -> Optional[str]:
    content_type = (content_type or "").lower()
    filename = (filename or "").lower()
    if content_type.startswith("image/") or filename.endswith((".jpg", ".jpeg", ".png", ".webp", ".heic")):
        return "image"
    if content_type.startswith("video/") or filename.endswith((".mp4", ".mov", ".m4v", ".avi")):
        return "video"
    return None


def image_bytes_to_data_url(image_bytes: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def parse_macro_basis(description: str) -> Optional[MacroBasis]:
    if not description:
        return None
    basis_match = re.search(r"Per\s+([0-9]+(?:\.[0-9]+)?)g", description, re.IGNORECASE)
    cal_match = re.search(r"Calories:\s*([0-9]+(?:\.[0-9]+)?)kcal", description, re.IGNORECASE)
    fat_match = re.search(r"Fat:\s*([0-9]+(?:\.[0-9]+)?)g", description, re.IGNORECASE)
    carb_match = re.search(r"Carbs:\s*([0-9]+(?:\.[0-9]+)?)g", description, re.IGNORECASE)
    protein_match = re.search(r"Protein:\s*([0-9]+(?:\.[0-9]+)?)g", description, re.IGNORECASE)
    if not (basis_match and cal_match and fat_match and carb_match and protein_match):
        return None
    return MacroBasis(
        basis_g=float(basis_match.group(1)),
        calories=float(cal_match.group(1)),
        fat=float(fat_match.group(1)),
        carbs=float(carb_match.group(1)),
        protein=float(protein_match.group(1)),
    )


def scale_macros(weight_g: float, basis: MacroBasis) -> Dict[str, float]:
    factor = (weight_g / basis.basis_g) if basis.basis_g else 1.0
    return {
        "calories": round(basis.calories * factor),
        "protein": round(basis.protein * factor, 1),
        "carbs": round(basis.carbs * factor, 1),
        "fat": round(basis.fat * factor, 1),
    }


def user_provided_portion_hint(user_input: str) -> bool:
    text = user_input or ""
    return bool(PORTION_EXPLICIT_PATTERN.search(text))


def build_portion_options(weight_g: float) -> List[int]:
    if weight_g <= 0:
        weight_g = 100
    candidates = [weight_g * 0.75, weight_g, weight_g * 1.25]
    normalized: List[int] = []
    for candidate in candidates:
        rounded = max(20, int(round(candidate / 5.0) * 5))
        if rounded not in normalized:
            normalized.append(rounded)
    return normalized[:4]


def needs_portion_confirmation(user_input: str, items: List[Dict[str, Any]]) -> bool:
    if user_provided_portion_hint(user_input):
        return False
    if not items:
        return False
    return any(
        bool(item.get("requires_confirmation"))
        and str(item.get("portion_basis") or "visual_estimate") != "standard_unit"
        for item in items
    )


def fallback_media_gate(user_input: str, media_kind: str) -> Dict[str, Any]:
    if media_kind == "image":
        keywords = ["热量", "卡路里", "蛋白质", "碳水", "脂肪", "营养", "早餐", "午饭", "晚饭", "加餐", "吃的"]
        if any(word in user_input for word in keywords):
            return {"should_invoke": True, "capability": "nutrition_photo", "message": "已识别为食物图片营养分析请求。"}
    if media_kind == "video":
        keywords = ["姿势", "动作", "标准", "正确", "纠正", "分析", "质量", "动作质量"]
        if any(word in user_input for word in keywords):
            return {"should_invoke": True, "capability": "movement_video", "message": "已识别为动作视频分析请求。"}
    return {
        "should_invoke": False,
        "capability": "none",
        "message": "请明确告诉我要分析这张食物照片的营养，或分析这段训练视频的动作。",
    }


async def classify_media_intent(
    user_input: str,
    media_kind: str,
    *,
    user_id: str,
    db: AsyncSession,
    session_id: Optional[str],
) -> Dict[str, Any]:
    try:
        result = await llm_call_structured(
            system_prompt=MEDIA_INTENT_SYSTEM,
            user_prompt=f"media_kind={media_kind}\nuser_input={user_input}",
            temperature=0.0,
            max_tokens=300,
            user_id=user_id,
            db=db,
            session_id=session_id,
            trace_enabled=False,
        )
        should_invoke = bool(result.get("should_invoke"))
        capability = result.get("capability") or "none"
        if should_invoke and capability in {"nutrition_photo", "movement_video"}:
            return {
                "should_invoke": True,
                "capability": capability,
                "message": result.get("message") or "",
            }
    except Exception:
        pass
    return fallback_media_gate(user_input, media_kind)


def _get_direct_vision_client() -> Optional[AsyncOpenAI]:
    if not settings.VISION_API_KEY:
        return None
    return AsyncOpenAI(
        api_key=settings.VISION_API_KEY,
        base_url=settings.VISION_BASE_URL,
        timeout=45.0,
        max_retries=1,
    )


async def _run_food_vision_analysis(
    *,
    image_bytes: bytes,
    mime_type: str,
    user_input: str,
    user_id: str,
    db: AsyncSession,
    session_id: Optional[str],
) -> Dict[str, Any]:
    image_data_url = image_bytes_to_data_url(image_bytes, mime_type)
    messages = [
        {"role": "system", "content": FOOD_IMAGE_ANALYSIS_SYSTEM},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": f"用户请求：{user_input}"},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ],
        },
    ]

    direct_client = _get_direct_vision_client()
    if direct_client is not None:
        response = await direct_client.chat.completions.create(
            model=settings.LLM_VISION_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=1200,
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)

    return await llm_call_messages_structured(
        messages=messages,
        model=settings.LLM_VISION_MODEL,
        temperature=0.1,
        max_tokens=1200,
        user_id=user_id,
        db=db,
        session_id=session_id,
    )


def _draft_items_from_vision_result(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    llm_items = result.get("items") if isinstance(result.get("items"), list) else []
    draft_items: List[Dict[str, Any]] = []
    for item in llm_items[:5]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip() or str(item.get("display_name") or "鏈煡椋熺墿").strip()
        display_name = str(item.get("display_name") or name or "鏈煡椋熺墿").strip()
        estimated_weight = float(item.get("estimated_weight_g") or 0) or 100.0
        portion_options = item.get("portion_options_g") if isinstance(item.get("portion_options_g"), list) else []
        cleaned_options = [max(20, int(option)) for option in portion_options if isinstance(option, (int, float))]
        if not cleaned_options:
            cleaned_options = build_portion_options(estimated_weight)
        selected_weight = int(round(estimated_weight))
        if selected_weight not in cleaned_options:
            cleaned_options = sorted(set(cleaned_options + [selected_weight]))

        draft_items.append(
            {
                "name": name,
                "display_name": display_name,
                "selected_weight_g": selected_weight,
                "portion_options_g": cleaned_options[:4],
                "estimated_calories": round(float(item.get("estimated_calories") or 0)),
                "estimated_protein": round(float(item.get("estimated_protein") or 0), 1),
                "estimated_carbs": round(float(item.get("estimated_carbs") or 0), 1),
                "estimated_fat": round(float(item.get("estimated_fat") or 0), 1),
                "confidence": round(float(item.get("confidence") or 0), 2),
                "portion_basis": str(item.get("portion_basis") or "visual_estimate"),
                "requires_confirmation": bool(item.get("requires_confirmation", True)),
            }
        )
    return draft_items


async def _normalize_food_items(draft_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized_items: List[Dict[str, Any]] = []

    for item in draft_items:
        name = str(item.get("name") or "").strip()
        display_name = str(item.get("display_name") or name or "鏈煡椋熺墿").strip()
        selected_weight = float(item.get("selected_weight_g") or 0) or 100.0
        base_weight = float(item.get("selected_weight_g") or selected_weight or 100.0)
        fallback_macros = {
            "calories": round(float(item.get("estimated_calories") or 0)),
            "protein": round(float(item.get("estimated_protein") or 0), 1),
            "carbs": round(float(item.get("estimated_carbs") or 0), 1),
            "fat": round(float(item.get("estimated_fat") or 0), 1),
        }

        matched_name = display_name
        source = "llm_fallback"
        macros = fallback_macros

        if name and FatSecretService.enabled():
            try:
                search_payload = await FatSecretService.foods_search(name, max_results=1)
                candidate = FatSecretService.first_food_candidate(search_payload)
                if candidate:
                    basis = parse_macro_basis(str(candidate.get("food_description") or ""))
                    if basis:
                        macros = scale_macros(selected_weight, basis)
                        matched_name = str(candidate.get("food_name") or display_name)
                        source = "fatsecret"
            except Exception:
                pass

        if source == "llm_fallback" and base_weight > 0 and base_weight != selected_weight:
            factor = selected_weight / base_weight
            macros = {
                "calories": round(fallback_macros["calories"] * factor),
                "protein": round(fallback_macros["protein"] * factor, 1),
                "carbs": round(fallback_macros["carbs"] * factor, 1),
                "fat": round(fallback_macros["fat"] * factor, 1),
            }

        normalized_items.append(
            {
                "name": matched_name or display_name,
                "weight_g": int(round(selected_weight)),
                "calories": int(macros["calories"]),
                "protein": float(macros["protein"]),
                "carbs": float(macros["carbs"]),
                "fat": float(macros["fat"]),
                "source": source,
                "display_name": display_name,
                "confidence": round(float(item.get("confidence") or 0), 2),
            }
        )

    return normalized_items


def _build_diet_card(meal_type: str, record_id: str, normalized_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_calories = sum(int(item["calories"]) for item in normalized_items)
    total_protein = round(sum(float(item["protein"]) for item in normalized_items), 1)
    total_carbs = round(sum(float(item["carbs"]) for item in normalized_items), 1)
    total_fat = round(sum(float(item["fat"]) for item in normalized_items), 1)
    return {
        "type": "diet_card",
        "record_id": record_id,
        "mealType": meal_type if meal_type in {"breakfast", "lunch", "dinner", "snack"} else "snack",
        "foodItems": [
            {
                "name": item["name"],
                "weight_g": item["weight_g"],
                "calories": item["calories"],
                "protein": item["protein"],
                "carbs": item["carbs"],
                "fat": item["fat"],
            }
            for item in normalized_items
        ],
        "totalCalories": total_calories,
        "totalProtein": total_protein,
        "totalCarbs": total_carbs,
        "totalFat": total_fat,
    }


async def _finalize_food_analysis(
    *,
    user_input: str,
    meal_type: str,
    portion_note: str,
    draft_items: List[Dict[str, Any]],
    user_id: str,
    db: AsyncSession,
    session_id: Optional[str],
) -> Dict[str, Any]:
    normalized_items = await _normalize_food_items(draft_items)
    total_calories = sum(int(item["calories"]) for item in normalized_items)
    total_protein = round(sum(float(item["protein"]) for item in normalized_items), 1)
    total_carbs = round(sum(float(item["carbs"]) for item in normalized_items), 1)
    total_fat = round(sum(float(item["fat"]) for item in normalized_items), 1)

    feedback = await llm_call(
        system_prompt=FOOD_RESPONSE_SYSTEM,
        user_prompt=(
            f"用户请求：{user_input}\n"
            f"份量备注：{portion_note}\n"
            f"识别食物：{json.dumps(normalized_items, ensure_ascii=False)}\n"
            f"总计：热量 {total_calories} kcal, 蛋白质 {total_protein} g, 碳水 {total_carbs} g, 脂肪 {total_fat} g"
        ),
        temperature=0.4,
        max_tokens=700,
        user_id=user_id,
        db=db,
        session_id=session_id,
    )

    record_id = str(uuid.uuid4())
    db.add(
        DietRecord(
            id=record_id,
            user_id=user_id,
            meal_type=meal_type if meal_type in {"breakfast", "lunch", "dinner", "snack"} else "snack",
            food_items=[
                {
                    "name": item["name"],
                    "weight_g": item["weight_g"],
                    "calories": item["calories"],
                    "protein": item["protein"],
                    "carbs": item["carbs"],
                    "fat": item["fat"],
                    "source": item["source"],
                }
                for item in normalized_items
            ],
            total_calories=total_calories,
            total_protein=total_protein,
            total_carbs=total_carbs,
            total_fat=total_fat,
        )
    )
    db.add(
        Events(
            user_id=user_id,
            event_type="diet",
            payload={
                "meal_type": meal_type,
                "food_items": normalized_items,
                "total_calories": total_calories,
                "total_protein": total_protein,
                "total_carbs": total_carbs,
                "total_fat": total_fat,
            },
            event_date=datetime.date.today(),
        )
    )
    await db.commit()

    card = _build_diet_card(meal_type, record_id, normalized_items)
    return {
        "capability": "nutrition_photo",
        "final_response": feedback,
        "card": card,
        "structured_result": {
            "meal_type": meal_type,
            "portion_note": portion_note,
            "items": normalized_items,
            "pending_confirmation": False,
        },
    }


async def analyze_food_image(
    *,
    image_bytes: bytes,
    mime_type: str,
    user_input: str,
    user_id: str,
    db: AsyncSession,
    session_id: Optional[str],
) -> Dict[str, Any]:
    """
    食物图片分析入口。
    通过 MCP CapabilityPlanFactory 获取执行计划，
    按顺序执行 DETECT → CANONICALIZE 两个阶段。
    """
    from app.services.mcp.factory import CapabilityPlanFactory
    from app.services.mcp.types import Capability

    plan = CapabilityPlanFactory.build(Capability.NUTRITION_PHOTO)

    # 将原始输入打包成 payload 传入 Plan
    payload = await plan.execute(
        {
            "image_bytes": image_bytes,
            "mime_type": mime_type,
            "user_prompt": user_input,
        },
        user_id=user_id,
        db=db,
        session_id=session_id,
    )

    # 如果 MCP Vision 成功，使用其结果；否则回退到原始实现
    vision_result = payload if payload.get("items") else None
    if vision_result is None:
        vision_result = await _run_food_vision_analysis(
            image_bytes=image_bytes,
            mime_type=mime_type,
            user_input=user_input,
            user_id=user_id,
            db=db,
            session_id=session_id,
        )

    meal_type = str(vision_result.get("meal_type") or "snack")
    portion_note = str(vision_result.get("portion_note") or "")
    draft_items = _draft_items_from_vision_result(vision_result)

    if needs_portion_confirmation(user_input, draft_items):
        return {
            "capability": "nutrition_photo",
            "final_response": "我已经先识别出这顿饭的大致构成了，但这次的分量还不够确定。你先在下方确认每样食物的大致重量，我再给你更可靠的热量和三大营养素估算。",
            "card": {
                "type": "portion_confirm_card",
                "mealType": meal_type if meal_type in {"breakfast", "lunch", "dinner", "snack"} else "snack",
                "prompt": user_input,
                "portionNote": portion_note,
                "items": draft_items,
            },
            "structured_result": {
                "meal_type": meal_type,
                "portion_note": portion_note,
                "items": draft_items,
                "pending_confirmation": True,
            },
        }

    return await _finalize_food_analysis(
        user_input=user_input,
        meal_type=meal_type,
        portion_note=portion_note,
        draft_items=draft_items,
        user_id=user_id,
        db=db,
        session_id=session_id,
    )


async def confirm_food_portions(
    *,
    user_input: str,
    meal_type: str,
    portion_note: str,
    items: List[Dict[str, Any]],
    user_id: str,
    db: AsyncSession,
    session_id: Optional[str],
) -> Dict[str, Any]:
    sanitized_items: List[Dict[str, Any]] = []
    for item in items[:5]:
        if not isinstance(item, dict):
            continue
        selected_weight = int(float(item.get("selected_weight_g") or 0) or 0)
        if selected_weight <= 0:
            continue
        sanitized_items.append(
            {
                "name": str(item.get("name") or "").strip(),
                "display_name": str(item.get("display_name") or item.get("name") or "鏈煡椋熺墿").strip(),
                "selected_weight_g": selected_weight,
                "estimated_calories": round(float(item.get("estimated_calories") or 0)),
                "estimated_protein": round(float(item.get("estimated_protein") or 0), 1),
                "estimated_carbs": round(float(item.get("estimated_carbs") or 0), 1),
                "estimated_fat": round(float(item.get("estimated_fat") or 0), 1),
                "confidence": round(float(item.get("confidence") or 0), 2),
            }
        )

    return await _finalize_food_analysis(
        user_input=user_input,
        meal_type=meal_type,
        portion_note=portion_note,
        draft_items=sanitized_items,
        user_id=user_id,
        db=db,
        session_id=session_id,
    )


def _distance(a: Any, b: Any) -> float:
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


def _analyze_pose_frames(video_bytes: bytes) -> Dict[str, Any]:
    try:
        import cv2
        import mediapipe as mp
    except Exception as exc:
        raise RuntimeError("MediaPipe video analysis is not available in the current backend environment") from exc

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        tmp.write(video_bytes)
        temp_path = tmp.name

    issues: List[str] = []
    observed_frames = 0
    valid_frames = 0
    shoulder_imbalance = 0.0
    hip_imbalance = 0.0
    torso_offset = 0.0

    try:
        cap = cv2.VideoCapture(temp_path)
        pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        frame_index = 0
        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                break
            frame_index += 1
            if frame_index % 6 != 0:
                continue
            observed_frames += 1
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = pose.process(rgb)
            landmarks = result.pose_landmarks.landmark if result.pose_landmarks else None
            if not landmarks:
                continue
            valid_frames += 1

            left_shoulder = landmarks[mp.solutions.pose.PoseLandmark.LEFT_SHOULDER]
            right_shoulder = landmarks[mp.solutions.pose.PoseLandmark.RIGHT_SHOULDER]
            left_hip = landmarks[mp.solutions.pose.PoseLandmark.LEFT_HIP]
            right_hip = landmarks[mp.solutions.pose.PoseLandmark.RIGHT_HIP]

            shoulder_imbalance = max(shoulder_imbalance, abs(left_shoulder.y - right_shoulder.y))
            hip_imbalance = max(hip_imbalance, abs(left_hip.y - right_hip.y))
            shoulder_center_x = (left_shoulder.x + right_shoulder.x) / 2
            hip_center_x = (left_hip.x + right_hip.x) / 2
            torso_offset = max(torso_offset, abs(shoulder_center_x - hip_center_x))

        cap.release()
        pose.close()
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass

    if observed_frames == 0:
        raise RuntimeError("视频帧读取失败，暂时无法分析动作。")

    detection_ratio = valid_frames / observed_frames if observed_frames else 0.0
    score = 88
    if detection_ratio < 0.45:
        issues.append("视频角度或清晰度一般，姿态识别的有效帧偏少。")
        score -= 12
    if shoulder_imbalance > 0.06:
        issues.append("双肩存在明显高低差，动作过程中上半身不够稳定。")
        score -= 10
    if hip_imbalance > 0.06:
        issues.append("骨盆左右不够平稳，可能存在重心偏移。")
        score -= 8
    if torso_offset > 0.08:
        issues.append("躯干有明显侧移或倾斜，核心稳定性需要加强。")
        score -= 10
    if not issues:
        issues.append("整体动作轨迹较稳定，没有识别到明显的大幅失衡。")

    return {
        "score": max(55, min(96, score)),
        "detection_ratio": round(detection_ratio, 2),
        "issues": issues,
        "observed_frames": observed_frames,
        "valid_frames": valid_frames,
    }


async def analyze_movement_video(
    *,
    video_bytes: bytes,
    user_input: str,
    user_id: str,
    db: AsyncSession,
    session_id: Optional[str],
) -> Dict[str, Any]:
    """
    运动视频分析入口。
    通过 MCP CapabilityPlanFactory 获取执行计划，
    按顺序执行 POSE_EXTRACT 阶段，再由 LLM 将姿态数据转化为训练建议。
    """
    from app.services.mcp.factory import CapabilityPlanFactory
    from app.services.mcp.types import Capability

    plan = CapabilityPlanFactory.build(Capability.MOVEMENT_VIDEO)

    payload = await plan.execute(
        {"video_bytes": video_bytes},
        user_id=user_id,
        db=db,
        session_id=session_id,
    )

    # pose_extract 阶段结果就是 payload，回退默认到直接调用
    pose_result = payload.get("pose_extract") or _analyze_pose_frames(video_bytes)

    feedback = await llm_call(
        system_prompt=MOVEMENT_RESPONSE_SYSTEM,
        user_prompt=(
            f"用户请求：{user_input}\n"
            f"结构化姿态结果：{json.dumps(pose_result, ensure_ascii=False)}"
        ),
        temperature=0.35,
        max_tokens=700,
        user_id=user_id,
        db=db,
        session_id=session_id,
    )
    return {
        "capability": "movement_video",
        "final_response": feedback,
        "card": None,
        "structured_result": pose_result,
    }


