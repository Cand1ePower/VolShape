from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from app.services.rag.config import RagSettings, get_rag_settings
from app.services.rag.normalizer import normalize_chunk_text
from app.services.rag.types import (
    RagChunk,
    RagChunkType,
    RagDocument,
    RagLanguage,
    RagSourceType,
)


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_ASCII_WORD_RE = re.compile(r"[A-Za-z]{2,}")


@dataclass(frozen=True)
class MarkdownBlock:
    heading_path: tuple[str, ...]
    text: str


def chunk_documents(documents: list[RagDocument], settings: RagSettings | None = None) -> list[RagChunk]:
    settings = settings or get_rag_settings()
    chunks: list[RagChunk] = []
    for document in documents:
        chunks.extend(chunk_document(document, settings))
    return chunks


def chunk_document(document: RagDocument, settings: RagSettings | None = None) -> list[RagChunk]:
    settings = settings or get_rag_settings()
    blocks = split_markdown_blocks(document.text, document.source.title)
    chunks: list[RagChunk] = []
    for block_index, block in enumerate(blocks):
        if _is_noise_block(document, block):
            continue
        for part_index, text in enumerate(pack_block_text(block.text, settings)):
            clean_text = normalize_chunk_text(text)
            if len(clean_text) < settings.chunk_min_chars:
                continue
            chunks.append(
                RagChunk(
                    chunk_id=_build_chunk_id(document.source.source_id, block_index, part_index, clean_text),
                    source_id=document.source.source_id,
                    source_type=document.source.source_type,
                    title=document.source.title,
                    text=clean_text,
                    heading_path=block.heading_path,
                    chunk_type=_infer_chunk_type(clean_text, document.source.source_type),
                    language=_infer_language(clean_text),
                    topics=_infer_topics(document.source.title, block.heading_path, clean_text),
                    token_estimate=estimate_tokens(clean_text),
                    char_count=len(clean_text),
                    metadata={
                        "source_path": str(document.source.path),
                        **document.metadata,
                    },
                )
            )
    return chunks


def split_markdown_blocks(text: str, fallback_title: str) -> list[MarkdownBlock]:
    headings: list[str] = [fallback_title]
    current_lines: list[str] = []
    blocks: list[MarkdownBlock] = []

    def flush() -> None:
        body = "\n".join(current_lines).strip()
        if body:
            blocks.append(MarkdownBlock(heading_path=tuple(headings), text=body))
        current_lines.clear()

    for line in text.split("\n"):
        match = _HEADING_RE.match(line)
        if match:
            flush()
            level = len(match.group(1))
            title = match.group(2).strip()
            headings[:] = headings[:level]
            while len(headings) < level:
                headings.append("")
            if len(headings) == level:
                headings.append(title)
            else:
                headings[level] = title
            headings[:] = [heading for heading in headings if heading]
            continue
        current_lines.append(line)

    flush()
    if not blocks and text.strip():
        return [MarkdownBlock(heading_path=(fallback_title,), text=text.strip())]
    return blocks


def pack_block_text(text: str, settings: RagSettings) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if not paragraphs:
        return []

    packed: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > settings.chunk_max_chars:
            if current:
                packed.append(current)
                current = ""
            packed.extend(_split_long_text(paragraph, settings))
            continue

        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= settings.chunk_target_chars or len(current) < settings.chunk_min_chars:
            current = candidate
            continue

        packed.append(current)
        current = _with_overlap(current, settings.chunk_overlap_chars, paragraph)

    if current:
        packed.append(current)
    return packed


def estimate_tokens(text: str) -> int:
    cjk = len(_CJK_RE.findall(text))
    ascii_words = len(_ASCII_WORD_RE.findall(text))
    other = max(len(text) - cjk - sum(len(word) for word in _ASCII_WORD_RE.findall(text)), 0)
    return max(1, int(cjk * 0.65 + ascii_words * 1.2 + other * 0.25))


def _split_long_text(text: str, settings: RagSettings) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + settings.chunk_max_chars, len(text))
        chunks.append(text[start:end].strip())
        if end == len(text):
            break
        start = max(end - settings.chunk_overlap_chars, start + 1)
    return chunks


def _with_overlap(previous: str, overlap_chars: int, next_text: str) -> str:
    if overlap_chars <= 0:
        return next_text
    overlap = previous[-overlap_chars:].strip()
    return f"{overlap}\n\n{next_text}".strip()


def _build_chunk_id(source_id: str, block_index: int, part_index: int, text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return f"{source_id}_{block_index:04d}_{part_index:03d}_{digest}"


def _infer_chunk_type(text: str, source_type: RagSourceType) -> RagChunkType:
    if source_type == RagSourceType.PERSONAL_NOTE:
        return RagChunkType.NOTE
    if "|" in text and "---" in text:
        return RagChunkType.TABLE
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines and sum(line.startswith(("-", "*", "+")) or re.match(r"^\d+\.", line) is not None for line in lines) >= max(2, len(lines) // 2):
        return RagChunkType.LIST
    return RagChunkType.PARAGRAPH


def _infer_language(text: str) -> RagLanguage:
    cjk = len(_CJK_RE.findall(text))
    ascii_words = len(_ASCII_WORD_RE.findall(text))
    if cjk and ascii_words:
        return RagLanguage.MIXED
    if cjk:
        return RagLanguage.ZH
    if ascii_words:
        return RagLanguage.EN
    return RagLanguage.UNKNOWN


def _infer_topics(title: str, heading_path: tuple[str, ...], text: str) -> tuple[str, ...]:
    haystack = " ".join((title, *heading_path, text[:500])).lower()
    topic_keywords = {
        "hypertrophy": ("肌肥大", "增肌", "mechanical tension", "机械张力"),
        "fatigue": ("疲劳", "恢复", "doms", "神经系统"),
        "nutrition": ("蛋白质", "氨基酸", "omega", "肌酸", "维生素", "血糖", "胰岛素"),
        "cardio": ("心率", "有氧", "供能系统", "zone"),
        "injury": ("疼痛", "损伤", "炎症", "筋膜"),
        "programming": ("训练计划", "负荷", "容量", "强度", "周期"),
    }
    topics = [topic for topic, keywords in topic_keywords.items() if any(keyword.lower() in haystack for keyword in keywords)]
    return tuple(topics)


def _is_noise_block(document: RagDocument, block: MarkdownBlock) -> bool:
    if document.source.source_type != RagSourceType.TEXTBOOK:
        return False

    heading_text = " ".join(block.heading_path).lower()
    body_start = block.text[:600].lower()
    noise_markers = (
        "美国国家体能协会 体能教练认证指南",
        "essentials of strength training",
        "版权声明",
        "免责声明",
        "内容提要",
        "图书在版编目",
        "cip",
        "isbn",
        "目录",
        "contents",
        "译者序",
        "前言",
        "序言",
        "修订后的第4版",
        "认证考试",
        "学习试题",
        "关键词",
        "完成这一章的学习后",
        "致谢",
        "contributors",
        "copyright",
    )
    if any(marker in heading_text or marker in body_start for marker in noise_markers):
        return True

    chapter_toc = re.search(r"第\s*\d+\s*章", heading_text) is not None
    author_line = "译者:" in block.text and "审校:" in block.text
    toc_like = "·" in block.text and len(block.text) < 900
    return chapter_toc and author_line and toc_like
