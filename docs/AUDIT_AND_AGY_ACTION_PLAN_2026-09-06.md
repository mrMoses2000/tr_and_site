# Повторная приёмка «Логоса»: подтверждённые дефекты и задание agy

Дата: 2026-09-06. Проверяемый commit: `8c5ca76c0066432fe1de94270f60294adc47aab1`, ветка `agy/fidelity-recovery`.
Вердикт: **REQUEST CHANGES. Не всё выполнено. Визуальная и функциональная приёмка не пройдена.**

Этот документ — результат независимой проверки, а не отчёт об исправлениях. При его подготовке runtime-код не менялся, бот/платные модели не запускались, DNS и production release не переключались. Проверки кода, reader и hosting выполнялись параллельно тремя субагентами; основной агент независимо проверил браузер, Ubuntu, сборки и реальные извлечения.

## 1. Что реально проверено

| Проверка | Факт / результат |
|---|---|
| Mac и Ubuntu Git | Одинаковый HEAD `8c5ca76`, одна recovery-ветка, исходные деревья чистые; fetch и Ubuntu `pull --ff-only` — already up to date |
| Ubuntu origin | `/srv/logos/current` указывает на `/srv/logos/releases/rel-fidelity-v4`; это отдельное состояние от Git HEAD |
| Доступ для аудита | Mac browser → SSH local forward `127.0.0.1:18080` → Ubuntu `127.0.0.1:8080`; публичный Tunnel не менялся |
| Контрольный PDF | `/home/moses/tr_and_site/storage/inbox/681537e1_Озборн_Герменевтическая спираль.pdf` |
| SHA-256 | `d2736cb9b551bdeef6a5f7b8078c5c4b9a5ab13e6ae9f44eff63aaebc548ef46`, повторно вычислен на Ubuntu |
| Полный extraction dry-run | Все 736 страниц через текущий `PDFExtractor.extract_page_structure`, без публикации и без внешних API |
| Backend | `PYTHONPATH=. .venv/bin/pytest ingestion_service/tests/ -q`: exit 0, 133 passed, 2 skipped, 8.08 s |
| Frontend | В `app`: `./node_modules/.bin/vitest run`: exit 0, 78 passed / 10 files, 7.68 s; есть React `act(...)` warnings |
| Build Ubuntu | Изолированная копия HEAD `/tmp/logos-audit-build.2PmBDT`; `npm run build --prefix .../app`: exit 0; Vite 1.36 s |
| Build Mac | Изолированная копия HEAD `/tmp/logos-review.LHm67f`; `npm ci --ignore-scripts`, затем build: exit 0; Vite 2.32 s |
| Bundle | JS 703.35 kB / gzip 162.94 kB; обе сборки выдают warning о chunk >500 kB, это не «zero warnings» |
| Browser | Osborne PDF 45/46/50/430 × 375/768/1440; исходные PDF renders, сканы, настройки, поиск, языковой переключатель |
| Mac standalone | Свежая локальная сборка на `127.0.0.1:18081`, p430: те же фигуры и дефекты; проблема воспроизводится вне Ubuntu |
| Уже опубликованные figure assets | Все 36 URL отвечают HTTP 200; на контрольных страницах дополнительно проверены decode и naturalWidth |

Нельзя экстраполировать визуальную проверку 4 страниц на 736. Полный extraction pass выполнен, но ручная вычитка всех страниц, других книг, всех тем, всех диалогов и внешнего HTTPS не выполнена. Сквозной запуск Telegram→translation→production намеренно не выполнялся: он затрагивает внешние сервисы/публикацию и не нужен для доказанных ниже дефектов.

Среда: Ubuntu Python 3.14.4 / Node 22.23.1; Mac Python 3.14.6 / Node 24.7.0. При Mac install получен `EBADENGINE`: jsdom требует `^22.22.2 || ^24.15.0 || >=26`. Сборка прошла, но Mac test environment нельзя объявлять поддерживаемым до выбора подходящего Node. `agy` обнаружен на обоих хостах; его наличие не доказывает авторизацию/квоты.

