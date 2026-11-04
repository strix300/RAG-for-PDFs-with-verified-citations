"""Общий транспорт LangChain к локальному Ollama со строгим JSON Schema."""

import json
import logging
from time import perf_counter

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, JsonValue
from pydantic.json_schema import JsonSchemaValue
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_random_exponential

from app.core.config import Settings
from app.core.errors import ApplicationError, InvalidGeneration, ServiceUnavailable
from app.core.timing import AnswerTrace, check_deadline

logger = logging.getLogger(__name__)


def ollama_output_schema(schema: type[BaseModel]) -> JsonSchemaValue:
    """Убирает строковые повторы из грамматики, сохраняя ограничения модели Pydantic."""
    schema_json = schema.model_json_schema()

    def remove_string_bounds(value: JsonValue) -> None:
        if isinstance(value, dict):
            if value.get("type") == "string":
                value.pop("minLength", None)
                value.pop("maxLength", None)
            for child in value.values():
                remove_string_bounds(child)
        elif isinstance(value, list):
            for child in value:
                remove_string_bounds(child)

    remove_string_bounds(schema_json)
    return schema_json


def validate_local_model(client: httpx.Client, model: str) -> None:
    """Отклоняет удалённые aliases до отправки вопроса или текста документа."""
    response = client.post("/api/show", json={"model": model})
    response.raise_for_status()
    try:
        metadata = response.json()
    except ValueError as exc:
        raise ApplicationError(
            "local_model_error", "Неверный ответ локального Ollama.", 503,
        ) from exc
    if (
        not isinstance(metadata, dict)
        or metadata.get("remote_host")
        or metadata.get("remote_model")
        or not isinstance(metadata.get("model_info"), dict)
        or not metadata.get("model_info")
    ):
        raise ApplicationError(
            "local_model_required", "Требуется установленная локальная модель Ollama.", 503,
        )


class LocalChat:
    """Использует только настроенный локальный endpoint; сетевой fallback отсутствует."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def complete[Output: BaseModel](
        self, model: str, schema: type[Output], system: str, prompt: str, deadline: float,
        *, trace: AnswerTrace | None = None, phase: str = "generation",
    ) -> Output:
        """Получает JSON, ограничивая время, память контекста и число сетевых повторов."""
        from langchain_ollama import ChatOllama
        from langsmith import tracing_context
        from ollama import ResponseError

        trace = trace if trace is not None else AnswerTrace()
        schema_json = ollama_output_schema(schema)
        upper_bound = len((system + prompt + json.dumps(schema_json)).encode("utf-8")) + 512
        if upper_bound + self.settings.llm_output_tokens > self.settings.ollama_context_tokens:
            raise ApplicationError(
                "context_budget", "Контекст превышает безопасный бюджет локальной модели.", 422,
            )

        def is_transient(exc: BaseException) -> bool:
            if isinstance(exc, httpx.HTTPStatusError):
                return exc.response.status_code in {408, 429, 500, 502, 503, 504}
            return isinstance(exc, (httpx.TransportError, ConnectionError)) or (
                isinstance(exc, ResponseError) and exc.status_code in {408, 429, 500, 502, 503, 504}
            )

        try:
            for attempt in Retrying(
                retry=retry_if_exception(is_transient),
                stop=stop_after_attempt(self.settings.retry_attempts),
                wait=wait_random_exponential(
                    multiplier=self.settings.retry_min_seconds, max=self.settings.retry_max_seconds,
                ), reraise=True,
            ):
                with attempt:
                    check_deadline(deadline)
                    timeout = min(self.settings.llm_timeout, deadline - perf_counter())
                    with httpx.Client(
                        base_url=self.settings.ollama_url, timeout=timeout, trust_env=False,
                    ) as client:
                        with trace.stage(f"{phase}.model_check"):
                            validate_local_model(client, model)
                    check_deadline(deadline)
                    timeout = min(self.settings.llm_timeout, deadline - perf_counter())
                    with httpx.HTTPTransport(trust_env=False) as transport:
                        chat = ChatOllama(
                            base_url=self.settings.ollama_url, model=model, format=schema_json,
                            reasoning=False, temperature=0,
                            num_ctx=self.settings.ollama_context_tokens,
                            num_predict=self.settings.llm_output_tokens,
                            num_gpu=self.settings.ollama_num_gpu,
                            num_thread=self.settings.inference_threads,
                            keep_alive=self.settings.llm_keep_alive,
                            client_kwargs={"timeout": timeout, "trust_env": False},
                            sync_client_kwargs={"transport": transport},
                        )
                        with tracing_context(enabled=False), trace.stage(f"{phase}.llm"):
                            message = chat.invoke(
                                [SystemMessage(content=system), HumanMessage(content=prompt)],
                                stream=False,
                            )
                    check_deadline(deadline)
                    metrics = {
                        key: message.response_metadata.get(key) for key in (
                            "done_reason", "total_duration", "load_duration", "prompt_eval_count",
                            "prompt_eval_duration", "eval_count", "eval_duration",
                        )
                    }
                    logger.info(
                        "ollama_call request_id=%s attempt=%s phase=%s model=%s metrics=%s",
                        trace.request_id, trace.attempt, phase, model, json.dumps(metrics),
                    )
                    if self.settings.llm_log_outputs:
                        logger.info(
                            "ollama_output request_id=%s attempt=%s phase=%s output=%s",
                            trace.request_id, trace.attempt, phase,
                            json.dumps(message.content, ensure_ascii=False),
                        )
                    with trace.stage(f"{phase}.pydantic"):
                        if not isinstance(message.content, str):
                            raise InvalidGeneration("Ответ модели не является JSON-текстом.")
                        return schema.model_validate_json(message.content)
        except (ResponseError, httpx.TransportError, httpx.HTTPStatusError, ConnectionError) as exc:
            if is_transient(exc):
                raise ServiceUnavailable("Ollama") from exc
            raise ApplicationError(
                "local_model_error", "Локальная модель недоступна или несовместима.", 503,
            ) from exc
        raise RuntimeError("Генерация завершилась без результата.")
