import pytest
from fastapi.testclient import TestClient
import cv2
import numpy as np
import os
import tempfile
from pathlib import Path

from app.main import app
from app.services.media_analysis import (
    _analyze_pose_frames,
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

    video_gate = fallback_media_gate("帮我分析一下这个动作姿势对不对", "video")
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


async def test_media_endpoint_rejects_oversized_upload(anyio_backend):
    from app.api import media as media_api
    from app.core.config import settings

    previous_limit = settings.MAX_IMAGE_UPLOAD_MB
    settings.MAX_IMAGE_UPLOAD_MB = 1

    async def fake_classify_media_intent(*args, **kwargs):
        return {"should_invoke": True, "capability": "nutrition_photo", "message": ""}

    async def fake_assert_can_chat(*args, **kwargs):
        return None

    async def fake_increment_message(*args, **kwargs):
        return None

    original_classifier = media_api.classify_media_intent
    original_assert = media_api.QuotaService.assert_can_chat
    original_increment = media_api.QuotaService.increment_message
    media_api.classify_media_intent = fake_classify_media_intent
    media_api.QuotaService.assert_can_chat = fake_assert_can_chat
    media_api.QuotaService.increment_message = fake_increment_message
    try:
        response = client.post(
            "/api/media/analyze",
            headers={"Authorization": "Bearer test-user-media-gate"},
            files={"file": ("meal.jpg", b"x" * (1024 * 1024 + 1), "image/jpeg")},
            data={"user_input": "这是我今天的晚饭，大概多少热量和蛋白质？", "mode": "detailed"},
        )
        assert response.status_code == 413
    finally:
        media_api.classify_media_intent = original_classifier
        media_api.QuotaService.assert_can_chat = original_assert
        media_api.QuotaService.increment_message = original_increment
        settings.MAX_IMAGE_UPLOAD_MB = previous_limit


async def test_media_endpoint_routes_video_to_movement_analysis(anyio_backend):
    from app.api import media as media_api

    async def fake_classify_media_intent(*args, **kwargs):
        return {"should_invoke": True, "capability": "movement_video", "message": ""}

    async def fake_assert_can_chat(*args, **kwargs):
        return None

    async def fake_increment_message(*args, **kwargs):
        return None

    async def fake_analyze_movement_video(*args, **kwargs):
        return {
            "capability": "movement_video",
            "final_response": "动作整体稳定，建议继续保持核心收紧。",
            "card": None,
            "structured_result": {
                "score": 86,
                "issues": ["肩部有轻微高低差"],
                "observed_frames": 18,
                "valid_frames": 12,
            },
        }

    original_classifier = media_api.classify_media_intent
    original_assert = media_api.QuotaService.assert_can_chat
    original_increment = media_api.QuotaService.increment_message
    original_analyze = media_api.analyze_movement_video
    media_api.classify_media_intent = fake_classify_media_intent
    media_api.QuotaService.assert_can_chat = fake_assert_can_chat
    media_api.QuotaService.increment_message = fake_increment_message
    media_api.analyze_movement_video = fake_analyze_movement_video
    try:
        response = client.post(
            "/api/media/analyze",
            headers={"Authorization": "Bearer test-user-video"},
            files={"file": ("form.mp4", b"fake-video", "video/mp4")},
            data={"user_input": "帮我分析一下这个动作姿势是否标准", "mode": "detailed"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["capability"] == "movement_video"
        assert "动作整体稳定" in payload["final_response"]
        assert payload["structured_result"]["score"] == 86
    finally:
        media_api.classify_media_intent = original_classifier
        media_api.QuotaService.assert_can_chat = original_assert
        media_api.QuotaService.increment_message = original_increment
        media_api.analyze_movement_video = original_analyze


async def test_analyze_pose_frames_handles_video_bytes_without_import_error(anyio_backend):
    fd, temp_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    try:
        width, height = 320, 240
        writer = cv2.VideoWriter(temp_path, cv2.VideoWriter_fourcc(*"mp4v"), 12.0, (width, height))
        for i in range(24):
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            cv2.putText(frame, f"frame {i}", (40, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            writer.write(frame)
        writer.release()

        result = _analyze_pose_frames(Path(temp_path).read_bytes())
        assert isinstance(result, dict)
        assert "score" in result
        assert "issues" in result
        assert result["observed_frames"] > 0
    finally:
        Path(temp_path).unlink(missing_ok=True)