Новые screenshots находятся локально в `tmp/audit-2026-09-06/ubuntu-p{45,46,50,430}-{375,768,1440}.png`; Mac counterpart — `mac-p430-1440.png`. Они не добавлены в Git. Исходные PDF renders: `tmp/pdfs/osborne-pdf-{45,46,50,430}.png`. На новом хосте пересоздать evidence из PDF, не полагаться на наличие Mac tmp.

## 2. Что улучшилось

- В оригинальном режиме extractor действительно формирует AST blocks, а reader отображает их.
- Старые бессмысленные жирные строки из схем на p45/50 заменены изображениями схем; `Во-вторых` и несколько диапазонов исправлены.
- Сохранились полезные queue/release/repository/search foundations и 211 проходящих тестов суммарно; два backend-теста пропущены.
- Фронтенд можно собрать и открыть на Mac без Ubuntu. Для полного PDF-прохода там отдельно нужны разрешённые source files и Python dependencies.

Но **готовая вручную подготовленная книга ≠ воспроизводимый автоматический конвейер следующей книги**.

## 3. Подтверждённые блокирующие дефекты

### F01 / P1 — FAIL не блокирует путь публикации

Текущий полный проход и committed manifest согласованно дают:

```text
pages: 736
block types: heading=51, paragraph=3126, figure=36
reviewStatus: verified=684, corrupt_text_layer=52
page 605: figures FAIL (5 drawings, 0 figures)
page 736: digits FAIL (153 raw / 151 normalized; missing 0, 23)
```

52 suspect pages — метка текущего classifier, не доказательство 52 безвозвратно испорченных страниц. Но такие статусы требуют review, а не молчаливого успеха.

`ingestion_service/pdf_extractor.py:354` возвращает `fidelityValidation`; pipeline/release не используют его как запрещающий gate. `pipeline.py` продолжает собирать/публиковать страницы. Наличие валидатора в отдельном файле не решает проблему.

**Исправление:** единый fail-closed validation contract, запись причин, quarantine/review либо явно проверенный scan fallback. Интеграционный тест: corrupted page/missing media → candidate rejected, active pointer/checksum неизменны. Нельзя просто заменить FAIL на PASS или игнорировать suspect pages.

### F02 / P1 — Автоматическое изготовление figure assets отсутствует

Свежий extraction pass выдаёт **36 из 36 `imageRef` вида `pdf-page://...`**. Например p45: `pdf-page://44/figure/0`. Это внутренний locator, не URL браузерного изображения.

`ingestion_service/ast/builder.py:353,584` создаёт locator; tracked ingestion/scripts не содержат стадии, воспроизводимо превращающей его в WebP clip. `ingestion_service/release/builder.py:224–239` копирует page-level `imageSrc`, не полный граф figure assets. В существующей книге ссылки уже заменены на `/scans/.../fig_p*.webp`, файлы есть и работают. Этот отдельный результат не доказывает автоматизацию.

**Исправление:** tracked media materializer + asset index/checksums + dependency closure в release builder. Тест запускать с новым slug в пустом isolated staging, не подсовывать готовые `/scans`. После сборки все figure URLs — допустимые HTTP paths, файлы реально декодируются. Подмена вручную manifest не является исправлением бота.

### F03 / P1 — p430: обрезка рисунка и дублирование вложенного растра

В браузере p430 первая фигура обрезана справа: край ленточной схемы заканчивается на границе clip. Следующим блоком повторяется ленточный raster-фрагмент той же схемы. Источник PDF содержит одну композицию рисунка 13.1.

Текущий bbox основан преимущественно на text spans, а не union всех нужных raster/vector shapes (`ast/builder.py:342–345`). Вложенный raster не поглощается родительской figure. Подписи p45/50/430 показаны дважды: внутри screenshot crop и отдельным figcaption.

**Исправление:** геометрически полная область рисунка, вложенность/дедупликация media, политика caption exactly once. Не удалять вручную только `fig_p429_1`: тот же алгоритм должен работать для новой книги. Нужны fixtures mixed raster/vector, стрелки за text bbox, captionless и English-caption diagrams.

