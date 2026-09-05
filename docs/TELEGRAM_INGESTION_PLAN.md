# План реализации: Telegram-бот + agy CLI для автоматической обработки и публикации книг

## 1. Обзор и цель
Автоматизация конвейера добавления новых книг (в первую очередь **PDF**) в цифровую двуязычную читалку:
1. Пользователь отправляет PDF книги в Telegram-бот.
2. Бот ставит задачу в очередь SQLite и мгновенно подтверждает прием.
3. Фоновый воркер извлекает текст, структуру и изображения страниц (PyMuPDF).
4. Агентный мост через **`agy cli`** выполняет академический богословский перевод, связывает сноски и выравнивает параллельные блоки.
5. Результат компилируется в каталог библиотеки (`Multi-Book Library`), тестируется (`npm test`) и автоматически деплоится на Netlify в production.
6. Бот информирует пользователя о каждом этапе и присылает ссылку на опубликованную книгу.

---

## 2. Утвержденная архитектура: Hexagonal Async Engine (Option 4)

### Компоненты системы

```mermaid
graph TD
    User([Telegram Пользователь]) -->|Отправляет PDF| BotAdapter[Telegram Delivery Adapter<br/>aiogram 3.x]
    
    subgraph "Telegram Gateway & Очередь"
        BotAdapter -->|Сохранение файла| InboxStorage[(/storage/inbox/*.pdf)]
        BotAdapter -->|Создание задачи| SQLiteDB[(SQLite: jobs & books)]
        BotAdapter -.->|Редактирование прогресса в чате| User
    end

    subgraph "Core Ingestion Engine (Чистая доменная логика)"
        WorkerDaemon[Worker Process] -->|Опрос очереди| SQLiteDB
        WorkerDaemon --> PDFExtractor[PyMuPDF: Текст, Сканы, TOC]
        PDFExtractor --> BatchChunker[Макро-батчер: 5-8 стр.]
        BatchChunker --> AgentPort[Порт IAgentExecutor]
    end

    subgraph "Агентный слой: agy CLI"
        AgentPort --> AgyRunner[AgyCliRunner: agy -p stream-json]
        AgyRunner --> GeminiModel[Gemini 3.8 / 2.5 Agent Engine]
        GeminiModel -->|JSON: ParagraphPair[], Footnotes[]| AgentPort
    end

    subgraph "Публикация и Верификация"
        WorkerDaemon --> LibraryBuilder[Компилятор библиотеки]
        LibraryBuilder --> MultiBookData[(app/src/data/books/{slug}/)]
        LibraryBuilder --> TestSuite[Vitest: npm test]
        TestSuite --> NetlifyDeployer[Netlify CLI: deploy --prod]
        NetlifyDeployer --> ProductionURL[Production Web Reader]
        NetlifyDeployer -.->|Финальное уведомление со ссылкой| BotAdapter
    end
```

---

## 3. Схема данных и статусы задач (SQLite)

### Таблица `jobs`
* `id`: TEXT PRIMARY KEY (UUID)
* `telegram_user_id`: INTEGER
* `telegram_message_id`: INTEGER (для редактирования сообщения с прогрессом)
* `file_name`: TEXT
* `file_path`: TEXT
* `book_slug`: TEXT
* `total_pages`: INTEGER
* `processed_pages`: INTEGER
* `current_batch`: INTEGER
* `total_batches`: INTEGER
* `status`: TEXT (`QUEUED`, `EXTRACTING`, `TRANSLATING`, `COMPILING`, `TESTING`, `DEPLOYING`, `COMPLETED`, `FAILED`)
* `error_message`: TEXT NULL
* `live_url`: TEXT NULL
* `created_at`: DATETIME
* `updated_at`: DATETIME

---

## 4. Пакетная нарезка и мост к `agy cli`

### Контракт вызова `agy cli`
* Команда:
  ```bash
  agy -p "<PROMPT>" \
    --dangerously-skip-permissions \
    --input-format text \
    --output-format json
  ```
* **Промпт шаблона батча:**
  * Передача исходного текста страниц с маркерами `[PAGE_START: N]`.
  * Инструкция по академическому богословскому переводу на русский язык.
  * Требование строгого JSON-вывода:
    ```json
    [
      {
        "pageNumber": 867,
        "chapterTitle": "Введение",
        "paragraphs": [
          { "id": "p-867-1", "en": "...", "ru": "..." }
        ],
        "footnotes": [
          { "id": 1, "textEn": "...", "textRu": "..." }
        ],
        "readingTimeMinutes": 2
      }
    ]
    ```

---

## 5. Доработки фронтенда (Multi-Book Library)

1. **Каталог книг (`app/src/data/library/`):**
   * Реестр доступных книг: `libraryManifest.ts`.
   * Каждая книга в отдельной папке: `books/{slug}/manifest.json` и сканы `public/scans/{slug}/`.
