# Исполнимый план развития «Логоса» для Gemini/agy

Дата фиксации: 5 сентября 2026 года.
Статус: **Approved for staged implementation — публичный production origin выбран на домашней Ubuntu через Caddy + named Cloudflare Tunnel; платные действия и решения о правах остаются отдельными gates**.
Базовый коммит при подготовке: `b7cf39e`.
Связанный аудит: [`AUDIT-2026-09-05.md`](./AUDIT-2026-09-05.md).
Обязательный отчёт исполнителя: [`AGY_IMPLEMENTATION_REPORT.md`](./AGY_IMPLEMENTATION_REPORT.md).

---

## 0. Как пользоваться этим документом

Этот файл — источник задания для Gemini 3.8 Flash High, запускаемого через `agy`, а не приглашение переписать проект за один проход.

Исполнитель обязан:

1. Работать **строго по одному этапу за раз** из раздела 16. Один продолжительный запуск может перейти к следующему этапу только после полного отчёта, зелёных gates и отдельного checkpoint commit.
2. Перед изменениями прочитать этот документ, аудит, `AGENTS.md` и файлы, перечисленные в выбранном этапе.
3. Сначала написать тест и увидеть ожидаемое падение (`RED`).
4. Затем сделать минимальное изменение (`GREEN`) и выполнить рефакторинг только при зелёных тестах.
5. Не менять файлы вне области этапа без явного объяснения в отчёте.
6. Разрешено подготовить Caddy, systemd и конфигурацию named Cloudflare Tunnel. Не создавать/менять Cloudflare account, DNS, tunnel token, платный перевод/TTS и не публиковать книги без необходимых credentials, rights decision и явного owner gate.
7. Не передавать содержимое книг сторонним API до подтверждения прав на такую обработку.
8. Не использовать `--dangerously-skip-permissions` для текста из загруженного PDF.
9. Не считать fallback исходного текста успешным переводом.
10. После каждого этапа заполнить шаблон `docs/AGY_IMPLEMENTATION_REPORT.md`, сохранить копию как `docs/reports/AGY-<PHASE>-<UTC>.md`, сделать checkpoint commit и только затем решать, можно ли продолжать.

В continuous mode исполнитель сам проверяет diff и доказательства по тем же gates. Он обязан остановиться на failed test, migration ambiguity, missing secret/domain/access, paid call, rights uncertainty или production cutover, требующем решения владельца.

### 0.1 Команда запуска — только как шаблон

Фактический синтаксис `agy` необходимо проверить через `agy --help` на сервере. Не копировать устаревшие флаги из старых ADR вслепую.

```text
Прочитай AGENTS.md, docs/GEMINI_IMPLEMENTATION_PLAYBOOK.md,
docs/AGY_IMPLEMENTATION_REPORT.md и docs/AGY_START_PROMPT.md.
Начни с первого незавершённого этапа. Соблюдай RED -> GREEN -> REFACTOR,
сохраняй отчёт и checkpoint commit после каждого этапа. Продолжай только
при зелёных gates; остановись перед owner/rights/paid/production gate.
```

### 0.2 Что считать завершением запуска

Запуск завершён только если:

- указан точный этап;
- приведён список изменённых файлов;
- зафиксировано исходное падение нового теста;
- приведены команды и коды возврата финальных проверок;
- проверено отсутствие секретов;
- для UI приложены скриншоты 375, 768 и 1440 px;
- описан rollback;
- перечислены незакрытые риски;
- следующий этап не начат до сохранения отчёта и checkpoint commit текущего.

---

## 1. Цель и границы продукта

«Логос» — академическая веб-библиотека, которая должна:

- принимать книгу через закрытый Telegram-интерфейс;
- сохранять неизменяемый исходный PDF;
- корректно обрабатывать текстовые PDF, ClearScan, повреждённые text layers, сканы и развороты;
- сохранять структуру: заголовки, абзацы, цитаты, списки, таблицы, рисунки, подписи, колонтитулы, сноски и печатную пагинацию;
- поддерживать оригинал и проверенные переводы без ложной маркировки языка;
- позволять сверять адаптированный текст со сканом;
- хранить заметки и прогресс отдельно для каждой книги/издания;
- публиковать только валидированный, воспроизводимый артефакт;
- в будущем добавлять проверенную аудиоредакцию с устойчивой привязкой к текстовым блокам.

### 1.1 Нецели текущей программы

- Переход на Next.js.
- Микросервисы, Kubernetes, Redis или PostgreSQL.
- Публичный API для сторонних пользователей.
- Автоматическая публикация любого присланного PDF.
- Полностью автоматическая «идеальная» OCR-вычитка без возможности остановиться на ручной проверке.
- Клонирование голоса без документированного согласия.
- Обещание высокой доступности при выключенной Ubuntu или недоступном домашнем интернете.
- Немедленная миграция медиа в R2: adapter сохраняется как будущая опция, но не входит в первичный production-path.

### 1.2 Ключевой принцип

Система должна уметь сказать **«результат недостаточно надёжен для публикации»**. Отказ и ручная проверка лучше красивого, но искажённого текста.

---

## 2. Подтверждённое текущее состояние

Это факты аудита, а не проектные предположения.

### 2.1 Backend

- Telegram delivery, PDF extraction, вызов agy, публикация и SQLite разнесены по файлам, но не по устойчивым портам.
- `bot.py` запускает обработку через detached `asyncio.create_task`; перезапуск процесса уничтожает выполняющуюся работу.
- SQLite хранит только общий статус и счётчики; lease, попытки, checkpoints и отдельные batch records отсутствуют.
- Администраторская проверка fail-open, если идентификатор администратора не задан.
- В истории репозитория присутствовал секрет Telegram; считать его скомпрометированным и ротировать вне Git.
- Текст недоверенного PDF включается в prompt агента, который запускался с чрезмерными полномочиями.
- После ошибок перевода текущий bridge способен вернуть исходный текст как `en` и `ru`, после чего pipeline публикует его как успех.
- Публикация пишет непосредственно в живые каталоги и манифест; promotion не атомарен.
- Одновременные книги и одинаковые slug не сериализованы.
- PDF handle закрывается не на всех ветках исключений.

### 2.2 Frontend

- `BookManifest` и `ParagraphPair` недостаточны для структуры академического документа.
- Доступные языковые режимы не выводятся из реальных возможностей конкретной книги.
- `localStorage` ключи прогресса, закладок и карточек не namespaced по книге.
- Библиографическая ссылка карточки жёстко привязана к Шрейнеру.
- Открытие другой книги и страницы не атомарно; callback может использовать границы старой книги.
- `hashchange` меняет только представление, но не синхронизирует книгу и страницу.
- Поиск синхронно обходит весь manifest на каждую клавишу и возвращает только первое совпадение в поле.
- Выбор результата поиска не гарантирует переход к блоку/сноске и подсветку.
- Hover-only инструменты и диалоги имеют пробелы в клавиатурной доступности.

### 2.3 Контент Осборна

- PDF и обработанный на сервере источник имеют одинаковый SHA-256.
- В manifest 736 страниц, 3 877 абзацев, 78 TOC entries и 321 сноска.
- Все 3 877 пар `en/ru` одинаковы при русском источнике.
- В основном тексте найдено 5 056 символов `#`, ещё 355 — в сносках.
- Проверены конкретные потери: переносы на с. 600, диапазоны стихов на с. 54, схема на с. 55, двухколоночная структура на с. 158, сноска на с. 609, библиография на с. 693, text-layer на с. 736 и разрыв TOC между 120 и 577.

### 2.4 Сервер исполнения

- Ubuntu host: 4 CPU cores, Intel Core i5-4570.
- RAM: 7.2 GiB; во время проверки было доступно около 1.7 GiB.
- Swap: 4 GiB, почти полностью использован во время проверки.
- NVIDIA GPU нет; только интегрированная графика Intel.
- `ffmpeg` и `cloudflared` установлены.
- На диске было около 150 GiB свободно.
- Текущие локальные каталоги содержали примерно 117 MiB `storage` и 123 MiB сканов.

Следствие: сервер подходит для bot/worker, PyMuPDF, лёгкой обработки и сборки, но нельзя проектировать production OCR/TTS вокруг несуществующей GPU.

---

## 3. Требования и измеримые NFR

### 3.1 Сохранность контента

- Исходный PDF никогда не перезаписывается.
- Для каждого published block можно восстановить source PDF hash, PDF page, координаты и extraction candidate.
- Никакая нормализация не удаляет исходное значение: хранится reversible raw-to-normalized map.
- Страница не публикуется при неразрешённом конфликте цифр, ссылок Писания, сносок, порядка колонок или обрезки разворота.
- Публикация книги требует полного множества ожидаемых страниц и уникальных block IDs.

