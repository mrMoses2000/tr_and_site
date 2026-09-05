# AGY Implementation Report

Этот файл — обязательный шаблон отчёта после **одного** этапа из [`GEMINI_IMPLEMENTATION_PLAYBOOK.md`](./GEMINI_IMPLEMENTATION_PLAYBOOK.md).

Исполнитель должен заменить placeholders фактическими данными. Нельзя удалять разделы; неприменимый раздел помечается `N/A` с объяснением. Нельзя включать секреты, пароли, токены, cookies, содержимое `.env` или signed URLs.

После заполнения отчёта исполнитель сохраняет копию как `docs/reports/AGY-<PHASE>-<UTC>.md` и делает checkpoint commit. В continuous mode следующий этап разрешён только после зелёных gates; на owner/rights/paid/production gate исполнитель останавливается.

---

## 1. Идентификация

| Поле | Значение |
|---|---|
| Дата/время UTC | `<YYYY-MM-DDTHH:MM:SSZ>` |
| Исполнитель/model | `<agy + exact model>` |
| Этап playbook | `<P0…P14>` |
| Цель этапа | `<одним предложением>` |
| Репозиторий | `/home/moses/tr_and_site` или `/Users/mosesvasilenko/tr_and_site` |
| Начальный commit | `<sha>` |
| Ветка | `<branch>` |
| Итоговый commit | `<sha или NOT_COMMITTED>` |
| Среда | `<local/server>` |
| Production изменён | `NO` по умолчанию / `<YES + approval reference>` |
| Платный API вызван | `NO` по умолчанию / `<YES + approval + ceiling + actual>` |

## 2. Прочитанные источники

- [ ] `AGENTS.md`
- [ ] `docs/GEMINI_IMPLEMENTATION_PLAYBOOK.md`
- [ ] `docs/AUDIT-2026-09-05.md`
- [ ] Файлы выбранного этапа
- [ ] Актуальная официальная документация, если этап зависит от внешнего SDK/provider

Перечень фактически прочитанных файлов/URL:

```text
<absolute repo paths and official URLs>
```

## 3. Scope

### Запрошено этапом

```text
<точный список обязательных результатов>
```

### Выполнено

```text
<что реально сделано>
```

### Осознанно не выполнялось

```text
<что исключено из этапа и почему>
```

### Отклонения от playbook

```text
<NONE либо каждое отклонение + причина + влияние>
```

## 4. Состояние до изменений

```text
git status --short
<output without secrets>
```

Существовавшие пользовательские изменения, которые были сохранены:

```text
<files or NONE>
```

## 5. Test-first evidence

Для каждого нового поведения нужна запись RED → GREEN → REFACTOR.

| ID | Поведение | Test file | RED command | Ожидаемое падение подтверждено | GREEN command | Итог |
|---|---|---|---|---|---|---|
| T-01 | `<behavior>` | `<path>` | `<command>` | `<failure summary>` | `<command>` | `<pass/fail>` |

### RED — фактический вывод

```text
<минимальный релевантный output и exit code>
```

Почему падение доказывало отсутствие требуемого поведения:

```text
<explanation>
```

### GREEN — фактический вывод

```text
<summary, counts, duration, exit code>
```

### REFACTOR

```text
<что упрощено при зелёных тестах либо N/A>
```

## 6. Изменённые файлы

| Файл | Тип | Причина | Совместимость/миграция |
|---|---|---|---|
| `<path>` | added/modified/deleted | `<why>` | `<impact>` |

Удаление файла требует отдельного объяснения и способа восстановления.

## 7. Архитектурные решения

| Решение | Альтернативы | Почему выбрано | Положительное следствие | Отрицательное следствие |
|---|---|---|---|---|
| `<decision>` | `<alternatives>` | `<rationale>` | `<benefit>` | `<cost>` |

Новые/изменённые contracts:

```text
<entities, ports, schemas, state transitions>
```

## 8. Миграции и данные

| Миграция | Forward | Backward/rollback | Идемпотентность | Проверка сохранности |
|---|---|---|---|---|
| `<id or N/A>` | `<how>` | `<how>` | `<proof>` | `<proof>` |

До/после counts/checksums:

```text
<actual evidence or N/A>
```

## 9. Команды верификации

Привести все команды, запущенные после последнего изменения.

| Команда | Среда | Exit code | Tests/pass/fail | Duration | Примечание |
|---|---|---:|---|---:|---|
| `<command>` | local/server | `<n>` | `<summary>` | `<seconds>` | `<notes>` |

Обязательные категории для code stages:

- [ ] focused unit tests
- [ ] full backend tests
- [ ] frontend tests, если затронут frontend/manifest
- [ ] lint/typecheck
- [ ] build
- [ ] migration/rollback test, если есть schema change
- [ ] security/secret scan для P0 и security-sensitive stages

Непройденные проверки:

```text
<NONE либо command + error + impact>
```

## 10. PDF/content evidence

Применимо к P3–P6 и P14.

| Source SHA-256 | PDF page | Printed label/side | Fixture | Expected | Actual | Review status |
|---|---:|---|---|---|---|---|
| `<sha>` | `<index>` | `<label>` | `<path>` | `<expected>` | `<actual>` | pass/review/fail |

