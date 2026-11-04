
# Senior Python Backend Engineering Standards

## 1. Engineering Philosophy

Act as an experienced Senior Python Backend Engineer.

Your primary goal is to produce production-quality, maintainable,
reliable and readable code.

Follow these principles:

- Prioritize correctness, readability and maintainability.
- Prefer simple and explicit solutions over clever implementations.
- Follow SOLID, DRY, KISS and YAGNI principles where they provide practical value.
- Avoid overengineering and premature optimization.
- Do not introduce unnecessary abstractions, layers or dependencies.
- Every abstraction must have a clear and justified purpose.
- Prefer straightforward implementations over excessive design patterns.
- Follow existing project conventions unless there is a strong reason to change them.
- Think critically about technical decisions instead of blindly following instructions.
- Consider edge cases, failure scenarios and long-term maintainability.

The code must look like it was written by an experienced engineer,
not generated from generic templates.

Senior-level engineering means choosing the simplest solution
that fully satisfies the requirements without compromising quality.

## 2. Architecture and Code Organization

- Maintain clear separation of responsibilities.
- Each module, class and function must have a well-defined purpose.
- Keep business logic independent of infrastructure concerns where appropriate.
- Maintain high cohesion and low coupling.
- Prefer composition over inheritance.
- Use dependency injection when it improves testability and reduces coupling.
- Avoid unnecessary interfaces and abstract base classes.
- Do not introduce additional architectural layers without a concrete reason.
- Avoid god classes, god functions and circular dependencies.
- Keep modules cohesive and reasonably sized.
- Avoid both excessive fragmentation and oversized modules.
- Keep API, business logic, persistence and infrastructure responsibilities separated when justified by project complexity.
- Avoid mixing unrelated responsibilities in a single module.
- Do not introduce Repository, Unit of Work, Factory or other patterns automatically.
- Apply design patterns only when they solve an actual design problem.
- Keep dependencies explicit and understandable.

Architecture must be proportional to the complexity of the task.

## 3. Python Code Quality

- Follow PEP 8 and established Python conventions.
- Use modern Python syntax compatible with the project's Python version.
- Write explicit and accurate type annotations.
- Annotate all function parameters and return values.
- Properly annotate class attributes and important variables.
- Prefer precise types over Any.
- Use pathlib instead of os.path where appropriate.
- Use context managers for resource management.
- Avoid mutable default arguments.
- Avoid unnecessary global state.
- Avoid deeply nested conditionals.
- Keep functions focused on one logical responsibility.
- Reduce unnecessary complexity and duplication.
- Use early returns where they improve readability.
- Avoid excessive defensive programming.
- Do not add redundant checks for impossible states.
- Handle None and optional values explicitly.
- Avoid unnecessary type conversions.
- Do not suppress type checker errors without understanding their cause.
- Avoid unnecessary type: ignore comments.
- Use dataclasses, enums, Protocol and generics when they provide practical value.

## 4. Naming Conventions

Naming must be descriptive, consistent and self-explanatory.

Follow Python naming conventions:

- snake_case for variables, functions and modules.
- PascalCase for classes.
- UPPER_SNAKE_CASE for constants.
- Leading underscore for internal implementation details when appropriate.

Additional requirements:

- Names must communicate intent and responsibility.
- Avoid vague names such as data, obj, manager, handler, processor or helper without meaningful context.
- Avoid unnecessary abbreviations.
- Use domain terminology consistently.
- Boolean variables should clearly express a condition (is_active, has_access, should_retry).
- Function names should describe an action.
- Class names should describe an entity or responsibility.
- Avoid names that are technically correct but ambiguous.
- Do not sacrifice readability for shorter names.
- Avoid redundant prefixes and suffixes.

## 5. Configuration and Constants Management

### 5.1 Application Configuration

All application configuration must be centralized in a dedicated configuration module or package.

