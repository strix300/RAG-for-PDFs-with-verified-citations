"""Проверяет совместимость грамматики Ollama без ослабления выходных моделей."""

import json
import sys
from copy import deepcopy
from time import perf_counter
from types import ModuleType
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import BaseModel, JsonValue, ValidationError

from app.core.config import Settings
from app.core.timing import AnswerTrace
from app.infrastructure.local_chat import LocalChat
from app.models import DraftAnswer, GroundingVerdict


class StubResponseError(Exception):
    """Заменяет только исключение отсутствующего SDK в изолированном тесте."""

    status_code: int = 500


@pytest.fixture
def chat_constructor(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """Перехватывает параметры LangChain, не загружая SDK и не выполняя inference."""
    constructor = Mock()
    constructor.return_value.invoke.return_value.response_metadata = {}
    langchain_module = ModuleType("langchain_ollama")
    langchain_module.ChatOllama = constructor
    ollama_module = ModuleType("ollama")
    ollama_module.ResponseError = StubResponseError
    monkeypatch.setitem(sys.modules, "langchain_ollama", langchain_module)
    monkeypatch.setitem(sys.modules, "ollama", ollama_module)
    monkeypatch.setattr("app.infrastructure.local_chat.validate_local_model", Mock())
    return constructor


@pytest.mark.parametrize("schema,payload", [
    (DraftAnswer, {"found": False, "claims": []}),
    (GroundingVerdict, {
        "sufficient_evidence": False, "answers_question": False, "claims": [],
    }),
])
def test_sent_schema_only_removes_string_bounds(
    chat_constructor: Mock, schema: type[BaseModel], payload: dict[str, JsonValue],
) -> None:
    original = schema.model_json_schema()
    expected = deepcopy(original)
    if schema is DraftAnswer:
        for definition, field in (("Claim", "text"), ("Evidence", "quote")):
            del expected["$defs"][definition]["properties"][field]["minLength"]
            del expected["$defs"][definition]["properties"][field]["maxLength"]
    chat_constructor.return_value.invoke.return_value.content = json.dumps(payload)
    settings = Settings()

    result = LocalChat(settings).complete(
        settings.generation_model, schema, "Инструкция", "Вопрос", perf_counter() + 30,
    )

    sent_schema = chat_constructor.call_args.kwargs["format"]
    assert sent_schema == expected
    assert '"minLength"' not in json.dumps(sent_schema)
    assert '"maxLength"' not in json.dumps(sent_schema)
    assert schema.model_json_schema() == original
    assert result == schema.model_validate(payload)


@pytest.mark.parametrize("field,length", [
    ("text", 0), ("text", 1501), ("quote", 0), ("quote", 4001),
])
def test_original_string_limits_reject_model_output(
    chat_constructor: Mock, field: str, length: int,
) -> None:
    evidence = {"fragment_id": str(uuid4()), "quote": "Точная цитата."}
    claim: dict[str, JsonValue] = {"text": "Утверждение.", "evidence": [evidence]}
    if field == "text":
        claim["text"] = "я" * length
    else:
        evidence["quote"] = "я" * length
    chat_constructor.return_value.invoke.return_value.content = json.dumps({
        "found": True, "claims": [claim],
    })
    settings = Settings()

    with pytest.raises(ValidationError) as error:
        LocalChat(settings).complete(
            settings.generation_model, DraftAnswer, "Инструкция", "Вопрос", perf_counter() + 30,
        )

    failure = error.value.errors()[0]
    assert failure["type"] == ("string_too_short" if length == 0 else "string_too_long")
    assert failure["loc"][-1] == field


def test_original_verifier_constraints_reject_model_output(chat_constructor: Mock) -> None:
    chat_constructor.return_value.invoke.return_value.content = json.dumps({
        "sufficient_evidence": True, "answers_question": True,
        "claims": [{"claim_index": -1, "supported": True}],
    })
    settings = Settings()

    with pytest.raises(ValidationError) as error:
        LocalChat(settings).complete(
            settings.verification_model, GroundingVerdict,
            "Инструкция", "Вопрос", perf_counter() + 30,
        )

    assert error.value.errors()[0]["loc"] == ("claims", 0, "claim_index")


@pytest.mark.parametrize("log_outputs", [False, True])
def test_llm_observability_keeps_outputs_opt_in(
    chat_constructor: Mock, caplog: pytest.LogCaptureFixture, log_outputs: bool,
) -> None:
    caplog.set_level("INFO")
    output = '{"sufficient_evidence":false,"answers_question":false,"claims":[]}'
    chat_constructor.return_value.invoke.return_value.content = output
    chat_constructor.return_value.invoke.return_value.response_metadata = {
        "eval_count": 21, "done_reason": "stop",
    }
    settings = Settings(llm_log_outputs=log_outputs)
    trace = AnswerTrace(attempt=2)

    LocalChat(settings).complete(
        settings.verification_model, GroundingVerdict, "Инструкция", "Вопрос",
        perf_counter() + 30, trace=trace, phase="grounding_verification",
    )

    assert '"eval_count": 21' in caplog.text
    assert "attempt=2 phase=grounding_verification" in caplog.text
    assert ("ollama_output" in caplog.text) is log_outputs
    assert "attempt_2.grounding_verification.llm" in trace.timings
    assert "attempt_2.grounding_verification.pydantic" in trace.timings
