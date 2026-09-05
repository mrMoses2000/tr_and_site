# Engineering Standards: Reference-Driven UI/UX & Test-First Architecture

This workspace operates under strict production engineering standards. Every feature, service, and interface created must adhere to these two non-negotiable principles:

---

## 1. UI/UX: Reference-Driven Design (Zero Generic AI UI)

- **Mandatory Reference Research:** Never generate UI based solely on generic templates or assumptions. Before generating components or layouts:
  1. Leverage **Mobbin** (`mobbin-reference` skill and `mobbin` MCP) and **Refero** (`refero-design` skill and `refero` MCP) to analyze real-world implementations from industry leaders (Stripe, Linear, Airbnb, Notion, Apple, Raycast).
  2. Extract concrete **Design Tokens** (color palette, elevation/borders, typography ladder, spacing scale).
  3. Deconstruct the full component state matrix: Default, Hover, Active, Focus-visible, Loading/Skeleton, Empty State, and Error.
- **Microcopy & Polish:** Ensure precise, contextual microcopy; smooth 150-200ms transitions (`cubic-bezier(0.16, 1, 0.3, 1)`); accessible focus rings; and WCAG 2.1 AA color contrast.
- **Visual Audits:** Validate all interfaces across mobile (375px), tablet (768px), and desktop (1440px) viewports using browser inspection or screenshots.

---

## 2. System Architecture: Test-First Architecture (Testability by Design)

- **Architecture Concurrently Planned with Tests:** When architecting any system, service, or API:
  1. Define the **Test Pyramid Strategy** in the technical design or Architecture Decision Record (ADR) before writing application code.
  2. Employ **Clean / Hexagonal Architecture (Ports & Adapters)**: Separate pure business/domain logic from delivery mechanisms (HTTP/GraphQL) and infrastructure (Database/External APIs). This guarantees business rules can be tested in sub-second unit test runs without spinning up DBs or network listeners.
  3. Define explicit interfaces/contracts for all external adapters (repositories, payment gateways, emailers) to ensure 100% reliable mocking and test doubles.
- **Layered Testing Discipline:**
  - **Unit Tests (Vitest/Jest/Pytest):** Test domain logic, utility algorithms, and state machines with comprehensive edge-case coverage.
  - **Integration / API Tests (Supertest/TestClient):** Test database queries against test instances, transaction rollbacks, auth middleware, and validation schemas.
  - **End-to-End Tests (Playwright):** Automate the critical user paths (auth, checkout, core workflow) with resilient role-based locators (`getByRole`, `getByLabel`), network mocking where appropriate, and visual regression checks.
- **Zero Flakiness Rule:** Tests must be deterministic, isolated, and order-independent. Never use arbitrary `sleep` in tests; always wait on explicit DOM states or network events.

---

## 3. Active Customization Toolset

- **MCP Tools:**
  - `chrome-devtools`: Headless/live browser automation, DOM inspection, screenshot capture, console/network debugging.
  - `gemini-notebook-mcp`: Knowledge base and research documentation.
  - `mobbin`: Reference library of 600k+ real product screens and user flows (`https://api.mobbin.com/mcp`).
  - `refero`: Curated UI styles, product screens, and user journeys (`https://api.refero.design/mcp`).
- **Skills Available:**
  - `refero-design`: Canonical Refero research methodology and craft guides (typography, motion, icons, copywriting).
  - `mobbin-reference`: Deconstructing real-world app flows and translating screens to Tailwind/React code.
  - `architecture-designer`: System design, ADRs, trade-off analysis, and test-first architecture planning.
  - `test-master`: Test strategy, mocking patterns, coverage analysis, and quality gates.
  - `fullstack-guardian`: 3-perspective implementation (Frontend + Backend + Security).
  - `playwright-expert` & `webapp-testing`: End-to-end browser testing and server verification.
  - `nextjs-developer` & `react-expert`: Next.js App Router, RSC, Tailwind, React 19, accessibility.
  - `typescript-pro`: Strict typing, discriminated unions, Zod validation.
  - `api-designer`: REST, OpenAPI, GraphQL, contract testing.
  - `database-optimizer` & `postgres-pro`: Schema design, indexing, query optimization, migrations.
  - `secure-code-guardian`: OWASP Top 10, auth/authz, input sanitization.
