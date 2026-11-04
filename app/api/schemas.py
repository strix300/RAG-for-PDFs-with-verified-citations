"""Публичные запросы, ответы и отдельный контракт диагностики."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.models import Candidate, StrictModel


class Submission(StrictModel):
    """Идентификаторы принятого документа и задания."""

    doc_id: UUID
    task_id: UUID
    status_url: str


class DocumentSummary(StrictModel):
    """Описывает загруженный документ независимо от срока жизни задания."""

    doc_id: UUID
    doc_title: str
    uploaded_at: datetime
    status: str
    task_id: UUID
    page_count: int | None
    chunk_count: int | None


class DocumentPage(StrictModel):
    """Возвращает ограниченную страницу каталога."""

    items: list[DocumentSummary]
    next_cursor: str | None


class QuestionRequest(StrictModel):
    """Содержит только текущий вопрос без истории и сессии."""

    question: str = Field(min_length=1, max_length=20000)


class Citation(StrictModel):
    """Содержит цитату и метаданные, восстановленные только из Qdrant payload."""

    fragment_id: UUID
    doc_id: UUID
    doc_title: str
    text: str
    page: int
    section: str | None
    char_start: int
    char_end: int


class Diagnostics(StrictModel):
    """Отделяет измерения диагностических запросов от основного результата."""

    branch_measurement: Literal["separate_queries"] = "separate_queries"
    dense_candidates: int
    sparse_candidates: int
    fusion_candidates: int
    rerank_input_candidates: int
    rerank_output_candidates: int
    reranked_candidates: list[Candidate]
    context_fragments: list[Candidate]
    timings_ms: dict[str, float]


class AnswerResponse(StrictModel):
    """Предоставляет только проверенный ответ и исходные цитаты."""

    answer: str
    found: bool
    citations: list[Citation]
    diagnostics: Diagnostics | None = None
