"""Проверяет отклонение страниц без текста и превышения лимита страниц."""

from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.errors import ApplicationError


@pytest.mark.parametrize("pages,code", [(1, "page_without_text"), (101, "page_limit")])
def test_blank_or_oversized_pdf(tmp_path: Path, pages: int, code: str) -> None:
    pypdf = pytest.importorskip("pypdf", reason="Требуется parser из зависимостей проекта")
    from app.processing.parsing import parse_pdf

    path = tmp_path / "document.pdf"
    writer = pypdf.PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=300, height=300)
    with path.open("wb") as target:
        writer.write(target)
    with pytest.raises(ApplicationError) as error:
        parse_pdf(path, Settings())
    assert error.value.code == code
