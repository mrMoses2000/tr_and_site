# Стартовый prompt для нового agy / Gemini 3.8 Flash

Скопируйте весь блок ниже в новую сессию `agy`:

```text
Работай в /home/moses/tr_and_site. Ты восстанавливаешь точность PDF-конвейера и живой читалки, а не продолжаешь этапы вслепую.

Сначала полностью прочитай AGENTS.md, docs/GEMINI_FIDELITY_RECOVERY_PLAYBOOK.md, docs/GEMINI_IMPLEMENTATION_PLAYBOOK.md, docs/AUDIT-2026-09-05.md, docs/AGY_IMPLEMENTATION_REPORT.md, docs/reports/AGY-P3-2026-09-05T12:30:00Z.md, docs/reports/AGY-P4-2026-09-05T12:35:00Z.md, docs/reports/AGY-P8-2026-09-05T13:00:00Z.md и docs/ADR-001-reader-architecture.md, docs/ADR-002-telegram-agy-book-ingestion.md, docs/ADR-006-ubuntu-origin-cloudflare-tunnel.md. Выполни обязательные skills из AGENTS.md, если они доступны; если skill отсутствует, честно зафиксируй это и соблюдай его intent вручную.

Запиши фактические branch, HEAD, git status, remote, версии окружения и команды проекта. Только если исходное дерево чистое, создай ветку agy/fidelity-recovery; существующую ветку не удаляй и не reset-ь. Начни строго с R0 и не исправляй runtime в R0.

Контрольный источник: /home/moses/tr_and_site/storage/inbox/681537e1_Озборн_Герменевтическая спираль.pdf; ожидаемый SHA-256 d2736cb9b551bdeef6a5f7b8078c5c4b9a5ab13e6ae9f44eff63aaebc548ef46. Сравни PDF-страницы 45, 46, 50 и 430 с текущей локальной читалкой; https://emerging-sherman-western-secret.trycloudflare.com/ используй только как необязательное read-only evidence, если URL ещё жив.

Работай test-first, по одному recovery phase и checkpoint. Можешь делегировать экономичным subagents только bounded-задачи, но они не коммитят, не push-ят и не касаются production; лично проверь каждый diff и все evidence. Отчёты сохраняй как docs/reports/AGY-R<phase>-<UTC>.md. Не добавляй PDF, corpus, generated releases или secrets в Git. Не выполняй реальные paid AI/OCR/translation/TTS calls, не отправляй книги внешним API, не меняй /srv/logos/current, DNS, Cloudflare Tunnel/credentials и ничего не публикуй без owner/rights gate. Не заявляй 100%, production-ready или завершение этапа без PDF/browser evidence.

В первом ответе сообщи только: подтверждённое состояние репозитория/окружения, проверку source hash, точный scope R0, список делегированных bounded-задач и стоп-условия. Затем выполняй R0.
```