### 3.2 Надёжность

- После SIGTERM/restart worker продолжает с последнего проверенного checkpoint.
- Один batch синтеза/перевода не выполняется одновременно двумя worker.
- Повторный upload одного и того же PDF обнаруживается по SHA-256.
- Повторный запуск с тем же content/config hash переиспользует verified artifacts.
- Promotion либо делает доступной целую новую версию, либо не меняет текущую.

### 3.3 Производительность

- Domain unit suite не поднимает Telegram, браузер, сеть или реальную SQLite и должна укладываться в секунды.
- Reader не импортирует многомегабайтный manifest в initial bundle, когда будет реализована lazy loading архитектура.
- Поиск не блокирует основной поток на каждом символе; запрос debounce и ограничение результатов обязательны.
- Статические PDF, scans и audio не проходят через runtime Worker без необходимости авторизации.

### 3.4 Безопасность

- Запуск прекращается, если обязательные секреты/allowlist отсутствуют.
- Недоверенный PDF не может влиять на shell-команды, пути или инструкции агента.
- В логи, отчёты, screenshots и manifests не попадают секреты.
- Платные вызовы имеют book-level budget cap и требуют подтверждения.
- Публичность книги определяется rights/access decision, а не наличием URL.

### 3.5 Доступность и UI

- WCAG 2.1 AA по контрасту и клавиатурной работе ключевых сценариев.
- Минимальная touch target — 44×44 px.
- Все диалоги имеют role, accessible name, focus trap, Escape и focus restore.
- На 375, 768 и 1440 px нет горизонтального переполнения панели.
- `prefers-reduced-motion` отключает необязательные анимации.

### 3.6 Операционные цели

- RPO локальной очереди: не более одного незавершённого незакоммиченного шага.
- RTO после restart: worker может взять просроченный lease и продолжить без ручного редактирования БД.
- Для каждой публикации сохраняются version, checksum, test report и rollback target.

---

## 4. Целевая архитектура

Выбран **модульный монолит с портами и адаптерами**: один репозиторий, один Python runtime для ingestion, один статический React/Vite reader, SQLite и object storage. Это сохраняет операционную простоту и даёт тестируемые границы.

```mermaid
flowchart LR
    U[Разрешённый Telegram пользователь] --> T[Telegram adapter]
    T --> I[Immutable inbox]
    T --> J[(SQLite job repository)]
    W[Worker process] --> J
    W --> C[Document classifier]
    C --> N[Native extractor]
    C --> O[OCR / vision adapter]
    N --> R[Candidate reconciler]
    O --> R
    R --> D[Document AST + provenance]
    D --> X[Translation projection]
    X --> A[Agent executor port]
    A --> V[Deterministic validators]
    V --> S[Per-job staging release]
    S --> P[Atomic publication port]
    P --> M[(Immutable media storage)]
    P --> B[Versioned reader manifest]
    B --> Q[Build + E2E gates]
    Q --> E[Deployment port]
    E --> T

    D --> SP[Speaking projection]
    SP --> TP[TTS provider port]
    TP --> AV[Audio validation + timing]
    AV --> M
```

### 4.1 Граница доверия

```text
Trusted control plane:
  allowlist, code, schemas, prompts, policy, budget, deploy credentials

Untrusted data plane:
  Telegram filename, PDF bytes, PDF metadata, extracted text,
  OCR result, model result, external media metadata
```

Данные из untrusted plane могут проходить только через typed inputs и validators. Они не могут становиться shell fragments, путями вне job workspace или system instructions.

### 4.2 Предлагаемая структура Python

```text
ingestion_service/
  domain/
    entities.py
    document_ast.py
    job_state.py
    provenance.py
    validation.py
  application/
    commands.py
    worker.py
    orchestration.py
    ports.py
  adapters/
    telegram_adapter.py
    sqlite_job_repository.py
    pymupdf_extractor.py
    ocr_adapter.py
    agy_agent_adapter.py
    filesystem_artifact_store.py
    r2_artifact_store.py
    netlify_deployer.py
  publication/
    manifest_compiler.py
    release_validator.py
    promoter.py
  migrations/
  tests/
    unit/
    integration/
    contract/
    fixtures/
```

Не выполнять массовое перемещение файлов в первом этапе. Сначала ввести contracts рядом с текущим кодом, затем переносить по одному adapter с characterization tests.

### 4.3 Основные порты

```python
class JobRepository(Protocol):
    def enqueue(self, command: "CreateIngestionJob") -> "Job": ...
    def claim_next(self, worker_id: str, lease_seconds: int) -> "Job | None": ...
    def renew_lease(self, job_id: str, worker_id: str, lease_epoch: int) -> None: ...
    def record_checkpoint(self, checkpoint: "Checkpoint") -> None: ...
    def complete_step(self, job_id: str, expected_version: int, result: "StepResult") -> None: ...
    def fail_step(self, job_id: str, failure: "FailureRecord") -> None: ...

class SourceRepository(Protocol):
    def put_immutable(self, stream, expected_sha256: str | None) -> "SourceRef": ...
    def open(self, source_ref: "SourceRef"): ...

class PageClassifier(Protocol):
    def classify(self, page: "PageEvidence") -> "Classification": ...

class TextCandidateExtractor(Protocol):
    def extract(self, page: "PageEvidence") -> list["ExtractionCandidate"]: ...

class AgentExecutor(Protocol):
    async def execute(self, request: "AgentRequest") -> "AgentResponse": ...

class ReleaseStore(Protocol):
    def create_staging(self, job_id: str, release_id: str) -> "StagingRelease": ...
    def promote(self, release: "VerifiedRelease") -> "PublishedRelease": ...

class DeploymentPort(Protocol):
    async def deploy(self, release: "PublishedRelease") -> "DeploymentResult": ...

class Clock(Protocol):
    def now(self) -> "datetime": ...

class ProcessRunner(Protocol):
    async def run(self, argv: list[str], cwd: "Path", timeout_seconds: int) -> "ProcessResult": ...

class Notifier(Protocol):
    async def job_changed(self, event: "JobEvent") -> None: ...
```

Domain и application tests используют fakes этих портов. Реальные Telegram, agy, filesystem, R2 и deploy не вызываются из unit tests.

---

## 5. Модель заданий и SQLite

### 5.1 State machine

```mermaid
stateDiagram-v2
    [*] --> RECEIVED
    RECEIVED --> ANALYZING
    ANALYZING --> AWAITING_MODE
    AWAITING_MODE --> QUEUED
    QUEUED --> EXTRACTING
    EXTRACTING --> RECONCILING
    RECONCILING --> TRANSLATING
    TRANSLATING --> VALIDATING
    VALIDATING --> NEEDS_REVIEW
    NEEDS_REVIEW --> VALIDATING
    VALIDATING --> STAGING
    STAGING --> TESTING
    TESTING --> READY_TO_PUBLISH
    READY_TO_PUBLISH --> PUBLISHING
    PUBLISHING --> PUBLISHED
    PUBLISHED --> [*]

    QUEUED --> CANCELLED
    NEEDS_REVIEW --> CANCELLED
    FAILED --> RETRY_WAIT: retryable + attempts remain
    RETRY_WAIT --> QUEUED: backoff elapsed

    ANALYZING --> FAILED
    EXTRACTING --> FAILED
    RECONCILING --> FAILED
    TRANSLATING --> FAILED
    VALIDATING --> FAILED
    STAGING --> FAILED
    TESTING --> FAILED
    PUBLISHING --> FAILED

    FAILED --> QUEUED: explicit retry from checkpoint
```

`FAILED`, `NEEDS_REVIEW`, `CANCELLED` и `PUBLISHED` — не взаимозаменяемы. Ошибка модели не превращается в published source-language duplicate. `CANCELLED` терминален; повтор создаёт новый job, а не оживляет отменённый.

### 5.2 Предлагаемая схема

DDL ниже — проект контракта. Реализация идёт миграциями, без удаления существующих таблиц и без потери старых jobs.

