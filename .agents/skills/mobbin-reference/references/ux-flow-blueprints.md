# UX Flow Blueprints & Component Deconstruction

This reference specifies proven patterns for the 6 core UX flows found in modern web applications.

---

## 1. Authentication & Onboarding
- **Pattern:** Split-screen layout or centered card (max-w-md) with subtle backdrop blur.
- **Social Login:** Brand buttons (Google, GitHub) on top with subtle borders, followed by a semantic "or continue with email" divider with line spans.
- **Form Inputs:** Floating labels or high-contrast top labels, clear error states with icons, real-time password strength indicator.
- **Onboarding Progress:** Multi-step wizard with persistent progress indicator, ability to skip optional steps, immediate value demonstration before asking for payment or complex configs.

## 2. Dashboards & Analytics
- **Grid Structure:** 12-column responsive CSS grid with standard 24px gutters.
- **Metric Cards (KPIs):** Top row with 3-4 cards: primary value (32px font-semibold), delta indicator (+12.4% vs last month) with colored badge (green/red), sparkline or mini trend chart.
- **Data Density:** High-density toggle for power users; collapsible sidebar with icon + label + keyboard shortcut badges.
- **Activity Stream / Feed:** Right-hand secondary panel or chronological timeline with relative timestamps ("2m ago").

## 3. Data Tables & Lists
- **Header Actions:** Search input (debounced 300ms) with `Cmd+K` hint, multi-select filter dropdowns (Status, Date range, Category), and primary export/action button.
- **Table Anatomy:** Sticky header with sort indicators, row hover highlights, selection checkboxes with indeterminate master checkbox.
- **Pagination & Infinite Scroll:** Server-side pagination with rows-per-page selector (10, 25, 50, 100) and current range label ("Showing 1-25 of 1,420").
- **Empty States:** Centered illustration or icon, explanatory heading ("No transactions found"), helpful subtext, and clear call-to-action ("Create your first transaction" or "Clear filters").

## 4. Settings & Account Management
- **Layout:** Vertical tab navigation on the left (Profile, Team, Billing, Security, API Keys) with content panel on the right.
- **Destructive Actions:** Danger zone section separated with a warning border and red badge; requires explicit text confirmation ("Type DELETE to confirm") in a modal.
- **Auto-save vs Explicit Save:** Use auto-save with a subtle status toast ("Saved 1s ago") for preferences, and explicit form buttons for critical security changes.

## 5. Paywalls & Pricing
- **Tier Comparison:** 3-column layout highlighting the recommended tier with a subtle border glow or "Most Popular" ribbon.
- **Billing Switcher:** Annual vs Monthly toggle with "Save 20%" discount badge.
- **Feature Checklist:** Clear check/cross icons, tooltip explanations for complex terms, transparent FAQs section below.
