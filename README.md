# Document RAG: полностью локальный backend

FastAPI принимает PDF до 100 страниц. Celery индексирует его через Redis. Фрагменты
в одной коллекции Qdrant содержат dense и BM25 векторы. Ответ строится из результатов
одного hybrid query с двумя `Prefetch` и `FusionQuery(RRF)`, после обязательного
переранжирования. Каждое утверждение проходит проверку цитат и отдельный вызов
локальной LLM-проверяющего. Истории диалога нет.

## Системные требования

Ориентиры для текущей конфигурации с контекстом 16384 токена и одним одновременно
выполняемым pipeline:

| Ресурс | Требование |
|---|---|
| CPU | От 4 ядер |
| RAM | От 16 ГБ; для разработки и сборки рекомендуется 24–32 ГБ |
| GPU | Поддержка CUDA 12.6, от 10 ГБ видеопамяти |
| Диск | От 40 ГБ свободного места для образов, весов и данных |
| Среда запуска | Linux с Docker Engine или Windows с Docker Desktop и WSL2, Linux-контейнеры |
| Docker Compose | v2.24+ |
| Python для нативной разработки | 3.12 |

Это ориентиры по ресурсам, а не измеренные минимумы или SLA. Расход памяти зависит
от контекста, размера документов и других процессов. В Docker Desktop учитывайте
отдельный лимит памяти WSL2 и оставляйте ресурсы операционной системе.
Драйвер с поддержкой CUDA 12.6 устанавливается на хосте. На Linux для доступа
контейнеров к GPU нужен
[NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html);
на Windows — поддержка GPU в WSL2.
См. [GPU в Docker Desktop](https://docs.docker.com/desktop/features/gpu/) и
[выделение GPU в Compose](https://docs.docker.com/compose/how-tos/gpu-support/).

## Модели и конфигурация

| Этап | Модель по умолчанию | Runtime |
|---|---|---|
| Dense | `intfloat/multilingual-e5-small`, 384 измерения | LangChain HuggingFaceEmbeddings, Sentence Transformers/PyTorch, CUDA FP32 |
| Sparse | `Qdrant/bm25`, русский stemmer | LangChain FastEmbedSparse, FastEmbed, CPU; IDF в Qdrant |
| Реранкер | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` | Sentence Transformers CrossEncoder, CUDA FP32 |
| Генерация | `qwen2.5:7b-instruct-q4_K_M` | Локальный Ollama, LangChain ChatOllama |
| Семантическая проверка | `qwen2.5:7b-instruct-q4_K_M` | Отдельный вызов и отдельный GroundingVerifier |

E5 получает обязательные `query: ` / `passage: ` префиксы, включая русские тексты.
BM25 — алгоритм BM25. Документы и вопросы могут быть многоязычными;
автоматического перевода нет. Все модели и лимиты настраиваются в `app/core/config.py`
и через `.env`; полный пример текущей конфигурации — `.env.example`.

Все вычисления локальны. Платные API и облачные модели не используются.
`RAG_API_KEY` защищает собственный HTTP API; он не связан с оплатой моделей.
Интернет нужен только для установки зависимостей и явной загрузки публичных весов.
При запросах используются локальные каталоги и `local_files_only=True`; tracing
LangSmith отключён на границе вызова LLM. Публичные Ollama endpoints и cloud-теги
отклоняются настройками. Перед inference `/api/show` проверяется на remote-модель,
включая локально названный alias; при отсутствии локальных model metadata запрос отклоняется.
Compose фиксирует Ollama `0.17.7` и отключает cloud-функции через `OLLAMA_NO_CLOUD=1`.

По умолчанию `RAG_MODEL_DEVICE=cuda`, `RAG_OLLAMA_NUM_GPU=-1`.
PyTorch зафиксирован на 2.14.1 / CUDA 12.6. API, worker и Ollama получают доступ к GPU;
scheduler использует тот же образ приложения без выделения GPU.
Веса dense и реранкера загружаются последовательно и освобождаются после этапа.
Ollama сохраняет LLM в памяти на 5 минут, поэтому генерация и verifier используют
одни загруженные веса. Это кеш модели; каждый вопрос обрабатывается независимо.

Контекст — 16384 токена, максимальный вывод — 1200 токенов, лимит фрагментов — 8000 байт.
Это ограничения памяти и длины запроса. Перед вызовом учитывается полный запрос:
инструкции, вопрос, JSON Schema и фактическое представление фрагментов.
Flash Attention включён, KV cache — `f16`. Batch dense — 16, реранкера — 8.
Redis и файловая блокировка в общем томе ограничивают число inference pipeline между API и worker:
`RAG_INFERENCE_SLOTS=1`. Параллелизм Ollama, число загруженных LLM и worker concurrency
тоже равны 1. Повышение лимитов увеличивает расход памяти.
Один pipeline может ждать свободного слота только ограниченное время.

Источники: [E5-small](https://huggingface.co/intfloat/multilingual-e5-small),
[реранкер](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1),
[Qwen2.5 7B Instruct Q4_K_M](https://ollama.com/library/qwen2.5:7b-instruct-q4_K_M),
[структурированный вывод Ollama](https://docs.ollama.com/capabilities/structured-outputs).

## Запуск в Docker

Из корня репозитория:

```sh
cp .env.example .env
docker compose --profile app --profile inference build
docker run --rm -v "${PWD}:/workspace" -w /workspace document-rag:cuda rag init-api-key
docker compose --profile inference up -d redis qdrant ollama
docker compose --profile app run --rm api rag download-models
docker compose --profile app run --rm api rag init
docker compose --profile app --profile inference up -d --no-build
docker compose exec -T api rag doctor
```

В PowerShell вместо `cp` можно использовать `Copy-Item .env.example .env`.
Если `.env` уже существует, перенесите нужные параметры из примера, сохранив свои настройки.
Итоговую конфигурацию проверяют командой
`docker compose --profile app --profile inference config`.
`download-models` скачивает все четыре набора весов, включая обе настроенные LLM,
через локальный Ollama. Если генератор и verifier используют одну модель, повторной
загрузки весов нет. Каталоги Docker volumes `models` и `ollama` сохраняются между
перезапусками. `rag doctor` проверяет хранилища и наличие моделей; это не тест качества ответов.

Проверка доступа контейнеров к GPU:

```sh
docker compose exec -T ollama nvidia-smi
docker compose exec -T api python -c "import torch; assert torch.cuda.is_available(); print(torch.__version__)"
docker compose exec -T ollama ollama ps
```

После запроса `ollama ps` должен показывать `100% GPU`, а логи Ollama — полное
размещение слоёв на GPU. `num_gpu=-1` сам по себе не подтверждает фактическое размещение.

API: `http://localhost:8000`, OpenAPI: `/docs`. Порты Redis, Qdrant и Ollama привязаны
к loopback хоста. Не используйте `docker compose down -v`, если нужно сохранить документы:
эта команда явно удаляет все volumes.

Compose фиксирует Qdrant `1.17.0` и совместимую ветку клиента `1.17.x`.
Проверенные Python-зависимости фиксируются в `requirements.lock`; Docker использует этот
набор при сборке. Обновлять lock следует вместе с проверками моделей и аудитом зависимостей.

## Нативная разработка

Поддерживаемый Python — **3.12**. Для Celery worker нужна Linux-среда; на Windows
используйте WSL2. Команды ниже рассчитаны на Linux/WSL2:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install 'torch==2.14.1' --index-url https://download.pytorch.org/whl/cu126
python -m pip install -e '.[dev]'
cp .env.example .env
rag init-api-key
docker compose up -d redis qdrant
OLLAMA_NO_CLOUD=1 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1 OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=f16 OLLAMA_KEEP_ALIVE=5m ollama serve
```

`ollama serve` запускается в отдельном терминале. Если Ollama уже работает как приложение,
используйте существующий сервер с такими же настройками. Затем:

```sh
rag download-models
rag init
rag doctor
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

В отдельных терминалах с тем же `.env` и активированной `.venv`:

```sh
celery -A app.workers.celery_app:celery_app worker --loglevel=INFO
celery -A app.workers.celery_app:celery_app beat --loglevel=INFO --schedule=.data/celerybeat-schedule
```

Для ручной загрузки LLM: `ollama pull qwen2.5:7b-instruct-q4_K_M`.
`rag download-models` дополнительно загружает E5, реранкер и BM25.
Весам не нужны приватные credentials. Настройка `RAG_MODEL_CACHE_DIR` задаёт постоянный
каталог. Если ID или revision модели меняется, используйте новый каталог кеша и
контролируемую переиндексацию; существующий кеш не перезаписывается молча.

## API

Запросы к документам и задачам требуют `Authorization: Bearer <RAG_API_KEY>`.
Ключ создаётся командой `rag init-api-key` и сохраняется в локальном `.env` без вывода
в терминал. Повтор команды сохраняет существующий ключ. Без ключа API не запускается.
Все обладатели ключа имеют доступ ко всем документам одной установки. В `/docs` ключ
вводится через **Authorize**. `/health/live` и `/health/ready` доступны без ключа.
В примерах переменная оболочки `RAG_API_KEY` должна содержать значение из `.env`.

Все UUID в примерах заменяются полученными значениями. Примеры JSON ниже показывают
контракт, **а не результат выполненного inference в текущей среде**.

### Загрузка

```sh
curl -X POST http://localhost:8000/documents \
  -H "Authorization: Bearer $RAG_API_KEY" \
  -H 'Idempotency-Key: upload-contract-001' \
  -F 'title=Договор поставки' -F 'file=@contract.pdf;type=application/pdf'
```

`202` после подтверждённой отправки задания либо обращения к уже существующему документу:

```json
{
  "doc_id": "ad46dc3b-334b-4cb1-9807-a38cd2802812",
  "task_id": "04d57902-b97c-4e25-a06d-5ebdd0a0769f",
  "status_url": "/tasks/04d57902-b97c-4e25-a06d-5ebdd0a0769f"
}
```

Одинаковые байты **и точный заголовок** переиспользуют документ. Другой заголовок создаёт
другой логический документ. HTTP `Idempotency-Key` — отдельная запись с собственной
проверкой сигнатуры; повтор ключа с другим запросом возвращает `409`. Если доставка
в broker имеет неопределённый результат, повторяется тот же task ID. Сам Celery не
дедуплицирует task ID: безопасность обеспечивают блокировка и идемпотентная индексация.

### Статус и список

```sh
curl -H "Authorization: Bearer $RAG_API_KEY" http://localhost:8000/tasks/TASK_ID
curl -H "Authorization: Bearer $RAG_API_KEY" 'http://localhost:8000/documents?limit=20'
```

Статусы: `queued`, `running`, `retrying`, `succeeded`, `failed`. Ответ содержит `stage`,
`attempt`, `completed_chunks`, `total_chunks`, `timings_ms` и безопасный `error`.
Процент выполнения не выдумывается. Неизвестные/истёкшие задания возвращают `404`, не `PENDING`.

Список возвращает `items` и `next_cursor`. Каталог хранится в Qdrant, поэтому документ
не исчезает после истечения Redis task record. `ready` определяется опубликованным
поколением. Для неготового документа без сохранившейся task record возвращается
`status_expired`; подробности прежней ошибки после срока хранения недоступны.

### Вопрос

```sh
curl -X POST 'http://localhost:8000/documents/DOC_ID/questions?diagnostics=true' \
  -H "Authorization: Bearer $RAG_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"question":"Какова неустойка по пункту 4.2?"}'
```

Пример контракта успешного ответа:

```json
{
  "answer": "Неустойка составляет 0,1% за каждый день просрочки.",
  "found": true,
  "citations": [
    {
      "fragment_id": "8de12178-010e-4fd5-a07c-f2a864679cb5",
      "doc_id": "ad46dc3b-334b-4cb1-9807-a38cd2802812",
      "doc_title": "Договор поставки",
      "text": "Неустойка составляет 0,1% за каждый день просрочки.",
      "page": 12,
      "section": "4.2 Штрафные санкции",
      "char_start": 2500,
      "char_end": 2551
    }
  ]
}
```

Вопрос без сведений в документе, например о банковском счёте в тестовом PDF:

```json
{
  "answer": "В документе не найдено сведений, достаточных для ответа на вопрос.",
  "found": false,
  "citations": []
}
```

При `diagnostics=true` добавляется отдельный объект: измеренные `dense_candidates`,
`sparse_candidates`, `fusion_candidates`, числа входных/выходных кандидатов реранкера,
`reranked_candidates`, точные `context_fragments` и `timings_ms`.
`branch_measurement=separate_queries`: Qdrant не возвращает внутренние prefetch counts.
Дополнительные запросы измеряют ветви повторно, с теми же фильтрами и лимитами; их
результаты **никогда** не используются для генерации. Это не telemetry исходного prefetch.
Время `retrieval` при включённой диагностике включает эти дополнительные измерения.
Без диагностики выполняется ровно один retrieval query с двумя Prefetch и FusionQuery.
`RAG_FUSION=rrf` выбирает RRF, `RAG_FUSION=dbsf` — DBSF.
Чтение каталога по ID является отдельной metadata-операцией, не поисковой ветвью.

### Явное удаление

```sh
curl -X DELETE -H "Authorization: Bearer $RAG_API_KEY" http://localhost:8000/documents/DOC_ID
```

`204` удаляет оригинал, каталог и все поколения. Активное индексирование защищено
блокировкой; при нём удаление возвращает `409`/`503`, его можно повторить позже.
Источники и индексированные данные не удаляются автоматически. Терминальные task
records по умолчанию хранятся 7 дней (`RAG_TERMINAL_TASK_TTL=604800`); активные — без TTL.

Основные ошибки: `401` — неверный ключ, `408` — таймаут чтения тела,
`429` — заняты доступные обработчики, `413` — размер тела, `415` — не PDF,
`422` — некорректный ввод или
недопустимый размер контекста, `404` — неизвестный ресурс, `409` — индекс не готов или
конфликт, `503` — инфраструктура/модель недоступна, `504` — deadline, `502` — ответ не
прошёл полный цикл проверки. Сбой инфраструктуры никогда не превращается в `found=false`.

## Проверка и воспроизводимый пример

При установленных зависимостях:

```sh
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy app
python -m pip check
python -m pip_audit -r requirements.lock --no-deps --disable-pip
```

Проверки с настоящими сервисами и моделями включаются явно:

```sh
RAG_RUN_INTEGRATION=1 python -m pytest tests/integration/test_qdrant.py
RAG_RUN_STACK_TESTS=1 python -m pytest tests/integration/test_worker.py
RAG_RUN_MODEL_TESTS=1 python -m pytest tests/integration/test_ollama.py
RAG_RUN_GPU_TESTS=1 python -m pytest tests/integration/test_gpu.py
RAG_RUN_HANDBOOK_TESTS=1 python -m pytest tests/integration/test_handbook.py
```

Для PowerShell задайте соответствующий флаг, например `$env:RAG_RUN_INTEGRATION='1'`,
перед командой `python -m pytest`. Qdrant-тест создаёт и удаляет собственную коллекцию
`test_<uuid>`. Worker-тест проверяет асинхронную ошибку страницы без текста.
Модельные проверки требуют загруженных локальных весов и работающего Ollama.
`test_gpu.py` проверяет фактическое устройство dense/реранкера, в том числе выполнение
на CPU, полное размещение LLM на GPU и реальную коррекцию ошибочной цитаты.

Все проверки можно запустить в одноразовом контейнере при работающем стеке.
PowerShell:

```powershell
docker compose run --rm --no-deps --user root `
  -v "${PWD}:/workspace:ro" -v "${PWD}/.data:/results" -e PYTHONPATH=/service `
  -e RAG_RUN_INTEGRATION=1 -e RAG_RUN_STACK_TESTS=1 -e RAG_RUN_MODEL_TESTS=1 `
  -e RAG_RUN_GPU_TESTS=1 -e RAG_TEST_API_URL=http://api:8000 `
  -e RAG_RUN_HANDBOOK_TESTS=1 -e RAG_TEST_REPORT_DIR=/results/handbook/http `
  api sh -c "pip install 'pytest>=8.3,<10' 'fakeredis[lua]>=2.28,<3' && python -m pytest -q /workspace/tests -o cache_dir=/tmp/pytest-cache -o junit_family=xunit1 --junitxml=/results/tests.xml"
```

HTTP-пример для запущенного стека:

```sh
python scripts/create_example.py .data/example.pdf
python scripts/smoke.py .data/example.pdf --output .data/smoke-results.json --warm
```

`create_example.py` создаёт небольшой читаемый английский PDF со стандартным шрифтом:
пункт `4.2`, ставка `0.1%`, стороны и дата. Русские вопросы в `smoke.py` дополнительно
проверяют multilingual retrieval. Русские фрагменты, цитаты и повторяющийся текст
проверяются unit-тестами. Скрипт сохраняет реальные ответы, состояния и измерения,
проверяет найденный ответ по точному обозначению и отсутствие сведений о счёте.
Документ после smoke сохраняется согласно политике retention; удалить его можно по
`doc_id` из отчёта.

Замер HTTP pipeline с мониторингом GPU выполняется отдельно от тестов. PowerShell:

```powershell
New-Item -ItemType Directory -Force .data/gpu-benchmark
docker compose run --rm --no-deps `
  -v "${PWD}/scripts:/service/scripts:ro" -v "${PWD}/.data:/results" `
  -e PYTHONPATH=/service api python scripts/benchmark_gpu.py --output-dir /results/gpu-benchmark
```

`answers.json` содержит индексацию, измерения стадий, найденный ответ, отказ
при отсутствии сведений и повторный запрос. `gpu.csv` содержит выборки каждые 250 мс,
`gpu-summary.json` — выборочные максимумы использования всей GPU, включая другие процессы.
Результаты сохраняются локально в `.data/`, исключённом из Git.

Регрессии `test_handbook.py` используют `severny_kontur_operational_handbook.pdf` и
`rag_test_answer_key.txt` из корня. Вопросы читаются из `rag_test_questions.txt`, если
он присутствует, иначе из ключа. Ключ используется только для оценки результатов.
Тесты создают собственный документ с текущим профилем индекса и удаляют его после проверки.
Проверяются ответы Q1–Q25, отказы для Q26–Q30 и дословное совпадение
цитат с исходными страницами PDF. Дополнительный локальный LLM-оценщик проверяет
смысловую полноту относительно эталона. Он не входит в приложение и не передаёт эталон в RAG.

## Границы компонентов и достоверности

`api` содержит HTTP-маршруты и защиту запросов; общие контракты находятся в `contracts.py`.
`services` содержит сценарии документов, индексации и ответа;
`processing` — PDF parsing и LangChain splitting; `infrastructure` — Qdrant, Redis,
файлы и локальные модели; `workers` — Celery. Конфигурация централизована в
`core/config.py`, неизменяемые соглашения — в `core/constants.py`.

Каталог использует `vector={}`; фрагменты содержат оба именованных вектора. Нулевые
или фиктивные векторы для каталога не создаются. При инициализации выполняется
реальная запись/чтение/удаление payload-only probe. Поддержка подтверждена
[документацией Qdrant](https://qdrant.tech/documentation/faq/qdrant-fundamentals/);
probe дополнительно проверяет конкретную запущенную версию. Все ветви фильтруются
по `record_type=chunk`, `doc_id` и `generation_id`. Для фильтров созданы payload indexes.
IDF вычисляется Qdrant по коллекции, а не отдельно для выбранного документа. Сохранённые
поколения также могут влиять на эту статистику. Фильтры изолируют возвращаемые фрагменты,
но не превращают collection-wide IDF в document-local BM25.

Страницы без извлекаемого текста, включая пустые, отклоняются с номером страницы;
OCR отсутствует. Parser сохраняет текст, который способен извлечь pypdf. Сложные
таблицы, колонки и страницы с частичным текстовым слоем требуют проверки на реальных
документах: текстовый слой не гарантирует правильный порядок чтения. Heading detection
консервативно распознаёт нумерованные строки; отсутствующий section не придумывается.
Номер страницы — физический индекс PDF от 1, не напечатанная метка.

PDF разбирается в отдельном процессе: `RAG_PDF_PARSE_TIMEOUT` ограничивает время,
`RAG_PDF_MEMORY_LIMIT_MB` — адресное пространство процесса в Linux. Эти ограничения
действуют до извлечения текста. Ограничения длины текста проверяются дополнительно.
Поддерживаемая среда сервиса — Linux-контейнеры; Windows без WSL не обеспечивает лимит памяти parser.

`char_start` / `char_end` — полуинтервал Unicode-символов в канонической последовательности
извлечённых страниц, соединённых `\f`. Чанк не пересекает страницу. Отдельные представления
для embedding не изменяют исходный текст цитат.

В `format` Ollama передаётся отдельная JSON Schema без строковых `minLength`/`maxLength`:
большие ограниченные повторы могут превышать предел grammar parser. Остальные ограничения
грамматики сохраняются. Ответ по-прежнему проверяется исходными моделями Pydantic,
включая непустые строки, лимит 1500 символов для тезиса и 4000 для цитаты. Адаптация
применяется одинаково к генератору и verifier и не меняет правила принятия ответа.

LLM генератора возвращает утверждения и выбирает `quote_id` из предложенных исходных
отрывков. Отрывки — точные срезы уже отобранных реранкером фрагментов, включая внутренние
переносы строк. Генератор проверяет выбранные ID и восстанавливает `fragment_id` и `quote`
из доверенного контекста, затем создаёт исходный `DraftAnswer`. Текст модели не исправляется
и не сопоставляется нечётко с источником. Далее:

1. Pydantic проверяет схему и согласованность `found`.
2. Каждый ID проверяется по реально переданному LLM контексту.
3. Каждая цитата проверяется как точная подстрока исходного фрагмента. Метаданные
   восстанавливаются из доверенных Qdrant payloads до семантической проверки.
4. Отдельная локальная LLM проверяет поддержку **каждого** утверждения его evidence,
   ответ на вопрос и достаточность контекста; проверяются и ответы `found=false`.
5. При отказе разрешена ровно одна коррекция, после неё повторяются все проверки.
6. Ответ выдаётся только после успешной проверки. Итоговый текст собирается сервером
   из проверенных утверждений. Лишние поля модели, например придуманные страницы, запрещены.

Verifier получает исходный текст один раз и ссылки утверждений на точные сегменты цитат.
Пересекающиеся и повторные свидетельства сохраняют границы без многократной передачи текста.
Ответ, оборванный лимитом вывода модели, также отклоняется и допускает одну коррекцию.

Семантическая проверка сама вероятностная. Совпадение цитаты не доказывает entailment;
для оценки качества нужны реальные русские документы и размеченные вопросы. При
сомнении pipeline должен отклонять ответ, но абсолютной гарантии отсутствия ошибок
малой LLM этот проект не заявляет.

## Отказы, переиндексация и эксплуатация

Фрагменты записываются под стабильным generation ID и детерминированными UUID.
Повтор задания перезаписывает те же точки. Перед публикацией проверяются полный
набор фрагментов, payload и оба вектора. Публикация — одно обновление каталога,
условное по ожидаемому generation ID и отсутствию удаления. Старое поколение остаётся
доступно до переключения; частично сохранённое не участвует в поиске. Старые поколения
хранятся до явного удаления документа.

```sh
rag reindex DOC_ID
```

Это внутренняя maintenance-команда; публичного reindex endpoint нет. Активное задание
нельзя заменить. Модель, revision, chunking и версии библиотек индексации входят в `index_profile`; несовместимый
профиль обнаруживается до ответа. Смена размерности требует отдельной согласованной
миграции коллекции: приложение никогда не удаляет и не пересоздаёт её автоматически.
При переиндексации с тем же профилем прежнее поколение остаётся доступным. Если
настройки embedding/chunking уже изменены, API возвращает `409` до публикации
совместимого поколения. Переключение моделей без перерыва в обслуживании не заявляется.

Redis хранит регистрацию до публикации Celery. Повторные доставки защищены блокировкой
документа. Lease продлевается; потеря владения прерывает работу перед публикацией.
Периодическое восстановление обрабатывает известные активные задания после
`RAG_STALE_TASK_SECONDS`, превышающего hard time limit. Если worker погиб после
публикации, существующее поколение распознаётся без повторной индексации.
Ошибка повторной проверки Qdrant или записи Redis не отменяет Celery retry. Если на последней
попытке результат публикации неизвестен, задание остаётся для последующей сверки.
Файловая блокировка inference удерживается до выхода из операции даже при потере Redis lease.
Это защита одной установки с общим локальным томом, а не распределённая блокировка для разных узлов.
Сквозной транзакции Redis/Qdrant/файловой системы и exactly-once гарантии нет.
Сбой до регистрации/подтверждения upload восстанавливается повтором того же запроса.

Qdrant и LLM повторяются только при временных сетевых ошибках/выбранных 5xx/429,
с ограниченным числом попыток и backoff. Неверный PDF, размерность, схема и постоянные
ошибки не повторяются как сетевые. Timeouts и количество попыток задаются `RAG_*`.
Общий deadline проверяется между этапами; локальный PyTorch вызов в потоке нельзя
безопасно прервать в середине вычисления. Celery hard time limit обеспечивает отдельную
границу индексации. Это ограничения выполнения, а не обещание latency.

Измерения индексации находятся в task record. Ответы возвращают `timings_ms` при
`diagnostics=true` и логируют их даже при ошибке. `generation` измеряет первую попытку,
`correction` — единственную коррекцию, `grounding_verification` — отдельную семантическую
проверку (суммарно при двух попытках), `validation` — локальные проверки черновика и цитат.
`total` включает весь запрос, включая embedding, retrieval, reranking и ожидание слота.

Ключи `attempt_1.*` и `attempt_2.*` раскрывают этапы: `generation.llm`, `correction.llm`,
`grounding_verification.llm`, соответствующие `.model_check` и `.pydantic`, а также
`validation.draft`, `validation.claim_text`, `validation.evidence_ids`,
`validation.exact_quotes`, `validation.metadata`, `validation.grounding_verdict`.
Этапы, до которых обработка не дошла, отсутствуют. Родительские интервалы включают
дочерние; складывать все значения словаря нельзя. Единицы — миллисекунды.

События `ollama_call`, `answer_rejected`, `answer_timing` связаны через `request_id`,
номер попытки и этап. Ollama дополнительно сообщает `done_reason`, число prompt/output
токенов и `load_duration`, `prompt_eval_duration`, `eval_duration` в **наносекундах**.
По умолчанию исходные тексты не логируются. `RAG_LLM_LOG_OUTPUTS=true` явно включает
`ollama_output` с сырым JSON генератора и verifier: используйте только для локальной
диагностики, поскольку ответы содержат цитаты документа. Эта настройка не включает
LangSmith, не передаёт данные наружу и не меняет проверки.

До занятия потоков API проверяет ключ и ограничивает число запросов:
`RAG_MAX_ACTIVE_REQUESTS=16`, из них одновременно не более `RAG_MAX_ACTIVE_QUESTIONS=2`
вопросов. JSON ограничен `RAG_MAX_JSON_BYTES`, чтение тела — `RAG_REQUEST_BODY_TIMEOUT`.
Compose ограничивает память процессов приложения, временный каталог и размер журналов.

Для внешнего production-развёртывания нужны TLS, права доступа при нескольких независимых
клиентах, дисковые квоты, резервное копирование volumes и проверка восстановления,
мониторинг и нагрузочные испытания под конкретный SLA. Качество retrieval/grounding следует
оценивать на документах целевого домена. Один ключ установки не заменяет многопользовательскую авторизацию.