```sql
CREATE TABLE ingestion_jobs (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  requested_by INTEGER NOT NULL,
  telegram_chat_id INTEGER NOT NULL,
  telegram_message_id INTEGER,
  requested_mode TEXT,
  source_language TEXT,
  book_slug TEXT,
  status TEXT NOT NULL,
  status_reason TEXT,
  current_step TEXT,
  version INTEGER NOT NULL DEFAULT 0,
  lease_owner TEXT,
  lease_expires_at TEXT,
  lease_epoch INTEGER NOT NULL DEFAULT 0,
  attempt_count INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 3,
  config_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  completed_at TEXT
);

CREATE TABLE source_documents (
  id TEXT PRIMARY KEY,
  sha256 TEXT NOT NULL UNIQUE,
  original_filename TEXT NOT NULL,
  storage_path TEXT NOT NULL,
  byte_size INTEGER NOT NULL,
  mime_type TEXT NOT NULL,
  page_count INTEGER,
  created_at TEXT NOT NULL
);

CREATE TABLE job_steps (
  id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL REFERENCES ingestion_jobs(id),
  step_name TEXT NOT NULL,
  step_key TEXT NOT NULL,
  status TEXT NOT NULL,
  input_hash TEXT NOT NULL,
  output_artifact_id TEXT,
  attempt INTEGER NOT NULL,
  started_at TEXT,
  completed_at TEXT,
  error_code TEXT,
  error_detail TEXT,
  UNIQUE(job_id, step_key, input_hash)
);

CREATE TABLE artifacts (
  id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL REFERENCES ingestion_jobs(id),
  kind TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  storage_path TEXT NOT NULL,
  byte_size INTEGER NOT NULL,
  media_type TEXT NOT NULL,
  schema_version TEXT,
  verified_at TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(kind, content_hash)
);

CREATE TABLE page_records (
  id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL REFERENCES ingestion_jobs(id),
  pdf_page_index INTEGER NOT NULL,
  rendered_side TEXT,
  printed_label TEXT,
  printed_label_confidence REAL,
  rotation INTEGER NOT NULL DEFAULT 0,
  width_pt REAL NOT NULL,
  height_pt REAL NOT NULL,
  render_hash TEXT NOT NULL,
  perceptual_hash TEXT,
  classification TEXT NOT NULL,
  review_status TEXT NOT NULL,
  UNIQUE(job_id, pdf_page_index, rendered_side)
);

CREATE TABLE review_findings (
  id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL REFERENCES ingestion_jobs(id),
  page_record_id TEXT,
  block_id TEXT,
  severity TEXT NOT NULL,
  code TEXT NOT NULL,
  message TEXT NOT NULL,
  evidence_json TEXT NOT NULL,
  resolved_at TEXT,
  resolution_note TEXT
);

CREATE INDEX idx_jobs_claim
  ON ingestion_jobs(status, lease_expires_at, created_at);
CREATE INDEX idx_steps_job
  ON job_steps(job_id, step_name, status);
CREATE INDEX idx_findings_open
  ON review_findings(job_id, resolved_at, severity);
```

### 5.3 Claim/lease правила

- Каждый SQLite connection выполняет `PRAGMA foreign_keys=ON`, настраивает `busy_timeout` и использует WAL после отдельного compatibility-теста файловой системы.
- `claim_next` выполняется одной `BEGIN IMMEDIATE` transaction.
- Claim возможен для `QUEUED` или job с истёкшим lease.
- Claim увеличивает `lease_epoch`; все последующие записи требуют одновременно `lease_owner`, `lease_epoch` и optimistic `version`.
- Worker renew lease между batches.
- Просроченный worker не может записать, завершить либо освободить job после смены lease; это проверяется отдельным конкурентным тестом.
- Side effect выполняется после durable `submitted` record.
- Timeout после потенциально платного вызова не означает «можно повторить»; сначала проверяется provider history/status, если доступно.

### 5.4 Миграции и восстановление

- Миграции append-only; применённый SQL не редактируется задним числом.
- Ledger хранит номер, checksum, время применения и версию приложения.
- Перед первой структурной миграцией создаётся проверенная копия SQLite и фиксируется команда восстановления.
- Startup останавливается на неизвестной или checksum-mismatched миграции.
- Upgrade и rollback/restore тестируются на копии существующей базы до server cutover.

---

## 6. Каноническая модель книги

### 6.1 Версионирование

```text
SourceDocumentRevision (immutable PDF)
  -> PageEvidenceRevision (render + candidates)
  -> DocumentAstRevision (reviewable canonical source)
  -> TranslationRevision (optional, language-specific)
  -> ReaderReleaseRevision (validated manifest + media refs)
  -> SpeakingProjectionRevision (optional)
  -> AudioEditionRevision (optional)
```

Ни один downstream revision не изменяет upstream. Исправление OCR создаёт новый AST revision; старая published release остаётся воспроизводимой.

### 6.2 Document AST

```ts
type LanguageCode = 'ru' | 'kk' | 'en' | 'grc' | 'he' | 'und';

type SourceAnchor = {
  sourceSha256: string;
  pdfPageIndex: number;
  printedPageLabel?: string;
  renderedSide?: 'left' | 'right' | 'full';
  bbox?: [number, number, number, number];
  extractionMethod: 'native' | 'ocr' | 'vision' | 'manual';
  candidateHash: string;
  confidence?: number;
};

type InlineRun = {
  id: string;
  text: string;
  language: LanguageCode;
  marks?: Array<'bold' | 'italic' | 'smallcaps' | 'superscript' | 'subscript'>;
  source: SourceAnchor;
};

type DocumentBlock =
  | { type: 'heading'; id: string; level: 1 | 2 | 3 | 4; runs: InlineRun[] }
  | { type: 'paragraph'; id: string; runs: InlineRun[] }
  | { type: 'quotation'; id: string; runs: InlineRun[]; attribution?: InlineRun[] }
  | { type: 'list'; id: string; ordered: boolean; items: DocumentBlock[][] }
  | { type: 'table'; id: string; rows: InlineRun[][][]; fallbackImageRef?: string }
  | { type: 'figure'; id: string; imageRef: string; caption?: InlineRun[]; alt?: string }
  | { type: 'footnote'; id: string; label: string; blocks: DocumentBlock[]; anchors: string[] }
  | { type: 'pageBreak'; id: string; pdfPageIndex: number; printedPageLabel?: string };
```

### 6.3 Manifest возможностей

```ts
type BookManifestV2 = {
  schemaVersion: '2.0';
  slug: string;
  releaseId: string;
  sourceRevision: string;
  title: Record<string, string>;
  subtitle?: Record<string, string>;
  contributors: Array<{ role: string; name: string; language?: string }>;
  citation: {
    shortTitle: string;
    publisher?: string;
    place?: string;
    year?: string;
    edition?: string;
  };
  sourceLanguage: LanguageCode;
  availableLanguages: LanguageCode[];
  availableViews: Array<'adapted' | 'scan' | 'compare'>;
  pageRange: { start: number; end: number };
  assets: { baseUrl?: string; scanPattern?: string; sourcePdf?: string };
  toc: TocNode[];
  pagesIndexUrl: string;
  audioEditions?: AudioEditionSummary[];
};
```

Frontend не показывает EN/bilingual controls, если `availableLanguages` этого не подтверждает.

### 6.4 ID правила

- `bookId` и `slug` различаются: slug человекочитаем, bookId стабилен.
- Release ID содержит content hash или ULID, но не зависит только от времени.
- Block ID сохраняется при косметическом reflow и переводе.
- ID не строится из порядкового DOM index.
- Для split spread side входит в source anchor, но не обязательно в semantic block ID.

---

## 7. Классификация и извлечение PDF

### 7.1 Категории router

| Категория | Признаки | Основной путь | Обязательная страховка |
|---|---|---|---|
| `native_good` | корректный Unicode, достаточное text coverage, разумный порядок | native geometry extraction | render fixture и digit checks |
| `clear_scan_text_layer` | OCR text поверх image, пробелы/лигатуры/soft hyphen | native + OCR comparison | per-span confidence и raw map |
| `bad_unicode_font_map` | custom encoding, визуальный текст не совпадает с extraction | rendered OCR primary candidate | native сохраняется как evidence |
| `image_only_spread` | почти нет текста, image coverage, две печатные страницы | duplicate detection, crop/split, OCR | gutter/side review |
| `mixed` | текст + крупные изображения/вставки | block-level routing | figure fallback |
| `vector_or_layout_figure` | диаграмма/таблица не сводится к строкам | image/vector asset + caption | manual/vision review |
| `blank_or_terminal` | нет содержимого или служебная страница | explicit empty block | не подставлять «пустая страница» без evidence |
| `needs_review` | кандидаты расходятся или порядок неоднозначен | остановка | ручное решение |

### 7.2 Сигналы классификации

- число и тип fonts, наличие ToUnicode;
- доля валидной кириллицы/латиницы/казахских символов;
- replacement/control/weird character rate;
- text bbox coverage;
- image coverage;
- duplicate exact/perceptual render hash;
- число колонок и line-order geometry;
- различие native/OCR digit sequences;
- rotation, crop box, page size;
- terminal/blank evidence.

Пороговые значения калибруются fixtures. Не использовать одно правило «меньше 40 символов = scan» как достаточное решение.

### 7.3 Корпус регрессии из шести книг

