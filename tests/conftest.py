"""Небольшие исходные данные для проверки поведения без загрузки моделей."""

from uuid import uuid4

import pytest

from app.models import Candidate, Chunk


@pytest.fixture
def context() -> list[Candidate]:
    """Предоставляет неизменённый русский фрагмент с доверенными координатами."""
    text = "4.2 Штрафные санкции\nНеустойка составляет 0,1% за каждый день просрочки."
    return [Candidate(fragment_id=uuid4(), fusion_score=0.05, rerank_score=0.8, chunk=Chunk(
        doc_id=uuid4(), doc_title="Договор", generation_id=uuid4(), index_profile="profile",
        chunk_index=0, page_from=12, page_to=12, section="4.2 Штрафные санкции",
        text=text, char_start=100, char_end=100 + len(text),
    ))]
