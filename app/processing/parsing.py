"""Извлекает текст PDF постранично; OCR намеренно отсутствует."""

from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.core.config import Settings
from app.core.constants import MAX_DOCUMENT_PAGES, PAGE_SEPARATOR
from app.core.errors import ApplicationError
from app.models import Page


def parse_pdf(path: Path, settings: Settings) -> list[Page]:
    """Возвращает текст всех страниц или ошибку с номером нечитаемой страницы.

    Raises:
        ApplicationError: PDF повреждён, зашифрован, слишком велик или требует OCR.
    """
    try:
        with path.open("rb") as source:
            reader = PdfReader(source)
            if reader.is_encrypted:
                raise ApplicationError("encrypted_pdf", "Зашифрованные PDF не поддерживаются.")
            if not 1 <= len(reader.pages) <= MAX_DOCUMENT_PAGES:
                raise ApplicationError("page_limit", "Допускается PDF от 1 до 100 страниц.")
            pages: list[Page] = []
            offset = 0
            for number, original in enumerate(reader.pages, start=1):
                text = original.extract_text() or ""
                if not text.strip():
                    raise ApplicationError(
                        "page_without_text",
                        f"На странице {number} нет извлекаемого текста. OCR не поддерживается.",
                    )
                if (
                    len(text) > settings.max_page_chars
                    or offset + len(text) > settings.max_document_chars
                ):
                    raise ApplicationError(
                        "text_limit", "Превышен допустимый объём извлечённого текста.",
                    )
                pages.append(Page(number=number, text=text, char_start=offset))
                offset += len(text) + len(PAGE_SEPARATOR)
            return pages
    except (PdfReadError, ValueError, OSError) as exc:
        raise ApplicationError("invalid_pdf", "Не удалось прочитать исходный PDF.") from exc