| Книга | SHA-256 | PDF страниц | Класс/главный риск | Обязательные fixtures |
|---|---|---:|---|---|
| Merrill C. Tenney, «Обзор Нового Завета» | `20eb70f061dfd70fab33157f4b93579ed900588fad73f2a161f504b09651029f` | 492 | image-only двухстраничные развороты и дубликаты | PDF 245/246 duplicate; spread с печатными 246/247 |
| «Деяния Апостолов» | `b7cc8d4c3e2edb6a1af221736c8dedcb5236be9106ea754707967413a9368cc8` | 91 | native good; авторство нельзя выводить из filename | p1, p46, terminal p91 |
| George Eldon Ladd, «Богословие Нового Завета» | `a937e6782d423f2a3d11955575c5b958f6b8b68584be0c40e05192785a916b91` | 802 | ClearScan, intrusive spacing, footnotes | p2; PDF 402 = printed 401; notes 1093–1096 |
| Leon Morris, «Теология Нового Завета» | `8d5286389d86dbbdfb8559c0a623ac0dc0912145744b36a0d850b966512a1588` | 394 | bad Unicode/font map | p2; PDF 197 = printed 196; визуальное `слово` не `слою` |
| Fee/Stewart, «Как читать Библию…» | `9276959c80dc700f43eca305224a96612eb08e28c7d6b2d8c6f0f0c6ce218823` | 146 | native good, quotations, TOC в конце | p1, p73, p146 TOC |
| Walter Kaiser Jr., «На пути к экзегетическому богословию» | `ad031f02204d5e8c91eecfbcc7e0f83a2131b6a3c1664ac8c3d9ff7fcad24b39` | 144 | metadata author конфликтует с title page | p1, p72 geometry/list, p144 bibliography |

Проверка была выборочной: начало/середина/конец извлечены машинно, по две страницы на PDF просмотрены визуально. Это fixture plan, не утверждение о ручной проверке всех 2 069 страниц.

### 7.4 Нормализация

Каждая операция возвращает:

```json
{
  "raw": "арсе-\nнале",
  "normalized": "арсенале",
  "operations": [{
    "kind": "line_end_dehyphenation",
    "rawRange": [4, 6],
    "normalizedRange": [4, 4],
    "reason": "visual_line_continuation+lexicon",
    "confidence": 0.98
  }]
}
```

Нельзя глобально удалять `#`, дефис, U+001E или апостроф. Защитные invariants:

- digit sequence и разделители диапазонов сохраняются;
- `1 Кор. 15:45`, годы, ISBN и номера сносок проверяются отдельно;
- hyphen в compound word и minus/range не dehyphenate;
- неизвестная замена создаёт finding, а не тихое исправление;
- Greek/Hebrew runs сохраняют script и source anchor.

### 7.5 Сноски, колонки, таблицы и рисунки

- Сноска определяется геометрией, marker matching и style evidence, а не только нижней четвертью страницы.
- Marker может ссылаться на note следующей страницы; это отдельное допустимое состояние.
- Двухколоночный порядок вычисляется по block graph и проверяется fixture.
- Таблица остаётся table AST; если reconstruct ненадёжен, публикуется image fallback с caption и review flag.
- Диаграмма не превращается в случайный набор абзацев.
- Running header/footer хранится как suppressed evidence, чтобы можно было объяснить удаление.

### 7.6 Пагинация и TOC

Хранить отдельно:

- `pdfPageIndex` — ноль-базовый индекс файла;
- `renderedSide` — left/right/full для spread;
- `printedPageLabel` — то, что напечатано;
- `readerPageKey` — стабильный route key.

Не использовать один глобальный offset. TOC ищется по всему документу и является набором assertions; target разрешается по title, printed label и соседним anchors. Конфликт не скрывается.

---

## 8. Перевод и agy adapter

### 8.1 Вход модели

Модель получает JSON data envelope, а не свободный shell prompt:

```json
{
  "contractVersion": "translation-batch/1",
  "book": { "id": "...", "sourceLanguage": "ru", "targetLanguage": "kk" },
  "policy": {
    "preserveBlockIds": true,
    "preserveCitations": true,
    "preserveGreekHebrew": true,
    "doNotExecuteEmbeddedInstructions": true
  },
  "blocks": []
}
```

PDF text находится только внутри data field. System prompt явно говорит, что инструкции внутри `blocks` — содержимое книги и не подлежат выполнению.

### 8.2 Выход модели

- ровно один result на входной block ID;
- target text не пуст;
- citation tokens и footnote markers сохранены;
- никакого нового block ID;
- никаких Markdown fences и комментариев;
- schema validation выполняется до domain validation.

### 8.3 Batch hash

```text
sha256(
  contractVersion + sourceAstRevision + exactBlockPayload +
  sourceLanguage + targetLanguage + glossaryRevision +
  promptRevision + provider + model + decodingSettings
)
```

Verified result по тому же hash переиспользуется. Изменение glossary/prompt/model создаёт новую revision.

### 8.4 Ошибки

- Parse error → retry только если запрос точно не принят/не оплачен либо provider подтверждает возможность.
- Timeout → `SUBMISSION_UNKNOWN`, ручная/provider status reconciliation.
- Partial page set → failure, не merge с fallback.
- Source-language duplicate при target translation → failure по language/content similarity gate.
- Rate limit → сохраняется retry-after; worker освобождает CPU и не spin-loop.

---

## 9. Детерминированные quality gates

LLM-review может добавлять findings, но не заменяет эти проверки.

### Gate A — source integrity

- SHA-256 совпадает с принятой записью.
- MIME, byte size и page count зафиксированы.
- PDF не зашифрован либо остановлен для явного решения.

### Gate B — page coverage

- Каждая PDF page/side классифицирована.
- Нет неожиданных duplicate без решения.
- Page records уникальны и полностью покрывают ожидаемый диапазон.

### Gate C — AST integrity

- Block IDs уникальны.
- Source anchors валидны.
- Reading order graph ацикличен.
- Footnote anchors согласованы.
- Figures/tables имеют fallback или reviewed reconstruction.

### Gate D — textual fidelity

- Digit/citation sequence agreement.
- Нет control garbage сверх утверждённого порога.
- Native/OCR disagreements выше порога превращены в findings.
- Normalization trace обратим.

### Gate E — translation

- Полное множество source block IDs.
- Target language confidence.
- Нет ложного fallback/дубликата.
- Словарь и специальные богословские термины версионированы.

### Gate F — reader release

- Manifest schema valid.
- Все asset references существуют и checksums совпадают.
- TOC targets разрешаются.
- Scan/source links открываются.
- Runtime не предлагает несуществующий language/view.

### Gate G — publication

- Unit/integration/contract/E2E suites зелёные.
- Staged release проверен отдельно от live path.
- Нет Critical/High open findings.
- Есть release report и rollback target.

---

## 10. Staging, атомарная публикация и deploy

### 10.1 Каталог релиза

```text
storage/jobs/<job-id>/
  source/source.pdf
  evidence/pages/*.json
  evidence/renders/*.webp
  candidates/native/*.json
  candidates/ocr/*.json
  ast/<revision>.json
  translations/<lang>/<revision>.json
  validation/findings.json
  release/<release-id>/
    manifest.json
    pages/*.json
    checksums.json
    release-report.json

storage/releases/<release-id>/
  immutable candidate copied from a known checkout/commit
  manifest.json
  checksums.json
  deploy-metadata.json
```

### 10.2 Promotion

1. Собрать release в job staging, затем скопировать проверенный candidate в `storage/releases/<release-id>` из известного checkout/commit.
2. Проверить schema, count, checksums и links.
3. Записать immutable media keys.
4. Создать новый versioned manifest.
5. Выполнить build/E2E против staged manifest.
6. Атомарно обновить маленький registry pointer.
7. Зафиксировать previous release ID.
8. Только затем deploy shell/registry из immutable candidate, а не из активного рабочего дерева.

Ни один шаг не перезаписывает текущий manifest до Gate G.

Если процесс упал после переключения локального release pointer или перезапуска origin, publisher сначала сверяет текущий pointer, checksums и публичный health endpoint. Повторная promotion вслепую запрещена. Версии build dependencies фиксируются; production всегда предваряется проверкой того же immutable артефакта на loopback preview.

### 10.3 Конкуренция

- Unique slug reservation включает book identity, не только title.
- Publication lock один на registry/release pointer.
- Media keys content-addressed и не требуют overwrite.
- Два job могут извлекать разные книги параллельно, но promotion сериализован.

---

## 11. Frontend migration

### 11.1 Совместимость

Ввести adapter `ManifestV1 -> BookManifestV2`. Существующие книги продолжают открываться до миграции данных. Не менять все manifests одновременно с reader engine.

### 11.2 Reader storage v2

```text
logos.reader.settings.v2                         global
logos.reader.book.<bookId>.last-location.v2     per book
logos.reader.book.<bookId>.bookmarks.v2         per book
logos.reader.book.<bookId>.cards.v2             per book
```

