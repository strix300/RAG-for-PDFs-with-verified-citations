"""Неизменяемые соглашения о данных и идентификаторах."""

from uuid import UUID

DENSE_VECTOR = "dense"
SPARSE_VECTOR = "bm25"
POINT_NAMESPACE = UUID("db891af8-f1b2-4ba5-8d38-d60fca98bd12")
PAGE_SEPARATOR = "\f"
MAX_DOCUMENT_PAGES = 100
PIPELINE_VERSION = "1"
NOT_FOUND_ANSWER = "В документе не найдено сведений, достаточных для ответа на вопрос."
TERMINAL_STATUSES = frozenset({"succeeded", "failed"})
