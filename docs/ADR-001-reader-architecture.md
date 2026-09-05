# ADR-001: Theological Web Reader Architecture & Test Strategy

## Status
Accepted

## Context
We are building a specialized bilingual digital reader for Thomas R. Schreiner's academic work *New Testament Theology: Magnifying God in Christ* (Appendix: *Reflections on New Testament Theology*, pages 867–888). The original material comprises high-resolution scans of the physical book with marginalia, footnotes, and nuanced theological discourse.

The system must provide:
1. High-fidelity reading experience in Russian (academic translation) and English (original text).
2. Synchronized bilingual mode (side-by-side or parallel aligned paragraphs).
3. Scan inspection mode (viewing original book photos with high-resolution clarity and zoom).
4. Table of contents, fast multi-lingual search, progress tracking, and personalized reading preferences (theme, typography, font sizing).
5. Strict adherence to clean hexagonal architecture and test-first discipline.

---

## Architectural Decision: Hexagonal / Clean Architecture

To ensure testability and isolation from framework idiosyncrasies, the system is separated into three distinct concentric rings:

```
+-------------------------------------------------------------+
| Delivery Layer (React 19 + Tailwind v4 UI Components)       |
|  - ReaderHeader, ReaderContent, BilingualView, ScanModal,   |
|    SettingsDrawer, TableOfContents, FootnotesSheet          |
+-------------------------------------------------------------+
                              | uses
                              v
+-------------------------------------------------------------+
| Application / Ports Layer                                   |
|  - IStorageService (localStorage abstraction)               |
|  - IBookRepository (retrieval and search adapter)          |
|  - useReaderEngine (state orchestrator hook)                |
+-------------------------------------------------------------+
                              | depends on
                              v
+-------------------------------------------------------------+
| Core Domain Logic (Pure TypeScript, Zero Framework Deps)    |
|  - Reading progress & estimation calculator                 |
|  - Search & snippet highlighter                             |
|  - Pagination & bounds validator                            |
|  - Setting normalizer & theme token manager                 |
|  - Footnote linker & paragraph pairing                      |
+-------------------------------------------------------------+
```

### Domain Layer (`app/src/domain/`)
- `types.ts`: Domain models (`PageData`, `BookManifest`, `ReaderSettings`, `ParagraphPair`, `FootnoteItem`).
- `pagination.ts`: Pure functions for page stepping, clamp boundaries, and URL deep-linking.
- `progress.ts`: Percent completion and estimated reading time calculation based on word count.
- `searchEngine.ts`: Full-text bilingual search, accent/case normalization, scoring, and context snippet extraction.
- `footnotes.ts`: Parser and resolver for inline footnote markers `[^n]` to metadata.

### Infrastructure & Adapters (`app/src/infrastructure/`)
- `LocalSettingsStorage`: Port implementation saving user preferences and bookmarks in `localStorage`, with graceful fallback for memory/test environments.
- `BookDataRepository`: In-memory and cached repository providing indexed access, manifest loading, and fast page lookup.

### Delivery / UI Layer (`app/src/components/`)
- Adheres to `refero-design` specifications:
  - 4 tailored themes: `sepia` (natural warm paper), `light` (editorial studio), `dark` (deep graphite), `oled` (true pitch black).
  - Continuous typography ladder using `Literata` / `Merriweather` for serif and `Inter` for sans-serif.
  - Interactive state matrix: Default, Hover, Active, Focus-visible, Loading, Empty, and Modal.

---

## Test Pyramid Strategy

1. **Unit Tests (Vitest)**:
   - Target: 100% of pure domain algorithms (`pagination`, `progress`, `searchEngine`, `footnotes`).
   - Execution time: < 50ms, zero external dependencies.
2. **Integration Tests (Vitest + React Testing Library)**:
   - Target: Hook orchestration (`useReaderEngine`), component interactions (page navigation, settings change, theme switching, footnote popovers).
3. **E2E / Browser Verification (Playwright / Web testing)**:
   - Target: Critical reading paths, viewport responsiveness (mobile 375px, tablet 768px, desktop 1440px), visual clarity and scan modal interactions.

---

## Consequences & Trade-offs
- **Pros**: Pure domain functions can be tested instantly without browser mocks or rendering delays. UI components remain thin presentation wrappers.
- **Cons**: Requires explicit mapping between raw data batches and domain entity representations, which is handled cleanly during the build/initialization phase.
