import uuid
import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.database.models import DietRecord
from app.core.auth import get_current_user_id
from app.services.llm_client import llm_call_structured

router = APIRouter()


class DietDescription(BaseModel):
    meal_type: str  # "breakfast" | "lunch" | "dinner" | "snack"
    description: str  # "150g鸡胸肉 + 200g西兰花 + 一碗米饭"


@router.post("/analyze")
async def analyze_diet(
    request: DietDescription,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    if request.meal_type not in ("breakfast", "lunch", "dinner", "snack"):
        raise HTTPException(status_code=400, detail="meal_type 必须是 breakfast/lunch/dinner/snack 之一")

    try:
        from app.prompts import DIET_ANALYSIS_SYSTEM
        result = await llm_call_structured(
            system_prompt=DIET_ANALYSIS_SYSTEM,
            user_prompt=f"餐食描述: {request.description}\n餐别: {request.meal_type}",
            temperature=0.2,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"营养分析失败: {str(e)}")

    food_items = result.get("foodItems", [])
    total_calories = result.get("totalCalories", 0)
    total_protein = result.get("totalProtein", 0.0)
    total_carbs = result.get("totalCarbs", 0.0)
    total_fat = result.get("totalFat", 0.0)

    if not total_calories:
        total_calories = sum(item.get("calories", 0) for item in food_items)
        total_protein = sum(item.get("protein", 0) for item in food_items)
        total_carbs = sum(item.get("carbs", 0) for item in food_items)
        total_fat = sum(item.get("fat", 0) for item in food_items)

    record_id = str(uuid.uuid4())
    diet_record = DietRecord(
        id=record_id,
        user_id=user_id,
        meal_type=request.meal_type,
        food_items=food_items,
        total_calories=int(total_calories),
        total_protein=float(total_protein),
        total_carbs=float(total_carbs),
        total_fat=float(total_fat),
    )
    db.add(diet_record)
    await db.commit()

    return {
        "record_id": record_id,
        "type": "diet_card",
        "mealType": request.meal_type,
        "foodItems": food_items,
        "totalCalories": int(total_calories),
        "totalProtein": float(total_protein),
        "totalCarbs": float(total_carbs),
        "totalFat": float(total_fat),
        "status": "success",
        "message": "膳食营养估算完成！",
    }
