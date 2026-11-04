"""Типизированные данные между этапами индексации и формирования ответа."""

from datetime import UTC, datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator


class StrictModel(BaseModel):
    """Запрещает неописанные поля на границах приложения."""

    model_config = ConfigDict(extra="forbid")


class Page(StrictModel):
    """Сохраняет исходный текст страницы и его положение в документе."""

    number: int = Field(ge=1, le=100)
    text: str
    char_start: int = Field(ge=0)


class Chunk(StrictModel):
    """Содержит неизменённый фрагмент и проверяемую привязку к источнику."""

    record_type: Literal["chunk"] = "chunk"
    doc_id: UUID
    doc_title: str
    generation_id: UUID
    index_profile: str
    chunk_index: int = Field(ge=0)
    page_from: int = Field(ge=1, le=100)
    page_to: int = Field(ge=1, le=100)
    section: str | None
    text: str = Field(min_length=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)

    @model_validator(mode="after")
    def check_span(self) -> Self:
        """Не допускает противоречивые координаты источника."""
        if self.page_from != self.page_to or self.char_end - self.char_start != len(self.text):
            raise ValueError("Некорректные границы фрагмента.")
        return self


class DocumentRecord(StrictModel):
    """Хранит каталог документа и ссылку на полностью опубликованное поколение."""

    record_type: Literal["document"] = "document"
    doc_id: UUID
    doc_title: str
    content_hash: str
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    task_id: UUID
    pending_generation: UUID
    active_generation: UUID | None = None
    index_profile: str
    active_profile: str | None = None
    page_count: int | None = None
    chunk_count: int | None = None
    deleting: bool = False


class SparseVector(StrictModel):
    """Представляет разреженные веса без типов конкретного хранилища."""

    indices: list[int]
    values: list[float]


class EmbeddedChunk(StrictModel):
    """Объединяет исходный фрагмент с двумя представлениями поиска."""

    chunk: Chunk
    dense: list[float]
    sparse: SparseVector


class Candidate(StrictModel):
    """Сохраняет источник и оценки после поиска и переранжирования."""

    fragment_id: UUID
    chunk: Chunk
    fusion_score: float
    rerank_score: float | None = None


class Evidence(StrictModel):
    """Ограничивает свидетельство идентификатором контекста и точной цитатой."""

    fragment_id: UUID
    quote: str = Field(min_length=1, max_length=4000)


class Claim(StrictModel):
    """Связывает каждое утверждение с конкретными свидетельствами."""

    text: str = Field(min_length=1, max_length=1500)
    evidence: list[Evidence] = Field(min_length=1, max_length=8)


class DraftAnswer(StrictModel):
    """Задаёт структурированный ответ генератора до проверки."""

    found: StrictBool
    claims: list[Claim] = Field(max_length=8)

    @model_validator(mode="after")
    def check_found(self) -> Self:
        """Отделяет отсутствие сведений от ответа с утверждениями."""
        if self.found != bool(self.claims):
            raise ValueError("found должен соответствовать наличию утверждений.")
        return self


class ClaimVerdict(StrictModel):
    """Содержит семантическую оценку одного утверждения отдельным verifier."""

    claim_index: int = Field(ge=0, strict=True)
    supported: StrictBool


class GroundingVerdict(StrictModel):
    """Проверяет полноту ответа и поддержку каждого утверждения контекстом."""

    sufficient_evidence: StrictBool
    answers_question: StrictBool
    claims: list[ClaimVerdict]


class TaskError(StrictModel):
    """Предоставляет безопасное описание ошибки фонового задания."""

    code: str
    message: str


class TaskRecord(StrictModel):
    """Состояние задания, хранимое исключительно в Redis."""

    task_id: UUID
    doc_id: UUID
    generation_id: UUID
    status: Literal["queued", "running", "retrying", "succeeded", "failed"] = "queued"
    stage: str = "queued"
    attempt: int = 0
    completed_chunks: int = 0
    total_chunks: int | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    error: TaskError | None = None
    timings_ms: dict[str, float] = Field(default_factory=dict)