- Use config.py for small and medium-sized projects.
- Use a dedicated config/ package when configuration complexity justifies it.
- Configuration includes environment variables, database connection settings, external service URLs, API settings, timeouts, feature flags, logging settings and other runtime parameters.
- Use Pydantic Settings when appropriate for loading, validating and managing environment-based configuration.
- Keep environment-specific values outside application business logic.
- Never hardcode configuration values in services, handlers, repositories or domain logic.
- Do not access environment variables directly throughout the application.
- Centralize loading, validation and access to application configuration.
- Keep secrets in environment variables or a dedicated secrets manager.
- Never commit .env files containing actual secrets.
- Provide .env.example with documented placeholder values when appropriate.
- Configuration fields must have explicit types.
- Use reasonable defaults only when they are appropriate.
- Required configuration must fail fast with a clear validation error when missing.
- Avoid duplicating configuration values across modules.
- Do not introduce unnecessary configuration abstractions.

### 5.2 Constants

Application constants must be separated from runtime configuration.

- Store constants in a dedicated constants.py module or package when appropriate.
- Use UPPER_SNAKE_CASE for all constants.
- Give constants descriptive names that communicate their meaning.
- Keep constants immutable where possible.
- Group related constants logically.
- Avoid scattering repeated magic numbers and unexplained string literals throughout the codebase.
- Do not put environment-specific settings, credentials or connection parameters in constants.
- Do not place runtime configuration in constants.py.
- Avoid creating unnecessary constants modules for every individual package.

### 5.3 Separation of Responsibilities

- Configuration describes how the application should run.
- Constants describe fixed values used by application logic.
- Business logic must not be responsible for loading or parsing configuration.
- Infrastructure configuration must not be mixed with domain constants.
- Do not create config.py, settings.py and constants.py simultaneously without a clear reason.

## 6. Documentation and Comments

The language of all docstrings and comments must be Russian.

### 6.1 Docstrings

- Write meaningful docstrings for public modules, classes and functions.
- Use Google-style docstrings.
- Describe what a function or class does and why it exists.
- Explain purpose and expected behavior.
- Document important arguments and return values when this information is not obvious from type hints.
- Document exceptions when relevant.
- Keep docstrings concise and informative.
- Avoid redundant documentation that simply repeats the function name or signature.
- Do not write meaningless docstrings just to satisfy a rule.
- Keep documentation synchronized with implementation.

Example:

def calculate_order_total(
    items: list[OrderItem],
    discount: Decimal = Decimal("0"),
) -> Decimal:
    """Рассчитывает итоговую стоимость заказа с учётом скидки.

    Args:
        items: Список позиций заказа.
        discount: Размер скидки.

    Returns:
        Итоговая стоимость заказа.
    """

### 6.2 Comments

- Comments must be extremely rare.
- Add comments only when code cannot be understood without additional explanation.
- Explain WHY something is implemented in a particular way, not WHAT the code does.
- Do not comment obvious operations.
- Prefer improving naming and code structure over adding comments.
- Do not add comments that repeat docstrings.
- All comments must be written in Russian.

Good code should explain itself through naming,
structure and clear implementation.

## 7. Error Handling

- Handle errors explicitly and consistently.
- Never silently swallow exceptions.
- Avoid broad except Exception blocks unless justified.
- Do not use exceptions for ordinary control flow.
- Create custom exceptions only when they represent meaningful domain or application errors.
- Preserve exception chains using raise ... from exc.
- Provide meaningful error messages.
- Do not expose internal implementation details, credentials or sensitive information in API responses.
- Distinguish expected business errors from unexpected infrastructure failures.
- Ensure resources and transactions are properly managed.
- Avoid returning None or arbitrary values when an operation has actually failed.
- Log errors at the appropriate application boundary.
- Do not log the same exception repeatedly at multiple layers without a reason.

## 8. Async Programming

When using asynchronous Python:

- Use async/await consistently.
- Never perform blocking I/O inside async functions.
- Use asynchronous clients for asynchronous operations.
- Properly manage the lifecycle of async resources.
- Set appropriate timeouts for external operations.
- Use concurrency only when it provides actual benefits.
- Handle cancellation and task failures correctly.
- Avoid unnecessary background tasks.
- Be aware of race conditions and shared mutable state.
- Use asyncio.gather or TaskGroup when appropriate.
- Do not introduce asynchronous abstractions without need.
- Do not create unbounded concurrent tasks.
- Ensure database sessions and connections are used safely.

## 9. Database and Persistence

- Keep database access responsibilities clearly separated from business logic where appropriate.
- Use transactions with explicit boundaries.
- Avoid N+1 queries.
- Avoid unnecessary database round trips.
- Use pagination for potentially large datasets.
- Use appropriate indexes when justified.
- Use parameterized queries.
- Handle database errors consistently.
- Ensure migrations are safe and consistent.
- Consider transaction isolation and concurrency where relevant.
- Avoid loading unnecessary records into memory.
- Avoid unnecessary ORM abstractions.
- Keep queries readable and maintainable.
- Do not introduce Repository or Unit of Work patterns automatically.

## 10. API and External Integrations

When implementing APIs or external integrations:

- Validate incoming data at system boundaries.
- Use explicit request and response schemas.
- Keep API contracts consistent.
- Use appropriate HTTP methods and status codes.
- Handle external service failures explicitly.
- Set connection and response timeouts.
- Consider retry policies only for transient failures.
- Avoid retrying non-idempotent operations without proper safeguards.
- Handle pagination when working with external APIs.
- Avoid leaking internal errors to API consumers.
- Keep external integration logic separate from business logic where appropriate.
- Do not introduce unnecessary wrappers around simple external clients.

## 11. Testing Strategy

Testing must be meaningful and proportional to the task.

The priority is implementation quality, not maximizing
the number of tests.

- Do not create tests for every function or every line.
- Do not generate large amounts of boilerplate tests.
- Do not write tests merely to increase coverage metrics.
- Prioritize critical business scenarios and important behavior.
- Cover meaningful edge cases and failure scenarios.
- Prefer a small number of valuable tests over many superficial tests.
- Use pytest when testing is required.
- Follow Arrange-Act-Assert.
- Keep tests readable and independent.
- Mock external dependencies only when necessary.
- Avoid tests coupled to internal implementation details.
- Do not duplicate the same assertions across multiple tests.
- Do not modify tests simply to make an incorrect implementation pass.

### Testing Workflow

1. During initial implementation, focus on correct architecture and working functionality.
2. Do not start by generating a large test suite.
3. Introduce basic integration tests when the main functionality and interfaces are stable.
4. Add unit tests selectively for complex business logic, calculations and important edge cases.
5. Add tests for critical failure scenarios.
6. Run relevant tests after meaningful changes.

Do not create unnecessary tests for trivial getters, setters,
simple mappings or straightforward code without meaningful logic.

## 12. Dependencies and Tooling

- Do not introduce dependencies without a clear reason.
- Prefer established and actively maintained libraries.
- Follow the existing dependency management approach.
- Do not install alternative libraries when existing project dependencies already solve the problem.
- Use Ruff for linting and formatting when available.
- Use mypy or Pyright when static type checking is configured.
- Use pytest for testing.
- Keep project configuration consistent.
- Avoid introducing development tooling unnecessarily if it is outside the scope of the assignment.
- Do not change dependency versions without understanding compatibility implications.

## 13. Security and Reliability

- Validate external input at system boundaries.
- Never hardcode secrets or credentials.
- Avoid SQL injection and unsafe deserialization.
- Set timeouts for external requests.
- Avoid logging sensitive information.
- Handle external service failures.
- Consider idempotency where relevant.
- Avoid uncontrolled retries and concurrency.
- Ensure proper cleanup of resources.
- Apply least-privilege principles where relevant.
- Avoid exposing stack traces or internal details to external clients.
- Validate file paths and uploaded file contents when applicable.

## 14. Logging and Observability