Миграция legacy:

- выполняется один раз;
- старые карточки привязываются к `schreiner-ntt` только если сохранённые metadata однозначно доказывают книгу; совпадения одной `page` недостаточно;
- неоднозначные данные сохраняются в legacy bucket и показываются как требующие выбора;
- старые ключи не удаляются до успешной записи и проверки v2;
- миграция идемпотентна.

`ResearchCard` получает `bookId`, `releaseId`, `blockId`, `sourceAnchor` и snapshot citation metadata.

### 11.3 Единая route command

```ts
openLocation({ bookSlug, pageKey, blockId?, footnoteId? })
```

Она:

1. разрешает target manifest;
2. проверяет target bounds;
3. атомарно меняет book/location;
4. обновляет hash;
5. восстанавливает scroll/focus;
6. закрывает stale overlays.

Один parser/serializer обслуживает initial load, Back/Forward, TOC, search, catalog и ссылки из карточек.

### 11.4 Lazy data и поиск

- Registry содержит summary и URL index, а не весь текст книги.
- Page chunks загружаются по demand и кешируются.
- Search index строится заранее либо работает в Web Worker.
- Input имеет debounce 200–300 ms.
- Результаты ограничены/виртуализированы.
- Возвращаются все релевантные matches, включая повторные.
- Result содержит block/footnote target; после открытия выполняется focus/highlight.

### 11.5 Citation

Форматирование получает `BookCitationMetadata`; ни один автор/название не hard-coded. Экспорт должен содержать book/release/source page и уметь вернуться к блоку.

---

## 12. UI/UX implementation specification

### 12.1 Reference lock

Design brief:

```text
Проектируем академическую веб-читалку для студентов, преподавателей и
исследователей. Главная цель — долго читать, быстро сверять источник и
делать точные выписки. Тон — сосредоточенный, редакционный, надёжный.
Главный риск — инструменты и неверная структура отвлекают от текста.
Путь — постепенная доработка текущего React UI, не визуальная перепись.
```

| Референс | Закреплённая роль | Что взять | Что не копировать |
|---|---|---|---|
| Readwise Reader | основной | текст как главный слой, contextual actions, спокойная плотность | брендинг и точную композицию |
| Apple Books | вторичный | настройки чтения, mobile ergonomics, progressive disclosure | consumer-декорации вне роли |
| Zotero | вторичный | scholarly notes, citation/source return, явная связь аннотации с документом | desktop-плотность целиком |

Reject: generic SaaS dashboard, декоративные градиенты, чрезмерные карточки, постоянный ряд всех действий, «AI-пастель» без роли.

### 12.2 Информационная иерархия reader

1. Текст/страница и текущая позиция.
2. Название книги и раздел.
3. Навигация назад/вперёд.
4. Контекстные действия выделения/абзаца.
5. Поиск, TOC, scan/compare, заметки и settings по запросу.

Desktop header не должен одновременно показывать каталог, TOC, режим, page badge, scan, cards, search, settings, help и fullscreen как равноправные controls.

### 12.3 Компонентная схема

```text
ReaderShell
  ReaderTopBar
    BackToLibrary
    BookPosition
    PrimaryViewSwitcher
    MoreMenu
  ReadingCanvas
    DocumentBlockRenderer
    ContextActionTrigger
    SourceComparePane?
  ReaderBottomNav (mobile / zen)
  TocSheet
  SearchDialog
  ReadingSettingsSheet
  NotesDrawer
  SourceViewer
```

`DocumentBlockRenderer` переключается по AST `type`, а не угадывает заголовок по длине строки.

`ReaderWorkspace` — явный composition contract: один `main` с читаемой колонкой, один именованный complementary region для source/notes и портальные dialog/sheet layers. URL хранит `bookSlug`, stable location и optional `blockId`; активная книга никогда не выводится только из последнего значения localStorage.

### 12.4 Начальные design tokens

Это стартовое направление из аудита, которое Gemini реализует через CSS variables и проверяет контрастом.

```css
:root {
  --reader-bg: #f5f5f4;
  --reader-surface: #ffffff;
  --reader-text: #202124;
  --reader-muted: #5f6368;
  --reader-border: #dedede;
  --reader-accent: #1e40af;
  --reader-accent-hover: #1e3a8a;
  --reader-accent-soft: #e8eeff;
  --reader-focus: #1e40af;

  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-12: 48px;

  --radius-control: 8px;
  --radius-panel: 14px;
  --reader-column: 68ch;
  --motion-fast: 160ms cubic-bezier(0.16, 1, 0.3, 1);
  --motion-panel: 200ms cubic-bezier(0.16, 1, 0.3, 1);
}
```

Роль serif — основной книжный текст. Интерфейс и metadata — sans. Не использовать serif как декоративный маркер «премиальности» во всём UI.

### 12.5 Типографика

- Body desktop: 18–20 px, line-height 1.65–1.8, max width 62–72ch.
- Body mobile: 17–19 px, line-height 1.55–1.7.
- Default alignment: start/left.
- Justify доступен настройкой; при включении требуются `lang`, `hyphens:auto`, `overflow-wrap` и визуальная проверка.
- Heading levels приходят из AST.
- Footnote: меньше body, но не ниже доступного минимального размера.
- Numbers/page counters: tabular figures.

### 12.6 Responsive contracts

#### 375 px

- Верх: Back, сокращённый title/position, More.
- Низ: Prev, location, Next; одна primary contextual action.
- TOC/settings/notes — bottom sheets.
- Scan compare — переключение Text/Scan либо vertical sequence; не две узкие колонки.
- Bilingual — interleaved block pair или language toggle, не две колонки.
- Нет скрытых controls в tab order.

#### 768 px

- Компактный top bar.
- TOC/notes могут быть overlay drawer.
- Compare допускает adjustable split, если обе колонки сохраняют читаемую ширину.
- Bottom navigation остаётся доступной при touch layout.

#### 1440 px

- Центральная колонка 62–72ch.
- Optional source/notes rail открывается без сдвига текста за пределы readable width.
- Secondary controls находятся в меню/rail, а не заполняют header.

### 12.7 State matrix

| Компонент | Default | Hover | Active/selected | Focus-visible | Loading | Empty | Error |
|---|---|---|---|---|---|---|---|
| navigation button | иконка + accessible label | surface tint | pressed 0.98 | 2px focus ring | disabled + progress | n/a | toast/live region |
| view switcher | quiet segmented | border emphasis | accent-soft + strong label | ring per segment | skeleton width fixed | only available views | invalid view fallback |
| paragraph action | one subtle trigger, no reserved gap | reveals actions | selected quote | visible via `focus-within` | n/a | n/a | action remains retryable |
| dialog/sheet | hidden/unmounted | n/a | modal | initial logical focus | labelled skeleton | contextual empty copy | inline summary + recovery |
| search | input + recent/blank guidance | result hover | selected result | keyboard active descendant | cancellable progress | «Совпадений нет» | retry, query preserved |
| scan | source thumbnail/action | zoom cue | compare active | keyboard zoom/actions | aspect-ratio placeholder | «Скан недоступен» | keep text readable |
| audio | play + edition label | control feedback | playing/progress | full keyboard | buffered state | «Аудиоредакции нет» | retry/download fallback |

### 12.8 Dialog accessibility

- `role="dialog"`, `aria-modal="true"`, labelled title.
- Focus enters first meaningful control or heading.
- Tab trapped inside.
- Escape closes top-most layer.
- Focus returns to trigger.
- Background inert/aria-hidden while modal.
- Footnote click target is button/link, не `<li onClick>`.
- Status updates use restrained `aria-live`.

### 12.9 Motion

- 150–200 ms `cubic-bezier(0.16, 1, 0.3, 1)` для hover/panel transitions.
- Не анимировать каждую строку текста.
- Не использовать animation для page navigation, если она вызывает layout shift.
- `prefers-reduced-motion: reduce` убирает transforms и smooth scrolling.

### 12.10 Microcopy

- «Текст», «Скан», «Сверка» — view, не language.
- «Русский», «Қазақша», «English» — language и показываются только при наличии edition.
- «Добавить выписку» вместо абстрактного icon-only действия без accessible name.
- Ошибка контента сообщает: страница, тип проблемы, возможность открыть скан и отправить замечание.
- Пустой поиск: «Введите слово или фразу по текущей книге»; без совпадений: «Ничего не найдено. Проверьте форму слова или откройте оглавление».
- Ошибка локального хранения не маскируется: «Не удалось сохранить прогресс на этом устройстве. Чтение можно продолжить, но позиция может потеряться».
- Никаких утверждений «перевод проверен», если release не имеет такого статуса.

