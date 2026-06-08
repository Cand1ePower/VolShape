from __future__ import annotations

import math
import re
from collections import Counter

from app.services.rag.types import RagChunk, RagHit


_ASCII_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_KNOWN_TERMS = (
    "acwr",
    "doms",
    "rpe",
    "rm",
    "omega-3",
    "epa",
    "dha",
    "机械张力",
    "肌肥大",
    "延迟性肌肉酸痛",
    "神经疲劳",
    "中枢疲劳",
    "外周疲劳",
    "炎症",
    "恢复",
    "蛋白质",
    "氨基酸",
    "肌酸",
    "胰岛素",
    "血糖",
    "心率",
    "供能系统",
    "筋膜",
)


class BM25Index:
    def __init__(self, chunks: list[RagChunk], *, k1: float = 1.5, b: float = 0.75) -> None:
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.tokenized = [_tokenize(chunk.text, chunk.heading_path, chunk.title) for chunk in chunks]
        self.doc_lengths = [len(tokens) for tokens in self.tokenized]
        self.avg_doc_length = sum(self.doc_lengths) / max(len(self.doc_lengths), 1)
        self.doc_freq = self._build_doc_freq()

    def search(self, query: str, *, top_k: int = 20) -> list[RagHit]:
        query_tokens = _tokenize(query, (), "")
        if not query_tokens:
            return []

        scores: list[tuple[int, float]] = []
        query_counts = Counter(query_tokens)
        for index, tokens in enumerate(self.tokenized):
            token_counts = Counter(tokens)
            score = 0.0
            for token, query_weight in query_counts.items():
                tf = token_counts.get(token, 0)
                if not tf:
                    continue
                idf = self._idf(token)
                dl = self.doc_lengths[index]
                denom = tf + self.k1 * (1 - self.b + self.b * dl / max(self.avg_doc_length, 1))
                score += query_weight * idf * (tf * (self.k1 + 1) / denom)
            if score > 0:
                scores.append((index, score))

        scores.sort(key=lambda item: item[1], reverse=True)
        return [
            RagHit(chunk=self.chunks[index], score=score, score_type="bm25", rank=rank, source="bm25")
            for rank, (index, score) in enumerate(scores[:top_k], start=1)
        ]

    def _build_doc_freq(self) -> Counter[str]:
        doc_freq: Counter[str] = Counter()
        for tokens in self.tokenized:
            doc_freq.update(set(tokens))
        return doc_freq

    def _idf(self, token: str) -> float:
        total = max(len(self.tokenized), 1)
        df = self.doc_freq.get(token, 0)
        return math.log(1 + (total - df + 0.5) / (df + 0.5))


def _tokenize(text: str, heading_path: tuple[str, ...], title: str) -> list[str]:
    title_tokens = _tokenize_text(title)
    heading_tokens = _tokenize_text(" ".join(heading_path))
    body_tokens = _tokenize_text(text)
    return title_tokens * 4 + heading_tokens * 2 + body_tokens


def _tokenize_text(text: str) -> list[str]:
    haystack = text.lower()
    tokens = _ASCII_TOKEN_RE.findall(haystack)
    cjk_chars = _CJK_RE.findall(haystack)
    tokens.extend(cjk_chars)
    tokens.extend("".join(cjk_chars[index : index + 2]) for index in range(max(len(cjk_chars) - 1, 0)))
    tokens.extend(term for term in _KNOWN_TERMS if term in haystack)
    return [token for token in tokens if token.strip()]