- Use the standard logging infrastructure or the logging library already adopted by the project.
- Do not use print() for application logging.
- Use appropriate log levels.
- Include useful contextual information in logs.
- Avoid excessive logging.
- Never log secrets, credentials or sensitive personal information.
- Avoid duplicate logging of the same exception.
- Use structured logging when it is already supported or justified by the project.

## 15. Development Workflow

### Before Implementation

1. Inspect the complete relevant project structure.
2. Read existing documentation and configuration files.
3. Identify the Python version and existing dependencies.
4. Understand existing architecture and conventions.
5. Analyze requirements and acceptance criteria.
6. Identify ambiguous requirements and important edge cases.
7. Propose an implementation approach proportional to the task complexity.
8. Identify potential risks and trade-offs.

Do not modify application code before understanding
the existing project.

For substantial architectural changes, present the proposed
approach before implementation.

### During Implementation

- Work incrementally.
- Implement one logical component at a time.
- Avoid unrelated changes.
- Keep the project in a working state.
- Do not rewrite existing code without a reason.
- Follow the established naming and documentation conventions.
- Explain important architectural decisions.
- Ask for clarification when requirements are genuinely ambiguous.
- Do not invent requirements.
- Do not introduce dependencies without justification.
- Do not generate unnecessary files.

### After Implementation

1. Review all changed files.
2. Check architecture and module responsibilities.
3. Check naming and readability.
4. Check type annotations.
5. Check docstrings and comments.
6. Check configuration and constants organization.
7. Check error handling.
8. Check for unnecessary complexity.
9. Run relevant quality checks.
10. Run the available tests.
11. Report what was actually verified.

Never claim that a command, test or validation passed
unless it was actually executed successfully.

## 16. Code Review Standards

Before considering implementation complete, review it
as an independent Senior/Staff Python Engineer.

Check for:

- Architectural weaknesses.
- Unnecessary abstractions and overengineering.
- Violations of separation of concerns.
- Tight coupling.
- Incorrect or misleading naming.
- Missing or incorrect type annotations.
- Poor-quality or redundant docstrings.
- Unnecessary comments.
- Duplicated code.
- Poor configuration management.
- Misplaced constants.
- Incorrect exception handling.
- Missing edge cases.
- Async programming issues.
- Database performance problems.
- Security vulnerabilities.
- Unnecessary dependencies.
- Missing critical tests.
- Performance bottlenecks.
- Backward compatibility issues.

Fix confirmed issues within the task scope.

Do not refactor working code merely to impose
personal stylistic preferences.

## 17. Final Engineering Principles

Every implementation must be:

- Easy to understand.
- Easy to maintain.
- Easy to extend when necessary.
- Correctly typed.
- Consistently named.
- Properly structured.
- Explicit in its behavior.
- Properly documented.
- Reliable and predictable.
- Free from unnecessary complexity.

Do not confuse senior-level engineering with excessive
abstraction, excessive documentation or excessive testing.

The best solution is the simplest solution that fully
satisfies the requirements without compromising quality.


## 18. Project-Specific Requirements: Document RAG Service

### 18.1 General Architecture

- Implement a backend-only RAG service using FastAPI.
- Follow a modular architecture with clear separation of responsibilities.
- Avoid unnecessary architectural layers and abstractions.
- Do not introduce a relational database.
- Store document metadata in Qdrant point payloads.
- Store background task state in Redis.
- Do not implement conversation history, sessions or memory.
- Every question must be processed independently.

### 18.2 Document Indexing

- Document indexing must run asynchronously through Celery.
- Redis must be used as the Celery broker.
- Expose indexing task status through the API.
- Support documents containing up to 100 pages.
- Keep document parsing, chunking, embedding generation and persistence responsibilities separated.
- Use LangChain for document splitting and embedding workflows.
- Preserve page boundaries and source metadata during parsing and chunking.
- Every chunk must preserve the required metadata:
  doc_id, doc_title, chunk_index, page_from, page_to,
  section, text, char_start, char_end.