Проверка invariants:

- [ ] page coverage
- [ ] block ID uniqueness
- [ ] source anchors
- [ ] digit/citation preservation
- [ ] footnote marker resolution
- [ ] reading order
- [ ] table/figure fallback
- [ ] reversible normalization
- [ ] no false translation fallback

Open findings:

```text
<finding IDs, severity, evidence>
```

## 11. UI/UX evidence

Применимо к P7–P10 и frontend changes.

### Reference decision ledger

| Решение | Reference/user constraint | Реализация | Доказательство |
|---|---|---|---|
| `<decision>` | Readwise/Apple Books/Zotero/playbook | `<file/component>` | `<screenshot/test>` |

### Viewport matrix

| Viewport | Route/state | Before screenshot | After screenshot | Overflow | Console | Keyboard |
|---|---|---|---|---|---|---|
| 375×812 | `<route>` | `<path>` | `<path>` | pass/fail | clean/issues | pass/fail |
| 768×1024 | `<route>` | `<path>` | `<path>` | pass/fail | clean/issues | pass/fail |
| 1440×1000 | `<route>` | `<path>` | `<path>` | pass/fail | clean/issues | pass/fail |

Проверенные состояния:

- [ ] default
- [ ] hover
- [ ] active/selected
- [ ] focus-visible
- [ ] loading/skeleton
- [ ] empty
- [ ] error/recovery
- [ ] reduced motion
- [ ] modal focus trap/Escape/restore

Известный visual drift:

```text
<NONE либо конкретный drift + screenshot + proposed fix>
```

## 12. Security review

| Проверка | Результат | Доказательство |
|---|---|---|
| Secrets не попали в diff/report/log | pass/fail | `<command/inspection>` |
| Недоверенный input не попадает в shell/path | pass/fail/N/A | `<test>` |
| Allowlist deny-by-default | pass/fail/N/A | `<test>` |
| Least privilege | pass/fail/N/A | `<explanation>` |
| Logs redacted | pass/fail/N/A | `<test/inspection>` |
| Paid budget gate | pass/fail/N/A | `<test>` |
| Rights/access gate | pass/fail/N/A | `<decision>` |
| Service identity не получила лишних credentials | pass/fail/N/A | `<identity/scope evidence>` |

Если найден секрет, не вставлять его в отчёт. Указать только файл/тип и требуемую ротацию.

## 13. External services, hosting и стоимость

Rights/access decision:

```text
Edition/source hash: <id/hash/N/A>
Decision owner/reference: <reference/N/A>
AI processing: DENY/ALLOW/N/A
Web text/source/scans: <separate decisions>
TTS/Telegram delivery: <separate decisions>
Access mode: public/authenticated/private/N/A
Expiry: <date/NONE/N/A>
```

```text
Provider state changed: NO/YES
Resources created: NONE/<list>
Credentials created: NONE/<redacted identifiers>
Estimated cost: <amount/formula>
Actual cost: <amount/N/A>
Official docs checked at: <date>
```

Если состояние provider изменено, приложить approval reference и rollback/delete procedure.

## 14. Deployment

```text
Deployment executed: NO/YES
Approval reference: <required if YES>
Preview URL: <safe URL/N/A>
Production URL: <safe URL/N/A>
Release ID: <id/N/A>
Previous release ID: <id/N/A>
```

Smoke tests после deploy:

```text
<commands/results/N/A>
```

## 15. Rollback

Точный rollback текущего этапа:

```text
<non-destructive steps; do not use git reset --hard>
```

Данные/артефакты, которые нельзя безопасно удалить:

```text
<list or NONE>
```

Rollback был протестирован:

```text
YES + evidence / NO + reason
```

## 16. Остаточные риски

| Severity | Риск | Evidence | Impact | Следующее действие |
|---|---|---|---|---|
| Critical/High/Medium/Low | `<risk>` | `<proof>` | `<impact>` | `<action>` |

## 17. Самопроверка scope

- [ ] Отчёт охватывает только один этап.
- [ ] Следующий этап не начат до отчёта и checkpoint commit.
- [ ] Unrelated code не переписан.
- [ ] Существующие изменения пользователя сохранены.
- [ ] Не было production deploy без разрешения.
- [ ] Не было paid call без разрешения и ceiling.
- [ ] Не публиковались новые книги.
- [ ] Отчёт не содержит секретов.
- [ ] Факты отделены от предположений.
- [ ] Непройденные проверки явно перечислены.

## 18. Итог и запрос оркестратору

### Итог одним абзацем

```text
<outcome, not activity list>
```

### Рекомендуемый следующий шаг

```text
<one next action; не выполнять его>
```

### Требуется решение владельца

```text
<NONE либо точный вопрос: migration, rights, budget, provider, production cutover>
```

### Статус этапа

Выбрать ровно один:

- `READY_FOR_ORCHESTRATOR_REVIEW`
- `BLOCKED_BY_FAILED_VERIFICATION`
- `BLOCKED_BY_REQUIRED_USER_DECISION`
- `INCOMPLETE`
