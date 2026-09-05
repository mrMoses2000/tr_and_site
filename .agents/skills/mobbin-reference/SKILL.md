---
name: mobbin-reference
description: >-
  Expert UI/UX reference research, pattern extraction, and design deconstruction using Mobbin.
  Activate this skill when creating, redesigning, or refining websites, web apps, or mobile interfaces,
  researching industry-standard design patterns from world-class products (e.g. Stripe, Linear, Airbnb,
  Notion, Apple), deconstructing UX flows (onboarding, checkout, dashboard, settings, search/filter,
  empty states), and transforming real-world visual references into clean, accessible, modern frontend code.
---

# Mobbin UI/UX Reference & Design Deconstruction Skill

This skill guides the agent in researching real-world design patterns, extracting visual blueprints,
and building world-class interfaces grounded in shipped product references rather than generic AI templates.

---

## 1. Core Principles

1. **Evidence-Based UI (No AI Slop):** Never invent arbitrary layouts from scratch. Ground every page,
   component, and user flow in proven solutions from top-tier apps.
2. **Layered Deconstruction:** Every screen reference must be decomposed into 5 distinct layers:
   - **Information Hierarchy:** What the user sees first, second, and third.
   - **Layout & Spacing Grid:** Container bounds, column structures, padding rhythm (4px/8px scale).
   - **Color & Elevation:** Background shades, subtle border contrasts, semantic accents, surface depth.
   - **Typography Ladder:** Font scale, weights, letter-spacing, line-height ratios.
   - **State Completeness:** Default, hover, active, focus-visible, loading/skeleton, empty, and error states.
3. **Test-First UI Architecture:** Component contracts and viewport responsiveness must be validated
   using browser tools and automated tests (Playwright, Vitest).

---

## 2. Research Workflow

### Step 1: Identify Reference Category & Archetype
Determine the product archetype before searching:
- **B2B / DevTool (Linear, Raycast, GitHub):** Dense, keyboard-first, high contrast, subtle borders, monospace accents, collapsible sidebars.
- **Fintech / Trust (Stripe, Mercury, Revolut):** Clean whitespace, sharp numbers, high typography contrast, distinct transaction tables, audit logs.
- **SaaS / Productivity (Notion, Slack, Figma):** Modular panels, contextual menus, drag-and-drop handles, rich empty states.
- **Consumer / E-Commerce (Airbnb, Apple):** Large photography, fluid micro-interactions, bold editorial headlines, sticky action bars.

### Step 2: Retrieve References
When the **Mobbin MCP** server is active:
- Use `mobbin_search_screens` to find specific screen types (e.g., `query: "saas pricing comparison with billing toggle"`).
- Use `mobbin_search_flows` to trace end-to-end user journeys (e.g., `query: "team workspace invite flow"`).
- Use `mobbin_search_sections` to inspect isolated UI elements (e.g., `query: "data table with multi-column filter"`).

When using **Browser-Based Research (Chrome DevTools)**:
- Navigate to Mobbin or target product pages.
- Inspect real DOM structures, CSS class names, flex/grid layouts, and responsive breakpoints.
- Extract typography styles, color hex codes, border-radii, and shadow specifications.

### Step 3: Extract Design Tokens
Transform the selected reference into a concrete design system dictionary:
```json
{
  "theme": {
    "colors": {
      "background": "#090A0F",
      "surface": "#12141C",
      "surface-hover": "#1A1D27",
      "border": "rgba(255, 255, 255, 0.08)",
      "border-strong": "rgba(255, 255, 255, 0.16)",
      "text-primary": "#F4F5F7",
      "text-secondary": "#8F95A3",
      "accent": "#5E6AD2",
      "accent-hover": "#6F7BE0"
    },
    "typography": {
      "font-sans": "Inter, -apple-system, sans-serif",
      "font-mono": "JetBrains Mono, monospace",
      "scale": {
        "h1": "text-4xl font-semibold tracking-tight leading-tight",
        "body": "text-sm font-normal text-muted-foreground leading-relaxed"
      }
    },
    "radii": {
      "card": "rounded-xl",
      "button": "rounded-lg",
      "badge": "rounded-full"
    }
  }
}
```

### Step 4: Implement with Modern Component Architecture
- Use **Tailwind CSS** or CSS Modules with structured design tokens.
- Use headless accessible primitives (Radix UI, Headless UI, React Aria).
- Implement robust microcopy, subtle hover transitions (150ms-200ms ease-out), and zero layout shift.

### Step 5: Verification & Quality Audit
- Run Lighthouse or Chrome DevTools audits for accessibility (WCAG AA), contrast ratios, and performance.
- Test across mobile (375px), tablet (768px), and desktop (1440px) breakpoints.

---

## 3. Sub-References
Read the detailed guides in the `references/` folder when working on specific topics:
- [UX Flow Blueprints](./references/ux-flow-blueprints.md): Detailed patterns for Auth, Onboarding, Tables, Dashboards, and Settings.
- [UI Craft Rules](./references/ui-craft-rules.md): Micro-spacing, typography scales, contrast, elevation, and anti-slop rules.
- [MCP & Browser Guide](./references/mcp-and-browser-guide.md): API specs, token management, and browser automation runbook.