### 12.11 Visual verification protocol для Gemini + chromedriver

Для каждого UI этапа исполнитель обязан:

1. До массового изменения согласовать один эталонный экран reader на Osborne page 600; без reference approval остальной UI этап не расширять.
2. Сохранить before screenshots 375×812, 768×1024, 1440×1000.
3. Проверить каталог, reader, TOC, search, settings, notes, scan и error/empty state.
4. Реализовать только утверждённый этап.
5. Сохранить after screenshots с теми же route, viewport, scroll position и data fixture.
6. Использовать зафиксированный Chromium, DPR 1, локально доступные шрифты и ждать `document.fonts.ready` плюс конкретный DOM/network state; `waitForTimeout` запрещён.
7. Зафиксировать DOM overflow checks: `scrollWidth <= clientWidth`.
8. Проверить клавиатурный путь без мыши.
9. Проверить console errors и failed network requests.
10. В отчёте дать таблицу «reference decision → implementation evidence → screenshot» и drift table по каждому viewport.

Скриншоты складывать в `artifacts/ui/<stage-id>/`; не коммитить временные browser profiles.

---

## 13. Архитектура аудиокниги

Текущий `AUDIOBOOK_TTS_ARCHITECTURE.md` — историческое предложение. В коде нет provider, queue, player, VTT, audio assets или Telegram audio delivery. Устаревшие цены, поддержка языков и неподтверждённые throughput claims нельзя использовать как решение.

### 13.1 Source of speech

```text
ReaderTextRevision
  -> SpeakingProjectionRevision
  -> ChunkPlan
  -> TtsJob
  -> AudioAsset + TimingAsset
  -> AudioEditionManifest
```

Display text не переписывается для озвучки. Speaking projection отдельно решает:

- как читать ссылки Писания;
- Greek/Hebrew: оригинал, транслитерация или пропуск;
- сноски: omit, отдельный notes track или explicit inline;
- числа, инициалы, сокращения, URL, таблицы;
- смешанные языки и ударения.

### 13.2 Speaking block

```json
{
  "blockId": "book:p600:para-3",
  "readerTextRevision": "sha256:...",
  "language": "ru",
  "spokenText": "...",
  "policy": {
    "bibleReferences": "expanded",
    "footnotes": "omit",
    "greekHebrew": "approved_transliteration"
  },
  "editorStatus": "approved"
}
```

### 13.3 Provider port

```ts
type SynthesisRequest = {
  projectHash: string;
  chunkHash: string;
  provider: string;
  model: string;
  voice: string;
  language: string;
  speakingProjection: SpeakingBlock[];
  audioFormat: 'mp3' | 'm4a';
  timingMode: 'none' | 'provider-character' | 'provider-word' | 'forced-alignment';
};
```

Provider без alignment metadata получает только block-level timing. Нельзя выдумывать word-level VTT.

### 13.4 Chunk/cache/retry

- Chunk по block/sentence boundaries, целевой размер 1–3 минуты аудио после пилота.
- Hash включает exact spoken text, provider/model/voice, dictionary, settings и format.
- Состояния: `planned -> submitted -> completed -> verified -> published`.
- До paid call проверяется verified cache.
- Budget estimate и ceiling фиксируются до первой отправки.
- Timeout после `submitted` не повторяется вслепую.
- Verify: checksum, decode, duration, channel/sample metadata, timing bounds, silence anomalies.

### 13.5 Web delivery

- Immutable audio URL.
- Корректные `Content-Type`, `Content-Length`, `ETag`, Range/206.
- Progress key: `(audioEdition, chunkId, offsetMs)`.
- При новой edition позиция переносится по stable block ID, не по старым milliseconds.
- VTT — derived artifact, связанный с exact projection revision.

### 13.6 Telegram

- Использовать `sendAudio`, если нужен audiobook/music-player UX.
- Текущий Bot API указывает лимит `sendAudio` 50 MB; operational ceiling установить 45 MB и всё равно резать по фактическому размеру кодированного файла, а не по выдуманному числу минут.
- Chapter title/performer/cover берутся из manifest.
- `sendVoice` не является default.

### 13.7 Обязательный пилот

До полной книги:

1. RU sample 2–3 минуты со ссылками Писания и Greek/Hebrew.
2. KK sample 2–3 минуты со специфическими графемами и именами.
3. EN sample 2–3 минуты.
4. Для каждого: exact input hash, provider/model/voice/settings, request ID, billed units, cost, duration, decode, timing и editor score.
5. Только после прослушивания выбирается provider per language и full-book budget.

Актуальные provider возможности и цены проверять в день пилота. Официальные источники перечислены в разделе 18.

---

## 14. Hosting и доставка медиа

### 14.1 Утверждённая production-граница

```text
Internet browser
  -> Cloudflare DNS/TLS/cache/WAF
  -> named Cloudflare Tunnel (outbound connection from home)
  -> cloudflared systemd service on Ubuntu
  -> Caddy bound to 127.0.0.1:<origin-port>
  -> immutable release selected by an atomic current pointer
       ├─ Vite shell + registry/manifests
       ├─ page JSON and search indexes
       ├─ scans and source PDFs
       └─ audio/VTT when approved

Telegram -> bot/worker -> per-job staging -> verified local release -> atomic promotion
```

Netlify не входит в production delivery path. R2 не обязателен на первом запуске и остаётся совместимым будущим adapter для overflow, backup или выноса самых тяжёлых public assets.

### 14.2 Ограничения домашнего public origin

Tunnel решает NAT/CGNAT, TLS edge и необходимость входящих портов, но не решает питание, Wi-Fi, upload bandwidth, отказ диска, backup и отсутствие SLA. Это осознанный owner trade-off: если Ubuntu выключена или домашний интернет недоступен, библиотека недоступна. Никакой UI не должен заявлять обратное.

### 14.3 Локальная файловая модель

```text
/srv/logos/releases/<release-id>/
  app/
  catalog.json
  books/<book-id>/<book-release-id>/manifest.json
  books/<book-id>/<book-release-id>/pages/*.json
  books/<book-id>/<book-release-id>/scans/page-0001.webp
  books/<book-id>/<book-release-id>/source/source.pdf
  books/<book-id>/<book-release-id>/audio/<edition>/<chunk-hash>.m4a
  books/<book-id>/<book-release-id>/audio/<edition>/<chunk-hash>.vtt
/srv/logos/current -> /srv/logos/releases/<release-id>
/srv/logos/staging/<job-id>/
/srv/logos/backups/
```

- Release directories и book-release paths immutable; `current` переключается атомарной заменой symlink/pointer.
- Worker пишет только в staging. Caddy читает только verified releases и не имеет доступа к inbox, SQLite, `.env`, tunnel credentials или source с запрещённым public access.
- Caddy слушает только loopback; router port-forward и public bind не нужны.
- Correct MIME для PDF/WebP/JSON/M4A/VTT; `GET`, `HEAD`, byte `Range`/`206`, `Content-Length` и `ETag` проверяются интеграционно.
- Hash-versioned assets получают длинный immutable cache; `index.html`, registry, release pointer и health metadata получают короткий cache/no-cache согласно роли.
- Неавторизованные source PDF/scans не копируются в public release. Для authenticated/private editions нужен отдельный access design, а не скрытый URL.
- Disk low-watermark блокирует новую ingestion/promotion до исчерпания места; backup проверяется восстановлением, а не наличием файла.

### 14.4 Central asset resolver

Frontend получает `assetUrl(key)` через единственный adapter и `VITE_ASSET_ORIGIN`. Сначала тесты same-origin/absolute-origin, затем миграция URLs. Не выполнять массовую замену строк `/scans/` без контракта.

Primary mode — same-origin через Caddy/Tunnel. Absolute origin остаётся совместимостью для будущего R2 без переписывания manifests.

### 14.5 Стоимостные формулы

```text
audio_decimal_GB = hours * 3600 * bitrate_kbps / 8,000,000
scans_GiB        = pages * mean_scan_KiB / 1,048,576
active_storage   = source_PDFs + scans + audio + 10-20% headroom
```

Основные capacity-параметры для Ubuntu: usable disk, growth per book, backup overhead, upload Mbps, одновременные readers и cache hit ratio Cloudflare. Тарифы/лимиты Cloudflare перепроверяются в день provisioning; не считать Tunnel или CDN «безлимитным» без проверки выбранного плана.

### 14.6 Cutover

