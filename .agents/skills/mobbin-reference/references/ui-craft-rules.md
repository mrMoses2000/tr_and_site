# UI Craft Rules & Anti-Slop Guidelines

Follow these guidelines to elevate design beyond standard boilerplate:

---

## 1. Spacing Rhythm (Strict 4px/8px System)
- **Compact:** 4px (gap-1), 8px (gap-2) - button icons, tag paddings, badge chips.
- **Component Internal:** 12px (p-3), 16px (p-4), 20px (p-5) - cards, modal bodies, table cells.
- **Section Spacing:** 32px (mb-8), 48px (mb-12), 64px (mb-16) - grid sections, landing page blocks.
- **Container Max-Widths:**
  - Content/Article: `max-w-2xl` (672px)
  - Forms/Modals: `max-w-md` (448px) or `max-w-lg` (512px)
  - Application Canvas: `max-w-7xl` (1280px) or full width with padding `px-6 lg:px-8`

## 2. Typography & Contrast
- Never use pure black `#000000` text on pure white `#FFFFFF` or vice versa.
  - Light mode: Body `#111827`, Subdued `#4B5563`, Border `#E5E7EB`
  - Dark mode: Background `#0B0D13`, Card `#151821`, Text `#F3F4F6`, Subdued `#9CA3AF`, Border `rgba(255,255,255,0.08)`
- Headlines must have negative letter spacing (`tracking-tight` or `-0.02em`) when above 24px.
- Tabular data, dates, and numbers must use tabular figures (`font-mono` or `tabular-nums`).

## 3. Borders & Shadows (Elevation)
- Modern interfaces rely on subtle border strokes (`border border-white/10` or `border border-black/5`) rather than heavy drop shadows.
- Glows and active states: Use subtle ring offsets (`ring-2 ring-primary/20 ring-offset-2`).
- Rounded corners hierarchy: Outer container `rounded-2xl` -> inner card `rounded-xl` -> inner button `rounded-lg` (nested radius rule: `R_inner = R_outer - padding`).

## 4. Micro-Interactions & Fluidity
- Transitions should be 150ms-200ms with `cubic-bezier(0.16, 1, 0.3, 1)`.
- Interactive elements must provide immediate visual feedback (active scale `active:scale-[0.98]`, hover contrast shifts).
- Ensure all interactive controls have accessible focus rings (`focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring`).
