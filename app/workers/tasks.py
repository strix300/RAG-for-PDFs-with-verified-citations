"""Исполняет идемпотентные задания и восстанавливает прерванные попытки."""

import json
import logging
from time import perf_counter
from uuid import UUID

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from app.core.config import Settings
from app.core.constants import TERMINAL_STATUSES
from app.core.errors import ApplicationError, ServiceUnavailable
from app.infrastructure.files import FileStore
from app.infrastructure.qdrant import QdrantStore
from app.infrastructure.task_state import TaskState
from app.models import DocumentRecord, TaskError, TaskRecord
from app.services.indexing import IndexingService
from app.workers.celery_app import celery_app
from app.workers.publishing import enqueue_indexing

logger = logging.getLogger(__name__)


def complete_published_task(record: TaskRecord, document: DocumentRecord, state: TaskState) -> None:
    """Согласует состояние задания с уже опубликованным поколением Qdrant."""
    record.status = "succeeded"
    record.stage = "completed"
    record.error = None
    record.total_chunks = document.chunk_count
    record.completed_chunks = document.chunk_count or 0
    state.save(record)


@celery_app.task(bind=True, name="document_rag.index", max_retries=None)
def index_document(self: Task, doc_id: str, generation_id: str) -> None:
    """Завершает задание только после успешной публикации проверенного поколения."""
    settings = Settings()
    state = TaskState(settings)
    store = QdrantStore(settings)
    record: TaskRecord | None = None
    started = perf_counter()
    previous_total = 0.0
    try:
        with state.document_lease(UUID(doc_id), wait=5) as lease:
            record = state.get(UUID(self.request.id))
            if record is None:
                logger.warning("unknown_or_expired_task task_id=%s", self.request.id)
                return
            previous_total = record.timings_ms.get("total", 0.0)
            if record.status in TERMINAL_STATUSES:
                return
            document = store.get_document(UUID(doc_id))
            if document is None:
                raise ApplicationError("document_not_found", "Документ удалён.", 404)
            if document.active_generation == record.generation_id:
                complete_published_task(record, document, state)
                return
            if record.attempt >= settings.task_max_attempts:
                raise ApplicationError("attempts_exhausted", "Исчерпаны попытки индексации.", 503)
            record.attempt += 1
            record.status = "running"
            record.error = None
            state.save(record)
            service = IndexingService(settings, store, state, FileStore(settings))
            service.run(document, record, lease)
            lease.ensure_owned()
            record.status = "succeeded"
            record.stage = "completed"
            record.timings_ms["total"] = (
                previous_total + (perf_counter() - started) * 1000
            )
            state.save(record)
    except ServiceUnavailable as exc:
        if record is not None:
            record.timings_ms["total"] = (
                previous_total + (perf_counter() - started) * 1000
            )
            document = store.get_document(record.doc_id)
            if document and document.active_generation == record.generation_id:
                complete_published_task(record, document, state)
                return
            record.error = TaskError(code=exc.code, message=exc.message)
            record.status = "retrying" if record.attempt < settings.task_max_attempts else "failed"
            state.save(record)
            if record.status == "failed":
                raise
        elif self.request.retries >= settings.task_max_attempts:
            raise
        raise self.retry(exc=exc, countdown=min(2 ** (self.request.retries + 1), 30))
    except (ApplicationError, SoftTimeLimitExceeded) as exc:
        if record is not None:
            record.timings_ms["total"] = (
                previous_total + (perf_counter() - started) * 1000
            )
            if isinstance(exc, SoftTimeLimitExceeded):
                document = store.get_document(record.doc_id)
                if document and document.active_generation == record.generation_id:
                    complete_published_task(record, document, state)
                    return
            record.status = "failed"
            record.error = TaskError(
                code=exc.code if isinstance(exc, ApplicationError) else "indexing_timeout",
                message=(
                    exc.message if isinstance(exc, ApplicationError)
                    else "Истекло время индексации."
                ),
            )
            state.save(record)
        raise
    except Exception:
        logger.exception("unexpected_indexing_failure doc_id=%s", doc_id)
        if record is not None:
            record.timings_ms["total"] = (
                previous_total + (perf_counter() - started) * 1000
            )
            record.status = "failed"
            record.error = TaskError(
                code="indexing_failed", message="Внутренняя ошибка индексации.",
            )
            state.save(record)
        raise
    finally:
        if record is not None:
            logger.info(
                "index_timing task_id=%s timings_ms=%s",
                record.task_id, json.dumps(record.timings_ms),
            )
        store.close()
        state.close()


@celery_app.task(name="document_rag.reconcile")
def reconcile_indexing() -> None:
    """Восстанавливает известные активные задания после истечения максимального времени попытки."""
    settings = Settings()
    state = TaskState(settings)
    store = QdrantStore(settings)
    try:
        for record in state.stale_tasks():
            try:
                with state.document_lease(record.doc_id) as lease:
                    current = state.get(record.task_id)
                    if current is None or current.status in TERMINAL_STATUSES:
                        continue
                    document = store.get_document(record.doc_id)
                    if document and document.active_generation == record.generation_id:
                        complete_published_task(current, document, state)
                        continue
                    elif document is None or current.attempt >= settings.task_max_attempts:
                        current.status = "failed"
                        current.error = TaskError(
                            code="worker_lost",
                            message="Задание не завершилось после восстановления.",
                        )
                    else:
                        current.status = "queued"
                        lease.ensure_owned()
                        state.save(current)
                        enqueue_indexing(current.doc_id, current.generation_id, current.task_id)
                        continue
                    state.save(current)
            except ServiceUnavailable:
                logger.warning("reconciliation_deferred task_id=%s", record.task_id)
    finally:
        store.close()
        state.close()
