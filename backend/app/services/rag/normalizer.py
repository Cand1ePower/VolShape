from __future__ import annotations

import re
import unicodedata


_ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\ufeff]")
_MULTI_BLANK_RE = re.compile(r"\n{3,}")
_TRAILING_SPACE_RE = re.compile(r"[ \t]+$")
_IMAGE_ONLY_RE = re.compile(r"^\s*!\[[^\]]*\]\([^)]+\)\s*$")
_DETAILS_RE = re.compile(r"<details>.*?</details>", re.IGNORECASE | re.DOTALL)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = _ZERO_WIDTH_RE.sub("", text)
    text = _DETAILS_RE.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    cleaned_lines = []
    for line in text.split("\n"):
        line = _TRAILING_SPACE_RE.sub("", line)
        if _looks_like_noise_line(line):
            continue
        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)
    text = _MULTI_BLANK_RE.sub("\n\n", text)
    return text.strip()


def normalize_chunk_text(text: str) -> str:
    text = normalize_text(text)
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line).strip()


def _looks_like_noise_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if _IMAGE_ONLY_RE.match(stripped):
        return True
    if stripped in {"---", "***", "___"}:
        return True
    if re.fullmatch(r"\d{1,4}", stripped):
        return True
    return False