2. **Маршрутизация читалки:**
   * Поддержка выбора книги через меню/селектор в шапке или URL-хеш (`#book=schreiner-ntt&page=867`).
3. **Обратная совместимость:**
   * Текущая книга Томаса Шрайнера автоматически становится первой книгой в библиотеке (`schreiner-ntt`).

---

## 6. Улучшенная мобильная адаптация (Mobile-First Experience & Ergonomics)

Ориентир на эталонные мобильные читалки (Apple Books, Notion, Readwise Reader) в соответствии со стандартом `AGENTS.md` (валидация на экранах от 375px):

1. **Эргономика под большой палец одной руки (Thumb Zone UX):**
   * Все ключевые действия (перелистывание страниц, вызов карточек, поиск, переключение языка) в мобильном представлении выносятся в нижнюю панель быстрого доступа (`Bottom Navigation Dock`).
   * Увеличенные зоны нажатия (touch targets не менее 44×44px по гайдлайнам Apple HIG).

2. **Мобильные шторки снизу (Native Bottom Sheets):**
   * На экранах `< 640px` боковые ящики (Оглавление, Настройки, Картотека) трансформируются в шторки, выезжающие снизу вверх (`Bottom Sheet`) с ручкой перетаскивания (`drag handle`) и закрытием свайпом вниз.

3. **Свайп-навигация (Touch Gesture Engine):**
   * Поддержка естественных горизонтальных свайпов влево/вправо (`touchstart` / `touchend`) для перелистывания страниц книги.
   * Анимация плавного перелистывания с инерцией.

4. **Двуязычный режим на смартфонах (Bilingual Mobile View):**
   * На узких экранах (375–430px) параллельные колонки сжимаются и становятся нечитаемыми.
   * **Решение:** Интеллектуальный интерливинг — абзац оригинала и абзац перевода группируются в единую адаптивную карточку с быстрым переключением акцента (`RU ↔ EN`) в один тап.

5. **Мобильное создание карточек без мыши (Touch Action Triggers):**
   * Замена недоступного на тач-устройствах ховера (`group-hover`) на видимые компактные кнопки у абзаца, а также мгновенный вызов контекстной панели `[📝 Создать карточку]` при выделении текста пальцем.

6. **Адаптивные экраны и безопасные зоны (Safe Areas & dvh):**
   * Корректная поддержка `env(safe-area-inset-bottom)` и `env(safe-area-inset-top)` для предотвращения наложения на панель «Домой» и Dynamic Island на iPhone.
   * Использование единиц `dvh` (Dynamic Viewport Height) для исключения скачков экрана при скрытии адресной строки мобильного браузера.

7. **PWA (Progressive Web App):**
   * Поддержка установки сайта как автономного мобильного приложения на главный экран смартфона (`display: standalone`) с иконкой и запуском без интерфейса браузера.

---

## 7. Пошаговый план реализации (по готовности к выполнению)

* [ ] **Этап 1: Архитектура Мульти-книжной библиотеки на фронтенде**
  * Создать структуру `app/src/data/library/` с реестром книг.
  * Обновить `useReader.ts` для поддержки переключения активной книги.
  * Добавить выпадающее меню выбора книги в `Header.tsx`.
  * Обновить и запустить тесты Vitest.

* [ ] **Этап 2: Улучшенная мобильная адаптация (Mobile-First UX & Gestures)**
  * Реализовать Bottom Sheets для оглавления, настроек и карточек на мобильных экранах.
  * Добавить свайп-жесты влево/вправо для перелистывания страниц.
  * Адаптировать параллельный двуязычный режим для узких мобильных экранов (375px).
  * Добавить поддержку безопасных зон (`safe-area-inset`) и PWA-манифест для полноэкранного запуска на телефоне.

* [ ] **Этап 3: Бэкенд-сервис `ingestion_service/` (Python)**
  * Создать структуру модуля: `ingestion_service/` с `requirements.txt` (`aiogram`, `pymupdf`, `pydantic`).
  * Реализовать очередь задач на SQLite (`queue_manager.py`).
  * Реализовать парсер PDF (`pdf_extractor.py`): извлечение текста, заголовков и рендеринг WebP-сканов страниц.

* [ ] **Этап 4: Мост к `agy cli` (`agy_bridge.py`)**
  * Реализовать вызов `agy -p` в неинтерактивном режиме с валидацией JSON через Pydantic.
  * Добавить обработку ошибок, таймаутов и автоматический повтор упавшего батча.

* [ ] **Этап 5: Компилятор и автодеплой (`publisher.py`)**
  * Запись сгенерированных JSON-батчей в репозиторий книги.
  * Запуск тестов `npm test`.
  * Вызов Netlify CLI деплоя (`npx netlify deploy --prod`).

* [ ] **Этап 6: Telegram-бот (`bot.py`)**
  * Авторизация пользователя по `TELEGRAM_ADMIN_ID`.
  * Прием файлов `.pdf`, обновление прогресса в реальном времени.
  * Финальная выдача ссылки на сайт.
