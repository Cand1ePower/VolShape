"""Prompt version manifest for evals and release tracking.

The prompt texts still live in their owning modules. This file gives us a
stable manifest with semantic versions and content hashes so eval reports can
say exactly which prompt set they tested.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Iterable

from app import prompts as core_prompts
from app.services import media_analysis


PROMPT_SET_VERSION = "2026-06-05.eval-v1"


@dataclass(frozen=True)
class PromptSpec:
    name: str
    owner: str
    module: Any
    attr: str
    version: str
    purpose: str

    @property
    def text(self) -> str:
        return str(getattr(self.module, self.attr))

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    def to_manifest_item(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "owner": self.owner,
            "module": self.module.__name__,
            "attr": self.attr,
            "version": self.version,
            "purpose": self.purpose,
            "sha256": self.sha256,
            "chars": len(self.text),
        }


PROMPT_SPECS: tuple[PromptSpec, ...] = (
    PromptSpec(
        name="intent_classifier",
        owner="workflow",
        module=core_prompts,
        attr="INTENT_CLASSIFIER_SYSTEM",
        version="2026-06-05.1",
        purpose="Classify user intent before routing the coaching workflow.",
    ),
    PromptSpec(
        name="quick_training_plan",
        owner="workflow",
        module=core_prompts,
        attr="QUICK_COMBINED_SYSTEM",
        version="2026-06-05.1",
        purpose="Generate quick-mode training plans with safety review.",
    ),
    PromptSpec(
        name="expert_planner",
        owner="workflow",
        module=core_prompts,
        attr="PLANNER_SYSTEM",
        version="2026-06-05.1",
        purpose="Plan expert-mode training strategy.",
    ),
    PromptSpec(
        name="expert_executor",
        owner="workflow",
        module=core_prompts,
        attr="EXECUTOR_SYSTEM",
        version="2026-06-05.1",
        purpose="Turn expert strategy into executable exercises.",
    ),
    PromptSpec(
        name="chat_response",
        owner="workflow",
        module=core_prompts,
        attr="RESPONSE_CHAT_SYSTEM",
        version="2026-06-05.1",
        purpose="Answer general coaching questions with profile and memory context.",
    ),
    PromptSpec(
        name="memory_extraction",
        owner="memory",
        module=core_prompts,
        attr="MEMORY_EXTRACTION_SYSTEM",
        version="2026-06-05.1",
        purpose="Extract structured user profile, state, injury, and event facts.",
    ),
    PromptSpec(
        name="media_intent",
        owner="media",
        module=media_analysis,
        attr="MEDIA_INTENT_SYSTEM",
        version="2026-06-05.1",
        purpose="Gate media analysis so uploads only invoke tools with explicit intent.",
    ),
    PromptSpec(
        name="food_image_analysis",
        owner="media",
        module=media_analysis,
        attr="FOOD_IMAGE_ANALYSIS_SYSTEM",
        version="2026-06-05.1",
        purpose="Identify food photos and produce nutrition candidates.",
    ),
    PromptSpec(
        name="movement_response",
        owner="media",
        module=media_analysis,
        attr="MOVEMENT_RESPONSE_SYSTEM",
        version="2026-06-05.2",
        purpose="Explain pose-analysis results without hallucinating exercise names.",
    ),
)


def iter_prompt_specs() -> Iterable[PromptSpec]:
    return PROMPT_SPECS


def get_prompt_manifest() -> Dict[str, Any]:
    return {
        "prompt_set_version": PROMPT_SET_VERSION,
        "prompts": [spec.to_manifest_item() for spec in PROMPT_SPECS],
    }


def get_prompt_version(name: str) -> str:
    for spec in PROMPT_SPECS:
        if spec.name == name:
            return spec.version
    raise KeyError(f"Unknown prompt: {name}")