### F04 / P1 — Сноски потеряны для читателя

На p45/46/50/430 в data присутствуют сноски 6/7/10/1, но в adapted view их bodies не видны, внутри article нет footnote buttons. В p46 `[7]` остаётся обычным текстом; в p45/50 markers внутри картинки не интерактивны.

`app/src/components/ReaderContent.tsx:131–170` возвращается до legacy footnotes footer (`:544`). Page blocks не содержат footnote blocks; `DocumentBlockRenderer` не превращает plain marker в связанную ссылку.

**Исправление:** explicit reference↔footnote binding, полный body, клавиатурный переход/backlink, отсутствующая ссылка — диагностируемая ошибка. Для marker внутри figure дать доступ к связанной сноске рядом с фигурой/source action. Не дублировать сноски при compatibility adapter.

### F05 / P1 — Настройки и язык не работают корректно в AST branch

Проверено браузером p46: настройки изменены 18→26 px, lineHeight 1.75→2.1, localStorage содержит новые значения; computed style текста остаётся **16px / 26px**. `ReaderContent.tsx:134–170` не передаёт эти параметры; renderer задаёт свои стили.

Кнопка `Original` получает selected style, settings.mode становится `en`, но текст остаётся русским. URL продолжает содержать `mode=ru`: `App.tsx:244` меняет settings напрямую, минуя router state. Поиск русской фразы выдаёт два одинаковых результата — «Русский» и «Original EN».

**Исправление:** единый state перехода mode/settings/router; реальные capabilities книги, русскоязычный оригинал не маркировать English/переводом. Настройки должны менять computed style; bilingual выводить только при существующих aligned editions. Отдельный regression для Schreiner.

### F06 / P1 — Мобильная и планшетная верхняя панель не помещается

На всех четырёх страницах horizontal overflow: при viewport 375 document scrollWidth около 572; при 768 — около 1156–1163. На 1440 overflow не обнаружен. Причина видна в `Header.tsx:83–167`: плотные flex-группы не имеют корректного compact/overflow layout. Поиск/настройки уходят за правый край экрана.

Не «исправлять» `overflow-x:hidden`, скрыв недоступные кнопки. Нужен проверенный compact/overflow-menu паттерн, все команды доступны touch/keyboard. Сохранять 44×44 targets. На узком тексте justify также создаёт заметные растянутые межсловные пробелы; проверить читабельность и согласованную типографику, не только размеры контейнера.

### F07 / P1 — V2 контракты расходятся между слоями

Живой artifact — V1-shaped manifest/page с дополнительным blocks, не законченный V2 contract. `libraryRegistry.ts:152–161` требует legacy поля, `pageRepository.ts:42–48` — paragraphs/footnotes. Это не мешает существующему hybrid book загружаться, но настоящий PageV2 может быть отклонён.

На Ubuntu реально выполнен `adapt_manifest_v1_to_v2` над текущим Osborne manifest: `ValidationError`, `caption: Input should be a valid string`. AST `FigureBlock.caption` — array InlineRun, Python `v2/contracts.py:40` — string. `extra='ignore'` также теряет source/table data.

**Исправление:** version-discriminated contracts, lossless adapter/roundtrip и strict shape validation на границах. Тестировать настоящий builder output, не fabricated string caption. Совместимость обсуждать до schema changes; не делать массовую миграцию без плана.

### F08 / P1 — Поиск и карточки не привязаны к AST blocks

Найти «Но скелетная диаграмма», открыть результат p46: URL получает `block=blk-681537e1-ozborn-germenevticheskaya-spiral-p45-0`; соответствующий DOM `data-block-id` существует, но activeElement остаётся BODY, highlight отсутствует. `useReader.ts:425` ищет `data-paragraph-id`, renderer выдаёт `data-block-id`.

`FloatingSelectionToolbar.tsx:50–59` тоже ожидает legacy attributes; `ReaderContent` не передаёт source anchor handler. Карточки могут терять block/language context.

