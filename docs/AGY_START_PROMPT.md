# Стартовый prompt для agy

```text
Работай в /home/moses/tr_and_site. Сначала прочитай AGENTS.md,
docs/AUDIT-2026-09-05.md, docs/GEMINI_IMPLEMENTATION_PLAYBOOK.md и
docs/AGY_IMPLEMENTATION_REPORT.md. Реализуй программу из playbook по этапам,
начиная с первого незавершённого. На каждом этапе соблюдай
RED -> GREEN -> REFACTOR, не переписывай unrelated code, сохрани отдельный
отчёт docs/reports/AGY-<PHASE>-<UTC>.md и checkpoint commit.

Production target: immutable releases на Ubuntu, Caddy только на loopback,
публичный доступ через named Cloudflare Tunnel; Netlify не использовать.
Продолжай к следующему этапу только при зелёных тестах. Остановись и задай
один точный вопрос при missing credentials/domain, правах на книгу,
платном API/TTS, необратимой migration или production cutover. Не раскрывай
секреты и не считай исходный текст успешным переводом.

Полные PDF не лежат в Git: перед PDF-этапом найди owner-provided файлы в
/srv/logos/sources/incoming и storage, сверяй книги только по SHA-256 из
раздела 7.3 playbook. Ничего похожего по имени не скачивай и не подменяй;
если hash отсутствует, остановись со списком MISSING_SOURCE.
```
