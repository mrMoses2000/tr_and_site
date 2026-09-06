# Prompt для новой сессии agy

Запустить agy на Ubuntu в `/home/moses/tr_and_site`. Скопировать блок целиком:

```text
Продолжай реализацию Логоса на текущей recovery-ветке. Прочитай полностью AGENTS.md и docs/AUDIT_AND_AGY_ACTION_PLAN_2026-09-06.md, затем перечисленные там playbooks/ADR/reports. Отчёты R0–R8 COMPLETE не являются доказательством: независимый аудит на 8c5ca76 выявил незакрытые F01–F10/H01.

Сначала проверь actual HEAD/status, Ubuntu current release и SHA-256 контрольного PDF. Не переключайся на старый master и не трогай неизвестные изменения. Работай по A0–A6: кратко воспроизведи baseline, затем реально исправляй код по RED→GREEN, а не создавай ещё один план. Expected RED не является поводом спрашивать разрешение. Экономичным subagents дай bounded задачи в непересекающихся файлах/worktrees; сам проверь каждый diff, интеграцию и evidence.

Главные цели: fresh PDF conversion из пустого staging с настоящими figure assets; fail-closed validation; lossless AST contracts; исправить обрезку/дубли схем, переносы, стихи/списки и сноски; работающие настройки, язык, поиск/cards/source anchors; отсутствие overflow на 375/768/1440. Не патчи вручную только готовый Osborne manifest. Проверяй реальный browser и source PDF, не только unit tests. Сохраняй отчёты AGY-A<n>-<UTC>.md и bounded checkpoint commits после review.

Полные проверки делай на Ubuntu; Mac может смотреть candidate через SSH forward. Не запускай платные/внешние AI/OCR/translation/TTS, не публикуй книги, не меняй /srv/logos/current, DNS/Tunnel/account и не добавляй corpus/secrets в Git без соответствующего owner gate. Домен — отдельный A6: уже доказан empty-200 при external Host. Не обещай выбранный бесплатный ngrok/trycloudflare hostname и не переносись на Pages вместо Ubuntu без решения владельца.

Первое сообщение: подтверждённый HEAD/hash/release, A0 scope, распределение задач, реальные стоп-условия. Затем выполняй A0 и переходи к исправлениям по критериям документа. Недоступные skills сообщи честно, не выдумывай их использование и результаты проверок.
```