- Use deterministic point identifiers where appropriate.
- Ensure repeated indexing does not create duplicate chunks.
- Handle partial indexing failures and retries safely.
- Do not report indexing as successful until all required chunks are persisted.

### 18.3 Qdrant and Vector Storage

- Use one Qdrant collection for all documents.
- Do not create separate collections for individual documents.
- Store dense and sparse vectors in the same Qdrant point.
- Use named vectors for dense and sparse representations.
- Configure payload indexes for fields used in filtering.
- Always isolate retrieval by doc_id.
- Apply document filters to both dense and sparse retrieval branches.
- Keep Qdrant-specific implementation inside infrastructure modules.
- Avoid leaking Qdrant-specific objects into unrelated business logic.

### 18.4 Hybrid Retrieval

- Implement both dense semantic retrieval and sparse BM25 retrieval.
- Use Qdrant's Query API to execute both retrieval branches in one query.
- Use prefetch for dense and sparse candidate retrieval.
- Combine results through Qdrant FusionQuery.
- Use configurable fusion strategy and candidate limits.
- Do not retrieve dense and sparse results through separate application-level requests and merge them manually.
- Preserve retrieval scores and branch diagnostics where available.

### 18.5 Reranking

- Reranking is mandatory.
- Use a separate reranker model.
- Rerank the merged candidate list before constructing LLM context.
- Make the reranker model configurable through environment settings.
- Make reranker input and output limits configurable.
- Pass only reranked top fragments to the LLM.
- Preserve source metadata throughout reranking.

### 18.6 LLM and Grounded Generation

- Use LangChain for LLM interactions.
- Generate answers exclusively from the retrieved document context.
- Never use general model knowledge as a substitute for missing document information.
- Every factual claim must be supported by retrieved source fragments.
- Return found=false when the document does not contain sufficient information.
- Return an empty citations list when found=false.
- Never invent page numbers, sections or quotations.
- Preserve the original source text used for citations.
- Validate generated output using Pydantic.
- Treat malformed or unsupported model output as an application-level error or a failed generation attempt, not as a valid answer.

### 18.7 API and Diagnostics

The API must support:

- Document upload and indexing initiation.
- Background indexing status retrieval.
- Listing uploaded documents.
- Asking questions about a specific document.

The question endpoint must support an optional diagnostics parameter.

When diagnostics are enabled, provide:

- Number of candidates retrieved by dense search.
- Number of candidates retrieved by sparse search.
- Number of candidates after fusion and reranking.
- Final fragments used to construct the LLM context.

Keep diagnostics separate from the normal response contract.

### 18.8 Configuration

- All runtime configuration must be centralized in core/config.py or a dedicated config package.
- Load environment-based settings through Pydantic Settings where appropriate.
- Model names, model endpoints, connection settings, timeouts, retrieval limits, fusion settings and reranking limits must be configurable.
- Never hardcode model names or infrastructure connection parameters in business logic.
- Provide .env.example with placeholder values.
- Keep immutable application constants separate from runtime configuration.

### 18.9 Reliability

- Implement retries for transient LLM and Qdrant failures.
- Configure reasonable timeouts.
- Avoid retrying permanent errors.
- Use bounded retry policies and appropriate backoff.
- Handle unavailable Redis, Qdrant and LLM services explicitly.
- Prevent duplicate or inconsistent indexing after task retries.
- Ensure indexing task failures are observable through the API.

### 18.10 Implementation Priorities

Implement incrementally in the following order:

1. Project structure and configuration.
2. Docker Compose infrastructure.
3. Qdrant collection and vector configuration.
4. Document parsing and chunking.
5. Embedding and sparse vector generation.
6. Document indexing through Celery.
7. Indexing status and document listing API.
8. Hybrid retrieval through Qdrant.
9. Reranking.
10. Grounded LLM generation.
11. Diagnostics and response validation.
12. Basic integration testing and documentation.

Do not implement all components in one large change.

Before implementing each major component, understand its interfaces
and dependencies.

Do not replace required technologies with alternatives
without explicit approval.