1. Inventory данных, rights, sizes, свободного диска и backup target.
2. Создать отдельного system user/group и `/srv/logos/{staging,releases,backups}` с минимальными правами.
3. Реализовать asset resolver и immutable release layout.
4. Собрать release, checksums и staged manifest вне active checkout.
5. Настроить Caddy на `127.0.0.1:<origin-port>`: SPA fallback только для routes, не для отсутствующих assets.
6. Проверить loopback `200/404/206`, MIME, ETag, cache headers, deep links и отсутствующий asset.
7. Установить named `cloudflared` tunnel как systemd service; token/credentials только вне Git.
8. Привязать owner-approved hostname и ограничить ingress единственным Caddy origin; admin routes закрыть Cloudflare Access либо не публиковать.
9. Выполнить внешний smoke test через мобильную сеть, затем атомарно переключить `current`.
10. Проверить systemd restart, отключение origin, rollback pointer и восстановление backup.

### 14.7 Runtime/process contract

| Process | Lifecycle | Health | Secrets |
|---|---|---|---|
| `logos-origin` (Caddy) | systemd, restart on failure | loopback `/healthz` + asset probe | none |
| `cloudflared` | vendor/systemd unit, named tunnel | tunnel status + external probe | tunnel credential only |
| `logos-bot` | systemd, graceful shutdown | process/job heartbeat | Telegram token + admin ID |
| `logos-worker` | systemd, bounded concurrency | lease heartbeat/queue metrics | only provider keys required by current step |

Startup order не означает readiness. Tunnel может быть connected при неготовом origin; внешний smoke test обязателен. Caddy и Tunnel не запускаются от root без необходимости.

### 14.8 Rights/access record — обязательный gate

До передачи текста внешнему AI/TTS и до создания public URL хранится отдельное решение:

```text
editionId, sourceSha256, rightsHolder, decisionOwner, decidedAt, expiresAt?
allowWebText, allowSourcePdf, allowScans, allowAiProcessing, allowTts,
allowTelegramDelivery, voiceConsentRef?, accessMode(public|authenticated|private), notes
```

- Отсутствующее или истёкшее решение означает deny.
- Права на исходный PDF, адаптированный текст, перевод, scans и audio оцениваются отдельно.
- `allowTts` не подразумевает `allowTelegramDelivery`; `allowAiProcessing` не подразумевает public web.
- Voice cloning требует отдельного документированного consent reference; generic voice не отменяет проверку прав на сам текст.
- Manifest публикует только безопасный access status, не персональные данные и не договоры.

---

## 15. Security и операционная защита

### 15.1 Немедленные действия владельца

- Ротировать Telegram token, который ранее попал в код/историю.
- Хранить новый token только в server secret environment.
- Сделать admin allowlist обязательным; отсутствие ID = startup failure.
- Проверить Git history и логи перед публикацией репозитория.
- Не включать секреты в `AGY_IMPLEMENTATION_REPORT.md`.

### 15.2 Upload policy

- Проверка sender до download.
- Ограничение MIME, размера, page count и безопасного filename.
- Storage path генерируется системой, не пользователем.
- Проверка PDF parser в ограниченном worker workspace.
- Quota: один active paid job на owner по умолчанию.
- Duplicate SHA сообщает о существующей книге/job.

### 15.3 Agent sandbox

- Agent получает только per-job input/output directories.
- Нет deploy credentials, repo-wide write и shell permission в extraction/translation run.
- Prompt templates immutable/versioned.
- Model output никогда не исполняется как command.
- Все пути canonicalized и должны оставаться внутри job root.

### 15.4 Logs

Structured fields: `job_id`, `step`, `attempt`, `book_id`, `page`, `batch`, `duration`, `status`, `error_code`, `provider_request_id` redacted as needed.

Не логировать:

- токены/пароли;
- полный текст книги;
- provider request payload;
- cookies/auth headers;
- signed URLs.

### 15.5 Изоляция сервисных учёток

| Identity | Разрешено | Запрещено |
|---|---|---|
| Telegram bot | принять allowlisted upload, enqueue, status | promotion, Caddy/Tunnel config, model/TTS credentials |
| ingestion worker | читать immutable source, писать job artifacts | production pointer, Telegram token, broad home access |
| agy/model adapter | читать конкретный batch, писать typed response | repo-wide shell/write, deploy/storage credentials |
| TTS adapter | читать approved speaking chunks, писать candidate audio | source PDF, production publish, unlimited spend |
| publisher | читать verified release, писать versioned media/pointer | model prompts, arbitrary job inputs, source mutation |

Credentials разные, минимально scoped и ротируемые независимо. Ни одна service identity не получает все пять наборов прав.

### 15.6 Ограничения текущего домашнего worker

Перед OCR benchmark проверить наличие binary через `command -v tesseract` и зафиксировать версию; на момент аудита `tesseract` не был доступен в `PATH`. Из-за ограниченной памяти и наблюдавшегося swap pressure concurrency для render/OCR начинается с `1` и повышается только по замерам RSS, load и времени страницы.

---

## 16. Этапы реализации

Каждый этап — отдельный запуск agy и отдельный отчёт.

### P0 — Security containment

**Цель:** закрыть текущую fail-open границу до развития функций.

**Файлы:** `ingestion_service/config.py`, `bot.py`, startup scripts, tests.

**RED:**

- startup без `TELEGRAM_BOT_TOKEN` падает с безопасным сообщением;
- startup без admin allowlist падает;
- unauthorized document не скачивается и job не создаётся;
- filename не может выйти из inbox;
- repository scan обнаруживает запрещённый token pattern.

**GREEN:** удалить secret default, валидировать env, deny-by-default, safe generated path, rotate token вне кода.

**Приёмка:** unit/integration tests; `git grep` не находит secret; сервис запускается на сервере только с secret env. Не показывать значения в отчёте.

**STOP:** если token не ротирован владельцем, кодовый этап можно закончить, но production service не перезапускать.

### P1 — Characterization tests и V2 contracts

**Цель:** заморозить текущее поведение и ввести versioned types без массового рефакторинга.

**RED:** tests для `ManifestV1 -> V2`, stable IDs, source anchors, capabilities и schema rejection.

**GREEN:** domain models, schemas, adapter; текущие manifests открываются через V1 adapter.

**Приёмка:** старые reader tests зелёные; новые contract tests зелёные; fixtures не требуют browser/network.

### P2 — Durable jobs и worker

**Цель:** убрать обработку из detached bot task.

**RED:** restart/resume, expired lease reclaim, stale worker rejection, duplicate hash, max attempts, deterministic order.

**GREEN:** migrations, repository, worker loop, Telegram enqueue/status adapter.

**Приёмка:** simulated SIGTERM после batch; новый worker продолжает без повторения verified step; бот остаётся responsive.

### P3 — Immutable source и page evidence

**Цель:** зафиксировать PDF, рендеры, candidates и классификацию.

**RED:** corpus fixtures из раздела 7, duplicate spread, bad Unicode, ClearScan, metadata conflict.

**GREEN:** source repository, page records, router signals, raw candidates, render hashes.

**Приёмка:** один отчёт на шесть fixtures; никакой модельный вызов; raw evidence сохранён.

### P4 — Document AST и fidelity validator

**Цель:** заменить `ParagraphPair` как формат ingestion.

**RED:** heading, bold/italic runs, list, quotation, two-column order, table/figure fallback, footnote anchors, reversible normalization, citations/digits.

**GREEN:** AST builder + deterministic validators.

**Приёмка:** Осборн 54/55/158/600/609/693/736 и corpus holdouts защищены тестами.

### P5 — Translation adapter hardening

**Цель:** типизированный, least-privilege и resume-safe model boundary.

**RED:** prompt injection fixture, partial output, duplicate source language, page/block mismatch, timeout/submission unknown, rate limit.

**GREEN:** data envelope, schema validation, batch hash/cache, durable submitted state, no success fallback.

**Приёмка:** fake agent tests; платные/реальные model calls запрещены на этом этапе.

### P6 — Staged release и atomic promotion

**Цель:** live library не меняется до полной проверки.

**RED:** failure after scans, after manifest, during tests, concurrent same slug, rollback pointer.

**GREEN:** staging release, checksum manifest, release validator, serialized promoter.

**Приёмка:** fault injection на каждом шаге оставляет старую release рабочей; stale lease holder не может завершить/publish job; все candidate writes происходят вне активного checkout.

### P7 — Reader storage/citation/router migration

**Цель:** исправить межкнижное смешение и deep links.

**RED:** одинаковая page двух книг не смешивает state; legacy migration; open target page с границами другой книги; Back/Forward; citation per book/release.

**GREEN:** storage v2, `openLocation`, citation metadata, hash parser/serializer.

**Приёмка:** integration tests и ручной browser path для двух книг.

### P8 — Lazy manifests и search

**Цель:** убрать большой eager bundle и блокирующий поиск.

**RED:** repeated matches, footnote target, cancellation/debounce, result limit, highlight, unavailable chunk error.

**GREEN:** registry summary, page loader/repository, index/worker search.

**Приёмка:** initial bundle budget и responsive search; никаких произвольных sleeps.

