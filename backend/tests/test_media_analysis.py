import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.media_analysis import (
    fallback_media_gate,
    infer_media_kind,
    needs_portion_confirmation,
    parse_macro_basis,
    scale_macros,
    user_provided_portion_hint,
)

client = TestClient(app)
pytestmark = pytest.mark.anyio


async def test_infer_media_kind_recognizes_supported_uploads(anyio_backend):
    assert infer_media_kind("image/jpeg", "lunch.jpg") == "image"
    assert infer_media_kind("video/mp4", "squat.mp4") == "video"
    assert infer_media_kind("", "meal.png") == "image"
    assert infer_media_kind("", "lift.mov") == "video"
    assert infer_media_kind("application/pdf", "report.pdf") is None


async def test_fallback_media_gate_requires_explicit_media_intent(anyio_backend):
    image_gate = fallback_media_gate("这是我今天的午饭，大概多少热量和蛋白质？", "image")
    assert image_gate["should_invoke"] is True
    assert image_gate["capability"] == "nutrition_photo"

    video_gate = fallback_media_gate("帮我分析一下这个动作姿势是否正确", "video")
    assert video_gate["should_invoke"] is True
    assert video_gate["capability"] == "movement_video"

    no_intent_gate = fallback_media_gate("这是今天拍的内容", "image")
    assert no_intent_gate["should_invoke"] is False
    assert no_intent_gate["capability"] == "none"


async def test_parse_and_scale_macro_basis_from_fatsecret_description(anyio_backend):
    basis = parse_macro_basis("Per 100g - Calories: 165kcal | Fat: 3.6g | Carbs: 0g | Protein: 31g")
    assert basis is not None

    scaled = scale_macros(150, basis)
    assert scaled == {
        "calories": 248,
        "protein": 46.5,
        "carbs": 0.0,
        "fat": 5.4,
    }


async def test_portion_confirmation_rules(anyio_backend):
    assert user_provided_portion_hint("这顿午饭里有200g鸡胸肉和一碗米饭") is True

    items = [
        {
            "name": "chicken breast",
            "display_name": "鸡胸肉",
            "selected_weight_g": 180,
            "requires_confirmation": True,
            "portion_basis": "visual_estimate",
        }
    ]
    assert needs_portion_confirmation("这是我今天的午饭，大概多少热量？", items) is True
    assert needs_portion_confirmation("这是我今天的午饭，鸡胸肉大概200g，多少热量？", items) is False


async def test_media_endpoint_rejects_non_expert_mode(anyio_backend):
    response = client.post(
        "/api/media/analyze",
        headers={"Authorization": "Bearer test-user-media-gate"},
        files={"file": ("meal.jpg", b"fake-image", "image/jpeg")},
        data={"user_input": "这是我今天的午饭，大概多少热量？", "mode": "quick"},
    )
    assert response.status_code == 403
