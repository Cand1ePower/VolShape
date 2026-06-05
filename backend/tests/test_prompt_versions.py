from app.prompt_versions import PROMPT_SET_VERSION, get_prompt_manifest, get_prompt_version


def test_prompt_manifest_contains_versioned_hashes():
    manifest = get_prompt_manifest()

    assert manifest["prompt_set_version"] == PROMPT_SET_VERSION
    assert manifest["prompts"]

    by_name = {item["name"]: item for item in manifest["prompts"]}
    assert "intent_classifier" in by_name
    assert "movement_response" in by_name

    for item in manifest["prompts"]:
        assert item["version"]
        assert len(item["sha256"]) == 64
        assert item["chars"] > 20


def test_get_prompt_version_returns_semantic_version():
    assert get_prompt_version("movement_response") == "2026-06-05.2"