**Исправление:** единый stable block ID и navigation contract для search, selection, cards и source; проверять focus/scroll/highlight/backlink на rendered book.

### F09 / P1 — Стихи, списки, переносы и геометрия не завершены

Реальный p46: `дру-гими`, `прилагатель-ные`; p430: `за-являющие`. Нумерованный список 1–3 склеен в один paragraph. AST всей книги не имеет list/table/quotation; стихотворная stanza/line-break модель отсутствует.

`ast/builder.py:87–104` может склеить split runs `Во-` + `вторых` или `по-` + `русски`, удаляя настоящий дефис без geometry/lexicon, хотя journal пишет `visual_line_continuation+lexicon`. `normalization.py:72–76` глобально заменяет `#`, включая потенциально настоящий символ. Figure detection основан на русских `Рис.`/`Рисунок` и text-based region; sort не является общим column-aware reading order.

**Исправление:** reversible normalization с корректными исходными offsets/причиной/confidence, geometric line/column evidence; типизированные list/verse/stanza или явно проверенный region fallback, если реконструкция ненадёжна. Не whitelist четырёх слов/страниц. Проверять настоящие дефисы, диапазоны, знак `#`, multi-column, poem, table, captionless figure на разных fixtures.

### F10 / P1 — Перевод снова обходит authoritative AST

Original branch улучшен; translation branch `pipeline.py:145+` всё ещё использует `extract_page_text` → bridge → legacy output. CAS/classifier/evidence не стали обязательным общим production flow. Вычисление SHA-256 само по себе не CAS.

**Исправление:** одна authoritative source AST; перевод — projection keyed by stable IDs с preservation media/footnotes/provenance. Тестировать fake translator без платного вызова. FAIL/missing/extra block в projection не может завершаться успешной публикацией.

## 4. Дополнительные дефекты и ограничения доказательств

- SettingsDialog: role=dialog отсутствует; при открытых настройках Escape не закрыл окно в проверенном сценарии. Проверить focus trap/restore, accessible names и все modal states.
- Figure renderer — static img с height cap 500px, нет отдельного accessible zoom/open/source action, retry/error state. Полный page scan p46 открывается и декодируется, но это не figure-to-bbox compare.
- ScanViewer mouse-only pan; touch/pinch не доказаны. Искажённый/отсутствующий asset должен давать явную ошибку, не пустую рамку.
- На homepage жёстко написаны «100% сверка», казахский перевод, bot online и Netlify Production. Эти заявления не выводятся из verified capabilities/runtime health; исправить честность microcopy. Не выдавать оригинал за существующий перевод.
- `ast/validator.py:2,42–46`: Optional не импортирован. На Python <=3.13 это import failure, Python 3.14 маскирует через lazy annotations. Текущие Ubuntu tests на 3.14 прошли; падение на другом Python здесь не запускалось. Явно определить поддерживаемые версии.
- Старые COMPLETE отчёты не доказывают текущий результат: в commit R8 `319b84c` у Osborne ещё было 0 страниц с blocks; регенерация добавлена позже в `127cf40`.
- R5 screenshots показывают legacy Schreiner p867, не Osborne fidelity. R7 не содержит reference ledger/URL, contrast measurements и полную screenshot matrix. R8 проверял 5 страниц одной книги, не корпус.
- Не утверждать, что старые тесты «подделаны»: повторный запуск подтвердил их прохождение. Их scope недостаточен.

## 5. Домен: проверка ответа на скриншоте

Скриншот — проверяемые утверждения другого агента, не разрешение создавать accounts/domains/services.