### P9 — Reader UI shell

**Цель:** спокойная reference-locked композиция без потери функций.

**RED:** accessible names, focus trap/restore, keyboard path, state visibility, no overflow 375/768/1440.

**GREEN:** top bar, More menu, contextual paragraph action, mobile bottom nav/sheets.

**Приёмка:** before/after screenshots, console/network clean, visual decision ledger.

### P10 — AST renderer и source compare

**Цель:** отображать структуру, а не эвристику строк.

**RED:** headings/runs/lists/quotes/table/figure/footnote/page break; compare fallback; source anchor navigation.

**GREEN:** renderer by discriminated union, source viewer contracts.

**Приёмка:** visual fixtures страниц Осборна и corpus; WCAG/keyboard pass.

### P11 — Ubuntu origin + Cloudflare Tunnel

**Цель:** исключить Netlify из production path и безопасно отдать versioned shell/PDF/scans/audio с домашней Ubuntu через named Tunnel.

**Предусловие:** права на публикацию, hostname/domain и Cloudflare account access подтверждены владельцем; Ubuntu online и доступна.

**RED:** release-root traversal, resolver, SPA route versus missing asset, MIME, `HEAD`, `Range/206`, ETag/cache policy, disk watermark, systemd restart, external unavailable-origin behavior, rollback.

**GREEN:** `/srv/logos` permissions/layout, atomic pointer publisher, Caddy loopback config, health endpoint, named cloudflared systemd handoff, backup/restore runbook. R2 adapter не требуется для приёмки.

**Приёмка:** loopback suite зелёный; внешний hostname проверен не из домашней LAN; router ports закрыты; reboot/restart и rollback доказаны; current release продолжает открывать PDF/scan/deep links.

### P12 — TTS pilot infrastructure

**Цель:** реализовать speaking projection/jobs без полной книги.

**RED:** normalization policies, chunk hash, budget rejection, timeout unknown, decode/timing validation, progress migration by block ID.

**GREEN:** provider port, fake provider, manifest/player skeleton.

**Приёмка:** unit/contract tests; реальные paid calls только в P13.

### P13 — Paid three-language TTS pilot

**Предусловие:** владелец утвердил provider, voices, consent/licensing и денежный ceiling.

**Действия:** три коротких samples RU/KK/EN; никаких full-book runs.

**Приёмка:** фактическая стоимость, pronunciation rubric, continuity, timing, size, legal provenance. Затем отдельное решение о provider per language.

### P14 — Onboard six books

**Предусловие:** P0–P10 закрыты; rights decision записан; каждый PDF проходит dry-run report.

Порядок рекомендуется от простого к сложному:

1. Penner/native good.
2. Fee/Stewart/native + end TOC.
3. Kaiser/metadata conflict + geometry.
4. Ladd/ClearScan.
5. Morris/bad Unicode dual path.
6. Tenney/image-only duplicate spreads.

Каждая книга — отдельный job/review/release. Не публиковать шесть одновременно.

---

## 17. Test pyramid и quality matrix

### 17.1 Unit

- state machine transitions;
- lease/optimistic version rules;
- slug/identity/citation;
- PDF classification scoring;
- normalization invariants;
- AST validators;
- manifest adapters;
- router/hash parser;
- storage migration;
- TTS projection/chunk hash.

### 17.2 Integration

- SQLite migrations and restart;
- filesystem staging/promotion with failure injection;
- PyMuPDF fixtures;
- fake agy subprocess protocol;
- React hook + repository/storage adapters;
- Caddy/local release integration, Range/headers и atomic pointer failure injection.

### 17.3 Contract

- Agent input/output schemas;
- Manifest V1/V2;
- release checksums;
- provider TTS response normalization;
- asset headers/Range behavior.

### 17.4 E2E

- open catalog → book → TOC → location;
- Back/Forward across books;
- search → exact paragraph/footnote highlight;
- create/export card with correct citation;
- Text/Scan/Compare availability;
- keyboard-only dialogs;
- responsive 375/768/1440;
- media missing/error recovery;
- audio play/seek only after TTS phase.

### 17.5 Security

- unauthorized upload is rejected before download;
- path traversal filename;
- oversized/wrong MIME;
- prompt injection inside PDF text;
- model output path/command injection;
- secret scan;
- log redaction;
- deploy adapter least privilege.

### 17.6 Запрещённые тестовые практики

- `sleep` вместо explicit condition;
- real paid API в unit/integration suite;
- production data mutation;
- retry until green;
- snapshots вместо semantic assertions для business rules;
- утверждение «всё проверено» без commands/codes/artifacts.

---

## 18. Решения ADR, которые нужно утвердить

### ADR-003 — Versioned Document AST

**Decision:** source fidelity хранится как immutable AST revisions с provenance.
**Alternatives:** прежние `en/ru` strings; HTML blobs.
**Trade-off:** больше данных/кода, но исчезают heuristic headings и необъяснимые исправления.

### ADR-004 — Durable SQLite worker

**Decision:** отдельный worker + leases/checkpoints поверх SQLite.
**Alternatives:** detached task; Redis queue.
**Trade-off:** migrations и worker service, но без нового server product.

### ADR-005 — Atomic release promotion

**Decision:** immutable staging/release + pointer switch.
**Alternatives:** прямое копирование в `app/public` и manifest overwrite.
**Trade-off:** дополнительное storage и release metadata ради rollback.

### ADR-006 — Ubuntu public origin + Cloudflare Tunnel

**Decision:** Caddy на loopback раздаёт immutable releases с локального Ubuntu disk; named Cloudflare Tunnel публикует approved hostname. Netlify исключён; R2 остаётся optional future adapter.
**Alternatives:** Pages + R2; всё в Netlify; прямой router port-forward.
**Trade-off:** снимаются Netlify deploy-size constraints и сохраняется контроль над большим корпусом, но uptime, upload, disk, backup и энергопитание становятся ответственностью владельца.

### ADR-007 — Provider-neutral TTS

**Decision:** speaking projection и provider port; provider выбирается пилотом per language.
**Alternatives:** hard-code одного provider; self-host GPU TTS.
**Trade-off:** больше contracts, но стоимость/качество/лицензии не зашиты в domain.

До пользовательского согласования статусы этих ADR остаются `Proposed`.

---

## 19. Внешние источники, которые перепроверяются перед исполнением

- OpenAI text-to-speech: <https://developers.openai.com/api/docs/guides/text-to-speech>
- ElevenLabs pricing: <https://elevenlabs.io/pricing>
- ElevenLabs models: <https://elevenlabs.io/docs/overview/models>
- Azure Speech language support: <https://learn.microsoft.com/en-us/azure/ai-services/Speech-Service/language-support>
- Cloudflare R2 pricing: <https://developers.cloudflare.com/r2/pricing/>
- Cloudflare R2 public/custom domains: <https://developers.cloudflare.com/r2/buckets/public-buckets/>
- Cloudflare Pages limits: <https://developers.cloudflare.com/pages/platform/limits/>
- Cloudflare Tunnel: <https://developers.cloudflare.com/tunnel/>
- Cloudflare Tunnel published applications: <https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/routing-to-tunnel/>
- Caddy file server: <https://caddyserver.com/docs/quick-starts/static-files>
- Caddy request matchers/headers: <https://caddyserver.com/docs/caddyfile/matchers>
- Netlify credit pricing: <https://docs.netlify.com/manage/accounts-and-billing/billing/billing-for-credit-based-plans/credit-based-pricing-plans/>
- Netlify legacy pricing: <https://docs.netlify.com/manage/accounts-and-billing/billing/billing-for-legacy-plans/legacy-pricing-plans/>
- Telegram `sendAudio`: <https://core.telegram.org/bots/api#sendaudio>

Цифры и model availability из старых документов не копируются без проверки в день действия.

---

## 20. Финальный Definition of Done программы

Программа считается выполненной, когда:

- секреты ротированы и deny-by-default подтверждён;
- worker выдерживает restart и duplicate execution;
- все шесть классов/книг имеют regression fixtures;
- published block имеет provenance;
- Осборнские дефекты защищены тестами и исправлены новой release;
- перевод не может ложно завершиться fallback;
- publication атомарна и имеет rollback;
- state/citations/routes не смешиваются между книгами;
- reader отображает AST без эвристики длины строки;
- UI проверен 375/768/1440, keyboard и WCAG AA;
- тяжёлые public assets доставляются через утверждённое object storage решение;
- TTS provider выбран по измеренному RU/KK/EN пилоту, а не маркетинговой таблице;
- каждая добавленная книга имеет source hash, validation report, release report и rights decision;
- все команды и доказательства сохранены в поэтапных AGY reports.

До этого нельзя заявлять, что конвейер универсален или что новая книга готова автоматически.
