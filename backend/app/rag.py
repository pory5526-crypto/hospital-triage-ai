"""轻量 RAG：中文按字二元组切分 + BM25 检索。

不引入向量库与 embedding 模型，保证开发期零下载、可离线运行；
接口保留了 `HybridRetriever` 的形状，后续换 Milvus / Qdrant 只需替换 `retrieve`。
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

_CJK = re.compile(r"[\u4e00-\u9fff]+")
_WORD = re.compile(r"[a-zA-Z0-9]+")


def tokenize(text: str) -> list[str]:
    """中文用二元组 + 单字，英文数字用整词。"""
    text = text or ""
    tokens: list[str] = []
    for run in _CJK.findall(text):
        if len(run) == 1:
            tokens.append(run)
            continue
        for i in range(len(run) - 1):
            tokens.append(run[i : i + 2])
    tokens.extend(w.lower() for w in _WORD.findall(text))
    return tokens


@dataclass
class Hit:
    item: dict
    score: float
    confidence: float


class BM25Index:
    def __init__(self, items: list[dict], k1: float = 1.5, b: float = 0.72) -> None:
        self.items = items
        self.k1 = k1
        self.b = b
        self.docs: list[list[str]] = []
        self.df: dict[str, int] = {}
        self.doc_len: list[int] = []

        for item in items:
            # 标题与关键词加权：正文权重 1，标题 2，关键词 3（重复进 token 流）
            title = item.get("title", "")
            content = item.get("content", "")
            keywords = " ".join(item.get("keywords", []) or [])
            category = item.get("category", "")
            tokens = (
                tokenize(content)
                + tokenize(title) * 2
                + tokenize(keywords) * 3
                + tokenize(category)
            )
            self.docs.append(tokens)
            self.doc_len.append(len(tokens))
            for token in set(tokens):
                self.df[token] = self.df.get(token, 0) + 1

        self.avgdl = (sum(self.doc_len) / len(self.doc_len)) if self.doc_len else 0.0
        self.n = len(self.docs)

    def _idf(self, token: str) -> float:
        n_q = self.df.get(token, 0)
        if n_q == 0:
            return 0.0
        return math.log(1 + (self.n - n_q + 0.5) / (n_q + 0.5))

    def search(self, query: str, top_k: int = 4) -> list[Hit]:
        q_tokens = tokenize(query)
        if not q_tokens or not self.docs:
            return []
        q_set = set(q_tokens)
        scores: list[float] = []
        for idx, doc in enumerate(self.docs):
            if not doc:
                scores.append(0.0)
                continue
            freq: dict[str, int] = {}
            for token in doc:
                if token in q_set:
                    freq[token] = freq.get(token, 0) + 1
            dl = self.doc_len[idx]
            score = 0.0
            for token, tf in freq.items():
                idf = self._idf(token)
                denom = tf + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1))
                score += idf * tf * (self.k1 + 1) / (denom or 1)
            # 关键词整词命中加分：患者原话直接撞上标注关键词时更可信
            for kw in self.items[idx].get("keywords", []) or []:
                if kw and kw in query:
                    score += 2.2
            scores.append(score)

        ranked = sorted(
            ((i, s) for i, s in enumerate(scores) if s > 0), key=lambda x: x[1], reverse=True
        )[:top_k]

        hits: list[Hit] = []
        for i, s in ranked:
            hits.append(Hit(item=self.items[i], score=s, confidence=round(s / (s + 4.0), 3)))
        return hits


class KnowledgeBase:
    def __init__(self) -> None:
        self._items: list[dict] = []
        self._index: BM25Index | None = None

    def build(self, items: list[dict]) -> None:
        self._items = items or []
        self._index = BM25Index(self._items)

    @property
    def size(self) -> int:
        return len(self._items)

    def retrieve(self, query: str, top_k: int = 4, min_confidence: float = 0.18) -> list[Hit]:
        if self._index is None:
            return []
        hits = self._index.search(query, top_k=top_k)
        return [h for h in hits if h.confidence >= min_confidence]

    def categories(self) -> list[str]:
        seen: list[str] = []
        for item in self._items:
            c = item.get("category")
            if c and c not in seen:
                seen.append(c)
        return seen


kb = KnowledgeBase()