| Утверждение | Уточнение |
|---|---|
| Можно выбрать красивый trycloudflare hostname | Нет: Quick Tunnel получает случайный hostname, предназначен для тестирования. Объяснение «ровно 4 слова против phishing» не подтверждено |
| `logos-bible-institute.pages.dev` гарантирован | Имя зависит от доступности; Pages — другой хостинг uploaded assets, не имя для существующего Ubuntu Tunnel |
| Upload dist решает всё для большой библиотеки | Не автоматически: Pages Free 20 000 файлов, максимум 25 MiB на asset; нужны storage/asset routing и отдельные decisions |
| Бесплатный ngrok даст выбранное `logos-bible-institute.ngrok-free.app` | Нет: free development domain назначается автоматически; есть лимиты traffic/requests и browser warning |
| Телефон откроет Ubuntu по `127.0.0.1:8080` | Нет: это loopback телефона. Caddy проекта специально bind только Ubuntu loopback, не LAN |

Официальные источники, проверены 2026-09-06:

- [Cloudflare Quick Tunnels](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/)
- [Pages Direct Upload / project name](https://developers.cloudflare.com/pages/get-started/direct-upload/)
- [Pages file limits](https://developers.cloudflare.com/pages/platform/limits/)
- [ngrok free plan limits](https://ngrok.com/docs/pricing-limits/free-plan-limits)

### H01 / P1 — Воспроизведён upstream Host mismatch

На текущем Ubuntu:

```sh
curl -s -o /dev/null -w 'status=%{http_code} bytes=%{size_download}\n' http://127.0.0.1:8080/healthz
# status=200 bytes=120
curl -s -o /dev/null -w 'status=%{http_code} bytes=%{size_download}\n' -H 'Host: reader.example.org' http://127.0.0.1:8080/healthz
# status=200 bytes=0
```

`reader.example.org` здесь synthetic Host для диагностики, не выбранный домен пользователя. На `/` то же различие: обычный ответ содержит HTML, внешний Host — пустой 200.

`infra/caddy/Caddyfile.template:7–8` использует explicit `http://127.0.0.1:PORT` Host matcher. `infra/cloudflared/config.yml.template:6–7` не задаёт `originRequest.httpHostHeader`; Quick Tunnel из скриншота задаёт override флагом, что скрывает проблему named template. Это доказанный local Host routing defect; не заявление, что мы уже проверили несуществующий публичный named domain.

Будущий исполнитель должен зафиксировать RED Host test и согласованно настроить upstream Host, сохранив loopback bind. Проверять **body, MIME и release identity**, не только HTTP 200. Не открывать Caddy на 0.0.0.0 для обхода этой ошибки.

Источники: [Caddy address/Host semantics](https://caddyserver.com/docs/caddyfile/concepts), [Cloudflare httpHostHeader](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/origin-parameters/#httphostheader).

Предпочтительная ранее утверждённая архитектура остаётся: Ubuntu immutable origin + named Cloudflare Tunnel на hostname контролируемой владельцем зоны. Нужен owner choice домена/zone/credentials. Не покупать домен и не обещать бесплатное свободное брендированное имя. Если владелец не выбирает домен, продолжать локальную fidelity работу, а public-hostname stage оставить BLOCKED_BY_OWNER_CHOICE.

Pages shell + Ubuntu media — отдельное архитектурное решение с CORS/Range/cache/version consistency, не просто rename. Не переносить туда corpus без явного решения.

## 6. Где и как продолжать agy

### Рекомендуемый короткий путь

Основную сессию agy запускать на Ubuntu: там уже PDF corpus, venv и совместимый Node. Mac использовать для браузера через SSH forward, либо для независимой frontend build. Это исключает лишние многократные commit/push/pull ради каждого screenshot.

```sh
# На Mac, только просмотр Ubuntu origin; пароль вводить интерактивно
ssh -N -L 18080:127.0.0.1:8080 moses@100.92.124.15
```

Открывать `http://127.0.0.1:18080/`. Для candidate не использовать production 8080: поднять isolated candidate на другом loopback port и пробросить отдельный local port.

Для Mac-only запуска: подходящий Node, isolated Python venv, проверенные зависимости; owner-provided PDFs копировать по SCP в ignored storage, сверять sha256 с Ubuntu. Не коммитить книги/production data. Команда `agy` существует на Mac, но здесь его auth/quota не проверялись. Не запускать второй agy над тем же деревом параллельно.

Ubuntu source inventory содержит 8 PDF-файлов, в том числе два Osborne filename, Тенни, Лэдд, «На пути к экзегетическому богословию», Фи/Стюарт, `14300.teologiya_novogo_zaveta.pdf`, Пеннер. Это **не 8 verified уникальных книг**: deduplicate по hash, не по имени. Остальные source hashes/полные dry-runs в этом аудите не проверялись.

### Git и safety

1. Прочитать `AGENTS.md`, этот документ, оригинальный и recovery playbook, ADR-001/002/006, текущие R0–R8 reports. Этот audit уточняет порядок следующего ремонта, а не отменяет security/rights gates.
2. Зафиксировать actual branch/HEAD/status и current release target отдельно. Не вернуться на старый master: recovery находится в `agy/fidelity-recovery`.
3. Сначала fetch/status; pull только ff-only при чистом согласованном checkout. Не force/reset/rebase чужие изменения. Изменения вне scope сохранить; пересекающиеся неизвестные изменения обсудить.
4. Один writer на checkout. Экономичным subagents — отдельные files/worktrees и bounded contracts; главный агент ревьюит diff и интеграцию. Subagents не делают deploy/DNS/production writes.
5. Не коммитить caches, PDFs, regenerated corpus/release assets, screenshots с закрытым контентом или credentials. Existing committed artifacts не удалять массово: отдельно описать миграцию хранения.
6. Код текущим аудитором не исправлен. Новый agy должен реализовывать поручение, не ограничиваться очередным MD с планом.

## 7. Исполнимый порядок ремонта: A0–A6

**Рабочее правило:** expected RED — нормальная часть ремонта, не owner stop. Исправлять причину и проходить GREEN. Неизвестный failure сначала расследовать. Остановиться перед новой стоимостью, отправкой книг внешнему сервису, потерей данных/неясной migration или production/DNS изменением. Отсутствие прав на публичную публикацию не запрещает private local dry-run разрешённого owner source.

### A0 — Краткий baseline и correction report

Проверить HEAD/hash и воспроизвести F01/F02/F04/F06/H01. Не переписывать старые отчёты: добавить correction report, перечислить что подтверждено и что опровергнуто. Сохранить скрипт воспроизведения в репозитории без секретов/книг; evidence в ignored directory.

Acceptance: reproducible commands + actual output, перечень environments и review matrix. Не тратить этап на повторное ручное «исследование с нуля» уже доказанных фактов, если HEAD не изменился.

### A1 — Исправить contracts, validation и свежую генерацию media

Закрыть F01/F02/F03/F07/F10. До runtime изменений написать наблюдаемые tests:

- actual builder output → typed contract → serialization roundtrip сохраняет caption/source/runs;
- fresh unseen slug / empty staging → images материализованы, все references существуют и совпадают с checksums;
- missing asset, corrupt text, dropped digits, missing footnote → release rejected, production pointer unchanged;
- original и fake-translated paths сохраняют authoritative AST/media;
- nested raster inside figure не даёт duplicate, clip охватывает весь рисунок;
- unknown schema/data ошибки видимы, не молчаливый fallback на соседнюю страницу.

Сначала согласовать source/AST/media/version boundaries и test pyramid в коротком ADR. Reuse существующие queue/CAS/evidence/release ports; не делать новый стек. Checkpoints keyed by source/config/extractor hash; retries не дублируют artifacts; cleanup только собственного candidate, никогда source/current.

Acceptance: новая книга собирается воспроизводимо без готовых scanned assets и ручного редактирования manifest; deterministic validation gate работает в настоящем publication path. Promotion/rollback тестировать в временном sandbox, не `/srv/logos/current`.

### A2 — Текст, структура, сноски

Закрыть F04/F09. Tests на genuine hyphens, line breaks, range separators, literal `#`, two columns, lists, poetry/stanzas, table и footnotes. Геометрическая стратегия и uncertain cases должны быть явными; не назначать 0.98/0.99 без основания.

Acceptance: контрольные pages и новые representative fixtures сохраняют порядок/смысл; сноски доступны; настоящий список не один paragraph, стих не prose. Scan fallback допустим только явно помеченный и сверенный; OCR/внешний AI не запускать без отдельного gate.

### A3 — Reader integration и поведение

Закрыть F05/F08, media/source controls и modal a11y. Привести versioned repository→reader к согласованному контракту. Настройки fontSize/lineHeight измерять через computed styles; mode отражать в URL, UI и реальных language projections. Search не должен дублировать русский оригинал как EN.

Acceptance: search→stable block focus/highlight, card→тот же block, footnote open/back, source bbox, unavailable media error/retry; settings/scan dialogs доступны с клавиатуры, Escape и focus restore; legacy Schreiner работает.

### A4 — Responsive/visual acceptance

До компонентов/CSS прочитать `refero-design` и `mobbin-reference`, собрать реальные references, tokens/state decision ledger. Если сервис недоступен — указать limitation и следовать разрешённому skill fallback, не придумывать посещённые URL/скриншоты.

Закрыть F06; убрать duplicate captions/figure fragments, читаемый zoom, honest homepage microcopy. Проверить 375/768/1440 на всех 4 контрольных pages, отдельной poetry/table page, homepage и critical dialogs; также темы/contrast, keyboard/touch, error/loading/empty states. Не выдавать hidden overflow за исправленный layout.

Acceptance: `scrollWidth <= innerWidth` после завершённых transitions, все команды доступны; images `decode()` + naturalWidth > 0, исходный PDF сверяется визуально. Lazy images сначала прокрутить в viewport и дождаться decode, а не помечать ещё не загруженные как broken. Screenshots должны быть реальной изменённой книги, не только Schreiner.

### A5 — Корпус и release candidate

После A1–A4 выполнить весь разрешённый corpus private dry-run, deduplicate hashes, classification и per-book warnings/storage estimate. На Osborne повторить все 736 страниц; suspect/FAIL не скрывать. Сравнить regression metrics с этим audit.

Acceptance: Ubuntu pytest/frontend/build/lint по поддерживаемому окружению; каждый skip/warning объяснён. Candidate image/scan/chunk/search dependency closure и byte checksums проверены, отдельный fresh-build E2E, отчёт о restart/checkpoint/rollback в sandbox. Ни одна книга не выходит в public без rights gate.

### A6 — Домен, отдельно от fidelity

Можно параллельно с A1–A5 исследовать read-only Host/DNS/config. Реализовать Host-aware tests и candidate config; не менять public infrastructure до выбора владельцем domain/zone/credentials.

Acceptance после owner approval: named Tunnel survives restart, внешний HTTPS вне LAN, правильные HTML/JSON/MIME/body/release id, catalog/pages/figures/scans без 404, missing asset настоящий 404, PDF Range=206 на реально разрешённом PDF (не на index.html), consistent cache headers, rollback. Не печатать токены, не отключать TLS verification, не пробрасывать роутерные порты.

## 8. Формат checkpoints и окончательная приёмка

Отчёт `docs/reports/AGY-A<n>-<UTC>.md` по `AGY_IMPLEMENTATION_REPORT.md`, плюс таблица F01–F10/H01: reproduced / RED / fixed / verified / remaining. На каждый пункт — file:line, команды и exit codes, artifact paths, источник/страница, ограничения. Главный агент делает bounded checkpoint commit после review; Git push — только выбранной рабочей ветки, без автоматического merge в master.

Не требовать, чтобы все будущие tests уже были зелёными в A0: вводить контракты по этапам. Не ослаблять assertions ради GREEN. Предыдущие утверждения COMPLETE не принимать как доказательства.

Работа закончена лишь когда fresh conversion работает из пустого staging, fidelity gate отказывает на плохих данных, реальные reader controls работают, visual matrix приложена, все существенные проверки пройдены либо оставшийся owner gate явно отделён. Нельзя обещать «все детали всех книг проверены» по выборке или «production-ready» при открытых P1.
